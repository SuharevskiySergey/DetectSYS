"""Draft shared numeric job/clock contract; no runtime authorization."""

SCHEMA_VERSION = 1
CLOCK_BLUEPRINT = '/Game/BeholderPrototype/Telescopic/BP_BeholderDoglegClock'
CLOCK_FUNCTION = 'EvaluateDoglegSegment'
TARGETS_BLUEPRINT = '/Game/BeholderPrototype/Telescopic/BP_BeholderDoglegTargets'
TARGETS_FUNCTION = 'CalculateDoglegTargets'
SAMPLE_BLUEPRINT = '/Game/BeholderPrototype/Telescopic/BP_BeholderDoglegSample'
SAMPLE_FUNCTION = 'CalculateDoglegSample'

CLOCK_INPUT_LAYOUT = (('SegmentElapsedSeconds', 'float'), ('SegmentDurationSeconds', 'float'),
                      ('PhaseStart', 'float'), ('PhaseEnd', 'float'), ('Returning', 'bool'))
CLOCK_OUTPUT_LAYOUT = (('NumericInputsAccepted', 'bool'), ('MotionAuthorized', 'bool'),
                       ('Phase', 'float'), ('PhaseVelocityPerSecond', 'float'),
                       ('PhaseAccelerationPerSecond2', 'float'), ('SegmentComplete', 'bool'))
TARGETS_INPUT_LAYOUT = (('BaseExtension', 'float'), ('Phase', 'float'),
                       ('AmplitudeDegrees', 'float'), ('UseYaw', 'bool'))
TARGETS_OUTPUT_LAYOUT = (('NumericInputsAccepted', 'bool'), ('MotionAuthorized', 'bool'),
                        ('CompensatedExtension', 'float'))+tuple(
    (f'Stage{i}Target', 'float') for i in range(10))+tuple(
    (f'Joint{i}{axis}Target', 'float') for i in range(1, 10) for axis in ('Pitch', 'Yaw'))

# Facade installed; limited 68-case editor numeric coverage, NOT motion admission.
# Phase is deliberately absent from its external inputs; it comes from clock.
SAMPLE_INPUT_LAYOUT = CLOCK_INPUT_LAYOUT+tuple(
    (name, kind) for name,kind in TARGETS_INPUT_LAYOUT if name != 'Phase')
SAMPLE_OUTPUT_LAYOUT = CLOCK_OUTPUT_LAYOUT+tuple(
    (name, kind) for name,kind in TARGETS_OUTPUT_LAYOUT
    if name not in ('NumericInputsAccepted', 'MotionAuthorized'))

# Confirmed for these three libraries in the 228-case editor numeric run.
# Do not infer the hidden context's positional order from another library.
REFLECTED_INPUT_NAMES = (
    ('SegmentElapsedSeconds', 'segment_elapsed_seconds'),
    ('SegmentDurationSeconds', 'segment_duration_seconds'),
    ('PhaseStart', 'phase_start'), ('PhaseEnd', 'phase_end'), ('Returning', 'returning'),
    ('BaseExtension', 'base_extension'), ('Phase', 'phase'),
    ('AmplitudeDegrees', 'amplitude_degrees'), ('UseYaw', 'use_yaw'))

# Proposed arithmetic limits, NOT approved physical/controller settings.
MIN_SEGMENT_DURATION_TEXT = '0.000001'
MAX_SEGMENT_DURATION_TEXT = '60.000000'
MIN_SEGMENT_DURATION_SECONDS = float(MIN_SEGMENT_DURATION_TEXT)
MAX_SEGMENT_DURATION_SECONDS = float(MAX_SEGMENT_DURATION_TEXT)
