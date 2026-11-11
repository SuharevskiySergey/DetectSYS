import copy
import itertools
import math
import unittest
from pathlib import Path

from beholder_reference_transfer import plan_reference_transfers
from beholder_support_polygon import evaluate_footprint


SQUARE = {0: (-10, -10, 0), 2: (-10, 10, 0), 4: (10, -10, 0), 6: (10, 10, 0)}


class ReferenceTransferTests(unittest.TestCase):
    def test_planner_has_no_editor_or_motion_calls(self):
        source = Path(__file__).with_name('beholder_reference_transfer.py').read_text(encoding='utf-8')
        self.assertNotIn('import unreal', source)
        self.assertNotIn('call_method', source)
        self.assertNotIn('set_editor_property', source)

    def test_square_nearest_shift_is_margin_plus_reserve(self):
        r = plan_reference_transfers(SQUARE, (0, 0, 100))
        self.assertEqual(r['geometricallyFeasibleIndices'], [0, 2, 4, 6])
        self.assertFalse(r['motionAuthorized'])
        for row in r['transfers']:
            self.assertAlmostEqual(row['shiftCm'], 1.1)
            self.assertAlmostEqual(row['targetTriangleFootprint']['marginCm'], 1.1)
            self.assertAlmostEqual(row['triangleInradiusCm'], 20-10*math.sqrt(2))
            self.assertEqual(row['proposedReferenceWorld'][2], 100)
            removed = SQUARE[row['removedIndex']]
            target = row['proposedReferenceWorld']
            self.assertLess(target[0]*removed[0]+target[1]*removed[1], 0)

    def test_already_inside_keeps_reference_and_zero_budget(self):
        r = plan_reference_transfers(SQUARE, (-4, -2, 100), maximum_shift=0)
        self.assertEqual(r['geometricallyFeasibleIndices'], [4, 6])
        for row in r['transfers'][2:]:
            self.assertEqual(row['shiftCm'], 0)
            self.assertEqual(row['proposedReferenceWorld'], (-4, -2, 100))

    def test_budget_rejection_keeps_diagnostic_not_permission(self):
        r = plan_reference_transfers(SQUARE, (0, 0, 100), maximum_shift=1)
        self.assertEqual(r['geometricallyFeasibleIndices'], [])
        for row in r['transfers']:
            self.assertEqual(row['reason'], 'maximum_shift_exceeded')
            self.assertGreater(row['shiftCm'], 1)

    def test_exact_budget_is_allowed_but_smaller_budget_is_not(self):
        baseline = plan_reference_transfers(SQUARE, (0, 0, 100))
        shift = baseline['transfers'][0]['shiftCm']
        self.assertTrue(plan_reference_transfers(SQUARE, (0, 0, 100), maximum_shift=shift)['transfers'][0]['feasibleGeometry'])
        self.assertFalse(plan_reference_transfers(SQUARE, (0, 0, 100), maximum_shift=shift-1e-6)['transfers'][0]['feasibleGeometry'])

    def test_unrepresentable_reserve_fails_closed_in_world_coordinates(self):
        offset = 1e16
        points = {i: (offset+p[0], offset+p[1], p[2]) for i, p in SQUARE.items()}
        r = plan_reference_transfers(points, (offset, offset, 100), minimum_margin=0, reserve_margin=0.1)
        self.assertEqual(r['geometricallyFeasibleIndices'], [])
        self.assertTrue(all(row['reason'] == 'target_verification_failed' for row in r['transfers']))

    def test_inset_too_large_is_rejected(self):
        r = plan_reference_transfers(SQUARE, (0, 0, 0), minimum_margin=6)
        self.assertTrue(r['currentFootprint']['passesMargin'])
        for row in r['transfers']:
            self.assertEqual(row['reason'], 'insufficient_triangle_inradius')
            self.assertIsNone(row['proposedReferenceWorld'])

    def test_inset_at_inradius_collapses_to_incenter(self):
        radius = 20-10*math.sqrt(2)
        r = plan_reference_transfers(SQUARE, (0, 0, 100), minimum_margin=1, reserve_margin=radius-1)
        for row in r['transfers']:
            self.assertTrue(row['feasibleGeometry'])
            self.assertAlmostEqual(row['targetTriangleFootprint']['marginCm'], radius)

    def test_current_invalid_or_outside_cannot_plan(self):
        for points, ref in (({i: (i, 0, 0) for i in SQUARE}, (0, 0, 0)), (SQUARE, (100, 100, 0))):
            r = plan_reference_transfers(points, ref)
            self.assertEqual(r['geometricallyFeasibleIndices'], [])
            self.assertTrue(all(row['proposedReferenceWorld'] is None for row in r['transfers']))

    def test_duplicate_contact_leaves_some_degenerate_triangles(self):
        points = {**SQUARE, 6: SQUARE[4]}
        r = plan_reference_transfers(points, (-5, -2, 100), minimum_margin=0)
        self.assertEqual(r['transfers'][0]['reason'], 'degenerate_triangle')

    def test_permutation_and_no_mutation(self):
        before = copy.deepcopy(SQUARE)
        baseline = plan_reference_transfers(SQUARE, (0, 0, 100))
        for order in itertools.permutations(SQUARE):
            self.assertEqual(plan_reference_transfers({i: SQUARE[i] for i in order}, (0, 0, 100)), baseline)
        self.assertEqual(SQUARE, before)

    def test_translation_rotation_scale(self):
        angle = 0.31
        def transform(p):
            x, y, z = p
            return (1e6+3*(x*math.cos(angle)-y*math.sin(angle)),
                    -2e6+3*(x*math.sin(angle)+y*math.cos(angle)), z+200)
        a = plan_reference_transfers(SQUARE, (0, 0, 100))
        b = plan_reference_transfers({i: transform(p) for i, p in SQUARE.items()}, transform((0, 0, 100)),
                                     minimum_margin=3, reserve_margin=0.3, maximum_shift=300)
        self.assertEqual(a['geometricallyFeasibleIndices'], b['geometricallyFeasibleIndices'])
        for x, y in zip(a['transfers'], b['transfers']):
            self.assertAlmostEqual(y['shiftCm'], 3*x['shiftCm'], places=8)
            for actual, expected in zip(y['proposedReferenceWorld'], transform(x['proposedReferenceWorld'])):
                self.assertAlmostEqual(actual, expected, places=8)

    def test_fixed_contact_reference_segment_stays_in_four_hull(self):
        r = plan_reference_transfers(SQUARE, (0, 0, 100))
        for row in r['transfers']:
            x, y, _ = row['proposedReferenceWorld']
            for step in range(101):
                f = step/100
                self.assertTrue(evaluate_footprint([p[:2] for p in SQUARE.values()], (f*x, f*y), 1)['passesMargin'])

    def test_invalid_settings_and_coordinates_raise(self):
        for settings in (dict(reserve_margin=0), dict(reserve_margin=-1), dict(reserve_margin=float('nan')),
                         dict(reserve_margin=float('inf')), dict(maximum_shift=-1),
                         dict(maximum_shift=float('nan')), dict(maximum_shift=float('inf')),
                         dict(minimum_margin=-1), dict(minimum_margin=float('nan'))):
            with self.assertRaises(ValueError):
                plan_reference_transfers(SQUARE, (0, 0, 0), **settings)
        with self.assertRaises(ValueError):
            plan_reference_transfers({**SQUARE, 0: (float('inf'), 0, 0)}, (0, 0, 0))

    def test_nearest_target_against_independent_inset_line_intersections(self):
        # Oracle constructs offset edge equations, not incenter homothety.
        points = {0: (-12, -9, 0), 2: (-8, 14, 0), 4: (15, -7, 0), 6: (9, 11, 0)}
        checks = 0
        for x, y in itertools.product(range(-6, 7, 2), repeat=2):
            r = plan_reference_transfers(points, (x, y, 100), minimum_margin=0.7, reserve_margin=0.3)
            for row in r['transfers']:
                if not row['feasibleGeometry']:
                    continue
                tri = [points[i][:2] for i in row['remainingIndices']]
                a, b, c = tri
                if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]) < 0:
                    tri.reverse()
                lines = []
                for a, b in zip(tri, tri[1:]+tri[:1]):
                    length = math.dist(a, b)
                    nx, ny = -(b[1]-a[1])/length, (b[0]-a[0])/length
                    lines.append((nx, ny, nx*a[0]+ny*a[1]+1.0))
                vertices = []
                for (a, b, c), (d, e, f) in itertools.combinations(lines, 2):
                    determinant = a*e-b*d
                    vertices.append(((c*e-b*f)/determinant, (a*f-c*d)/determinant))
                tx, ty, _ = row['proposedReferenceWorld']
                for nx, ny, bound in lines:
                    self.assertGreaterEqual(nx*tx+ny*ty-bound, -1e-10)
                # Projection optimality: (reference-target) dot (v-target)<=0
                # for all vertices proves nearest point over the convex inset.
                for vx, vy in vertices:
                    self.assertLessEqual((x-tx)*(vx-tx)+(y-ty)*(vy-ty), 1e-9)
                checks += 1
        self.assertEqual(checks, 196)
