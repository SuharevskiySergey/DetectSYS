"""PIE-only independent-branch regression for the eight-socket body."""
import importlib
import json
from pathlib import Path
import sys
import time

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
import validate_beholder_body as checks
importlib.reload(checks)


def start():
    body = checks.find_body()
    branches = checks.legs(body)
    path = Path(unreal.Paths.project_dir()) / 'Saved/BeholderBodyRegression.json'
    state = {'phase': 0, 'since': time.monotonic(), 'check': 0, 'handle': None}
    result = {'passed': False, 'samples': 0, 'selectedLegGeometryChecks': 0,
              'allLegGeometryChecks': 0, 'poses': [], 'error': None}

    def call(actor, name, *args):
        actor.call_method(name, args)

    def checkpoint():
        validated = checks.validate(body)
        result['allLegGeometryChecks'] += 1
        result['poses'].append({'phase': state['phase'], 'legs': validated['legs']})
        return validated['legs']

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
            assert age < 30, 'Body regression phase timed out'
            result['samples'] += 1
            # Full eight-leg checks at checkpoints; selected moving branch in between.
            if now-state['check'] > 0.25:
                checks.validate_beholder_telescope.validate(branches[7])
                result['selectedLegGeometryChecks'] += 1
                state['check'] = now
            phase = state['phase']
            if phase == 0:
                rows = checkpoint()
                assert all(row['extension'] < 1e-6 for row in rows)
                call(body, 'SetBodyLegExtension', 7, 0.2)
                call(branches[7], 'SetHeadOpening', 1.0)
                call(branches[1], 'SetHeadOpening', 1.0)
                call(branches[2], 'SetHeadEyelidOpening', 0.0)
                advance()
            elif phase == 1 and age > 2.5:
                rows = checkpoint()
                assert abs(rows[7]['extension']-0.2) < 1e-6
                assert all(rows[i]['extension'] < 1e-6 for i in range(7))
                assert min(rows[7]['claws']) > 0.999
                assert all(abs(c-0.6) < 0.001 for c in rows[1]['claws'])
                assert rows[2]['eyelid'] < 0.001 and rows[3]['eyelid'] > 0.999
                # Bad body indices must not route to a real branch.
                for index in (-1, 8):
                    call(body, 'SetBodyLegExtension', index, 1.0)
                call(body, 'SetBodyLegExtension', 7, 1.0)
                call(branches[7], 'SetJointBend', 7, -2.0, 0.0)
                call(body, 'SetBodyLegExtension', 0, 0.1)
                advance()
            elif phase == 2 and age > 3:
                rows = checkpoint()
                assert abs(rows[0]['extension']-0.1) < 1e-6
                assert rows[7]['extension'] > 0.999999
                assert all(rows[i]['extension'] < 1e-6 for i in range(1, 7))
                bend = branches[7].get_editor_property('Joint7Bend')
                assert abs(bend.x+2) < 0.001 and abs(bend.y) < 0.001
                call(body, 'RetractBodyLeg', 7, True)
                advance()
            elif phase == 3 and age > 2:
                rows = checkpoint()
                assert rows[7]['extension'] < 1e-6
                assert abs(rows[0]['extension']-0.1) < 1e-6, 'Retracting branch 7 changed branch 0'
                call(body, 'RetractBodyLeg', 0, False)
                for branch in branches:
                    call(branch, 'SetHeadOpening', 0.0)
                    call(branch, 'SetHeadEyelidOpening', 1.0)
                    call(branch, 'ClearJointBend', 7)
                advance()
            elif phase == 4 and age > 1.5:
                rows = checkpoint()
                assert all(row['extension'] < 1e-6 and max(row['claws']) < 0.001 for row in rows)
                finish()
        except Exception as exc:
            finish(str(exc))

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    print('Eight-leg body regression registered:', path)


if __name__ == '__main__':
    start()
