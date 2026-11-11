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


def xyz(v):
    return (v.x, v.y, v.z)


def boolean(value):
    if isinstance(value, tuple):
        assert len(value) == 1
        value = value[0]
    assert type(value) is bool
    return value


def start(fault='none'):
    assert fault in ('none', *REASONS)
    path = Path(unreal.Paths.project_dir())/f'Saved/BeholderRedistribution_{fault}.json'
    report = dict(passed=False, running=True, fault=fault, samples=0, maximumHeadDriftCm=0,
                  maximumClawDriftCm=0, maximumSumError=0, geometryChecks=0,
                  worldDriftExcludedAfterExternalMove=fault == 'moved')
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        assert world
        actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                     if a.get_actor_label() == 'Redistribution_Demo')
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
                assert boolean(actor.call_method('TryExperimentalStageRedistribution', (1.0,)))
                assert not boolean(actor.call_method('TryExperimentalStageRedistribution', (1.0,)))
                assert actor.get_editor_property('RedistributionState') == 1
                assert actor.get_editor_property('RedistributionUpdates') == 0
                state.update(phase=1, since=time.monotonic(), last_progress=0)
                return
            report['samples'] += 1
            phase = actor.get_editor_property('RedistributionState')
            progress = actor.get_editor_property('RedistributionProgress')
            updates = actor.get_editor_property('RedistributionUpdates')
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
                assert actor.get_editor_property('RedistributionReason') == REASONS[fault]
                assert not boolean(actor.call_method('ReleaseStageRedistribution', ()))
                if 'held' not in state:
                    assert 0 < progress < 1
                    if fault != 'cancel':
                        assert updates > state['updates_at_fault']
                    state.update(held=stages, held_updates=updates, hold_samples=0, since=time.monotonic())
                    report.update(abortReason=REASONS[fault], progressAtAbort=progress, nativeUpdates=updates)
                assert stages == state['held'] and updates == state['held_updates']
                state['hold_samples'] += 1
                if state['hold_samples'] >= 3 and time.monotonic()-state['since'] >= 0.25:
                    geometry()
                    report['holdSamples'] = state['hold_samples']
                    finish()
                return
            if state['phase'] == 3:
                assert phase == 2 and updates == state['completed_updates']
                assert stages == [1]*5+[0]*5
                state['hold_samples'] += 1
                if state['hold_samples'] >= 3 and time.monotonic()-state['since'] >= 0.25:
                    report['completeHoldSamples'] = state['hold_samples']
                    assert boolean(actor.call_method('ReleaseStageRedistribution', ()))
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
                else:
                    actor.call_method('CancelStageRedistribution', ())
        except Exception as exc:
            finish(exc)

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    print('Redistribution native-Tick observation started: '+str(path))
