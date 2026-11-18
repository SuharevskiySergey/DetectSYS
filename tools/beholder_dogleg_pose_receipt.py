"""Draft pose-evidence contract with targeted synthetic standalone coverage.

No Unreal access, actor ownership, actuator writes or real emergency stop.
Incoming evidence is caller-supplied DATA, not an authenticated engine capture.
All proposal/receipt packets remain motionAuthorized=false/runtimeReady=false.
"""
from dataclasses import asdict, dataclass
import math
import uuid

from beholder_contact_dogleg import dogleg_pose
from beholder_dogleg_job import finite
from beholder_dogleg_pipeline import DoglegCalculationPipeline, NumericPoseSample
from generate_beholder_telescope import STROKE


def vector(values, count, name):
    values = tuple(values)
    if len(values) != count or not all(finite(v) for v in values):
        raise ValueError('Invalid finite '+name)
    return values


@dataclass(frozen=True)
class FrameEvidence:
    location: tuple[float, float, float]
    quaternion: tuple[float, float, float, float]
    scale: tuple[float, float, float]

    def __post_init__(self):
        object.__setattr__(self, 'location', vector(self.location, 3, 'frame location'))
        object.__setattr__(self, 'quaternion', vector(self.quaternion, 4, 'frame quaternion'))
        object.__setattr__(self, 'scale', vector(self.scale, 3, 'frame scale'))
        if min(self.scale) <= 0 or abs(math.hypot(*self.quaternion)-1) > 1e-6:
            raise ValueError('Positive scale and a unit quaternion required; no silent normalization')


@dataclass(frozen=True)
class CaptureStamp:
    application_revision: int
    probe_revision: int
    capture_sequence: int

    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in asdict(self).values()):
            raise ValueError('Nonnegative integer capture counters required')


@dataclass(frozen=True)
class PoseEvidence:
    world_id: str
    actor_id: str
    owner_epoch: str
    geometry_revision: str
    stamp_before: CaptureStamp
    stamp_after: CaptureStamp
    root: FrameEvidence
    tip: FrameEvidence
    stages: tuple[float, ...]
    sleeve_offsets: tuple[tuple[float, float, float], ...]
    joint_rotations_degrees: tuple[tuple[float, float, float], ...]
    contact_point: tuple[float, float, float]
    contact_valid: bool
    claw_positions: tuple[float, float, float]
    eyelid_opening: float

    def __post_init__(self):
        if any(not isinstance(v, str) or not v for v in self.identity):
            raise ValueError('World, actor, owner epoch and geometry identity required')
        if not isinstance(self.stamp_before, CaptureStamp) or self.stamp_before != self.stamp_after:
            raise ValueError('Coherent before/after native capture stamps required')
        if not isinstance(self.root, FrameEvidence) or not isinstance(self.tip, FrameEvidence):
            raise ValueError('Root and tip frame evidence required')
        object.__setattr__(self, 'stages', vector(self.stages, 10, 'stage positions'))
        object.__setattr__(self, 'contact_point', vector(self.contact_point, 3, 'contact point'))
        object.__setattr__(self, 'claw_positions', vector(self.claw_positions, 3, 'claw positions'))
        object.__setattr__(self, 'sleeve_offsets', tuple(vector(v, 3, 'sleeve offset') for v in self.sleeve_offsets))
        object.__setattr__(self, 'joint_rotations_degrees', tuple(
            vector(v, 3, 'actual joint pitch/yaw/roll') for v in self.joint_rotations_degrees))
        if len(self.sleeve_offsets) != 10 or len(self.joint_rotations_degrees) != 10:
            raise ValueError('Ten actual sleeve offsets and joint rotations required')
        if not all(0 <= v <= 1 for v in self.stages+self.claw_positions):
            raise ValueError('Stage/claw values outside unit range')
        if type(self.contact_valid) is not bool or not finite(self.eyelid_opening) or not 0 <= self.eyelid_opening <= 1:
            raise ValueError('Invalid contact flag or eyelid value')

    @property
    def identity(self):
        return self.world_id, self.actor_id, self.owner_epoch, self.geometry_revision


@dataclass(frozen=True)
class EvidenceTolerances:
    # Proposed numeric comparison settings only; not new runtime/physics policy.
    stage: float = 1e-6
    joint_degrees: float = 1e-6
    sleeve_local_cm: float = 1e-4
    root_world_cm: float = 0.001
    tip_and_contact_world_cm: float = 0.01
    quaternion_chord: float = 1e-8
    scale: float = 1e-6

    def __post_init__(self):
        if any(not finite(v) or v <= 0 for v in asdict(self).values()):
            raise ValueError('Finite positive evidence comparison tolerances required')


@dataclass(frozen=True)
class ApplicationProposal:
    transaction_id: str
    before: PoseEvidence
    sample: NumericPoseSample

    def to_dict(self):
        return dict(transactionId=self.transaction_id, status='draft_application_proposal',
                    actorIdentity=list(self.before.identity), basedOnStamp=asdict(self.before.stamp_after),
                    expectedApplicationRevision=self.before.stamp_after.application_revision+1,
                    numericTargets=self.sample.to_dict(), actualPoseConfirmed=False,
                    runtimeReady=False, motionAuthorized=False)


class PoseReceiptLedger:
    """Local proposal/receipt ordering, not an actuator or native ownership lock."""
    def __init__(self, pipeline, baseline, tolerances=None):
        if not isinstance(pipeline, DoglegCalculationPipeline) or not isinstance(baseline, PoseEvidence):
            raise ValueError('Numeric pipeline and baseline evidence required')
        self._pipeline, self._job = pipeline, pipeline.job
        self._baseline = self._last_evidence = baseline
        self._tolerances = EvidenceTolerances() if tolerances is None else tolerances
        if not isinstance(self._tolerances, EvidenceTolerances):
            raise ValueError('Typed evidence tolerances required')
        self._session, self._sequence = uuid.uuid4().hex, 0
        self._pending = None
        self._last_sample = None
        self._used_samples = set()
        self.held_reason = None
        initial = dogleg_pose(self._job.extension, 0, self._job.axis)
        self._environment(baseline)
        self._pose(baseline, initial['stages'], initial['angles'])

    @property
    def pending_proposal(self):
        return self._pending

    def hold(self, reason):
        # Deliberately LOCAL ONLY. A future native executor must perform its own
        # Cancel/hold; this code has no actor reference and cannot stop motion.
        if not isinstance(reason, str) or not reason:
            raise ValueError('Local hold reason required')
        if self.held_reason is None:
            self.held_reason = reason
        self._pending = None
        self._pipeline.hold(self.held_reason)

    def _frame(self, actual, expected, position_tolerance):
        t = self._tolerances
        # Quaternion sign is arbitrary: q and -q represent the same rotation.
        chord = min(math.dist(actual.quaternion, expected.quaternion),
                    math.dist(actual.quaternion, tuple(-v for v in expected.quaternion)))
        if (math.dist(actual.location, expected.location) > position_tolerance
                or chord > t.quaternion_chord
                or max(abs(a-b) for a,b in zip(actual.scale, expected.scale)) > t.scale):
            raise ValueError('Root/tip frame changed')

    def _environment(self, evidence):
        if not isinstance(evidence, PoseEvidence) or evidence.identity != self._baseline.identity:
            raise ValueError('Actor/world/owner/geometry identity changed')
        if not evidence.contact_valid:
            raise ValueError('Contact evidence is invalid')
        self._frame(evidence.root, self._baseline.root, self._tolerances.root_world_cm)
        self._frame(evidence.tip, self._baseline.tip, self._tolerances.tip_and_contact_world_cm)
        if math.dist(evidence.contact_point, self._baseline.contact_point) > self._tolerances.tip_and_contact_world_cm:
            raise ValueError('Contact anchor changed')
        if (max(abs(v) for v in evidence.claw_positions) > self._tolerances.stage
                or abs(evidence.eyelid_opening) > self._tolerances.stage):
            raise ValueError('Draft pose contract requires closed unchanged claws/eyelid')

    def _pose(self, evidence, stages, angles):
        t = self._tolerances
        if max(abs(a-b) for a,b in zip(evidence.stages, stages)) > t.stage:
            raise ValueError('Actual stages differ from the expected pose')
        for position, stage in zip(evidence.sleeve_offsets, stages):
            if math.dist(position, (STROKE*stage, 0, 0)) > t.sleeve_local_cm:
                raise ValueError('Sleeve transforms do not match the expected stages')
        for actual, expected in zip(evidence.joint_rotations_degrees, angles):
            if max(abs(a-b) for a,b in zip(actual, (expected[0], expected[1], 0))) > t.joint_degrees:
                raise ValueError('Actual pitch/yaw/roll differs from the expected pose')

    def _sample_order(self, sample):
        # Calculation order alone does not establish receipt order: a caller
        # can calculate several samples between ledger proposals.
        previous = self._last_sample
        if previous is None:
            if sample.segment_index != 0 or sample.segment_elapsed_seconds != 0:
                raise ValueError('First application proposal must describe the initial pose')
        elif sample.segment_index == previous.segment_index:
            if sample.segment_elapsed_seconds < previous.segment_elapsed_seconds:
                raise ValueError('Application proposal time regressed')
        elif sample.segment_index == previous.segment_index+1:
            segment = self._job.segments[previous.segment_index]
            if (previous.segment_elapsed_seconds != segment.duration_seconds
                    or sample.segment_elapsed_seconds != 0):
                raise ValueError('Segment boundary requires pose receipts on both sides')
        else:
            raise ValueError('Skipping or reversing pose receipt segments is forbidden')

    def propose(self, before):
        try:
            if self.held_reason is not None or self._pending is not None:
                raise ValueError('Ledger is held or an application receipt is pending')
            sample = self._pipeline.numeric_sample
            if (self._pipeline.job is not self._job or self._pipeline.state != 'idle'
                    or not isinstance(sample, NumericPoseSample) or sample.sample_id in self._used_samples):
                raise ValueError('A fresh completed numeric sample from the bound pipeline is required')
            self._sample_order(sample)
            self._environment(before)
            old, new = self._last_evidence.stamp_after, before.stamp_after
            if (new.capture_sequence <= old.capture_sequence or new.probe_revision < old.probe_revision
                    or new.application_revision != old.application_revision):
                raise ValueError('Pre-application capture is stale or another application occurred')
            if self._last_sample is None:
                reference = dogleg_pose(self._job.extension, 0, self._job.axis)
                stages, angles = reference['stages'], reference['angles']
            else:
                stages, angles = self._last_sample.stages, self._last_sample.angles
            self._pose(before, stages, angles)
            self._sequence += 1
            self._pending = ApplicationProposal(f'{self._session}:{self._sequence}', before, sample)
            return self._pending
        except (ValueError, TypeError, AttributeError) as exc:
            self.hold(str(exc))
            raise

    def confirm(self, transaction_id, after):
        try:
            proposal = self._pending
            if self.held_reason is not None or proposal is None or proposal.transaction_id != transaction_id:
                raise ValueError('Missing, repeated or stale application transaction')
            if (self._pipeline.job is not self._job or self._pipeline.state != 'idle'
                    or self._pipeline.numeric_sample is not proposal.sample):
                raise ValueError('Numeric pipeline advanced before pose evidence was confirmed')
            self._environment(after)
            old, new = proposal.before.stamp_after, after.stamp_after
            if (new.application_revision != old.application_revision+1 or new.probe_revision <= old.probe_revision
                    or new.capture_sequence <= old.capture_sequence):
                raise ValueError('Post-application evidence is incomplete, stale or not exclusive')
            self._pose(after, proposal.sample.stages, proposal.sample.angles)
            self._last_sample, self._last_evidence = proposal.sample, after
            self._used_samples.add(proposal.sample.sample_id)
            self._pending = None
            return dict(transactionId=transaction_id, sampleId=proposal.sample.sample_id,
                        suppliedPoseEvidenceCompared=True, actualPoseConfirmed=False,
                        runtimeReady=False, motionAuthorized=False)
        except (ValueError, TypeError, AttributeError) as exc:
            self.hold(str(exc))
            raise
