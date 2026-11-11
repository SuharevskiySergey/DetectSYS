"""PIE-only, read-only surface-probe regression. No runtime BP changes."""
import importlib
import json
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
import inspect_beholder_surface as probe
importlib.reload(probe)


def run():
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'Start PIE first'
    output = Path(unreal.Paths.project_dir()) / 'Saved/BeholderSurfaceRegression.json'
    result = {'passed': False, 'reports': [], 'error': None}
    try:
        for distance, expect_hit in ((1000, True), (1, False), (1000, True)):
            report = probe.inspect(distance=distance, verbose=False)
            assert report['mode'] == 'PIE'
            assert len(report['legs']) == 8
            for row in report['legs']:
                assert row['valid'], row
                assert row['hit'] == expect_hit, row
                if expect_hit:
                    assert row['gap'] >= 0 and row['gap'] <= distance, row
                    assert row['impactNormal'][2] > 0, row
                    assert row['hitActor'], row
                    assert row['planeEstimate']['normalClearance'] > 0, row
                    assert abs(row['impactPoint'][0]-row['lowest']['point'][0]) < 0.01
                    assert abs(row['impactPoint'][1]-row['lowest']['point'][1]) < 0.01
                else:
                    assert all(row[key] is None for key in ('gap', 'impactPoint', 'impactNormal', 'hitActor', 'planeEstimate')), row
            result['reports'].append({'distance': distance, **report})
        result['passed'] = True
    except Exception as exc:
        result['error'] = str(exc)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'error': result['error'],
                      'samples': sum(len(r['legs']) for r in result['reports']), 'path': str(output)}))
    assert result['passed'], result['error']


if __name__ == '__main__':
    run()
