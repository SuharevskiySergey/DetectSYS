"""Immutable numeric job draft; limited numeric integration, no motion admission.

No Unreal imports, asset edits, clocks, Tick, function calls into the editor,
or actuator integration. Producing a packet never makes it runtime-ready.
"""
from dataclasses import asdict, dataclass
import math

from beholder_dogleg_job_contract import (
    SCHEMA_VERSION, CLOCK_BLUEPRINT, CLOCK_FUNCTION, TARGETS_BLUEPRINT, TARGETS_FUNCTION,
    MIN_SEGMENT_DURATION_SECONDS, MAX_SEGMENT_DURATION_SECONDS)
from beholder_dogleg_timing import DoglegTiming, QUINTIC_SPEED, QUINTIC_ACCELERATION
from check_beholder_dogleg_plane import split_fractions


def finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        # An arbitrarily large Python int must be rejected, not escape the
        # numeric guards before their caller can invalidate a pending receipt.
        return False


@dataclass(frozen=True)
class Segment:
    index: int
    start_seconds: float
    end_seconds: float
    phase_start: float
    phase_end: float
    returning: bool

    def __post_init__(self):
        if type(self.index) is not int or self.index < 0 or type(self.returning) is not bool:
            raise ValueError('Invalid segment index/direction')
        if not all(finite(v) for v in (self.start_seconds, self.end_seconds, self.phase_start, self.phase_end)):
            raise ValueError('Finite segment coordinates required')
        if self.start_seconds < 0 or not MIN_SEGMENT_DURATION_SECONDS <= self.duration_seconds <= MAX_SEGMENT_DURATION_SECONDS:
            raise ValueError('Segment is outside the proposed numeric clock duration limits')
        if not 0 <= self.phase_start < self.phase_end <= 1:
            raise ValueError('Strictly ordered unit phase bounds required')

    @property
    def duration_seconds(self):
        return self.end_seconds-self.start_seconds

    @property
    def initial_phase(self):
        return self.phase_end if self.returning else self.phase_start

    @property
    def final_phase(self):
        return self.phase_start if self.returning else self.phase_end

    def clock_arguments(self, elapsed_seconds):
        """Build argument DATA only. Does not invoke the future clock function."""
        if not finite(elapsed_seconds) or not 0 <= elapsed_seconds <= self.duration_seconds:
            raise ValueError('Elapsed must be within this exact segment; no silent clamp')
        return dict(SegmentElapsedSeconds=elapsed_seconds, SegmentDurationSeconds=self.duration_seconds,
                    PhaseStart=self.phase_start, PhaseEnd=self.phase_end, Returning=self.returning)


@dataclass(frozen=True)
class ReferenceBounds:
    maximum_joint_speed_degrees_per_second: float
    maximum_joint_acceleration_degrees_per_second2: float
    maximum_stage_speed_per_second: float
    maximum_stage_acceleration_per_second2: float
    single_axis_joint_speed_budget_degrees_per_second: float
    stage_speed_budget_per_second: float
    optional_joint_acceleration_limit: float | None


def _segment_reference_maxima(segments, amplitude_degrees):
    """Shared offline formulas, not a UE/physical timing certificate.

    Stage acceleration is conditional on the required clamp-kink stops. The job
    constructor checks reference split membership; this helper alone does not.
    """
    speed = max(QUINTIC_SPEED*(s.phase_end-s.phase_start)/s.duration_seconds for s in segments)
    acceleration = max(QUINTIC_ACCELERATION*(s.phase_end-s.phase_start)/s.duration_seconds**2
                       for s in segments)
    amplitude = abs(amplitude_degrees)
    radians = math.radians(amplitude)
    values = (2*amplitude*speed, 2*amplitude*acceleration,
              2*math.sin(radians)*radians*speed,
              2*((radians*speed)**2+math.sin(radians)*radians*acceleration))
    if not all(finite(value) and value >= 0 for value in values):
        raise ValueError('Stored segments produced invalid reference maxima')
    return values


@dataclass(frozen=True)
class PreparedDoglegJob:
    extension: float
    amplitude_degrees: float
    axis: str
    half_duration_seconds: float
    duration_fitted: bool
    segments: tuple[Segment, ...]
    reference_bounds: ReferenceBounds

    def __post_init__(self):
        # frozen=True alone does not freeze a caller-supplied list. Capture a
        # private immutable sequence even when construction bypasses prepare_job.
        segments = tuple(self.segments)
        if not segments or any(type(s) is not Segment for s in segments):
            raise ValueError('Nonempty sequence of immutable numeric segments required')
        object.__setattr__(self, 'segments', segments)
        if (not finite(self.half_duration_seconds) or self.half_duration_seconds <= 0
                or not finite(2*self.half_duration_seconds)):
            raise ValueError('Finite positive half and full cycle duration required')
        if type(self.duration_fitted) is not bool:
            raise ValueError('Boolean duration-fit flag required')
        if type(self.reference_bounds) is not ReferenceBounds:
            raise ValueError('Immutable reference bounds required')
        for name, value in asdict(self.reference_bounds).items():
            if name == 'optional_joint_acceleration_limit' and value is None:
                continue
            if not finite(value) or value < 0:
                raise ValueError('Finite nonnegative reference bound required: '+name)
        if (not finite(self.extension) or not 0.4 <= self.extension <= 0.9
                or not finite(self.amplitude_degrees) or abs(self.amplitude_degrees) > 1
                or self.axis not in ('pitch', 'yaw')):
            raise ValueError('Supported single-axis numeric dogleg parameters required')
        if (segments[0].start_seconds != 0 or segments[0].initial_phase != 0
                or segments[-1].end_seconds != 2*self.half_duration_seconds
                or segments[-1].final_phase != 0):
            raise ValueError('Stored segments must cover a complete returning cycle')
        for index, segment in enumerate(segments):
            if segment.index != index:
                raise ValueError('Stored segment indices must be contiguous')
            if (segment.start_seconds < self.half_duration_seconds
                    and (segment.returning or segment.end_seconds > self.half_duration_seconds)):
                raise ValueError('Forward segments must end at or before the half-cycle boundary')
            if segment.start_seconds >= self.half_duration_seconds and not segment.returning:
                raise ValueError('Second half of the cycle must use returning segments')
        for previous, following in zip(segments, segments[1:]):
            if (previous.end_seconds != following.start_seconds
                    or previous.final_phase != following.initial_phase):
                raise ValueError('Stored job has a time or phase discontinuity')
        forward = tuple(s for s in segments if not s.returning)
        if not forward or forward[-1].end_seconds != self.half_duration_seconds or forward[-1].final_phase != 1:
            raise ValueError('Forward half-cycle must reach phase one at the boundary')
        # Reuse the same analytic reference split as DoglegTiming. Do not accept
        # a near-enough boundary: that could leave a short unsplit clamp region.
        # Additional subdivisions are allowed, provided all required stops are
        # present on BOTH halves. Each segment uses a rest-to-rest quintic.
        required_stops, _critical = split_fractions(self.extension, self.amplitude_degrees, samples=2)
        returning = tuple(s for s in segments if s.returning)
        for half_segments in (forward, returning):
            boundaries = {phase for s in half_segments for phase in (s.phase_start, s.phase_end)}
            if any(stop not in boundaries for stop in required_stops):
                raise ValueError('Stored half-cycle omits a required reference clamp-kink stop')
        bounds = self.reference_bounds
        actual = _segment_reference_maxima(segments, self.amplitude_degrees)
        declared = (bounds.maximum_joint_speed_degrees_per_second,
                    bounds.maximum_joint_acceleration_degrees_per_second2,
                    bounds.maximum_stage_speed_per_second,
                    bounds.maximum_stage_acceleration_per_second2)
        if any(stated < computed for stated, computed in zip(declared, actual)):
            raise ValueError('Declared reference maxima understate stored segment formulas')
        if (bounds.single_axis_joint_speed_budget_degrees_per_second <= 0
                or bounds.stage_speed_budget_per_second <= 0):
            raise ValueError('Positive reference velocity budgets required')
        # Retain the factory's existing comparison margin; this is an offline
        # arithmetic guard, not a new physical/controller acceptance tolerance.
        if (actual[0] > bounds.single_axis_joint_speed_budget_degrees_per_second+1e-12
                or actual[2] > bounds.stage_speed_budget_per_second+1e-12):
            raise ValueError('Stored job exceeds reference velocity budgets')
        if bounds.optional_joint_acceleration_limit is not None:
            if (bounds.optional_joint_acceleration_limit <= 0
                    or actual[1] > bounds.optional_joint_acceleration_limit+1e-12):
                raise ValueError('Stored job exceeds the supplied reference acceleration budget')

    def target_arguments(self, phase):
        """Build target-calculator argument DATA, never call/apply it."""
        if not finite(phase) or not 0 <= phase <= 1:
            raise ValueError('Unit geometric phase required')
        return dict(BaseExtension=self.extension, Phase=phase,
                    AmplitudeDegrees=self.amplitude_degrees, UseYaw=self.axis == 'yaw')

    def to_dict(self):
        # Fresh containers: serialising/altering a packet cannot mutate this job.
        return dict(schemaVersion=SCHEMA_VERSION, status='draft_unverified',
                    extension=self.extension, amplitudeDegrees=self.amplitude_degrees, axis=self.axis,
                    halfDurationSeconds=self.half_duration_seconds, cycleDurationSeconds=2*self.half_duration_seconds,
                    durationFitted=self.duration_fitted, segments=[asdict(s) for s in self.segments],
                    referenceBounds=asdict(self.reference_bounds),
                    clockBinding=dict(blueprintPath=CLOCK_BLUEPRINT, functionName=CLOCK_FUNCTION),
                    targetBinding=dict(blueprintPath=TARGETS_BLUEPRINT, functionName=TARGETS_FUNCTION,
                                       phaseInput='Phase', phaseSource='clock.Phase'),
                    requires=['target_numeric_validation', 'clock_numeric_validation',
                              'live_pose_and_contact_admission', 'exclusive_controller_ownership',
                              'synchronous_application_and_actual_pose_confirmation',
                              'historical_observer_issue_resolution'],
                    referenceBudgetsOnly=True, physicalAccelerationValidated=False,
                    runtimeReady=False, runtimeTimingCertified=False, runtimeIKExecuted=False,
                    motionAuthorized=False)


def prepare_job(extension=0.5, amplitude_degrees=1.0, axis='yaw', half_duration=1.0,
                joint_speed_degrees=6.0, transition_seconds=0.6, joint_acceleration_limit=None):
    """Prepare numeric segments; half_duration=None requests reference-budget fit.

    Reject a sub-floor segment instead of merging it across a clamp kink or
    silently stretching the schedule. Never open a live admission from here.
    """
    # Validate before entering legacy timing/geometry helpers, whose finite
    # predicates can overflow on arbitrarily large Python ints. No coercion.
    scalar_inputs = (('extension', extension, 0.4, 0.9),
                     ('amplitude_degrees', amplitude_degrees, -1.0, 1.0),
                     ('joint_speed_degrees', joint_speed_degrees, 0.01, 1e6),
                     ('transition_seconds', transition_seconds, 0.01, 60.0))
    for name, value, lower, upper in scalar_inputs:
        if not finite(value) or not lower <= value <= upper:
            raise ValueError('Unsupported finite numeric job input: '+name)
    if type(axis) is not str or axis not in ('pitch', 'yaw'):
        raise ValueError('Single pitch or yaw axis required')
    if half_duration is not None and (not finite(half_duration) or not 0.1 <= half_duration <= 60):
        raise ValueError('Half duration must be None or finite in 0.1..60 seconds')
    if joint_acceleration_limit is not None and (
            not finite(joint_acceleration_limit) or joint_acceleration_limit <= 0):
        raise ValueError('Positive finite optional acceleration budget required')
    arguments = dict(extension=extension, amplitude=amplitude_degrees, axis=axis,
                     joint_speed_degrees=joint_speed_degrees, transition_seconds=transition_seconds,
                     joint_acceleration_limit=joint_acceleration_limit)
    schedule = (DoglegTiming.fit_duration(**arguments) if half_duration is None
                else DoglegTiming(half_duration=half_duration, **arguments))
    half = schedule.half_duration
    segments = [Segment(i, s['startSeconds'], s['endSeconds'], s['phaseStart'], s['phaseEnd'], False)
                for i,s in enumerate(schedule.segments)]
    for s in reversed(schedule.segments):
        segments.append(Segment(len(segments), 2*half-s['endSeconds'], 2*half-s['startSeconds'],
                                s['phaseStart'], s['phaseEnd'], True))
    if segments[0].start_seconds != 0 or segments[-1].end_seconds != 2*half:
        raise ValueError('Job does not cover the full cycle')
    if segments[0].initial_phase != 0 or segments[-1].final_phase != 0:
        raise ValueError('Job does not return to its initial phase')
    for previous, following in zip(segments, segments[1:]):
        if previous.end_seconds != following.start_seconds or previous.final_phase != following.initial_phase:
            raise ValueError('Job has a time or phase discontinuity')

    # Recompute from the actual stored forward AND reflected durations: do not
    # assume floating-point endpoint subtraction reproduced every forward span.
    joint_speed, joint_acceleration, stage_speed, stage_acceleration = _segment_reference_maxima(
        segments, amplitude_degrees)
    axis_budget, stage_budget = joint_speed_degrees/math.sqrt(2), 1/transition_seconds
    # The constructor enforces budgets for both factory and direct callers.
    bounds = ReferenceBounds(joint_speed, joint_acceleration, stage_speed, stage_acceleration,
                             axis_budget, stage_budget, joint_acceleration_limit)
    return PreparedDoglegJob(extension, amplitude_degrees, axis, half, half_duration is None,
                             tuple(segments), bounds)
