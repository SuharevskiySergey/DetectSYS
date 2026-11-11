"""PIE numerical oracle tests for the new Blueprint footprint functions.

Only the math helper receives synthetic points. No actor is moved; the live
wrapper must reject the elevated stand and must not change motion goals.
"""
import json
import math
from pathlib import Path
import random
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve()/'tools'))
from beholder_support_polygon import evaluate_footprint
import validate_beholder_body as geometry


def run():
    assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'Start PIE'
    body = geometry.find_body()
    legs = geometry.legs(body)
    report = dict(passed=False, numericalChecks=0, rejectedChecks=0, liveChecks=0, error=None)

    def calculate(points, reference=(0, 0, 0), minimum=0):
        args = tuple(unreal.Vector(*p) for p in points)+(unreal.Vector(*reference), minimum)
        value = body.call_method('CalculateOrderedFourFootprint', args)
        assert isinstance(value, tuple) and len(value) == 5, value
        return value

    def compare(points, reference=(0, 0, 0), minimum=0):
        expected = evaluate_footprint([p[:2] for p in points], reference[:2], minimum)
        actual = calculate(points, reference, minimum)
        assert actual[:3] == (expected['valid'], expected['inside'], expected['passesMargin']), (actual, expected)
        assert abs(actual[3]-expected['marginCm']) < 0.002, (actual, expected)
        assert abs(actual[4]-expected['areaCm2']) < max(0.01, expected['areaCm2']*2e-6), (actual, expected)
        report['numericalChecks'] += 1

    square = [(-10, -10, 0), (10, -10, 0), (10, 10, 0), (-10, 10, 0)]
    try:
        for reference, minimum in [((0, 0, 0), 0), ((0, 0, 0), 10), ((0, 0, 0), 9),
                                   ((10, 0, 0), 0), ((12, 0, 0), 0), ((20, 20, 3), 0)]:
            compare(square, reference, minimum)
            compare(list(reversed(square)), reference, minimum)
        rng = random.Random(54191)
        for _ in range(80):
            cx, cy = rng.uniform(-2000, 2000), rng.uniform(-2000, 2000)
            rx, ry, angle = rng.uniform(20, 400), rng.uniform(20, 400), rng.uniform(-math.pi, math.pi)
            points = []
            for k in range(4):
                t = angle+k*math.pi/2+rng.uniform(-0.08, 0.08)
                points.append((cx+rx*math.cos(t), cy+ry*math.sin(t), rng.uniform(-5, 5)))
            reference = (cx+rng.uniform(-2, 2)*rx, cy+rng.uniform(-2, 2)*ry, 7)
            compare(points, reference, rng.uniform(0, 15))
            compare(points[::-1], reference, rng.uniform(0, 15))
        invalid = [([square[0]]*4, (0, 0, 0), 0),
                   ([(i, i, 0) for i in range(4)], (0, 0, 0), 0),
                   ([square[i] for i in (0, 2, 1, 3)], (0, 0, 0), 0),
                   ([square[0], square[1], (0, -5, 0), square[3]], (0, 0, 0), 0),
                   (square, (0, 0, 0), -1), (square, (0, 0, 0), float('nan')),
                   (square, (0, 0, 0), float('inf')), (square, (0, 0, 0), 1000001),
                   (square, (10000001, 0, 0), 0),
                   ([(10000001, 0, 0)]+square[1:], (0, 0, 0), 0),
                   # Nonzero finite components avoid the Python reflection
                   # bridge treating (0,0,NaN) as an unchanged zero default.
                   (square, (1, 2, float('nan')), 0)]
        for value in (float('nan'), float('inf'), -float('inf')):
            for axis in range(3):
                bad = [1.0, 2.0, 3.0]
                bad[axis] = value
                invalid.append((square, tuple(bad), 0))
                for i in range(4):
                    points = list(square)
                    points[i] = tuple(bad)
                    invalid.append((points, (0, 0, 0), 0))
        for points, reference, minimum in invalid:
            assert calculate(square)[0], 'Seed a valid result before every rejection'
            actual = calculate(points, reference, minimum)
            assert actual == (False, False, False, 0, 0), (points, reference, minimum, actual)
            report['rejectedChecks'] += 1
        goals = [leg.get_editor_property('ExtensionAmount') for leg in legs]
        assert body.call_method('EvaluateExperimentalFourFootprint', (body.get_actor_location(), 1.0)) == (False, False, False, 0, 0)
        assert goals == [leg.get_editor_property('ExtensionAmount') for leg in legs]
        report['liveChecks'] += 1
        report['passed'] = True
    except Exception as exc:
        report['error'] = repr(exc)
    path = Path(unreal.Paths.project_dir())/'Saved/BeholderFootprintRegression.json'
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    assert report['passed'], report['error']


if __name__ == '__main__':
    run()
