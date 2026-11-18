"""Explicitly opted-in editor numeric runner; no gameplay/actor application.

Uses only the three installed dogleg libraries. No import-time Unreal access,
PIE, clocks, setters, compilation, graph edits or application integration.
Every run requires separate user permission; this opt-in is not permission.
"""
import json
import math
from pathlib import Path
import sys
import traceback
import uuid


def run(*, allow_numeric_calls=False, absolute_tolerance, derivative_relative_tolerance):
    if allow_numeric_calls is not True:
        raise PermissionError('Separate permission and explicit numeric-call opt-in required')
    import unreal

    def require_edit_mode():
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor is None or editor.get_game_world() is not None:
            raise RuntimeError('Edit mode without game world required')

    require_edit_mode()
    tools_dir = str(Path(__file__).resolve().parent)
    added_path = tools_dir not in sys.path
    if added_path:
        sys.path.insert(0, tools_dir)
    try:
        from beholder_dogleg_job import finite
        from beholder_dogleg_job_contract import (
            CLOCK_BLUEPRINT, CLOCK_FUNCTION, CLOCK_INPUT_LAYOUT, CLOCK_OUTPUT_LAYOUT,
            TARGETS_BLUEPRINT, TARGETS_FUNCTION, TARGETS_INPUT_LAYOUT, TARGETS_OUTPUT_LAYOUT,
            SAMPLE_BLUEPRINT, SAMPLE_FUNCTION, SAMPLE_INPUT_LAYOUT, SAMPLE_OUTPUT_LAYOUT)
        from beholder_dogleg_numeric_validation_plan import validation_plan, plan_fingerprint
        from beholder_dogleg_numeric_result_review import _expected, review_supplied_results
    finally:
        if added_path:
            sys.path.remove(tools_dir)
    for tolerance in (absolute_tolerance, derivative_relative_tolerance):
        if not finite(tolerance) or tolerance < 0:
            raise ValueError('Agreed finite nonnegative tolerances required')
    specs = dict(clock=(CLOCK_BLUEPRINT, CLOCK_FUNCTION, CLOCK_INPUT_LAYOUT, CLOCK_OUTPUT_LAYOUT),
                 targets=(TARGETS_BLUEPRINT, TARGETS_FUNCTION, TARGETS_INPUT_LAYOUT, TARGETS_OUTPUT_LAYOUT),
                 sample=(SAMPLE_BLUEPRINT, SAMPLE_FUNCTION, SAMPLE_INPUT_LAYOUT, SAMPLE_OUTPUT_LAYOUT))
    python_names = dict(SegmentElapsedSeconds='segment_elapsed_seconds',
                        SegmentDurationSeconds='segment_duration_seconds', PhaseStart='phase_start',
                        PhaseEnd='phase_end', Returning='returning', BaseExtension='base_extension',
                        Phase='phase', AmplitudeDegrees='amplitude_degrees', UseYaw='use_yaw')
    libraries = {}
    for kind, (path, function, inputs, outputs) in specs.items():
        require_edit_mode()
        cls = unreal.load_class(None, path+'.'+path.rsplit('/', 1)[-1]+'_C')
        if cls is None:
            raise RuntimeError('Compiled numeric library unavailable: '+kind)
        library = unreal.get_default_object(cls)
        if not isinstance(library, unreal.BlueprintFunctionLibrary):
            raise TypeError('Only whitelisted Function Library CDOs may be called')
        libraries[kind] = library
    plan = validation_plan()
    fingerprint = plan_fingerprint(plan)
    report = dict(passed=False, running=True, planSha256=fingerprint,
                  absoluteTolerance=absolute_tolerance,
                  derivativeRelativeTolerance=derivative_relative_tolerance,
                  plannedCases=len(plan['cases']), completedCases=0,
                  casesByKind=dict(clock=0, targets=0, sample=0), records=[],
                  maximumAbsoluteNumericDifference=0.0,
                  pieStarted=False, actorCommandsIssued=False, graphEditsPerformed=False,
                  gameplayConnected=False, motionAuthorized=False,
                  binding='CDO.call_method(name, args=(), kwargs=snake_case_inputs_with_world_context_None)')
    path = Path(unreal.Paths.project_dir())/'Saved'/('BeholderDoglegNumeric_'+uuid.uuid4().hex+'.json')
    with path.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2, allow_nan=False)
    try:
        for case in plan['cases']:
            kind = case['kind']
            blueprint, function, inputs, outputs = specs[kind]
            arguments = case['arguments']
            if (case['blueprintPath'] != blueprint or case['functionName'] != function
                    or set(arguments) != {name for name, _kind in inputs}):
                raise ValueError('Plan case is outside the whitelisted numeric signature')
            kwargs = {'world_context': None}
            for name, scalar in inputs:
                value = arguments[name]
                if scalar == 'bool':
                    if type(value) is not bool:
                        raise ValueError('Exact Boolean input required')
                elif not finite(value):
                    raise ValueError('This finite first-stage plan cannot probe NaN/Inf')
                kwargs[python_names[name]] = value
            expected = _expected(case)
            record = dict(caseId=case['caseId'], kind=kind, arguments=dict(arguments),
                          expected=expected, passed=False)
            report['records'].append(record)
            require_edit_mode()
            raw = libraries[kind].call_method(function, args=(), kwargs=kwargs)
            require_edit_mode()
            if type(raw) is not tuple or len(raw) != len(outputs):
                raise ValueError('Unexpected reflected output tuple: '+case['caseId'])
            actual = {}
            for (name, scalar), value in zip(outputs, raw):
                if scalar == 'bool':
                    if type(value) is not bool:
                        raise ValueError('Exact Boolean output required: '+name)
                elif not finite(value):
                    raise ValueError('Finite numeric output required: '+name)
                actual[name] = value
            record['outputs'] = actual
            for name, reference in expected.items():
                value = actual[name]
                if type(reference) is bool:
                    matches = value is reference
                elif not case['expectedNumericInputsAccepted']:
                    matches = value == 0
                else:
                    derivative = name in ('PhaseVelocityPerSecond', 'PhaseAccelerationPerSecond2')
                    matches = math.isclose(value, reference, abs_tol=absolute_tolerance,
                                           rel_tol=derivative_relative_tolerance if derivative else 0)
                    report['maximumAbsoluteNumericDifference'] = max(
                        report['maximumAbsoluteNumericDifference'], abs(value-reference))
                if not matches:
                    record['mismatchField'] = name
                    raise AssertionError('Dogleg numeric mismatch: '+case['caseId']+':'+name)
            record['passed'] = True
            report['completedCases'] += 1
            report['casesByKind'][kind] += 1
        # Complete-plan checks include returned-Phase and companion consistency.
        report['review'] = review_supplied_results(
            [dict(caseId=record['caseId'], outputs=record['outputs']) for record in report['records']],
            submitted_plan_sha256=fingerprint, absolute_tolerance=absolute_tolerance,
            derivative_relative_tolerance=derivative_relative_tolerance)
        require_edit_mode()
        report.update(passed=True, editModeConfirmedAfter=True, realEditorCallsPerformed=True)
    except Exception as exc:
        report.update(error=repr(exc), traceback=traceback.format_exc())
        raise
    finally:
        report['running'] = False
        path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        print('DOGLEG_NUMERIC_REPORT', str(path))
        print('DOGLEG_NUMERIC_SUMMARY', json.dumps({key: report[key] for key in (
            'passed', 'running', 'plannedCases', 'completedCases', 'casesByKind',
            'maximumAbsoluteNumericDifference', 'motionAuthorized')}))
    return report
