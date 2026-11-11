"""PIE-only simultaneous eight-leg sector-clearance regression.

Read-only geometric certificates are sampled during commands. This is not a
runtime collision controller or a swept collision test. Stop PIE to discard
all test commands. Result: Saved/BeholderBodyStress.json.
"""
import importlib
import json
from pathlib import Path
import sys
import time

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
import validate_beholder_body as checks
importlib.reload(checks)
from generate_beholder_telescope import stage_targets
from beholder_socket_safety import requested_claw


def start():
    body = checks.find_body()
    branches = checks.legs(body)
    assert body.get_actor_location().z >= 1600*body.get_actor_scale3d().z+190, 'Use the elevated technical stand for this test'
    original_rotation = body.get_actor_rotation()
    heads = [next(c for c in a.get_components_by_class(unreal.ChildActorComponent)
                  if c.get_name() == 'HeadModule').get_editor_property('child_actor') for a in branches]
    path = Path(unreal.Paths.project_dir()) / 'Saved/BeholderBodyStress.json'
    state = {'phase': 0, 'since': time.monotonic(), 'check': 0, 'handle': None}
    result = {'passed': False, 'samples': 0, 'allLegGeometryChecks': 0,
              'minimumOctantMarginLocal': None, 'poses': [], 'error': None}
    goals_a = (0.2, 0.35, 0.55, 0.8, 1, 0.65, 0.3, 1)
    goals_b = (0.05, 0.1, 0.2, 0.55, 1, 0.35, 0, 0.75)

    def call(actor, name, *args):
        actor.call_method(name, args)

    def settled():
        for leg, head in zip(branches, heads):
            goals = stage_targets(leg.get_editor_property('ExtensionAmount'), leg.get_editor_property('bSequentialMotion'))
            if max(abs(leg.get_editor_property(f'Stage{i}Position')-g) for i, g in enumerate(goals)) > 0.00001:
                return False
            for i in range(3):
                desired = requested_claw(leg.get_editor_property('SocketRequestedOpening'),
                                         leg.get_editor_property(f'SocketRequestedClaw{i}'),
                                         leg.get_editor_property('bSocketClawsLocked'),
                                         seated=leg.get_editor_property('ExtensionPosition') < 1e-6)
                if abs(head.get_editor_property(f'Claw{i}Position')-desired) > 0.001:
                    return False
        return True

    def validate(checkpoint=False):
        report = checks.validate(body)
        result['allLegGeometryChecks'] += 1
        margin = min(row['outboardSector']['minimumOctantMarginLocal'] for row in report['legs'])
        result['minimumOctantMarginLocal'] = margin if result['minimumOctantMarginLocal'] is None else min(margin, result['minimumOctantMarginLocal'])
        if checkpoint:
            result['poses'].append({'phase': state['phase'], 'extensions': [r['extension'] for r in report['legs']],
                                    'minimumOctantMarginLocal': margin})

    def advance():
        state['phase'] += 1
        state['since'] = time.monotonic()

    def finish(error=None):
        try:
            body.set_actor_rotation(original_rotation, False)
        except Exception as exc:
            error = error or str(exc)
        result['error'] = error
        result['passed'] = error is None
        path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        unreal.unregister_slate_post_tick_callback(state['handle'])

    def tick(_dt):
        try:
            assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'PIE stopped'
            now = time.monotonic()
            age = now-state['since']
            assert age < 45, 'Stress phase timed out'
            result['samples'] += 1
            if now-state['check'] > 1.0:
                validate()
                state['check'] = time.monotonic()
            phase = state['phase']
            if phase == 0:
                validate(True)
                for i, leg in enumerate(branches):
                    call(leg, 'SetMotionMode', bool(i % 2))
                    for joint in range(1, 10):
                        sign = 1 if i % 2 else -1
                        call(leg, 'SetJointBend', joint, sign*1.5, -sign*0.5)
                    call(leg, 'SetHeadOpening', 1.0)
                    call(leg, 'SetHeadClawOpening', 1, i/7)
                    call(leg, 'SetHeadEyelidOpening', i/7)
                    call(body, 'SetBodyLegExtension', i, goals_a[i])
                advance()
            elif phase == 1 and age > 3 and settled():
                validate(True)
                body.set_actor_rotation(unreal.Rotator(pitch=10, yaw=37, roll=-6), False)
                advance()
            elif phase == 2 and age > 1.5:
                validate(True)
                for i, leg in enumerate(branches):
                    call(leg, 'SetMotionMode', not bool(i % 2))
                    call(body, 'SetBodyLegExtension', i, goals_b[i])
                advance()
            elif phase == 3 and age > 3 and settled():
                validate(True)
                for i in range(8):
                    call(body, 'RetractBodyLeg', i, bool(i % 2))
                advance()
            elif phase == 4 and age > 3 and settled():
                validate(True)
                assert all(a.get_editor_property('ExtensionPosition') < 1e-6 for a in branches)
                for leg in branches:
                    call(leg, 'SetHeadOpening', 0.0)
                    for claw in range(3):
                        call(leg, 'SetHeadClawOpening', claw, -1.0)
                    call(leg, 'SetHeadEyelidOpening', 1.0)
                    for joint in range(1, 10):
                        call(leg, 'ClearJointBend', joint)
                body.set_actor_rotation(original_rotation, False)
                advance()
            elif phase == 5 and age > 1.5 and settled():
                validate(True)
                finish()
        except Exception as exc:
            finish(str(exc))

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    print('Eight-leg stress regression registered:', path)


if __name__ == '__main__':
    start()
