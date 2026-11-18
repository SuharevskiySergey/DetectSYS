"""Numeric request draft with synthetic and limited real-adapter coverage.

No Unreal calls, clocks, Tick, actuator writes, real ownership or physical hold.
All returned packets remain calculation-only and motionAuthorized=false.
"""
from dataclasses import asdict, dataclass
import math
import uuid

from beholder_contact_dogleg import dogleg_pose
from beholder_dogleg_job import PreparedDoglegJob, finite
from beholder_dogleg_job_contract import CLOCK_BLUEPRINT, CLOCK_FUNCTION, TARGETS_BLUEPRINT, TARGETS_FUNCTION
from beholder_dogleg_timing import quintic

# Proposed comparison tolerances for calculation receipts only, not geometry,
# contact, controller safety or physical acceleration acceptance settings.
CALCULATION_ABS_TOLERANCE = 1e-6
DERIVATIVE_REL_TOLERANCE = 1e-5


@dataclass(frozen=True)
class CalculationRequest:
    request_id: str
    kind: str
    blueprint_path: str
    function_name: str
    arguments: tuple[tuple[str, object], ...]

    def to_dict(self):
        return dict(requestId=self.request_id, kind=self.kind, blueprintPath=self.blueprint_path,
                    functionName=self.function_name, arguments=dict(self.arguments),
                    calculationOnly=True, motionAuthorized=False)


@dataclass(frozen=True)
class NumericPoseSample:
    sample_id: str
    segment_index: int
    segment_elapsed_seconds: float
    planned_cycle_seconds: float
    phase: float
    phase_velocity_per_second: float
    phase_acceleration_per_second2: float
    compensated_extension: float
    stages: tuple[float, ...]
    angles: tuple[tuple[float, float], ...]

    def to_dict(self):
        return dict(**asdict(self), status='draft_numeric_sample', calculationOnly=True,
                    actualPoseConfirmed=False, runtimeReady=False, motionAuthorized=False)


class DoglegCalculationPipeline:
    """One pending calculator request, with local fail-closed bookkeeping.

    Request production is not request execution. A completed numeric sample
    does not mean a pose was applied, confirmed, or admitted to runtime motion.
    """
    def __init__(self, job):
        if not isinstance(job, PreparedDoglegJob) or not job.segments:
            raise ValueError('Prepared numeric job required')
        self._job = job
        self.session = uuid.uuid4().hex
        self.state = 'idle'
        self.held_reason = None
        self._sequence = 0
        self._pending = None
        self._candidate = None
        self._sample = None
        self._last_position = None

    @property
    def job(self):
        return self._job

    @property
    def pending_request(self):
        return self._pending

    @property
    def numeric_sample(self):
        return self._sample

    def hold(self, reason):
        """LOCAL bookkeeping only: never a Cancel call or physical stop."""
        if not isinstance(reason, str) or not reason:
            raise ValueError('Nonempty local hold reason required')
        if self.held_reason is None:
            self.held_reason = reason
        self.state = 'held'
        self._pending = self._candidate = self._sample = None

    def _request(self, kind, arguments):
        path, name = ((CLOCK_BLUEPRINT, CLOCK_FUNCTION) if kind == 'clock'
                      else (TARGETS_BLUEPRINT, TARGETS_FUNCTION))
        request_id = f'{self.session}:{self._sequence}:{kind}'
        self._pending = CalculationRequest(request_id, kind, path, name, tuple(arguments.items()))
        self.state = 'awaiting_'+kind
        return self._pending

    def _expect(self, request_id, kind):
        if self.state == 'held':
            raise ValueError('Pipeline is locally held: '+self.held_reason)
        if (self._pending is None or self.state != 'awaiting_'+kind
                or self._pending.kind != kind or self._pending.request_id != request_id):
            raise ValueError('Stale or out-of-order calculation receipt')

    @staticmethod
    def _number(result, key):
        value = result.get(key)
        if not finite(value):
            raise ValueError('Missing or nonfinite calculation output: '+key)
        return value

    @staticmethod
    def _flags(result):
        if not isinstance(result, dict):
            raise ValueError('Named calculation outputs required')
        if result.get('NumericInputsAccepted') is not True:
            raise ValueError('Calculator did not accept numeric inputs')
        if result.get('MotionAuthorized') is not False:
            raise ValueError('Unexpected or missing motion authorization flag')

    @staticmethod
    def _near(actual, expected, derivative=False):
        if not math.isclose(actual, expected, abs_tol=CALCULATION_ABS_TOLERANCE,
                            rel_tol=DERIVATIVE_REL_TOLERANCE if derivative else 0):
            raise ValueError('Calculation output differs from the numeric reference')

    def begin_sample(self, segment_index, elapsed_seconds):
        try:
            if self.state != 'idle':
                raise ValueError('A calculation is pending or the pipeline is locally held')
            if type(segment_index) is not int or not 0 <= segment_index < len(self.job.segments):
                raise ValueError('Invalid segment index')
            segment = self.job.segments[segment_index]
            arguments = segment.clock_arguments(elapsed_seconds)
            if self._last_position is None:
                if segment_index != 0 or elapsed_seconds != 0:
                    raise ValueError('First calculation must begin at the job origin')
            else:
                previous_index, previous_elapsed = self._last_position
                if segment_index == previous_index:
                    if elapsed_seconds < previous_elapsed:
                        raise ValueError('Segment time regressed')
                elif segment_index == previous_index+1:
                    previous = self.job.segments[previous_index]
                    if previous_elapsed != previous.duration_seconds or elapsed_seconds != 0:
                        raise ValueError('Segment boundary must be calculated on both sides')
                else:
                    raise ValueError('Skipping or reversing segment order is forbidden')
            self._sequence += 1
            self._sample = None
            self._candidate = dict(segment_index=segment_index, elapsed_seconds=elapsed_seconds)
            return self._request('clock', arguments)
        except (ValueError, TypeError) as exc:
            self.hold(str(exc))
            raise

    def _validated_clock_candidate(self, result):
        """Validate without publishing state or creating a calculator request."""
        self._flags(result)
        candidate = dict(self._candidate)
        segment = self.job.segments[candidate['segment_index']]
        u = candidate['elapsed_seconds']/segment.duration_seconds
        q, dq, ddq = quintic(u)
        span = segment.phase_end-segment.phase_start
        sign = -1 if segment.returning else 1
        expected_phase = (segment.phase_end-span*q if segment.returning
                          else segment.phase_start+span*q)
        phase = self._number(result, 'Phase')
        velocity = self._number(result, 'PhaseVelocityPerSecond')
        acceleration = self._number(result, 'PhaseAccelerationPerSecond2')
        if not segment.phase_start <= phase <= segment.phase_end:
            raise ValueError('Clock phase left its planned segment')
        self._near(phase, expected_phase)
        self._near(velocity, sign*span*dq/segment.duration_seconds, derivative=True)
        self._near(acceleration, sign*span*ddq/segment.duration_seconds**2, derivative=True)
        complete = candidate['elapsed_seconds'] == segment.duration_seconds
        if result.get('SegmentComplete') is not complete:
            raise ValueError('Clock completion flag disagrees with the requested endpoint')
        candidate.update(phase=phase, velocity=velocity, acceleration=acceleration)
        return candidate

    def accept_clock(self, request_id, result):
        try:
            self._expect(request_id, 'clock')
            self._candidate = self._validated_clock_candidate(result)
            return self._request('targets', self.job.target_arguments(self._candidate['phase']))
        except (ValueError, TypeError, KeyError) as exc:
            self.hold(str(exc))
            raise

    def _validated_target_sample(self, request_id, result, candidate):
        """Build an unpublished sample; no request/state transition here."""
        self._flags(result)
        reference = dogleg_pose(self.job.extension, self.job.amplitude_degrees*candidate['phase'], self.job.axis)
        extension = self._number(result, 'CompensatedExtension')
        self._near(extension, reference['extension'])
        stages = tuple(self._number(result, f'Stage{i}Target') for i in range(10))
        if not all(0 <= value <= 1 for value in stages):
            raise ValueError('Calculated stage left the unit range')
        for actual, expected in zip(stages, reference['stages']):
            self._near(actual, expected)
        angles = ((0.0, 0.0),)+tuple(
            (self._number(result, f'Joint{i}PitchTarget'), self._number(result, f'Joint{i}YawTarget'))
            for i in range(1, 10))
        for actual, expected in zip(angles, reference['angles']):
            for a,b in zip(actual, expected):
                self._near(a, b)
        segment = self.job.segments[candidate['segment_index']]
        return NumericPoseSample(request_id, candidate['segment_index'], candidate['elapsed_seconds'],
                                 segment.start_seconds+candidate['elapsed_seconds'], candidate['phase'],
                                 candidate['velocity'], candidate['acceleration'], extension, stages, angles)

    def _publish_sample(self, sample):
        """Local publication after every required numeric check has passed."""
        self._last_position = (sample.segment_index, sample.segment_elapsed_seconds)
        self._pending = self._candidate = None
        self._sample, self.state = sample, 'idle'
        return sample

    def accept_targets(self, request_id, result):
        try:
            self._expect(request_id, 'targets')
            sample = self._validated_target_sample(request_id, result, self._candidate)
            return self._publish_sample(sample)
        except (ValueError, TypeError, KeyError) as exc:
            self.hold(str(exc))
            raise
