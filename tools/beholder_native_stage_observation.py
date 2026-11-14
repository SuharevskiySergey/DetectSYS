"""Fail-closed consumption of isolated Blueprint native step telemetry.

Does not drive Tick, certify collisions, or infer individual hidden steps from
their aggregate displacement. Per-step evidence comes from sticky native audit.
"""
import math

FIELDS = ('Samples', 'LastUpdate', 'Direction', 'Last', 'Maximum',
          'MaximumExcess', 'Violation', 'Invalid')
TOLERANCE = 2e-6


def snapshot(value):
    if not isinstance(value, dict) or any(k not in value for k in FIELDS):
        raise ValueError('native_step_telemetry_missing')
    result = {k: value[k] for k in FIELDS}
    for key in ('Samples', 'LastUpdate'):
        if type(result[key]) is not int or result[key] < 0:
            raise ValueError('native_step_counter_invalid')
    for key in ('Direction', 'Last', 'Maximum', 'MaximumExcess'):
        v = result[key]
        if type(v) not in (int, float) or not math.isfinite(v):
            raise ValueError('native_step_nonfinite')
    if result['Direction'] not in (-1, 0, 1):
        raise ValueError('native_step_direction_invalid')
    if any(not 0 <= result[k] <= 1+TOLERANCE for k in ('Last', 'Maximum', 'MaximumExcess')):
        raise ValueError('native_step_range_invalid')
    if any(type(result[k]) is not bool for k in ('Violation', 'Invalid')):
        raise ValueError('native_step_flag_invalid')
    if result['Invalid']:
        raise ValueError('native_step_invalid')
    if result['Violation'] or result['MaximumExcess'] > TOLERANCE:
        raise ValueError('native_step_cap')
    if result['Last'] > result['Maximum']:
        raise ValueError('native_step_maximum_inconsistent')
    return result


def stage_values(stages):
    values = tuple(stages)
    if len(values) != 10 or any(type(v) not in (int, float) or not math.isfinite(v)
                               or not -TOLERANCE <= v <= 1+TOLERANCE for v in values):
        raise ValueError('native_step_stages_invalid')
    return values


class NativeStageObservation:
    def __init__(self, initial_snapshot, stages, direction, cap):
        if type(direction) not in (int, float) or direction not in (-1, 1):
            raise ValueError('native_step_motion_direction_invalid')
        if type(cap) not in (int, float) or not math.isfinite(cap) or not 0.001 <= cap <= 1:
            raise ValueError('native_step_cap_setting_invalid')
        self.previous = snapshot(initial_snapshot)
        self.baseline = self.previous['Samples']
        self.stages = stage_values(stages)
        self.direction, self.cap, self.updates = direction, cap, 0
        self.report = dict(sampleBaseline=self.baseline, nativeAppliedUpdatesVerified=0,
                           observedWindows=0, skippedNativeObservations=0,
                           maximumSampledWindowDelta=0.0, perStepEvidence='native_sticky_telemetry',
                           perAppliedUpdateStepCapVerified=False, continuousCollisionCertified=False)

    def observe(self, telemetry, stages, updates):
        current, stages = snapshot(telemetry), stage_values(stages)
        if type(updates) is not int or updates < self.updates:
            raise ValueError('native_step_update_regression')
        if current['Samples'] != self.baseline+updates:
            raise ValueError('native_step_coverage')
        if updates and (current['LastUpdate'] != updates or current['Direction'] != self.direction):
            raise ValueError('native_step_stamp')
        if any(current[k] < self.previous[k] for k in ('Samples', 'Maximum', 'MaximumExcess')):
            raise ValueError('native_step_counter_regression')
        span = updates-self.updates
        delta = max(abs(a-b) for a,b in zip(stages, self.stages))
        if not span and current != self.previous:
            raise ValueError('native_step_changed_without_update')
        if updates and current['Last'] > self.cap+TOLERANCE:
            raise ValueError('native_step_cap')
        # This is an aggregate consistency check, NOT evidence for each hidden
        # update. The complete counter/stamp and native sticky flags are needed.
        if delta > span*self.cap+max(1, span)*TOLERANCE:
            raise ValueError('native_step_window_budget')
        if span:
            self.report['observedWindows'] += 1
            self.report['skippedNativeObservations'] += span-1
        self.report.update(nativeAppliedUpdatesVerified=updates,
                           perAppliedUpdateStepCapVerified=updates > 0,
                           maximumSampledWindowDelta=max(self.report['maximumSampledWindowDelta'], delta),
                           nativeMaximum=current['Maximum'], nativeMaximumExcess=current['MaximumExcess'])
        # A rejected snapshot must never advance observation state.
        self.previous, self.stages, self.updates = current, stages, updates
