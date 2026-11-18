"""Supplied-answer review; exercised on 228 editor receipts, no editor calls here.

Supplied answers are not authenticated engine observations. Tolerances must be
explicitly agreed by the caller; this module grants no execution permission.
"""
import math

from beholder_contact_dogleg import dogleg_pose
from beholder_dogleg_job import finite
from beholder_dogleg_job_contract import (
    CLOCK_OUTPUT_LAYOUT, TARGETS_OUTPUT_LAYOUT, SAMPLE_OUTPUT_LAYOUT)
from beholder_dogleg_numeric_validation_plan import validation_plan, plan_fingerprint
from beholder_dogleg_timing import quintic


def _expected(case, *, target_phase=None):
    kind, arguments = case['kind'], case['arguments']
    layout = dict(clock=CLOCK_OUTPUT_LAYOUT, targets=TARGETS_OUTPUT_LAYOUT,
                  sample=SAMPLE_OUTPUT_LAYOUT)[kind]
    result = {name: False if scalar == 'bool' else 0.0 for name, scalar in layout}
    if not case['expectedNumericInputsAccepted']:
        return result
    result['NumericInputsAccepted'] = True
    if kind in ('clock', 'sample'):
        duration = arguments['SegmentDurationSeconds']
        elapsed = arguments['SegmentElapsedSeconds']
        q, dq, ddq = quintic(elapsed/duration)
        lo, hi = arguments['PhaseStart'], arguments['PhaseEnd']
        span = hi-lo
        reverse = arguments['Returning']
        phase = hi-span*q if reverse else lo+span*q
        sign = -1 if reverse else 1
        result.update(Phase=phase, PhaseVelocityPerSecond=sign*span*dq/duration,
                      PhaseAccelerationPerSecond2=sign*span*ddq/duration**2,
                      SegmentComplete=elapsed == duration)
    if kind in ('targets', 'sample'):
        phase = arguments['Phase'] if kind == 'targets' else result['Phase']
        if kind == 'sample' and target_phase is not None:
            phase = target_phase
        pose = dogleg_pose(arguments['BaseExtension'], arguments['AmplitudeDegrees']*phase,
                           'yaw' if arguments['UseYaw'] else 'pitch')
        result['CompensatedExtension'] = pose['extension']
        result.update({f'Stage{i}Target': v for i, v in enumerate(pose['stages'])})
        result.update({f'Joint{i}{axis}Target': pose['angles'][i][component]
                       for i in range(1, 10) for component, axis in enumerate(('Pitch', 'Yaw'))})
    return result


def review_supplied_results(records, *, submitted_plan_sha256,
                            absolute_tolerance, derivative_relative_tolerance):
    """Require exactly one named-output record per canonical plan case.

    A record is {caseId, outputs}; tuple binding must be resolved upstream.
    submitted_plan_sha256 must identify the plan selected BEFORE collecting
    answers, not be retroactively filled from the current plan for old data.
    Missing, duplicate, extra, malformed or mismatched cases raise ValueError.
    No success packet is produced on partial coverage or numeric disagreement.
    """
    for tolerance in (absolute_tolerance, derivative_relative_tolerance):
        if not finite(tolerance) or tolerance < 0:
            raise ValueError('Explicit finite nonnegative comparison tolerances required')
    plan = validation_plan()
    fingerprint = plan_fingerprint(plan)
    if type(submitted_plan_sha256) is not str or submitted_plan_sha256 != fingerprint:
        raise ValueError('Submitted numeric plan fingerprint does not match the current plan')
    cases = {case['caseId']: case for case in plan['cases']}
    seen = set()
    accepted_outputs = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {'caseId', 'outputs'}:
            raise ValueError('Exact caseId/outputs record required')
        case_id = record['caseId']
        if not isinstance(case_id, str) or case_id not in cases or case_id in seen:
            raise ValueError('Unknown or duplicate case ID')
        case = cases[case_id]
        expected = _expected(case)
        outputs = record['outputs']
        if not isinstance(outputs, dict) or set(outputs) != set(expected):
            raise ValueError('Exact named output layout required: '+case_id)
        for name, reference in expected.items():
            value = outputs[name]
            if type(reference) is bool:
                if type(value) is not bool or value is not reference:
                    raise ValueError('Boolean mismatch: '+case_id+':'+name)
            else:
                if not finite(value):
                    raise ValueError('Nonfinite/non-numeric output: '+case_id+':'+name)
                # Refusals must return literal zeros, not values within an
                # acceptance tolerance. Bool is rejected by finite above.
                if not case['expectedNumericInputsAccepted']:
                    matches = value == 0
                else:
                    derivative = name in ('PhaseVelocityPerSecond', 'PhaseAccelerationPerSecond2')
                    matches = math.isclose(value, reference, abs_tol=absolute_tolerance,
                                           rel_tol=derivative_relative_tolerance if derivative else 0)
                if not matches:
                    raise ValueError('Numeric mismatch: '+case_id+':'+name)
        if case['kind'] == 'sample' and case['expectedNumericInputsAccepted']:
            # Passing the separate reference checks is not sufficient evidence
            # of phase forwarding. Also compare targets against the supplied
            # clock phase. This is data consistency, not authenticated execution.
            phase = outputs['Phase']
            arguments = case['arguments']
            if not arguments['PhaseStart'] <= phase <= arguments['PhaseEnd']:
                raise ValueError('Supplied facade phase left its segment: '+case_id)
            forwarded = _expected(case, target_phase=phase)
            for name, _scalar in TARGETS_OUTPUT_LAYOUT:
                if name in ('NumericInputsAccepted', 'MotionAuthorized'):
                    continue
                if not math.isclose(outputs[name], forwarded[name],
                                    abs_tol=absolute_tolerance, rel_tol=0):
                    raise ValueError('Facade targets disagree with returned Phase: '+case_id+':'+name)
        seen.add(case_id)
        accepted_outputs[case_id] = dict(outputs)
    if seen != set(cases):
        raise ValueError('Incomplete plan coverage; missing cases: '+str(len(set(cases)-seen)))
    for comparison in plan['comparisons']:
        sample = accepted_outputs[comparison['sampleCaseId']]
        for key, layout in (('clockCaseId', CLOCK_OUTPUT_LAYOUT),
                            ('targetsCaseId', TARGETS_OUTPUT_LAYOUT)):
            companion = accepted_outputs[comparison[key]]
            for name, scalar in layout:
                if scalar == 'bool':
                    matches = sample[name] is companion[name]
                else:
                    derivative = name in ('PhaseVelocityPerSecond', 'PhaseAccelerationPerSecond2')
                    matches = math.isclose(sample[name], companion[name], abs_tol=absolute_tolerance,
                                           rel_tol=derivative_relative_tolerance if derivative else 0)
                if not matches:
                    raise ValueError('Inter-library mismatch: '+comparison['sampleCaseId']+':'+name)
    return dict(status='supplied_numeric_data_compared', casesCompared=len(seen),
                planSchemaVersion=plan['schemaVersion'], planSha256=fingerprint,
                companionGroupsCompared=len(plan['comparisons']),
                absoluteTolerance=absolute_tolerance,
                derivativeRelativeTolerance=derivative_relative_tolerance,
                engineExecutionAuthenticated=False, blueprintNumericValidationConfirmed=False,
                runtimeReady=False, motionAuthorized=False)
