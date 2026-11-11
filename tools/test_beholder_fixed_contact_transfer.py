import copy
import itertools
import math
from pathlib import Path
import unittest

from beholder_fixed_contact_transfer import evaluate_fixed_contact_translation as evaluate


class FixedContactTransferTests(unittest.TestCase):
    def test_zero_translation_keeps_extensions(self):
        r = evaluate({0: (100, 0, 0), 2: (0, -200, -200)}, {0: 0.3, 2: 0.8}, (0, 0, 0))
        self.assertTrue(r['compatibleGeometry'])
        self.assertFalse(r['motionAuthorized'])
        self.assertEqual([p['boundedTarget'] for p in r['contacts']], [0.3, 0.8])
        self.assertEqual(r['maximumResidualCm'], 0)

    def test_parallel_translation_can_be_cancelled(self):
        r = evaluate({0: (100, 0, 0), 2: (-200, 0, 0)}, {0: 0.5, 2: 0.5}, (10, 0, 0))
        self.assertTrue(r['compatibleGeometry'])
        self.assertAlmostEqual(r['contacts'][0]['boundedTarget'], 0.4)
        self.assertAlmostEqual(r['contacts'][1]['boundedTarget'], 0.55)

    def test_perpendicular_translation_cannot_be_cancelled_by_extension(self):
        r = evaluate({0: (100, 0, 0)}, {0: 0.5}, (0, 1.1, 0))
        self.assertFalse(r['compatibleGeometry'])
        self.assertEqual(r['contacts'][0]['boundedTarget'], 0.5)
        self.assertEqual(r['maximumResidualCm'], 1.1)

    def test_nonparallel_axes_reject_common_translation(self):
        r = evaluate({0: (100, 0, 0), 2: (0, 100, 0)}, {0: 0.5, 2: 0.5}, (1, 1, 0))
        self.assertFalse(r['compatibleGeometry'])
        self.assertTrue(all(row['extensionInRange'] for row in r['contacts']))
        self.assertEqual(r['maximumResidualCm'], 1)

    def test_stroke_limit_is_clamped_and_residual_preserved(self):
        r = evaluate({0: (100, 0, 0)}, {0: 0.05}, (10, 0, 0))
        row = r['contacts'][0]
        self.assertFalse(row['extensionInRange'])
        self.assertAlmostEqual(row['unconstrainedTarget'], -0.05)
        self.assertEqual(row['boundedTarget'], 0)
        self.assertEqual(row['residualCm'], 5)
        self.assertFalse(r['compatibleGeometry'])

    def test_tolerance_is_explicit_inclusive_and_bounded(self):
        self.assertTrue(evaluate({0: (100, 0, 0)}, {0: 0.5}, (0, 0.01, 0))['compatibleGeometry'])
        self.assertFalse(evaluate({0: (100, 0, 0)}, {0: 0.5}, (0, 0.010001, 0))['compatibleGeometry'])
        self.assertFalse(evaluate({0: (100, 0, 0)}, {0: 0.5}, (0, 0.001, 0), 0)['compatibleGeometry'])

    def test_residual_reconstructs_fixed_contact_error_for_any_initial_point(self):
        stroke, movement = (70, -40, -90), (1.1, 0.2, -0.3)
        row = evaluate({4: stroke}, {4: 0.4}, movement)['contacts'][0]
        for p in ((0, 0, 0), (1000, -2000, 30), (-17, 99, 200)):
            moved = [v+t+s*(row['boundedTarget']-0.4) for v, t, s in zip(p, movement, stroke)]
            for actual, residual in zip((v-q for v, q in zip(moved, p)), row['residualWorld']):
                self.assertAlmostEqual(actual, residual)

    def test_fit_minimizes_error_against_independent_dense_extension_grid(self):
        checks = 0
        for stroke, translation, extension in itertools.product(
                [(100, 0, 0), (70, -40, -90), (-120, -50, 80)],
                [(1, 2, 3), (-100, 200, -50), (0, 0, 0)], [0, 0.3, 0.9, 1]):
            row = evaluate({0: stroke}, {0: extension}, translation)['contacts'][0]
            for j in range(101):
                target = j/100
                residual = math.hypot(*(t+s*(target-extension) for t, s in zip(translation, stroke)))
                self.assertLessEqual(row['residualCm'], residual+1e-10)
            if 0 < row['boundedTarget'] < 1:
                self.assertAlmostEqual(sum(s*r for s, r in zip(stroke, row['residualWorld'])), 0, places=8)
            checks += 1
        self.assertEqual(checks, 36)

    def test_joint_rotation_is_not_silently_assumed(self):
        r = evaluate({0: (100, 0, 0)}, {0: 0.5}, (0, 2, 0))
        self.assertFalse(r['compatibleGeometry'])
        source = Path(__file__).with_name('beholder_fixed_contact_transfer.py').read_text(encoding='utf-8')
        self.assertNotIn('import unreal', source)
        self.assertNotIn('call_method', source)

    def test_inputs_not_mutated_and_index_order_deterministic(self):
        strokes, extensions = {6: [10, 20, 30], 0: [50, 60, 70]}, {0: 0.5, 6: 0.6}
        before = copy.deepcopy((strokes, extensions))
        a = evaluate(strokes, extensions, (1, 2, 3))
        b = evaluate(dict(reversed(list(strokes.items()))), extensions, (1, 2, 3))
        self.assertEqual(a, b)
        self.assertEqual((strokes, extensions), before)

    def test_rigid_rotation_and_uniform_scaling_preserve_fit(self):
        angle = 0.47
        def transform(v):
            x, y, z = v
            return (3*(x*math.cos(angle)-y*math.sin(angle)),
                    3*(x*math.sin(angle)+y*math.cos(angle)), 3*z)
        strokes, extensions, translation = {0: (80, -40, -100), 2: (-100, 20, -80)}, {0: 0.4, 2: 0.6}, (1, -2, 0.3)
        a = evaluate(strokes, extensions, translation)
        b = evaluate({i: transform(s) for i, s in strokes.items()}, extensions, transform(translation), 0.03)
        for original, moved in zip(a['contacts'], b['contacts']):
            self.assertAlmostEqual(original['boundedTarget'], moved['boundedTarget'])
            self.assertAlmostEqual(3*original['residualCm'], moved['residualCm'])
            for expected, actual in zip(transform(original['residualWorld']), moved['residualWorld']):
                self.assertAlmostEqual(expected, actual)

    def test_endpoint_fit_rejection_and_new_snapshot_do_not_reuse_old_success(self):
        strokes, extensions = {0: (100, 0, 0)}, {0: 1}
        self.assertTrue(evaluate(strokes, extensions, (10, 0, 0))['compatibleGeometry'])
        r = evaluate(strokes, extensions, (-10, 0, 0))
        self.assertFalse(r['compatibleGeometry'])
        self.assertEqual(r['contacts'][0]['boundedTarget'], 1)
        self.assertEqual(r['contacts'][0]['residualCm'], 10)

    def test_invalid_inputs_raise(self):
        for strokes, extensions, translation, tolerance in (
                ({}, {}, (0, 0, 0), 0.01), ({0: (100, 0, 0)}, {}, (0, 0, 0), 0.01),
                ({False: (100, 0, 0)}, {False: 0.5}, (0, 0, 0), 0.01),
                ({8: (100, 0, 0)}, {8: 0.5}, (0, 0, 0), 0.01),
                ({0: (0, 0, 0)}, {0: 0.5}, (0, 0, 0), 0.01),
                ({0: (float('inf'), 0, 0)}, {0: 0.5}, (0, 0, 0), 0.01),
                ({0: (100, 0, 0)}, {0: float('nan')}, (0, 0, 0), 0.01),
                ({0: (100, 0, 0)}, {0: 1.1}, (0, 0, 0), 0.01),
                ({0: (100, 0, 0)}, {0: 0.5}, (0, float('nan'), 0), 0.01),
                ({0: (100, 0, 0)}, {0: 0.5}, (0, 0, 0), -1),
                ({0: (100, 0, 0)}, {0: 0.5}, (0, 0, 0), float('inf')),
                ({0: (100, 0, 0)}, {0: 0.5}, (0, 0, 0), 2)):
            with self.assertRaises(ValueError):
                evaluate(strokes, extensions, translation, tolerance)
