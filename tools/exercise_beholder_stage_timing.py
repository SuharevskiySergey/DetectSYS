"""Synthetic-delta regression against the actual Blueprint in PIE.

Uses only the playing copy, pauses its actor Tick during the synchronous test,
and calls UpdateStages with controlled delta values. This is NOT a measurement
of actual render FPS. Stop PIE afterwards to discard the synthetic setup.
"""
import json
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
from beholder_stage_timing import step


def exercise():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world, 'Start PIE first'
    actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                 if a.get_actor_label() == 'BeholderTelescopic_Demo')
    was_ticking = actor.is_actor_tick_enabled()
    rows = []
    maximum_error = 0.0
    updates = 0

    def reset(stages, sequential, target):
        assert max(stages)-min(stages) < 1e-10, 'Reset expects a uniform pose'
        for name, value in {'bAutoDemo': False, 'bSequentialMotion': False,
                            'TransitionSeconds': 0.6, 'ExtensionAmount': stages[0],
                            'BendPitchDegrees': 0, 'BendYawDegrees': 0}.items():
            actor.set_editor_property(name, value)
        actor.call_method('SnapStages')
        actor.call_method('SnapBend')
        actor.call_method('SnapJointBends')
        actor.set_editor_property('bSequentialMotion', sequential)
        actor.set_editor_property('ExtensionAmount', target)
        actor.call_method('UpdateSocketSafety')
        assert actor.get_editor_property('bSocketMotionReady'), 'Close claws before synthetic test'

    def advance(target, sequential, dt, expected_before):
        nonlocal maximum_error, updates
        expected = step(expected_before, target, sequential, dt)
        actor.call_method('UpdateStages', (target, dt))
        actual = [actor.get_editor_property(f'Stage{i}Position') for i in range(10)]
        error = max(abs(a-b) for a, b in zip(actual, expected))
        maximum_error = max(maximum_error, error)
        assert error < 0.0001, f'Blueprint/reference mismatch {error}: {actual} vs {expected}'
        updates += 1
        return expected

    actor.set_actor_tick_enabled(False)
    try:
        for fps in (10, 15, 30, 60, 120, 240):
            for sequential in (True, False):
                for initial, target in ((0, 1), (1, 0)):
                    expected = [initial]*10
                    reset(expected, sequential, target)
                    for _ in range(round(0.6*fps)):
                        expected = advance(target, sequential, 1/fps, expected)
                    final = [actor.get_editor_property(f'Stage{i}Position') for i in range(10)]
                    assert max(abs(v-target) for v in final) < 0.0001
                    rows.append({'fpsEquivalent': fps, 'sequential': sequential,
                                 'target': target, 'simulatedSeconds': 0.6})
        expected = [0.35]*10
        reset(expected, True, 0.7)
        for target, mode, dt in ((0.7, True, 0.07), (0.2, True, 0.03),
                                 (0.8, False, 0.11), (0.55, True, 0.9)):
            actor.set_editor_property('bSequentialMotion', mode)
            expected = advance(target, mode, dt, expected)
        actor.call_method('ApplyExtension')
        result = {'passed': True, 'updates': updates, 'maximumPredictionError': maximum_error,
                  'fixedDeltaCases': rows, 'modeSwitchAndReversal': True}
        path = Path(unreal.Paths.project_dir()) / 'Saved/BeholderStageTiming.json'
        path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
    finally:
        actor.set_actor_tick_enabled(was_ticking)


if __name__ == '__main__':
    exercise()
