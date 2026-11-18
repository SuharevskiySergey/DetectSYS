"""Opt-in editor numeric integration check; no actor/pose application.

No import-time Unreal access. Separate user permission is required per run.
Exercises real numeric adapters, not a native actuator or gameplay controller.
"""
import json
import math
from pathlib import Path
import sys
import traceback
import uuid


def run(*, allow_numeric_calls=False):
    if allow_numeric_calls is not True:
        raise PermissionError('Separate user permission and numeric opt-in required')
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
        from beholder_dogleg_job import prepare_job
        from beholder_dogleg_pipeline import (
            DoglegCalculationPipeline, CalculationRequest, NumericPoseSample,
            CALCULATION_ABS_TOLERANCE, DERIVATIVE_REL_TOLERANCE)
        from beholder_dogleg_numeric_adapter import NumericBlueprintAdapter, _EditorFunctionLibraryBackend
        from beholder_dogleg_sample_adapter import DoglegSamplePipeline, NumericSampleAdapter
    finally:
        if added_path:
            sys.path.remove(tools_dir)
    # Never silently exercise a cached pre-migration adapter implementation.
    if ('named_numeric_kwargs' not in _EditorFunctionLibraryBackend.call.__code__.co_names
            or 'named_numeric_kwargs' not in NumericSampleAdapter.dispatch_pending.__code__.co_names):
        raise RuntimeError('Cached adapter lacks named-binding migration; stop without reloading live modules')
    report = dict(passed=False, running=True, configurations=[], samples=0,
                  successfulNumericDispatches=0, closedAdapters=0,
                  absoluteTolerance=CALCULATION_ABS_TOLERANCE,
                  derivativeRelativeTolerance=DERIVATIVE_REL_TOLERANCE,
                  pieStarted=False, actorCommandsIssued=False, poseApplicationPerformed=False,
                  gameplayConnected=False, graphEditsPerformed=False, motionAuthorized=False)
    path = Path(unreal.Paths.project_dir())/'Saved'/('BeholderDoglegAdapters_'+uuid.uuid4().hex+'.json')
    with path.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2, allow_nan=False)
    live_adapter = None
    try:
        for axis, amplitude in (('yaw', 1.0), ('pitch', -1.0)):
            job = prepare_job(extension=0.5, amplitude_degrees=amplitude, axis=axis, half_duration=2.0)
            configuration = dict(axis=axis, amplitudeDegrees=amplitude, extension=0.5,
                                 segments=len(job.segments), paths=[])
            report['configurations'].append(configuration)
            path_samples = {}
            for mode in ('clock_targets', 'facade'):
                pipeline = DoglegCalculationPipeline(job) if mode == 'clock_targets' else DoglegSamplePipeline(job)
                adapter_class = NumericBlueprintAdapter if mode == 'clock_targets' else NumericSampleAdapter
                require_edit_mode()
                live_adapter = adapter_class(pipeline, allow_numeric_calls=True)
                if not live_adapter.enabled:
                    raise AssertionError('Adapter did not enable after explicit opt-in')
                mode_report = dict(mode=mode, samples=[], closed=False)
                configuration['paths'].append(mode_report)
                collected = []
                for index, segment in enumerate(job.segments):
                    for elapsed in (0.0, segment.duration_seconds/2, segment.duration_seconds):
                        request = pipeline.begin_sample(index, elapsed)
                        require_edit_mode()
                        result = live_adapter.dispatch_pending()
                        report['successfulNumericDispatches'] += 1
                        if mode == 'clock_targets':
                            if (not isinstance(result, CalculationRequest) or result.kind != 'targets'
                                    or pipeline.pending_request is not result or pipeline.state != 'awaiting_targets'):
                                raise AssertionError('Clock dispatch did not return the pending target request')
                            if pipeline.numeric_sample is not None:
                                raise AssertionError('Sample was published before targets were checked')
                            sample_request = result
                            result = live_adapter.dispatch_pending()
                            report['successfulNumericDispatches'] += 1
                        else:
                            sample_request = request
                        require_edit_mode()
                        if (not isinstance(result, NumericPoseSample) or result.sample_id != sample_request.request_id
                                or pipeline.numeric_sample is not result or pipeline.state != 'idle'
                                or pipeline.pending_request is not None):
                            raise AssertionError('Completed numeric sample violated ordering/identity')
                        packet = result.to_dict()
                        if any(packet[flag] is not False for flag in
                               ('motionAuthorized', 'runtimeReady', 'actualPoseConfirmed')):
                            raise AssertionError('Numeric result unexpectedly authorized pose/gameplay')
                        mode_report['samples'].append(packet)
                        collected.append(result)
                        report['samples'] += 1
                if collected[-1].phase != 0.0 or collected[-1].stages != collected[0].stages:
                    raise AssertionError('Numeric cycle did not return to initial phase/stages')
                path_samples[mode] = collected
                live_adapter.close()
                if (live_adapter.enabled or pipeline.state != 'held' or pipeline.pending_request is not None
                        or pipeline.numeric_sample is not None):
                    raise AssertionError('Close did not invalidate local calculation state')
                close_reason = pipeline.held_reason
                try:
                    live_adapter.dispatch_pending()
                except PermissionError:
                    mode_report['dispatchAfterCloseRejected'] = True
                else:
                    raise AssertionError('Closed adapter accepted dispatch')
                if pipeline.held_reason != close_reason:
                    raise AssertionError('Close hold reason was not sticky')
                mode_report.update(closed=True, heldReason=close_reason)
                report['closedAdapters'] += 1
                live_adapter = None
            if len(path_samples['clock_targets']) != len(path_samples['facade']):
                raise AssertionError('Adapter paths returned different sample counts')
            for left, right in zip(path_samples['clock_targets'], path_samples['facade']):
                if (left.segment_index != right.segment_index
                        or left.segment_elapsed_seconds != right.segment_elapsed_seconds):
                    raise AssertionError('Adapter paths sampled different schedule positions')
                pairs = [(left.phase, right.phase, False),
                         (left.compensated_extension, right.compensated_extension, False),
                         (left.phase_velocity_per_second, right.phase_velocity_per_second, True),
                         (left.phase_acceleration_per_second2, right.phase_acceleration_per_second2, True)]
                pairs += [(a, b, False) for a, b in zip(left.stages, right.stages)]
                pairs += [(a, b, False) for la, ra in zip(left.angles, right.angles) for a, b in zip(la, ra)]
                if any(not math.isclose(a, b, abs_tol=CALCULATION_ABS_TOLERANCE,
                                        rel_tol=DERIVATIVE_REL_TOLERANCE if derivative else 0)
                       for a, b, derivative in pairs):
                    raise AssertionError('Two-function and facade adapter numeric samples disagree')
            configuration['adapterPathsCompared'] = True
        require_edit_mode()
        report.update(passed=True, editModeConfirmedAfter=True)
    except Exception as exc:
        report.update(error=repr(exc), traceback=traceback.format_exc())
        raise
    finally:
        if live_adapter is not None:
            try:
                live_adapter.close()
            except Exception as exc:
                report['cleanupError'] = repr(exc)
        report['running'] = False
        path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        print('DOGLEG_ADAPTER_REPORT', str(path))
        print('DOGLEG_ADAPTER_SUMMARY', json.dumps({key: report[key] for key in (
            'passed', 'running', 'samples', 'successfulNumericDispatches', 'closedAdapters', 'motionAuthorized')}))
    return report
