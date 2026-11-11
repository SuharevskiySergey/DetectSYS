"""PIE-only observer of the separate Blueprint synchroniser, not a Python driver.

Spawn Redistribution_Demo via the editor tool INSIDE fresh PIE. No stage/state
telemetry is forced here. Faulted actors remain held until PIE is stopped.
"""
import json
import math
from pathlib import Path
import time

import unreal

from generate_beholder_telescope import COUNT, STROKE
from lapa5_geometry import claw_vertices_world
from validate_beholder_telescope import validate_nested_walls, validate_head, validate as validate_leg
from validate_beholder_housing import validate as validate_housing

REASONS = {'disabled': 1, 'moved': 2, 'goal_changed': 3, 'mode_changed': 3, 'profile_changed': 3, 'cancel': 5}
CONTACT_REASONS = {**REASONS, 'surface_lost': 6, 'invalid_probe_settings': 6}


def xyz(v):
    return (v.x, v.y, v.z)


def boolean(value):
    if isinstance(value, tuple):
        assert len(value) == 1
        value = value[0]
    assert type(value) is bool
    return value


def start(fault='none', contact_watch=False):
    reasons = CONTACT_REASONS if contact_watch else REASONS
    assert fault in ('none', *reasons)
    prefix = 'contact_' if contact_watch else ''
    path = Path(unreal.Paths.project_dir())/f'Saved/BeholderRedistribution_{prefix}{fault}.json'
    report = dict(passed=False, running=True, fault=fault, samples=0, maximumHeadDriftCm=0,
                  maximumClawDriftCm=0, maximumSumError=0, geometryChecks=0,
                  worldDriftExcludedAfterExternalMove=fault == 'moved')
    report['contactWatch'] = contact_watch
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        assert world
        label = 'RedistributionFixture_Demo' if contact_watch else 'Redistribution_Demo'
        actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                     if a.get_actor_label() == label)
        if contact_watch:
            actor = next(c for c in actor.get_components_by_class(unreal.ChildActorComponent)
                         if c.get_name() == 'TestLeg').get_editor_property('child_actor')
        assert actor.get_class().get_name() == 'BP_BeholderStageRedistribution_Test_C'
        assert actor.get_editor_property('RedistributionState') == 0
        assert not actor.get_editor_property('bEnableStageRedistribution')
        parts = {c.get_name(): c for c in actor.get_components_by_class(unreal.StaticMeshComponent)}
        sleeves = [parts[f'Sleeve{i:02d}'] for i in range(COUNT)]
        head = next(c for c in actor.get_components_by_class(unreal.ChildActorComponent)
                    if c.get_name() == 'HeadModule').get_editor_property('child_actor')
        actor.call_method('SetMotionMode', (False,))
        actor.call_method('SetMotionDurations', (0.5, 0.5, 0.5))
        actor.call_method('SetLegExtension', (0.5,))
    except Exception as exc:
        report.update(passed=False, running=False, error=repr(exc))
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        raise
    state = dict(phase=0, since=time.monotonic(), started=time.monotonic(), stable=0)

    def finish(error=None):
        if 'restore_fault' in state:
            try:
                state['restore_fault']()
                report['faultInputRestored'] = True
            except Exception as exc:
                error = error or exc
        report.update(passed=error is None, running=False, error=repr(error) if error else None)
        path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        unreal.unregister_slate_post_tick_callback(state['handle'])

    def geometry():
        validate_nested_walls(sleeves)
        validate_head(actor, sleeves)
        validate_housing(actor, sleeves)
        report['geometryChecks'] += 1

    def tick(_):
        try:
            assert time.monotonic()-state['started'] < 45, 'Redistribution test timed out'
            stages = [actor.get_editor_property(f'Stage{i}Position') for i in range(COUNT)]
            if state['phase'] == 0:
                if not all(abs(s-0.5) < 1e-6 for s in stages):
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
                actor.call_method('SetLegExtension', (0.2,))
                assert not boolean(actor.call_method('TryExperimentalStageRedistribution', (1.0,)))
                actor.call_method('SetLegExtension', (0.5,))
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
                assert boolean(actor.call_method(request_name, (1.0,)))
                assert not boolean(actor.call_method(request_name, (1.0,)))
                assert actor.get_editor_property('RedistributionState') == 1
                assert actor.get_editor_property('RedistributionUpdates') == 0
                if contact_watch:
                    state['contact_samples_start'] = actor.get_editor_property('RedistributionContactSamples')
                    state['anchor'] = xyz(actor.get_editor_property('ProbePlanePoint'))
                    report['contactSamplesAtStart'] = state['contact_samples_start']
                state.update(phase=1, since=time.monotonic(), last_progress=0)
                return
            report['samples'] += 1
            phase = actor.get_editor_property('RedistributionState')
            progress = actor.get_editor_property('RedistributionProgress')
            updates = actor.get_editor_property('RedistributionUpdates')
            if not contact_watch:
                assert actor.get_editor_property('RedistributionContactSamples') == 0
            elif 'anchor' in state and actor.get_editor_property('bProbeValid') and actor.get_editor_property('bProbePlaneValid'):
                drift = math.dist(xyz(actor.get_editor_property('ProbePlanePoint')), state['anchor'])
                report['maximumMeasuredContactDriftCm'] = max(report.get('maximumMeasuredContactDriftCm', 0), drift)
            assert progress >= state['last_progress']
            state['last_progress'] = progress
            assert all(-1e-6 <= s <= 1.000001 for s in stages)
            total_error = abs(math.fsum(stages)-5)
            report['maximumSumError'] = max(report['maximumSumError'], total_error)
            assert total_error < 1e-5
            for i, stage in enumerate(stages):
                expected = 0.5+((1 if i < 5 else 0)-0.5)*progress
                assert abs(stage-expected) < 1e-6
                assert math.dist(xyz(sleeves[i].get_relative_transform().translation), (STROKE*stage, 0, 0)) < 1e-4
            assert all(abs(actor.get_editor_property(f'Joint{i}Magnitude')) < 1e-6 for i in range(1, COUNT))
            if fault != 'moved' or 'injected' not in state:
                head_drift = math.dist(xyz(head.get_actor_location()), state['head'])
                claw_drift = max(math.dist(xyz(v), p) for v, p in zip(
                    [v for claw in claw_vertices_world(head) for v in claw], state['claws']))
                report['maximumHeadDriftCm'] = max(report['maximumHeadDriftCm'], head_drift)
                report['maximumClawDriftCm'] = max(report['maximumClawDriftCm'], claw_drift)
                assert max(head_drift, claw_drift) < 0.01
            if phase == 3:
                assert fault != 'none' and 'injected' in state
                assert actor.get_editor_property('RedistributionReason') == reasons[fault]
                assert not boolean(actor.call_method('ReleaseStageRedistribution', ()))
                if 'held' not in state:
                    assert 0 < progress < 1
                    if fault != 'cancel':
                        assert updates > state['updates_at_fault']
                    state.update(held=stages, held_updates=updates, hold_samples=0, since=time.monotonic())
                    report.update(abortReason=reasons[fault], progressAtAbort=progress, nativeUpdates=updates)
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
                assert stages == [1]*5+[0]*5
                if contact_watch:
                    assert actor.get_editor_property('RedistributionContactSamples') == report['contactSamplesAtComplete']
                state['hold_samples'] += 1
                if state['hold_samples'] >= 3 and time.monotonic()-state['since'] >= 0.25:
                    report['completeHoldSamples'] = state['hold_samples']
                    assert boolean(actor.call_method('ReleaseStageRedistribution', ()))
                    if contact_watch:
                        assert not actor.get_editor_property('bRedistributionContactOwned')
                    state.update(phase=2, since=time.monotonic(), stable=0)
                return
            if state['phase'] == 2:
                assert phase == 0 and updates == state['completed_updates']
                assert stages == [1]*5+[0]*5
                state['stable'] += 1
                if state['stable'] >= 3 and time.monotonic()-state['since'] >= 0.25:
                    geometry()
                    validate_leg(actor)
                    report['parentControllerValidated'] = True
                    finish()
                return
            assert phase in (1, 2)
            if phase == 2:
                assert fault == 'none'
                assert progress == 1 and stages == [1]*5+[0]*5 and updates >= 2
                assert actor.get_editor_property('bSequentialMotion')
                geometry()
                report.update(nativeUpdates=updates, elapsed=actor.get_editor_property('RedistributionElapsed'))
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
                if fault == 'disabled':
                    actor.set_editor_property('bEnableStageRedistribution', False)
                elif fault == 'moved':
                    actor.set_actor_location(actor.get_actor_location()+unreal.Vector(0, 1, 0), False, True)
                elif fault == 'goal_changed':
                    actor.call_method('SetLegExtension', (0.2,))
                elif fault == 'mode_changed':
                    actor.call_method('SetMotionMode', (True,))
                elif fault == 'profile_changed':
                    actor.call_method('SetMotionDurations', (2.0, 2.0, 0.5))
                elif fault == 'surface_lost':
                    component = state['surface']
                    channel = unreal.CollisionChannel.ECC_VISIBILITY
                    old = component.get_collision_response_to_channel(channel)
                    state['restore_fault'] = lambda: component.set_collision_response_to_channel(channel, old)
                    component.set_collision_response_to_channel(channel, unreal.CollisionResponseType.ECR_IGNORE)
                elif fault == 'invalid_probe_settings':
                    old = actor.get_editor_property('ProbeTraceDistance')
                    state['restore_fault'] = lambda: actor.set_editor_property('ProbeTraceDistance', old)
                    actor.set_editor_property('ProbeTraceDistance', -1)
                else:
                    actor.call_method('CancelStageRedistribution', ())
        except Exception as exc:
            finish(exc)

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    print('Redistribution native-Tick observation started: '+str(path))
