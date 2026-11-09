"""PIE-only per-joint command regression; no asset or editor-level writes.

Start at manual extension 1, common bend 1/1 and closed claws. The asynchronous
callback writes Saved/BeholderJointCommands.json and unregisters on completion.
"""
import importlib
import json
from pathlib import Path
import sys
import time

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
import validate_beholder_telescope
importlib.reload(validate_beholder_telescope)


def start():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world, 'Start PIE first'
    actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                 if a.get_actor_label() == 'BeholderTelescopic_Demo')
    path = Path(unreal.Paths.project_dir()) / 'Saved/BeholderJointCommands.json'
    state = {'phase': 0, 'since': time.monotonic(), 'check': 0, 'handle': None}
    result = {'passed': False, 'samples': 0, 'geometryChecks': 0, 'maximumJointRate': 0,
              'poses': [], 'error': None}

    def command(name, *args):
        actor.call_method(name, args)

    def values():
        return [(v.x, v.y) for i in range(1, 10) for v in [actor.get_editor_property(f'Joint{i}Bend')]]

    def expect(expected):
        assert max(abs(a-b) for actual, goal in zip(values(), expected)
                   for a, b in zip(actual, goal)) < 0.001, f'Unexpected joint pose: {values()}'
        result['poses'].append({'phase': state['phase'], 'joints': values()})

    def advance():
        state['phase'] += 1
        state['since'] = time.monotonic()

    def finish(error=None):
        result['error'] = error
        result['passed'] = error is None
        path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        unreal.unregister_slate_post_tick_callback(state['handle'])

    def tick(_dt):
        try:
            assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'PIE stopped'
            now = time.monotonic()
            age = now-state['since']
            assert age < 30, 'Phase timed out'
            dt = actor.get_editor_property('LastJointDeltaSeconds')
            for i in range(1, 10):
                current = actor.get_editor_property(f'Joint{i}Bend')
                previous = actor.get_editor_property(f'PreviousJoint{i}Bend')
                change = abs(current.x-previous.x)+abs(current.y-previous.y)
                assert change <= 6*dt+0.0001, 'Per-joint command bypassed angular speed limit'
                result['maximumJointRate'] = max(result['maximumJointRate'], change/dt if dt else 0)
            result['samples'] += 1
            if now-state['check'] > 0.2:
                validate_beholder_telescope.validate()
                result['geometryChecks'] += 1
                state['check'] = now
            phase = state['phase']
            if phase == 0:
                command('SetJointBend', 2, -8.0, 4.0)
                command('SetJointBend', 7, 0.0, -2.0)
                advance()
            elif phase == 1 and age > 1.5:
                expected = [(1, 1)]*9
                expected[1], expected[6] = (-4/3, 2/3), (0, -2)
                expect(expected)
                before = [actor.get_editor_property(f'bJoint{i}Override') for i in range(1, 10)]
                for index in (-1, 0, 10):
                    command('SetJointBend', index, 100.0, 100.0)
                    command('ClearJointBend', index)
                assert before == [actor.get_editor_property(f'bJoint{i}Override') for i in range(1, 10)]
                command('ClearJointBend', 2)
                advance()
            elif phase == 2 and age > 1.5:
                expected = [(1, 1)]*9
                expected[6] = (0, -2)
                expect(expected)
                command('SetJointBend', 2, 2.0, 0.0)
                command('ClearJointBend', 7)
                advance()
            elif phase == 3 and age > 1.5:
                expected = [(1, 1)]*9
                expected[1] = (2, 0)
                expect(expected)
                command('RetractLeg', True)
                advance()
            elif phase == 4 and actor.get_editor_property('ExtensionPosition') < 1e-6 and age > 1:
                expect([(0, 0)]*9)
                assert actor.get_editor_property('bJoint2Override'), 'Retraction discarded the stored command'
                command('SetLegExtension', 1.0)
                advance()
            elif phase == 5 and actor.get_editor_property('ExtensionPosition') > 0.999999 and age > 2:
                expected = [(1, 1)]*9
                expected[1] = (2, 0)
                expect(expected)
                command('ClearJointBend', 2)
                advance()
            elif phase == 6 and age > 1.5:
                expect([(1, 1)]*9)
                assert result['geometryChecks'] > 5
                finish()
        except Exception as exc:
            finish(str(exc))

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    print('Per-joint regression registered:', path)


if __name__ == '__main__':
    start()
