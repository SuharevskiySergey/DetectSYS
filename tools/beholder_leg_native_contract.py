"""Native-boundary DTO draft with targeted synthetic tests; no native transport.

All identities/claims/captures remain supplied data, NOT engine-authenticated.
No native owner is minted, no setter/application/recovery method is implemented.
"""
from dataclasses import asdict, dataclass

from beholder_dogleg_job import finite
from beholder_dogleg_pipeline import NumericPoseSample
from beholder_dogleg_pose_receipt import ApplicationProposal, CaptureStamp, PoseEvidence


SCHEMA_VERSION = 1


def _text(value, label):
    if type(value) is not str or not value:
        raise ValueError('Nonempty supplied '+label+' required')


def _counter(value, label):
    if type(value) is not int or value < 0:
        raise ValueError('Nonnegative integer '+label+' required')


@dataclass(frozen=True)
class NativeLegIdentity:
    world_id: str
    actor_id: str
    lifetime_id: str
    leg_index: int
    geometry_revision: str

    def __post_init__(self):
        for name in ('world_id', 'actor_id', 'lifetime_id', 'geometry_revision'):
            _text(getattr(self, name), name)
        if type(self.leg_index) is not int or not 0 <= self.leg_index < 8:
            raise ValueError('Leg index in 0..7 required')


@dataclass(frozen=True)
class NativeOwnerEvidence:
    subject: NativeLegIdentity
    owner_id: str
    owner_epoch: str
    claim_revision: int

    def __post_init__(self):
        if type(self.subject) is not NativeLegIdentity:
            raise ValueError('Typed leg instance identity required')
        _text(self.owner_id, 'owner ID')
        _text(self.owner_epoch, 'native owner epoch')
        _counter(self.claim_revision, 'claim revision')


@dataclass(frozen=True)
class NativeCaptureRevision:
    command_revision: int
    application_revision: int
    probe_revision: int
    capture_sequence: int

    def __post_init__(self):
        for name, value in asdict(self).items():
            _counter(value, name)

    def pose_stamp(self):
        return CaptureStamp(self.application_revision, self.probe_revision, self.capture_sequence)


@dataclass(frozen=True)
class NativeLegCapture:
    subject: NativeLegIdentity
    owner: NativeOwnerEvidence
    before: NativeCaptureRevision
    after: NativeCaptureRevision
    pose: PoseEvidence
    exclusive_owner_reported: bool
    writers_quiescent_reported: bool
    goals_match_actual_reported: bool

    def __post_init__(self):
        if type(self.subject) is not NativeLegIdentity or type(self.owner) is not NativeOwnerEvidence:
            raise ValueError('Typed subject/owner evidence required')
        if self.owner.subject != self.subject:
            raise ValueError('Owner and capture refer to different leg instances')
        if (type(self.before) is not NativeCaptureRevision or type(self.after) is not NativeCaptureRevision
                or self.before != self.after):
            raise ValueError('Equal before/after native revisions required for coherent capture')
        if type(self.pose) is not PoseEvidence:
            raise ValueError('Typed supplied pose evidence required')
        expected_identity = (self.subject.world_id, self.subject.actor_id,
                             self.owner.owner_epoch, self.subject.geometry_revision)
        if self.pose.identity != expected_identity:
            raise ValueError('Pose world/actor/epoch/geometry differs from capture')
        if self.pose.stamp_before != self.before.pose_stamp() or self.pose.stamp_after != self.after.pose_stamp():
            raise ValueError('Pose stamps differ from native capture revisions')
        for value in (self.exclusive_owner_reported, self.writers_quiescent_reported,
                      self.goals_match_actual_reported):
            if type(value) is not bool:
                raise ValueError('Exact reported ownership/command-state flags required')


def _sample_shape(sample):
    if type(sample) is not NumericPoseSample:
        raise ValueError('Typed numeric sample required')
    _text(sample.sample_id, 'numeric sample ID')
    _counter(sample.segment_index, 'segment index')
    for value in (sample.segment_elapsed_seconds, sample.planned_cycle_seconds,
                  sample.phase, sample.phase_velocity_per_second,
                  sample.phase_acceleration_per_second2, sample.compensated_extension):
        if not finite(value):
            raise ValueError('Finite numeric sample fields required')
    if (sample.segment_elapsed_seconds < 0 or sample.planned_cycle_seconds < 0
            or not 0 <= sample.phase <= 1):
        raise ValueError('Nonnegative sample times and unit phase required')
    if (type(sample.stages) is not tuple or len(sample.stages) != 10
            or any(not finite(value) or not 0 <= value <= 1 for value in sample.stages)):
        raise ValueError('Immutable ten-stage numeric sample required')
    if (type(sample.angles) is not tuple or len(sample.angles) != 10
            or any(type(pair) is not tuple or len(pair) != 2
                   or any(not finite(value) for value in pair) for pair in sample.angles)):
        raise ValueError('Immutable ten-joint pitch/yaw sample required')


@dataclass(frozen=True)
class NativeApplyIntent:
    transaction_id: str
    capture: NativeLegCapture
    sample: NumericPoseSample

    def __post_init__(self):
        _text(self.transaction_id, 'application transaction ID')
        if type(self.capture) is not NativeLegCapture:
            raise ValueError('Typed coherent before capture required')
        _sample_shape(self.sample)
        if not (self.capture.exclusive_owner_reported and self.capture.writers_quiescent_reported
                and self.capture.goals_match_actual_reported and self.capture.pose.contact_valid):
            raise ValueError('Reported owner/quiescent/matching goals/contact preconditions failed')

    def to_dict(self):
        revision = self.capture.after
        return dict(schemaVersion=SCHEMA_VERSION, status='draft_native_apply_intent',
                    transactionId=self.transaction_id, subject=asdict(self.capture.subject),
                    suppliedOwner=asdict(self.capture.owner), requiredBefore=asdict(revision),
                    suppliedBeforePose=asdict(self.capture.pose),
                    suppliedBeforeCommandState=dict(
                        exclusiveOwner=self.capture.exclusive_owner_reported,
                        writersQuiescent=self.capture.writers_quiescent_reported,
                        goalsMatchActual=self.capture.goals_match_actual_reported),
                    expectedCommandRevision=revision.command_revision+1,
                    expectedApplicationRevision=revision.application_revision+1,
                    numericTargets=self.sample.to_dict(),
                    nativeAdmissionRequired=True, nativeGeometryRecheckRequired=True,
                    nativeCommandSubmitted=False,
                    suppliedEvidenceAuthenticated=False, actualPoseConfirmed=False,
                    runtimeReady=False, motionAuthorized=False)


def prepare_native_apply_intent(proposal, capture):
    """Connect existing proposal DATA to native-boundary DATA, never dispatch."""
    if type(proposal) is not ApplicationProposal or type(capture) is not NativeLegCapture:
        raise ValueError('Typed application proposal and native capture required')
    if proposal.before != capture.pose:
        raise ValueError('Proposal before-pose differs from the supplied capture')
    return NativeApplyIntent(proposal.transaction_id, capture, proposal.sample)


@dataclass(frozen=True)
class NativeApplyReceipt:
    transaction_id: str
    sample_id: str
    requested_subject: NativeLegIdentity
    outcome_reported: str
    write_state_reported: str
    observed_before: NativeLegCapture | None
    observed_after: NativeLegCapture | None
    native_hold_reported: bool
    reason: str

    def __post_init__(self):
        _text(self.transaction_id, 'receipt transaction ID')
        _text(self.sample_id, 'receipt sample ID')
        if type(self.requested_subject) is not NativeLegIdentity:
            raise ValueError('Typed requested subject required')
        if type(self.native_hold_reported) is not bool or type(self.reason) is not str:
            raise ValueError('Exact reported hold Boolean and reason text required')
        allowed = {'applied_reported': ('complete',), 'rejected_reported': ('none',),
                   'partial_failure_reported': ('partial', 'unknown')}
        if (type(self.outcome_reported) is not str or self.outcome_reported not in allowed
                or self.write_state_reported not in allowed[self.outcome_reported]):
            raise ValueError('Consistent reported outcome/write-state required')
        for capture in (self.observed_before, self.observed_after):
            if capture is not None and type(capture) is not NativeLegCapture:
                raise ValueError('Observed captures must be typed or explicitly unavailable')
        if self.outcome_reported == 'applied_reported':
            if self.observed_before is None or self.observed_after is None:
                raise ValueError('Reported complete commit requires both coherent captures')
        elif not self.reason:
            raise ValueError('Rejected/partial/unknown outcome requires a reason')


def review_native_receipt_data(intent, receipt):
    """Correlate supplied metadata only; no actual-pose certificate or resume.

    This is stateless: transaction replay/one-pending enforcement still belongs
    to a future native owner. No success here authorizes another application.
    """
    if type(intent) is not NativeApplyIntent or type(receipt) is not NativeApplyReceipt:
        raise ValueError('Typed intent and supplied receipt required')
    if (receipt.transaction_id != intent.transaction_id or receipt.sample_id != intent.sample.sample_id
            or receipt.requested_subject != intent.capture.subject):
        raise ValueError('Receipt transaction/sample/subject does not match the intent')
    observed_before, observed_after = receipt.observed_before, receipt.observed_after
    no_write_counters_match = None
    if receipt.outcome_reported == 'applied_reported':
        for capture in (observed_before, observed_after):
            if capture.subject != intent.capture.subject or capture.owner != intent.capture.owner:
                raise ValueError('Reported commit changed subject/lifetime/geometry/owner/epoch')
        expected = intent.capture.after
        before, after = observed_before.after, observed_after.after
        if (before.command_revision != expected.command_revision
                or before.application_revision != expected.application_revision
                or before.probe_revision != expected.probe_revision
                or before.capture_sequence < expected.capture_sequence):
            raise ValueError('Native pre-commit revisions differ from required-before data')
        if (after.command_revision != before.command_revision+1
                or after.application_revision != before.application_revision+1
                or after.probe_revision <= before.probe_revision
                or after.capture_sequence <= before.capture_sequence):
            raise ValueError('Reported commit lacks exactly-one commit and fresh probe/capture revisions')
        status = 'reported_commit_metadata_correlated'
    elif receipt.outcome_reported == 'rejected_reported':
        # A stale-request rejection may legitimately observe a DIFFERENT owner
        # or revision from the request. Never mislabel this as an applied pose.
        if observed_before is not None and observed_after is not None:
            if observed_before.subject != observed_after.subject or observed_before.owner != observed_after.owner:
                raise ValueError('Reported no-write rejection changed the observed owner/subject')
            before, after = observed_before.after, observed_after.after
            if (after.capture_sequence <= before.capture_sequence
                    or after.probe_revision < before.probe_revision):
                raise ValueError('Reported rejection lacks a fresh, nonregressing after capture')
            no_write_counters_match = (before.command_revision == after.command_revision
                                       and before.application_revision == after.application_revision)
            if not no_write_counters_match:
                raise ValueError('Reported no-write rejection changed command/application revisions')
        status = 'reported_rejection_metadata_correlated'
    else:
        status = 'reported_partial_or_unknown_requires_native_recovery'
    return dict(schemaVersion=SCHEMA_VERSION, status=status, transactionId=receipt.transaction_id,
                sampleId=receipt.sample_id, outcomeReported=receipt.outcome_reported,
                suppliedNoWriteCountersMatch=no_write_counters_match,
                requiresNativeRecovery=receipt.outcome_reported == 'partial_failure_reported',
                suppliedNativeHoldReported=receipt.native_hold_reported,
                nativeHoldConfirmed=False, suppliedEvidenceAuthenticated=False,
                actualPoseCompared=False, actualPoseConfirmed=False, canContinue=False,
                autoRetryAllowed=False, runtimeReady=False, motionAuthorized=False)


class NativeReceiptLedger:
    """LOCAL supplied-data sequencing, not the native issuer or executor.

    There is no resume/reset/actual-pose confirmation API. A metadata-correlated
    commit must remain blocked until a separately implemented native review.
    """
    def __init__(self, subject, owner):
        if (type(subject) is not NativeLegIdentity or type(owner) is not NativeOwnerEvidence
                or owner.subject != subject):
            raise ValueError('Matching typed subject and supplied owner required')
        self._subject, self._owner = subject, owner
        self._pending = None
        self._last_receipt = None
        self._last_review = None
        self._used_transactions, self._used_samples = set(), set()
        self._state = 'idle'
        self._held_reason = None

    @property
    def state(self):
        return self._state

    @property
    def held_reason(self):
        return self._held_reason

    @property
    def pending_intent(self):
        return self._pending

    @property
    def last_metadata_review(self):
        return None if self._last_review is None else dict(self._last_review)

    def hold(self, reason):
        if type(reason) is not str or not reason:
            raise ValueError('Nonempty local native-boundary hold reason required')
        if self._held_reason is None:
            self._held_reason = reason
        self._state = 'held'
        self._pending = self._last_review = None
        # Keep consumed IDs/last supplied receipt for diagnosis, never auto-retry.

    def begin(self, intent):
        try:
            if self._state != 'idle' or self._held_reason is not None or self._pending is not None:
                raise ValueError('Native-boundary ledger is busy or locally held')
            if type(intent) is not NativeApplyIntent:
                raise ValueError('Typed native apply intent required')
            if intent.capture.subject != self._subject or intent.capture.owner != self._owner:
                raise ValueError('Intent differs from the bound leg/owner/epoch')
            if (intent.transaction_id in self._used_transactions
                    or intent.sample.sample_id in self._used_samples):
                raise ValueError('Previously consumed native transaction/sample ID')
            packet = intent.to_dict()
            self._used_transactions.add(intent.transaction_id)
            self._used_samples.add(intent.sample.sample_id)
            self._pending = intent
            self._state = 'awaiting_native_receipt'
            return packet  # DATA only; no native command is submitted.
        except Exception as exc:
            self.hold('native_boundary_begin: '+type(exc).__name__+': '+str(exc))
            raise

    def accept_receipt(self, receipt):
        try:
            if (self._state != 'awaiting_native_receipt' or self._held_reason is not None
                    or self._pending is None):
                raise ValueError('Missing, repeated or out-of-order native receipt')
            review = review_native_receipt_data(self._pending, receipt)
            self._last_receipt = receipt
            if receipt.outcome_reported == 'applied_reported':
                self._state = 'awaiting_actual_pose_review'
                # Retain intent for a future actual-pose reviewer. No transition
                # back to idle is implemented or inferred from counters alone.
                self._last_review = dict(review)
            else:
                self.hold('native_boundary_'+receipt.outcome_reported+': '+receipt.reason)
            return dict(review, localState=self._state)
        except Exception as exc:
            self.hold('native_boundary_receipt: '+type(exc).__name__+': '+str(exc))
            raise
