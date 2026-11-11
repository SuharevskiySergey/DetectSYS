"""PIE-only asynchronous regression. Commands affect only the playing copy.

Run in editor Python with PIE active and auto demo disabled at extension 1.
Results are written to Saved/BeholderSocketSafety.json; no asset writes.
"""
import json
import importlib
from pathlib import Path
import sys
import time

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
import validate_beholder_housing
importlib.reload(validate_beholder_housing)
from validate_beholder_housing import validate
from beholder_stage_timing import step as stage_step


def start():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world, 'Start PIE first'
    actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                 if a.get_actor_label() == 'BeholderTelescopic_Demo')
    head = next(c for c in actor.get_components_by_class(unreal.ChildActorComponent)
                if c.get_name() == 'HeadModule').get_editor_property('child_actor')
    result = {'passed': False, 'samples': 0, 'movingSamples': 0, 'waitingSamples': 0,
              'housingChecks': 0, 'maximumStageTimingError': 0.0, 'phases': [], 'error': None}
    path = Path(unreal.Paths.project_dir()) / 'Saved/BeholderSocketSafety.json'
    state = {'phase': 0, 'since': time.monotonic(), 'last': None, 'handle': None}

    def command(name, *args):
        actor.call_method(name, args)

    def finish(error=None):
        result['error'] = error
        result['passed'] = error is None
        path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        unreal.unregister_slate_post_tick_callback(state['handle'])

    def next_phase():
        result['phases'].append(state['phase'])
        state['phase'] += 1
        state['since'] = time.monotonic()

    def tick(_dt):
        try:
            assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'PIE stopped'
            age = time.monotonic()-state['since']
            assert age < 30, 'Phase timed out'
            stages = [actor.get_editor_property(f'Stage{i}Position') for i in range(10)]
            claws = [head.get_editor_property(f'Claw{i}Position') for i in range(3)]
            amount = sum(stages)/10
            predicted = stage_step(
                [actor.get_editor_property(f'PreviousStage{i}Position') for i in range(10)],
                actor.get_editor_property('LastStageTarget'),
                actor.get_editor_property('LastStageSequential'),
                actor.get_editor_property('LastStageDeltaSeconds'),
                actor.get_editor_property('LastStageTransitionSeconds'),
                [actor.get_editor_property(f'FrameStage{i}RetractReady') for i in range(10)],
                actor.get_editor_property('LastStageMotionReady'))
            timing_error = max(abs(a-b) for a, b in zip(stages, predicted))
            assert timing_error < 0.0001, f'Stage timing mismatch {timing_error}'
            result['maximumStageTimingError'] = max(result['maximumStageTimingError'], timing_error)
            moving = state['last'] is not None and max(abs(a-b) for a, b in zip(stages, state['last'])) > 1e-6
            if moving:
                assert sum(abs(v) for v in claws) < 1e-5, 'Sleeves moved before claws closed'
                result['movingSamples'] += 1
            elif actor.get_editor_property('bSocketClawsLocked') and sum(claws) > 0.001:
                result['waitingSamples'] += 1
            state['last'] = stages
            result['samples'] += 1
            validate(actor)
            result['housingChecks'] += 1
            phase = state['phase']
            if phase == 0:
                command('SetHeadOpening', 1.0)
                for i, value in enumerate((0.25, 0.6, 0.9)):
                    command('SetHeadClawOpening', i, value)
                next_phase()
            elif phase == 1 and age > 1.5:
                assert max(abs(a-b) for a, b in zip(claws, (0.25, 0.6, 0.9))) < 0.001
                command('RetractLeg', True)
                next_phase()
            elif phase == 2 and amount < 1e-6 and age > 1:
                for i in range(3):
                    command('SetHeadClawOpening', i, 1.0)
                next_phase()
            elif phase == 3 and age > 1.5:
                assert max(abs(a-0.6) for a in claws) < 0.001, 'Seated claw limit was not applied'
                for i, value in enumerate((0.25, 0.6, 0.9)):
                    command('SetHeadClawOpening', i, value)
                command('SetMotionMode', True)
                command('SetLegExtension', 0.1)
                next_phase()
            elif phase == 4 and abs(amount-0.1) < 1e-6 and age > 1:
                command('SetHeadClawOpening', 1, 1.0)
                command('SetHeadEyelidOpening', 0.35)
                next_phase()
            elif phase == 5 and age > 1:
                assert sum(claws) < 1e-5, 'Mid-stroke opening was not deferred'
                command('SetLegExtension', 0.2)
                next_phase()
            elif phase == 6 and abs(amount-0.2) < 1e-6 and age > 1:
                next_phase()
            elif phase == 7 and age > 1.5:
                assert max(abs(a-b) for a, b in zip(claws, (0.25, 1, 0.9))) < 0.001
                assert actor.get_editor_property('bSocketHeadOutside'), 'Partial working pose is not certified outside'
                assert not actor.get_editor_property('bSocketClawsLocked')
                result['partialWorkingPose'] = {'extension': amount, 'claws': claws,
                                               'headCenterXBodyLocal': actor.get_editor_property('SocketHeadCenterX')}
                command('SetHeadClawOpening', 0, -1.0)
                next_phase()
            elif phase == 8 and age > 1.5:
                assert abs(claws[0]-1) < 0.001, 'Negative override did not restore general control'
                assert abs(head.get_editor_property('EyelidPosition')-0.35) < 0.001, 'Safety changed eyelid override'
                command('SetLegExtension', 0.1)
                next_phase()
            elif phase == 9 and abs(amount-0.1) < 1e-6 and age > 1:
                assert sum(claws) < 1e-5, 'Retraction from partial working pose did not close claws'
                assert actor.get_editor_property('bSocketClawsLocked')
                command('SetLegExtension', 1.0)
                next_phase()
            elif phase == 10 and amount > 0.999999 and age > 1:
                next_phase()
            elif phase == 11 and age > 1.5:
                assert max(abs(a-b) for a, b in zip(claws, (1, 1, 0.9))) < 0.001
                assert result['waitingSamples'] > 0 and result['movingSamples'] > 0
                finish()
        except Exception as exc:
            finish(str(exc))

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    # Callback closure keeps all state alive until unregistering.
    print('Socket safety exercise registered; result:', path)


if __name__ == '__main__':
    start()
