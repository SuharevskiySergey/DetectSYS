"""Synchronous PIE timing-profile test against public Blueprint commands.

Synthetic delta time, not actual render-FPS measurements. Only the playing
copy is touched. Stop PIE afterwards to discard this artificial straight pose.
"""
import json
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
from generate_beholder_telescope import stage_targets


def exercise():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world, 'Start PIE first'
    actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                 if a.get_actor_label() == 'BeholderTelescopic_Demo')
    ticking = actor.is_actor_tick_enabled()
    actor.set_actor_tick_enabled(False)
    rows = []

    def command(name, *args):
        actor.call_method(name, args)

    def stages():
        return [actor.get_editor_property(f'Stage{i}Position') for i in range(10)]

    def reset(amount):
        for name, value in {'bAutoDemo': False, 'bSequentialMotion': True,
                            'ExtensionAmount': amount, 'BendPitchDegrees': 0,
                            'BendYawDegrees': 0}.items():
            actor.set_editor_property(name, value)
        for i in range(1, 10):
            command('ClearJointBend', i)
        command('SnapStages')
        command('SnapBend')
        command('SnapJointBends')
        command('ApplyExtension')

    def run(name, args, initial, goal, expected_duration, sequential):
        reset(initial)
        before = stages()
        command(name, *args)
        assert stages() == before, 'Timing selection snapped the pose'
        active = actor.get_editor_property('TransitionSeconds')
        assert abs(active-expected_duration) < 1e-6
        assert actor.get_editor_property('bSequentialMotion') == sequential
        elapsed, count = 0.0, 0
        goals = stage_targets(goal, sequential)
        while max(abs(v-g) for v, g in zip(stages(), goals)) > 1e-6:
            assert count < 1000, 'Motion timed out'
            command('UpdateSocketSafety')
            assert actor.get_editor_property('bSocketMotionReady'), 'Start test with closed claws'
            command('UpdateStages', goal, 0.01)
            command('ApplyExtension')
            elapsed += 0.01
            count += 1
        expected_travel = abs(goal-initial)*expected_duration
        assert abs(elapsed-expected_travel) <= 0.020001
        rows.append({'command': name, 'arguments': args, 'activeDuration': active,
                     'simulatedSeconds': elapsed, 'sequential': sequential})

    try:
        command('SetMotionDurations', 0.8, 1.2, 0.3)
        run('SetLegExtension', (1.0,), 0, 1, 0.8, True)
        run('SetLegExtension', (0.5,), 1, 0.5, 1.2, True)
        run('RetractLeg', (False,), 1, 0, 1.2, True)
        run('RetractLeg', (True,), 1, 0, 0.3, False)
        # An extension after emergency uses its own duration, not the last 0.3.
        before = stages()
        command('SetLegExtension', 1.0)
        assert stages() == before
        assert abs(actor.get_editor_property('TransitionSeconds')-0.8) < 1e-6
        before = stages()
        command('SetMotionDurations', -2.0, 0.0, 0.001)
        assert stages() == before
        for name in ('ExtensionSeconds', 'RetractionSeconds', 'EmergencyRetractionSeconds'):
            assert abs(actor.get_editor_property(name)-0.01) < 1e-6
        result = {'passed': True, 'cases': rows, 'minimumDurationClamp': True,
                  'extensionAfterEmergency': True, 'noPoseSnaps': True}
        path = Path(unreal.Paths.project_dir()) / 'Saved/BeholderMotionProfiles.json'
        path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
    finally:
        actor.set_actor_tick_enabled(ticking)


if __name__ == '__main__':
    exercise()
