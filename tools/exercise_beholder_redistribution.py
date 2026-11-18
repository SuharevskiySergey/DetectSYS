"""PIE-only observer of the separate Blueprint synchroniser, not a Python driver.

Spawn Redistribution_Demo via the editor tool INSIDE fresh PIE. No stage/state
telemetry is forced here. Faulted actors remain held until PIE is stopped.
"""
import json
import math
from pathlib import Path
import time
import traceback
import uuid
from collections import deque

import unreal

from generate_beholder_telescope import COUNT, STROKE
from lapa5_geometry import claw_vertices_world
from beholder_tick_observation import observe as observe_tick
from beholder_stage_observation import StageObservation
from beholder_native_stage_observation import NativeStageObservation
from validate_beholder_telescope import validate_nested_walls, validate_head, validate as validate_leg
from validate_beholder_housing import validate as validate_housing

REASONS = {'disabled': 1, 'moved': 2, 'goal_changed': 3, 'mode_changed': 3, 'profile_changed': 3,
           'invalid_step_cap': 4, 'game_timeout': 4, 'cancel': 5}
CONTACT_REASONS = {**REASONS, 'surface_lost': 6, 'invalid_probe_settings': 6}
MONITOR_REASONS = {k: v for k, v in CONTACT_REASONS.items() if k not in ('profile_changed', 'invalid_step_cap', 'game_timeout')}
MONITOR_REASONS['lost_before_begin'] = 6


def write_terminal_report(path, report):
    """Archive before updating the rolling report; never overwrite an archive.

    Source-only addition, not yet exercised. Serialization/archive errors must
    propagate rather than replace a previous terminal report with a false pass.
    """
    if report.get('running') is not False:
        raise ValueError('Only completed observer reports may be archived')
    archive = path.with_name(path.stem+'_Archive_'+uuid.uuid4().hex+path.suffix)
    report['terminalArchivePath'] = str(archive)
    text = json.dumps(report, indent=2, allow_nan=False)
    # Exclusive creation guards against collisions as well as later re-runs.
    # Write the archive first: a failed rolling write must not lose the evidence.
    with archive.open('x', encoding='utf-8') as output:
        output.write(text)
    path.write_text(text, encoding='utf-8')


def xyz(v):
    return (v.x, v.y, v.z)


def boolean(value):
    if isinstance(value, tuple):
        assert len(value) == 1
        value = value[0]
    assert type(value) is bool
    return value


def start(fault='none', contact_watch=False, monitor_contacts=False, monitor_fault='none',
          uniform_return=False, return_fault='none', cycles=1, extension=0.5, max_stage_step=1.0, game_timeout=0.0,
          pause_motion='none', pause_seconds=0.5, time_dilation=1.0, inspect_packed_ik=False,
          observer_failure='none', skip_return_observations=0):
    assert type(skip_return_observations) is int and 0 <= skip_return_observations <= 10
    assert not skip_return_observations or (uniform_return and cycles == 1 and fault == 'none'
        and return_fault == 'none' and monitor_fault == 'none' and observer_failure == 'none' and pause_motion == 'none')
    assert observer_failure in ('none', 'return', 'paused', 'native_coverage')
    assert observer_failure == 'none' or (fault == 'none' and return_fault == 'none' and monitor_fault == 'none' and cycles == 1)
    assert observer_failure != 'return' or uniform_return
    assert observer_failure != 'native_coverage' or uniform_return
    assert observer_failure != 'paused' or pause_motion != 'none'
    assert type(inspect_packed_ik) is bool
    assert not inspect_packed_ik or (contact_watch and fault == 'none' and cycles == 1)
    assert type(time_dilation) in (int, float) and math.isfinite(time_dilation) and 0.25 <= time_dilation <= 4
    assert pause_motion in ('none', 'packing', 'return', 'both')
    assert type(pause_seconds) in (int, float) and math.isfinite(pause_seconds) and 0.1 <= pause_seconds <= 10
    assert pause_motion == 'none' or (fault == 'none' and return_fault == 'none' and monitor_fault == 'none')
    assert pause_motion not in ('return', 'both') or uniform_return
    assert type(game_timeout) in (int, float) and math.isfinite(game_timeout)
    assert game_timeout == 0 or 0.01 <= game_timeout <= 600
    assert type(max_stage_step) in (int, float) and math.isfinite(max_stage_step) and 0.001 <= max_stage_step <= 1
    assert type(extension) in (int, float) and math.isfinite(extension) and 0.1 <= extension <= 0.9
    packed = [max(0.0, min(1.0, COUNT*extension-i)) for i in range(COUNT)]
    changed_goal = 0.3 if abs(extension-0.2) < 0.01 else 0.2

    def matches(actual, expected):
        return all(abs(a-b) <= 1e-6 for a, b in zip(actual, expected))
    def native_step_audit():
        return {suffix: actor.get_editor_property('RedistributionNativeStep'+suffix) for suffix in
                ('Samples', 'LastUpdate', 'Direction', 'Last', 'Maximum', 'MaximumExcess', 'Violation', 'Invalid')}
    reasons = CONTACT_REASONS if contact_watch else REASONS
    assert fault in ('none', *reasons)
    assert not monitor_contacts or (contact_watch and fault == 'none')
    assert monitor_fault in ('none', *MONITOR_REASONS)
    assert monitor_contacts or monitor_fault == 'none'
    assert type(cycles) is int and 1 <= cycles <= 3
    assert not uniform_return or (fault == 'none' and monitor_fault == 'none')
    assert return_fault in ('none', *reasons)
    assert uniform_return or (return_fault == 'none' and cycles == 1)
    assert return_fault == 'none' or cycles == 1
    prefix = 'contact_' if contact_watch else ''
    filename = f'BeholderRedistribution_monitor_{monitor_fault}.json' if monitor_contacts else f'BeholderRedistribution_{prefix}{fault}.json'
    if uniform_return:
        origin = 'unloaded' if not contact_watch else 'monitored' if monitor_contacts else 'complete'
        filename = f'BeholderRedistribution_return_{origin}_{return_fault}.json'
    if extension != 0.5:
        filename = filename[:-5]+f'_E{extension:.6f}.json'
    if max_stage_step != 1:
        filename = filename[:-5]+f'_Cap{max_stage_step:.6f}.json'
    if game_timeout != 0:
        filename = filename[:-5]+f'_Game{game_timeout:.6f}.json'
    if pause_motion != 'none':
        filename = filename[:-5]+f'_Pause{pause_motion}.json'
    if time_dilation != 1:
        filename = filename[:-5]+f'_Dilation{time_dilation:.6f}.json'
    if inspect_packed_ik:
        filename = filename[:-5]+'_IK.json'
    if observer_failure != 'none':
        filename = filename[:-5]+f'_ObserverFailure{observer_failure}.json'
    if skip_return_observations:
        filename = filename[:-5]+f'_SkipReturn{skip_return_observations}.json'
    path = Path(unreal.Paths.project_dir())/'Saved'/filename
    report = dict(passed=False, running=True, fault=fault, samples=0, maximumHeadDriftCm=0,
                  maximumClawDriftCm=0, maximumSumError=0, geometryChecks=0,
                  worldDriftExcludedAfterExternalMove=fault == 'moved' or monitor_fault == 'moved' or return_fault == 'moved')
    report['contactWatch'] = contact_watch
    report['requestedExtension'] = extension
    report['maxStageStep'] = max_stage_step
    report['gameTimeout'] = game_timeout
    report.update(pauseMotion=pause_motion, pauseSeconds=pause_seconds, pauses=[])
    report['requestedTimeDilation'] = time_dilation
    report['observerFailureInjection'] = observer_failure
    report['requestedSkippedReturnObservations'] = skip_return_observations
    report['skippedReturnObservations'] = []
    report.update(monitorContacts=monitor_contacts, monitorFault=monitor_fault if monitor_contacts else None)
    report.update(uniformReturn=uniform_return, returnFault=return_fault if uniform_return else None, cyclesRequested=cycles)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    dilation_before = None
    dilation_owned = False
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        assert world
        assert not unreal.GameplayStatics.is_game_paused(world), 'Start in an unpaused fresh PIE'
        dilation_before = unreal.GameplayStatics.get_global_time_dilation(world)
        report['timeDilationBefore'] = dilation_before
        if abs(dilation_before-time_dilation) > 1e-6:
            dilation_owned = True
            unreal.GameplayStatics.set_global_time_dilation(world, time_dilation)
        report['timeDilationDuring'] = unreal.GameplayStatics.get_global_time_dilation(world)
        assert abs(report['timeDilationDuring']-time_dilation) <= 1e-6
        label = 'RedistributionFixture_Demo' if contact_watch else 'Redistribution_Demo'
        actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                     if a.get_actor_label() == label)
        if contact_watch:
            actor = next(c for c in actor.get_components_by_class(unreal.ChildActorComponent)
                         if c.get_name() == 'TestLeg').get_editor_property('child_actor')
        assert actor.get_class().get_name() == 'BP_BeholderStageRedistribution_Test_C'
        assert actor.get_editor_property('RedistributionState') == 0
        assert not actor.get_editor_property('bEnableStageRedistribution')
        assert actor.get_editor_property('RedistributionMaxStageStep') == 1
        assert actor.get_editor_property('RedistributionGameTimeout') == 0
        report['nativeStageAuditAtSetup'] = native_step_audit()
        assert report['nativeStageAuditAtSetup']['Samples'] == 0, 'Start with a fresh native stage audit'
        actor.set_editor_property('RedistributionGameTimeout', game_timeout)
        actor.set_editor_property('RedistributionMaxStageStep', max_stage_step)
        assert not boolean(actor.call_method('BeginRedistributionContactMonitoring', ()))
        assert actor.get_editor_property('RedistributionMonitoringUpdates') == 0
        assert not boolean(actor.call_method('TryExperimentalUniformRedistribution', (1.0,)))
        parts = {c.get_name(): c for c in actor.get_components_by_class(unreal.StaticMeshComponent)}
        sleeves = [parts[f'Sleeve{i:02d}'] for i in range(COUNT)]
        head = next(c for c in actor.get_components_by_class(unreal.ChildActorComponent)
                    if c.get_name() == 'HeadModule').get_editor_property('child_actor')
        actor.call_method('SetMotionMode', (False,))
        actor.call_method('SetMotionDurations', (0.5, 0.5, 0.5))
        actor.call_method('SetLegExtension', (extension,))
    except Exception as exc:
        report['traceback'] = traceback.format_exc()
        if dilation_owned:
            try:
                unreal.GameplayStatics.set_global_time_dilation(world, dilation_before)
                assert abs(unreal.GameplayStatics.get_global_time_dilation(world)-dilation_before) <= 1e-6
                report['timeDilationRestoredOnSetupFailure'] = True
            except Exception as cleanup_exc:
                report['timeDilationRestoreError'] = repr(cleanup_exc)
        report.update(passed=False, running=False, error=repr(exc))
        try:
            write_terminal_report(path, report)
        except Exception as persistence_exc:
            # Keep the actual setup failure as the primary exception rather
            # than replacing it with a secondary report-storage failure.
            raise exc.with_traceback(exc.__traceback__) from persistence_exc
        raise
    state = dict(phase=0, since=time.monotonic(), started=time.monotonic(), stable=0, cycle=1,
                 recent_samples=deque(maxlen=8))

    def finish(error=None):
        if state.get('finishing'):
            raise RuntimeError('Observer finish already started; refusing repeated cleanup/archive')
        state['finishing'] = True
        if error is not None:
            report['failureMonotonicSeconds'] = time.monotonic()
            report['traceback'] = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
            report['recentSamplesAtFailure'] = list(state['recent_samples'])
            try:
                native_state = actor.get_editor_property('RedistributionState')
                if native_state in (1, 4):
                    held_fields = ['RedistributionUpdates', 'RedistributionContactSamples',
                                   'RedistributionMonitoringUpdates', 'ExtensionAmount', 'ExtensionPosition']
                    held_fields += [f'Stage{i}Position' for i in range(COUNT)]
                    before = {n: actor.get_editor_property(n) for n in held_fields}
                    report['failureCleanup'] = dict(stateBefore=native_state, cancelRequested=True,
                                                   heldSnapshot=before)
                    actor.call_method('CancelStageRedistribution', ())
                    after = {n: actor.get_editor_property(n) for n in held_fields}
                    report['failureCleanup'].update(stateAfter=actor.get_editor_property('RedistributionState'),
                        reasonAfter=actor.get_editor_property('RedistributionReason'), snapshotUnchanged=before == after)
                    assert report['failureCleanup']['stateAfter'] == 3
                    assert report['failureCleanup']['reasonAfter'] == 5
                    assert before == after
            except Exception as cleanup_exc:
                report['failureCleanupError'] = repr(cleanup_exc)
                report['failureCleanupTraceback'] = traceback.format_exc()
        if state.get('pause_owned'):
            try:
                assert unreal.GameplayStatics.set_game_paused(world, False)
                state['pause_owned'] = False
                report['pauseRestoredOnFinish'] = True
            except Exception as exc:
                report.setdefault('finishErrors', []).append(dict(
                    phase='restore_pause', error=repr(exc), traceback=traceback.format_exc()))
                error = error or exc
        if error is None and pause_motion != 'none':
            expected = cycles*(2 if pause_motion == 'both' else 1)
            if len(report['pauses']) != expected or not all(p['resumed'] for p in report['pauses']):
                error = AssertionError('Requested active-motion pauses were not all observed and resumed')
        if 'restore_fault' in state:
            try:
                state['restore_fault']()
                report['faultInputRestored'] = True
            except Exception as exc:
                report.setdefault('finishErrors', []).append(dict(
                    phase='restore_fault_input', error=repr(exc), traceback=traceback.format_exc()))
                error = error or exc
        if dilation_owned:
            try:
                unreal.GameplayStatics.set_global_time_dilation(world, dilation_before)
                report['timeDilationAfter'] = unreal.GameplayStatics.get_global_time_dilation(world)
                assert abs(report['timeDilationAfter']-dilation_before) <= 1e-6
                report['timeDilationRestored'] = True
            except Exception as exc:
                report.setdefault('finishErrors', []).append(dict(
                    phase='restore_time_dilation', error=repr(exc), traceback=traceback.format_exc()))
                error = error or exc
        # Attempt detach before serializing so a detach failure is itself part
        # of the terminal evidence, not an exception masking the original fault.
        try:
            unreal.unregister_slate_post_tick_callback(state['handle'])
            report['callbackUnregistered'] = True
        except Exception as exc:
            report['callbackUnregistered'] = False
            report.setdefault('finishErrors', []).append(dict(
                phase='unregister_callback', error=repr(exc), traceback=traceback.format_exc()))
            error = error or exc
        if error is not None and 'traceback' not in report:
            report['traceback'] = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        report.update(passed=error is None, running=False, error=repr(error) if error else None)
        try:
            write_terminal_report(path, report)
        except Exception as persistence_exc:
            if error is not None:
                raise error.with_traceback(error.__traceback__) from persistence_exc
            raise

    def geometry():
        validate_nested_walls(sleeves)
        validate_head(actor, sleeves)
        validate_housing(actor, sleeves)
        report['geometryChecks'] += 1

    def inject_fault(kind):
        if kind == 'disabled':
            actor.set_editor_property('bEnableStageRedistribution', False)
        elif kind == 'moved':
            actor.set_actor_location(actor.get_actor_location()+unreal.Vector(0, 1, 0), False, True)
        elif kind == 'goal_changed':
            actor.call_method('SetLegExtension', (changed_goal,))
        elif kind == 'mode_changed':
            actor.call_method('SetMotionMode', (not actor.get_editor_property('bSequentialMotion'),))
        elif kind == 'profile_changed':
            actor.call_method('SetMotionDurations', (2.0, 2.0, 0.5))
        elif kind == 'invalid_step_cap':
            old = actor.get_editor_property('RedistributionMaxStageStep')
            state['restore_fault'] = lambda: actor.set_editor_property('RedistributionMaxStageStep', old)
            actor.set_editor_property('RedistributionMaxStageStep', -1)
        elif kind == 'surface_lost':
            component = state['surface']
            channel = unreal.CollisionChannel.ECC_VISIBILITY
            old = component.get_collision_response_to_channel(channel)
            state['restore_fault'] = lambda: component.set_collision_response_to_channel(channel, old)
            component.set_collision_response_to_channel(channel, unreal.CollisionResponseType.ECR_IGNORE)
        elif kind == 'invalid_probe_settings':
            old = actor.get_editor_property('ProbeTraceDistance')
            state['restore_fault'] = lambda: actor.set_editor_property('ProbeTraceDistance', old)
            actor.set_editor_property('ProbeTraceDistance', -1)
        else:
            assert kind == 'cancel'
            actor.call_method('CancelStageRedistribution', ())

    def completed_pattern():
        return packed if actor.get_editor_property('RedistributionDirection') == 1 else [extension]*COUNT

    def observe_pause(stages, updates, progress):
        if pause_motion == 'none':
            return False
        label = 'packing' if state['phase'] == 1 else 'return' if state['phase'] == 6 else None
        key = (state['cycle'], label)
        if state.get('pause_owned'):
            pause = report['pauses'][-1]
            assert unreal.GameplayStatics.is_game_paused(world)
            assert actor.get_editor_property('RedistributionState') == 1
            assert stages == state['pause_stages'] and updates == pause['nativeUpdates']
            assert progress == pause['progress']
            assert actor.get_editor_property('RedistributionElapsed') == pause['controllerElapsed']
            assert actor.get_editor_property('RedistributionContactSamples') == pause['contactSamples']
            now = unreal.SystemLibrary.get_game_time_in_seconds(actor)
            assert abs(now-pause['gameTime']) <= 1e-6
            pause['heldSamples'] += 1
            if observer_failure == 'paused' and pause['heldSamples'] >= 3:
                raise RuntimeError('Injected observer failure while paused')
            wall = time.monotonic()-state['pause_wall_start']
            if wall >= pause_seconds and pause['heldSamples'] >= 3:
                assert unreal.GameplayStatics.set_game_paused(world, False)
                state['pause_owned'] = False
                pause.update(wallSeconds=wall, gameSeconds=now-pause['gameTime'], resumed=True)
            return True
        if label is None or pause_motion not in (label, 'both') or key in state.get('pauses_done', set()):
            return False
        if not 0.1 < progress < 0.8 or actor.get_editor_property('RedistributionState') != 1:
            return False
        assert unreal.GameplayStatics.set_game_paused(world, True)
        state.update(pause_owned=True, pause_stages=list(stages), pause_wall_start=time.monotonic())
        state.setdefault('pauses_done', set()).add(key)
        report['pauses'].append(dict(cycle=state['cycle'], motion=label, heldSamples=0, resumed=False,
            nativeUpdates=updates, progress=progress, controllerElapsed=actor.get_editor_property('RedistributionElapsed'),
            contactSamples=actor.get_editor_property('RedistributionContactSamples'),
            gameTime=unreal.SystemLibrary.get_game_time_in_seconds(actor)))
        return True

    def begin_uniform_return():
        origin = actor.get_editor_property('RedistributionState')
        assert origin in (2, 4) and actor.get_editor_property('RedistributionDirection') == 1
        before = [actor.get_editor_property(f'Stage{i}Position') for i in range(COUNT)]
        try:
            for invalid_cap in (0, -1, float('nan'), 1.1):
                actor.set_editor_property('RedistributionMaxStageStep', invalid_cap)
                assert not boolean(actor.call_method('TryExperimentalUniformRedistribution', (1.0,)))
                assert actor.get_editor_property('RedistributionState') == origin
        finally:
            actor.set_editor_property('RedistributionMaxStageStep', max_stage_step)
        report['invalidReturnCapRejected'] = True
        try:
            for invalid_timeout in (-1, 0.001, float('nan'), 601):
                actor.set_editor_property('RedistributionGameTimeout', invalid_timeout)
                assert not boolean(actor.call_method('TryExperimentalUniformRedistribution', (1.0,)))
                assert actor.get_editor_property('RedistributionState') == origin
        finally:
            actor.set_editor_property('RedistributionGameTimeout', game_timeout)
        report['invalidReturnTimeoutRejected'] = True
        for duration in (-1, 0.1, float('nan'), 61):
            assert not boolean(actor.call_method('TryExperimentalUniformRedistribution', (duration,)))
        actor.call_method('SetLegExtension', (changed_goal,))
        assert not boolean(actor.call_method('TryExperimentalUniformRedistribution', (1.0,)))
        actor.call_method('SetLegExtension', (extension,))
        assert before == [actor.get_editor_property(f'Stage{i}Position') for i in range(COUNT)]
        if return_fault == 'game_timeout':
            actor.set_editor_property('RedistributionGameTimeout', 0.3)
            state.update(injected=True, updates_at_fault=0)
        assert boolean(actor.call_method('TryExperimentalUniformRedistribution', (1.0,)))
        assert not boolean(actor.call_method('TryExperimentalUniformRedistribution', (1.0,)))
        assert actor.get_editor_property('RedistributionState') == 1
        assert actor.get_editor_property('RedistributionDirection') == -1
        assert actor.get_editor_property('RedistributionUpdates') == 0
        assert abs(actor.get_editor_property('ExtensionAmount')-extension) <= 1e-6
        if contact_watch:
            assert actor.get_editor_property('bRedistributionContactOwned')
        report['returnRun'] = dict(originState=origin, samples=0, holdSamples=0,
                                  contactSamplesAtStart=actor.get_editor_property('RedistributionContactSamples'))
        report['returnRun']['timing'] = {}
        report['returnRun']['gameStart'] = actor.get_editor_property('RedistributionGameStart')
        assert report['returnRun']['gameStart'] > report['packingGameStart']
        report['returnRun']['gameTimeout'] = actor.get_editor_property('RedistributionGameTimeout')
        state['stage_audit'] = StageObservation(before, [extension]*COUNT, 1.0,
            actor.get_editor_property('ExtensionSeconds'), actor.get_editor_property('RetractionSeconds'))
        report['returnRun']['stageAudit'] = state['stage_audit'].report
        state['native_step_audit'] = NativeStageObservation(native_step_audit(), before, -1, max_stage_step)
        report['returnRun']['nativeStepAudit'] = state['native_step_audit'].report
        state.update(phase=6, since=time.monotonic(), last_progress=0)

    def begin_monitor(label='monitoring'):
        state['monitor_contact_base'] = actor.get_editor_property('RedistributionContactSamples')
        state['active_monitor'] = label
        assert boolean(actor.call_method('BeginRedistributionContactMonitoring', ()))
        assert actor.get_editor_property('RedistributionState') == 4
        assert actor.get_editor_property('RedistributionMonitoringUpdates') == 1
        assert boolean(actor.call_method('BeginRedistributionContactMonitoring', ()))
        assert actor.get_editor_property('RedistributionMonitoringUpdates') == 2
        report[label] = dict(beginChecks=2, healthySamples=0, heldSamples=0,
            contactSamplesBeforeBegin=state['monitor_contact_base'],
            motionElapsed=actor.get_editor_property('RedistributionElapsed'))
        assert not boolean(actor.call_method('TryExperimentalContactRedistribution', (1.0,)))
        state.update(phase=4, since=time.monotonic(), monitor_game_start=unreal.SystemLibrary.get_game_time_in_seconds(actor))

    def reject_stale_begin():
        # Lose the previously validated surface while state 2 is still passive.
        inject_fault('surface_lost')
        assert not boolean(actor.call_method('BeginRedistributionContactMonitoring', ()))
        assert actor.get_editor_property('RedistributionState') == 3
        assert actor.get_editor_property('RedistributionReason') == 6
        count = actor.get_editor_property('RedistributionContactSamples')
        assert count == report['contactSamplesAtComplete']+1
        assert actor.get_editor_property('RedistributionMonitoringUpdates') == 1
        report['monitoring'] = dict(beginChecks=1, healthySamples=0, heldSamples=0, nativeUpdates=0,
            motionElapsed=actor.get_editor_property('RedistributionElapsed'), abortReason=6,
            updatesAtAbort=1, contactSamplesAtAbort=count, staleBeginRejected=True)
        state.update(phase=5, since=time.monotonic(), injected=True)

    def tick(_):
        if state.get('finishing'):
            # If engine detach failed, a retained callback must stay inert. This
            # does not prove it was freed and is not a native motion stop.
            return
        try:
            assert time.monotonic()-state['started'] < 45, 'Redistribution test timed out'
            read_stamp = tuple(actor.get_editor_property(n) for n in
                               ('RedistributionState', 'RedistributionDirection', 'RedistributionUpdates'))
            if (skip_return_observations and state['phase'] == 6 and read_stamp[:2] == (1, -1)
                    and 0.1 < actor.get_editor_property('RedistributionProgress') < 0.8
                    and len(report['skippedReturnObservations']) < skip_return_observations
                    and read_stamp[2] > state.get('last_intentionally_skipped_update', -1)):
                # Drop observer reads only; the native controller keeps ticking.
                report['skippedReturnObservations'].append(dict(nativeUpdates=read_stamp[2]))
                state['last_intentionally_skipped_update'] = read_stamp[2]
                return
            stages = [actor.get_editor_property(f'Stage{i}Position') for i in range(COUNT)]
            if state['phase'] == 0:
                if not matches(stages, [extension]*COUNT):
                    return
                state['stable'] += 1
                if state['stable'] < 3:
                    return
                if contact_watch:
                    actor.call_method('MeasureSurfaceProbe', ())
                    assert actor.get_editor_property('bProbeValid') and actor.get_editor_property('bProbePlaneValid')
                    normal = actor.get_editor_property('ProbePlaneNormal')
                    assert normal.z > 0.99999
                    if 'lowered' not in state:
                        assert actor.get_editor_property('ProbePlaneClearance') > 0.1
                        actor.set_editor_property('bEnableStageRedistribution', True)
                        assert not boolean(actor.call_method('TryExperimentalContactRedistribution', (1.0,)))
                        assert actor.get_editor_property('RedistributionState') == 0
                        actor.set_editor_property('bEnableStageRedistribution', False)
                        report['airborneContactRequestRejected'] = True
                        offset = -actor.get_editor_property('ProbePlaneClearance')/normal.z
                        actor.set_actor_location(actor.get_actor_location()+unreal.Vector(0, 0, offset), False, True)
                        state.update(lowered=True, stable=0, lowered_time=unreal.SystemLibrary.get_game_time_in_seconds(actor))
                        return
                    if unreal.SystemLibrary.get_game_time_in_seconds(actor) <= state['lowered_time']:
                        return
                    assert abs(actor.get_editor_property('ProbePlaneClearance')) <= 0.05
                    q = actor.get_editor_property('ProbePlanePoint')
                    hit = unreal.SystemLibrary.line_trace_single(actor, q+unreal.Vector(0, 0, 2), q-unreal.Vector(0, 0, 2),
                        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, actor.get_editor_property('ProbeIgnoreActors'),
                        unreal.DrawDebugTrace.NONE, True)
                    assert hit and hit.to_tuple()[0] and not hit.to_tuple()[1]
                    surface = hit.to_tuple()[9]
                    state['surface'] = surface.get_component_by_class(unreal.StaticMeshComponent)
                    assert state['surface']
                geometry()
                state['head'] = xyz(head.get_actor_location())
                state['claws'] = [xyz(v) for claw in claw_vertices_world(head) for v in claw]
                assert not boolean(actor.call_method('TryExperimentalStageRedistribution', (1.0,)))
                actor.set_editor_property('bEnableStageRedistribution', True)
                try:
                    for invalid_cap in (0, -1, float('nan'), 1.1):
                        actor.set_editor_property('RedistributionMaxStageStep', invalid_cap)
                        assert not boolean(actor.call_method('TryExperimentalStageRedistribution', (1.0,))), ('invalid_cap', invalid_cap)
                        assert actor.get_editor_property('RedistributionState') == 0
                finally:
                    actor.set_editor_property('RedistributionMaxStageStep', max_stage_step)
                report['invalidPackingCapRejected'] = True
                try:
                    for invalid_timeout in (-1, 0.001, float('nan'), 601):
                        actor.set_editor_property('RedistributionGameTimeout', invalid_timeout)
                        assert not boolean(actor.call_method('TryExperimentalStageRedistribution', (1.0,))), ('invalid_timeout', invalid_timeout)
                        assert actor.get_editor_property('RedistributionState') == 0
                finally:
                    actor.set_editor_property('RedistributionGameTimeout', game_timeout)
                report['invalidPackingTimeoutRejected'] = True
                for duration in (-1, 0, float('nan'), 0.1, 61):
                    assert not boolean(actor.call_method('TryExperimentalStageRedistribution', (duration,)))
                actor.call_method('SetJointBend', (1, 0.2, 0.0))
                assert not boolean(actor.call_method('TryExperimentalStageRedistribution', (1.0,)))
                actor.call_method('SetJointBend', (1, 0.0, 0.0))
                actor.call_method('ClearJointBend', (1,))
                actor.call_method('SetHeadOpening', (0.2,))
                assert not boolean(actor.call_method('TryExperimentalStageRedistribution', (1.0,)))
                actor.call_method('SetHeadOpening', (0.0,))
                actor.call_method('SetMotionMode', (True,))
                assert not boolean(actor.call_method('TryExperimentalStageRedistribution', (1.0,)))
                actor.call_method('SetMotionMode', (False,))
                actor.call_method('SetLegExtension', (changed_goal,))
                assert not boolean(actor.call_method('TryExperimentalStageRedistribution', (1.0,)))
                actor.call_method('SetLegExtension', (extension,))
                assert stages == [actor.get_editor_property(f'Stage{i}Position') for i in range(COUNT)]
                report['preflightRejections'] = ['disabled', 'five_bad_durations', 'pending_joint', 'pending_claw', 'wrong_mode', 'moving_goal']
                request_name = 'TryExperimentalContactRedistribution' if contact_watch else 'TryExperimentalStageRedistribution'
                if contact_watch:
                    old = actor.get_editor_property('ProbeTraceDistance')
                    try:
                        actor.set_editor_property('ProbeTraceDistance', -1)
                        assert not boolean(actor.call_method(request_name, (1.0,)))
                        assert not actor.get_editor_property('bProbeValid')
                        assert actor.get_editor_property('RedistributionState') == 0
                    finally:
                        actor.set_editor_property('ProbeTraceDistance', old)
                    report['invalidSnapshotPreflightRejected'] = True
                if fault == 'game_timeout':
                    actor.set_editor_property('RedistributionGameTimeout', 0.3)
                    state.update(injected=True, updates_at_fault=0)
                assert boolean(actor.call_method(request_name, (1.0,)))
                assert not boolean(actor.call_method(request_name, (1.0,)))
                assert actor.get_editor_property('RedistributionState') == 1
                assert actor.get_editor_property('RedistributionUpdates') == 0
                assert not boolean(actor.call_method('TryExperimentalUniformRedistribution', (1.0,)))
                assert not boolean(actor.call_method('BeginRedistributionContactMonitoring', ()))
                if contact_watch:
                    state['contact_samples_start'] = actor.get_editor_property('RedistributionContactSamples')
                    state['anchor'] = xyz(actor.get_editor_property('ProbePlanePoint'))
                    report['contactSamplesAtStart'] = state['contact_samples_start']
                state.update(phase=1, since=time.monotonic(), last_progress=0)
                report['packingTiming'] = {}
                report['packingGameStart'] = actor.get_editor_property('RedistributionGameStart')
                state['stage_audit'] = StageObservation(stages, packed, 1.0,
                    actor.get_editor_property('ExtensionSeconds'), actor.get_editor_property('RetractionSeconds'))
                report['packingStageAudit'] = state['stage_audit'].report
                state['native_step_audit'] = NativeStageObservation(native_step_audit(), stages, 1, max_stage_step)
                report['packingNativeStepAudit'] = state['native_step_audit'].report
                return
            report['samples'] += 1
            phase = actor.get_editor_property('RedistributionState')
            progress = actor.get_editor_property('RedistributionProgress')
            updates = actor.get_editor_property('RedistributionUpdates')
            relative_positions = [xyz(s.get_relative_transform().translation) for s in sleeves]
            direction = actor.get_editor_property('RedistributionDirection')
            blend = (1-direction)/2+direction*progress
            expected_stages = [extension+(p-extension)*blend for p in packed]
            sample = dict(observerPhase=state['phase'], nativeState=phase, direction=direction,
                          updates=updates, progress=progress, previousProgress=state.get('last_progress'),
                          elapsed=actor.get_editor_property('RedistributionElapsed'), stages=list(stages),
                          expectedStages=expected_stages, relativePositions=relative_positions,
                          stageErrors=[abs(s-e) for s, e in zip(stages, expected_stages)],
                           meshErrorsCm=[math.dist(p, (STROKE*s, 0, 0)) for p, s in zip(relative_positions, stages)])
            sample['nativeStageAudit'] = native_step_audit()
            report['nativeStageAuditLatest'] = sample['nativeStageAudit']
            sample['readStampBefore'] = read_stamp
            sample['readStampAfter'] = tuple(actor.get_editor_property(n) for n in
                ('RedistributionState', 'RedistributionDirection', 'RedistributionUpdates'))
            state['recent_samples'].append(sample)
            assert sample['readStampBefore'] == sample['readStampAfter'], 'mixed_native_snapshot'
            if state['phase'] in (1, 6):
                timing = report['packingTiming'] if state['phase'] == 1 else report['returnRun']['timing']
                sample['nativeUpdatesSincePreviousObservation'] = updates-timing.get('nativeUpdates', 0)
                sample['stageDisplacementSincePreviousObservation'] = max(abs(a-b) for a,b in
                    zip(stages, state['stage_audit'].previous))
                sample['singleNativeUpdateStepCap'] = max_stage_step
                sample['singleUpdateCapObservable'] = sample['nativeUpdatesSincePreviousObservation'] <= 1
                observe_tick(timing, updates, actor.get_editor_property('RedistributionElapsed'))
                state['stage_audit'].observe(stages, actor.get_editor_property('RedistributionElapsed'))
                if phase in (1, 2):
                    audit_input = sample['nativeStageAudit']
                    if observer_failure == 'native_coverage' and state['phase'] == 6 and phase == 1 and updates >= 3:
                        # Corrupt a COPY of the read evidence, never native data.
                        audit_input = dict(audit_input)
                        audit_input['Samples'] -= 1
                        sample['injectedNativeAuditInput'] = audit_input
                    state['native_step_audit'].observe(audit_input, stages, updates)
                # Aborted-before-apply updates have no native stage record;
                # never claim cap coverage for them or bypass fault/hold checks.
            if observe_pause(stages, updates, progress):
                return
            if not monitor_contacts:
                assert actor.get_editor_property('RedistributionMonitoringUpdates') == 0
            if not contact_watch:
                assert actor.get_editor_property('RedistributionContactSamples') == 0
            elif 'anchor' in state and actor.get_editor_property('bProbeValid') and actor.get_editor_property('bProbePlaneValid'):
                drift = math.dist(xyz(actor.get_editor_property('ProbePlanePoint')), state['anchor'])
                report['maximumMeasuredContactDriftCm'] = max(report.get('maximumMeasuredContactDriftCm', 0), drift)
            assert progress >= state['last_progress'], 'progress_monotonic'
            state['last_progress'] = progress
            assert all(-1e-6 <= s <= 1.000001 for s in stages)
            total_error = abs(math.fsum(stages)-COUNT*extension)
            report['maximumSumError'] = max(report['maximumSumError'], total_error)
            assert total_error < 1e-5, ('stage_sum', total_error)
            for i, stage in enumerate(stages):
                direction = actor.get_editor_property('RedistributionDirection')
                blend = (1-direction)/2+direction*progress
                expected = extension+(packed[i]-extension)*blend
                assert abs(stage-expected) < 1e-6, ('stage_pattern', i, stage, expected)
                assert sample['meshErrorsCm'][i] < 1e-4, ('stage_mesh_transform', i, sample['meshErrorsCm'][i])
            assert all(abs(actor.get_editor_property(f'Joint{i}Magnitude')) < 1e-6 for i in range(1, COUNT))
            if not (fault == 'moved' or monitor_fault == 'moved' or return_fault == 'moved') or 'injected' not in state:
                head_drift = math.dist(xyz(head.get_actor_location()), state['head'])
                claw_drift = max(math.dist(xyz(v), p) for v, p in zip(
                    [v for claw in claw_vertices_world(head) for v in claw], state['claws']))
                report['maximumHeadDriftCm'] = max(report['maximumHeadDriftCm'], head_drift)
                report['maximumClawDriftCm'] = max(report['maximumClawDriftCm'], claw_drift)
                assert max(head_drift, claw_drift) < 0.01, ('head_or_claw_drift', head_drift, claw_drift)
            if observer_failure == 'return' and state['phase'] == 6 and phase == 1 and 0.1 < progress < 0.8:
                raise RuntimeError('Injected observer failure during return')
            if state['phase'] in (6, 7):
                ret = report['returnRun']
                ret['samples'] += 1
                assert actor.get_editor_property('RedistributionDirection') == -1
                if phase == 3:
                    assert return_fault != 'none' and 'injected' in state
                    assert actor.get_editor_property('RedistributionReason') == reasons[return_fault]
                    assert not boolean(actor.call_method('TryExperimentalUniformRedistribution', (1.0,)))
                    assert not boolean(actor.call_method('ReleaseStageRedistribution', ()))
                    if 'updatesAtAbort' not in ret:
                        assert 0 < progress < 1
                        if return_fault != 'cancel':
                            assert updates > state['updates_at_fault']
                        ret.update(updatesAtAbort=updates, progressAtAbort=progress, abortReason=reasons[return_fault],
                                   heldStages=stages, contactSamplesAtAbort=actor.get_editor_property('RedistributionContactSamples'))
                        if return_fault == 'game_timeout':
                            game_elapsed = unreal.SystemLibrary.get_game_time_in_seconds(actor)-actor.get_editor_property('RedistributionGameStart')
                            ret['gameElapsedAtAbort'] = game_elapsed
                            ret['observedWallSecondsAtAbort'] = time.monotonic()-state['since']
                            assert game_elapsed > actor.get_editor_property('RedistributionGameTimeout')
                            assert actor.get_editor_property('RedistributionElapsed') < 0.3
                        state['since'] = time.monotonic()
                    assert updates == ret['updatesAtAbort'] and stages == ret['heldStages']
                    assert actor.get_editor_property('RedistributionContactSamples') == ret['contactSamplesAtAbort']
                    ret['holdSamples'] += 1
                    if ret['holdSamples'] >= 3 and time.monotonic()-state['since'] >= 0.25:
                        geometry()
                        finish()
                    return
                assert phase in (1, 2)
                if phase == 2:
                    assert return_fault == 'none'
                    assert matches(stages, [extension]*COUNT) and progress == 1 and not actor.get_editor_property('bSequentialMotion')
                    assert not boolean(actor.call_method('TryExperimentalUniformRedistribution', (1.0,)))
                    if 'nativeUpdates' not in ret:
                        assert updates >= 2
                        geometry()
                        ret.update(nativeUpdates=updates, observedWallSeconds=time.monotonic()-state['since'],
                                   finalStages=list(stages), elapsed=actor.get_editor_property('RedistributionElapsed'),
                                   contactSamplesAtComplete=actor.get_editor_property('RedistributionContactSamples'))
                        ret['gameElapsedAtComplete'] = unreal.SystemLibrary.get_game_time_in_seconds(actor)-actor.get_editor_property('RedistributionGameStart')
                        if contact_watch:
                            assert ret['contactSamplesAtComplete'] == ret['contactSamplesAtStart']+2*updates
                        state.update(phase=7, since=time.monotonic(), completed_updates=updates)
                    assert updates == ret['nativeUpdates']
                    assert actor.get_editor_property('RedistributionContactSamples') == ret['contactSamplesAtComplete']
                    ret['holdSamples'] += 1
                    if ret['holdSamples'] >= 3 and time.monotonic()-state['since'] >= 0.25:
                        if monitor_contacts:
                            begin_monitor('uniformMonitoring')
                        else:
                            assert boolean(actor.call_method('ReleaseStageRedistribution', ()))
                            state.update(phase=2, since=time.monotonic(), stable=0)
                    return
                if return_fault != 'none' and 'injected' not in state and 0.1 < progress < 0.8:
                    state.update(injected=True, updates_at_fault=updates)
                    inject_fault(return_fault)
                return
            if state['phase'] in (4, 5):
                monitor = report[state.get('active_monitor', 'monitoring')]
                monitor_updates = actor.get_editor_property('RedistributionMonitoringUpdates')
                contact_samples = actor.get_editor_property('RedistributionContactSamples')
                assert updates == state['completed_updates'] and progress == 1
                assert matches(stages, completed_pattern())
                assert actor.get_editor_property('RedistributionElapsed') == monitor['motionElapsed']
                if phase == 3:
                    assert monitor_fault != 'none' and 'injected' in state
                    assert actor.get_editor_property('RedistributionReason') == MONITOR_REASONS[monitor_fault]
                    assert not boolean(actor.call_method('BeginRedistributionContactMonitoring', ()))
                    assert not boolean(actor.call_method('ReleaseStageRedistribution', ()))
                    if state['phase'] == 4:
                        if monitor_fault != 'cancel':
                            assert monitor_updates > state['monitor_updates_at_fault']
                        monitor.update(abortReason=MONITOR_REASONS[monitor_fault], updatesAtAbort=monitor_updates,
                                       contactSamplesAtAbort=contact_samples)
                        state.update(phase=5, since=time.monotonic())
                    assert monitor_updates == monitor['updatesAtAbort'] and contact_samples == monitor['contactSamplesAtAbort']
                    monitor['heldSamples'] += 1
                    if monitor['heldSamples'] >= 3 and time.monotonic()-state['since'] >= 0.25:
                        geometry()
                        finish()
                    return
                assert phase == 4
                assert contact_samples == state['monitor_contact_base']+monitor_updates
                monitor['healthySamples'] += 1
                game_elapsed = unreal.SystemLibrary.get_game_time_in_seconds(actor)-state['monitor_game_start']
                if monitor_updates >= 5 and game_elapsed >= 1.25:
                    monitor.update(nativeUpdates=monitor_updates-2, healthyGameSeconds=game_elapsed)
                    if monitor_fault == 'none':
                        if uniform_return and actor.get_editor_property('RedistributionDirection') == 1:
                            begin_uniform_return()
                            return
                        assert boolean(actor.call_method('ReleaseStageRedistribution', ()))
                        assert not actor.get_editor_property('bRedistributionContactOwned')
                        monitor['updatesAtRelease'] = monitor_updates
                        state.update(phase=2, since=time.monotonic(), stable=0)
                    elif 'injected' not in state:
                        state.update(injected=True, monitor_updates_at_fault=monitor_updates)
                        inject_fault(monitor_fault)
                return
            if phase == 3:
                assert fault != 'none' and 'injected' in state
                assert actor.get_editor_property('RedistributionReason') == reasons[fault]
                assert not boolean(actor.call_method('ReleaseStageRedistribution', ()))
                if 'held' not in state:
                    assert 0 < progress < 1
                    if fault != 'cancel':
                        assert updates > state['updates_at_fault']
                    motion_wall_seconds = time.monotonic()-state['since']
                    state.update(held=stages, held_updates=updates, hold_samples=0, since=time.monotonic())
                    report.update(abortReason=reasons[fault], progressAtAbort=progress, nativeUpdates=updates)
                    if fault == 'game_timeout':
                        game_elapsed = unreal.SystemLibrary.get_game_time_in_seconds(actor)-actor.get_editor_property('RedistributionGameStart')
                        report.update(gameElapsedAtAbort=game_elapsed,
                                      observedWallSecondsAtAbort=motion_wall_seconds,
                                      controllerElapsedAtAbort=actor.get_editor_property('RedistributionElapsed'))
                        assert game_elapsed > actor.get_editor_property('RedistributionGameTimeout')
                        assert actor.get_editor_property('RedistributionElapsed') < 0.3
                    if contact_watch:
                        report['contactSamplesAtAbort'] = actor.get_editor_property('RedistributionContactSamples')
                        if fault in ('surface_lost', 'invalid_probe_settings'):
                            assert not actor.get_editor_property('bProbeValid') or not actor.get_editor_property('bProbeHit')
                assert stages == state['held'] and updates == state['held_updates']
                if contact_watch:
                    assert actor.get_editor_property('RedistributionContactSamples') == report['contactSamplesAtAbort']
                state['hold_samples'] += 1
                if state['hold_samples'] >= 3 and time.monotonic()-state['since'] >= 0.25:
                    geometry()
                    report['holdSamples'] = state['hold_samples']
                    finish()
                return
            if state['phase'] == 3:
                assert phase == 2 and updates == state['completed_updates']
                assert matches(stages, packed)
                if contact_watch:
                    assert actor.get_editor_property('RedistributionContactSamples') == report['contactSamplesAtComplete']
                state['hold_samples'] += 1
                if state['hold_samples'] >= 3 and time.monotonic()-state['since'] >= 0.25:
                    report['completeHoldSamples'] = state['hold_samples']
                    if monitor_contacts:
                        if monitor_fault == 'lost_before_begin':
                            reject_stale_begin()
                        else:
                            begin_monitor()
                        return
                    if uniform_return:
                        begin_uniform_return()
                        return
                    if not contact_watch:
                        assert not boolean(actor.call_method('BeginRedistributionContactMonitoring', ()))
                    assert boolean(actor.call_method('ReleaseStageRedistribution', ()))
                    if contact_watch:
                        assert not actor.get_editor_property('bRedistributionContactOwned')
                    state.update(phase=2, since=time.monotonic(), stable=0)
                return
            if state['phase'] == 2:
                assert phase == 0 and updates == state['completed_updates']
                assert matches(stages, completed_pattern())
                assert not boolean(actor.call_method('BeginRedistributionContactMonitoring', ()))
                if monitor_contacts:
                    monitor = report[state['active_monitor']]
                    assert actor.get_editor_property('RedistributionMonitoringUpdates') == monitor['updatesAtRelease']
                    assert actor.get_editor_property('RedistributionContactSamples') == state['monitor_contact_base']+monitor['updatesAtRelease']
                state['stable'] += 1
                if state['stable'] >= 3 and time.monotonic()-state['since'] >= 0.25:
                    geometry()
                    validate_leg(actor)
                    report['parentControllerValidated'] = True
                    if uniform_return:
                        report.setdefault('cycleResults', []).append(dict(cycle=state['cycle'],
                            packingNativeUpdates=report['nativeUpdates'], packingTiming=report['packingTiming'],
                            packingGameStart=report['packingGameStart'],
                            packingGameElapsedSeconds=report['gameElapsedAtComplete'], packingObservedWallSeconds=report['observedWallSeconds'],
                             packingStageAudit=report['packingStageAudit'], packingNativeStepAudit=report['packingNativeStepAudit'],
                             packedMonitoring=report.get('monitoring'),
                            uniformReturn=report['returnRun'], uniformMonitoring=report.get('uniformMonitoring')))
                        report['cyclesCompleted'] = state['cycle']
                        if state['cycle'] < cycles:
                            request_name = 'TryExperimentalContactRedistribution' if contact_watch else 'TryExperimentalStageRedistribution'
                            assert boolean(actor.call_method(request_name, (1.0,)))
                            assert actor.get_editor_property('RedistributionDirection') == 1
                            if contact_watch:
                                state['contact_samples_start'] = actor.get_editor_property('RedistributionContactSamples')
                                state['anchor'] = xyz(actor.get_editor_property('ProbePlanePoint'))
                            state.update(phase=1, since=time.monotonic(), last_progress=0, cycle=state['cycle']+1)
                            report['packingTiming'] = {}
                            report['packingGameStart'] = actor.get_editor_property('RedistributionGameStart')
                            assert report['packingGameStart'] > report['returnRun']['gameStart']
                            state['stage_audit'] = StageObservation(stages, packed, 1.0,
                                actor.get_editor_property('ExtensionSeconds'), actor.get_editor_property('RetractionSeconds'))
                            report['packingStageAudit'] = state['stage_audit'].report
                            state['native_step_audit'] = NativeStageObservation(native_step_audit(), stages, 1, max_stage_step)
                            report['packingNativeStepAudit'] = state['native_step_audit'].report
                            return
                    finish()
                return
            assert phase in (1, 2)
            if phase == 2:
                assert fault == 'none'
                assert progress == 1 and matches(stages, packed) and updates >= 2
                assert actor.get_editor_property('bSequentialMotion')
                geometry()
                if inspect_packed_ik:
                    from exercise_beholder_redistribution_ik import run as inspect_ik
                    report['packedIK'] = inspect_ik(actor)
                report.update(nativeUpdates=updates, observedWallSeconds=time.monotonic()-state['since'],
                              elapsed=actor.get_editor_property('RedistributionElapsed'))
                report['gameElapsedAtComplete'] = unreal.SystemLibrary.get_game_time_in_seconds(actor)-actor.get_editor_property('RedistributionGameStart')
                if contact_watch:
                    count = actor.get_editor_property('RedistributionContactSamples')
                    assert count == state['contact_samples_start']+2*updates
                    assert math.dist(xyz(actor.get_editor_property('ProbePlanePoint')), state['anchor']) <= 0.01
                    report['contactSamplesAtComplete'] = count
                assert not boolean(actor.call_method('TryExperimentalStageRedistribution', (1.0,)))
                state.update(phase=3, since=time.monotonic(), hold_samples=0, completed_updates=updates)
                return
            if fault != 'none' and 'injected' not in state and 0.1 < progress < 0.8:
                state.update(injected=True, updates_at_fault=updates)
                inject_fault(fault)
        except Exception as exc:
            if state.get('finishing'):
                # A terminal write/unregister failure is not a fresh observer
                # failure: repeating finish would repeat native cleanup too.
                raise
            finish(exc)

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    print('Redistribution native-Tick observation started: '+str(path))
