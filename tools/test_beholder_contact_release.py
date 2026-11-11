import copy
import ast
import itertools
import math
from pathlib import Path
import unittest

from beholder_contact_release import evaluate_four_releases


SQUARE = {0: (-10, -10, 0), 2: (-10, 10, 0), 4: (10, -10, 0), 6: (10, 10, 0)}


class ContactReleaseTests(unittest.TestCase):
    def test_editor_harness_only_records_release_diagnostic_without_commands(self):
        tree = ast.parse(Path(__file__).with_name('exercise_beholder_four_contact.py').read_text(encoding='utf-8'))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'evaluate_four_releases']
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0].args), 3)
        source = Path(__file__).with_name('beholder_contact_release.py').read_text(encoding='utf-8')
        self.assertNotIn('import unreal', source)
        self.assertNotIn('call_method', source)

    def test_centered_square_cannot_release_any_corner_with_positive_margin(self):
        r = evaluate_four_releases(SQUARE, (0, 0, 100))
        self.assertTrue(r['currentFootprint']['passesMargin'])
        self.assertEqual(r['geometricallyEligibleIndices'], [])
        self.assertFalse(r['motionAuthorized'])
        for row in r['releases']:
            self.assertEqual(row['footprint']['marginCm'], 0)
            self.assertFalse(row['passesGeometry'])

    def test_boundary_does_not_pass_even_zero_required_margin(self):
        self.assertEqual(evaluate_four_releases(SQUARE, (0, 0, 100), 0)['geometricallyEligibleIndices'], [])

    def test_shifted_reference_allows_only_triangles_containing_it(self):
        r = evaluate_four_releases(SQUARE, (-4, -2, 100), 1)
        self.assertEqual(r['geometricallyEligibleIndices'], [4, 6])
        self.assertFalse(r['motionAuthorized'])

    def test_exact_margin_is_rejected(self):
        r = evaluate_four_releases(SQUARE, (-4, -2, 0), 0)
        row = r['releases'][2]
        margin = row['footprint']['marginCm']
        equal = evaluate_four_releases(SQUARE, (-4, -2, 0), margin)
        self.assertFalse(equal['releases'][2]['passesGeometry'])

    def test_permutation_does_not_change_branch_identity(self):
        baseline = evaluate_four_releases(SQUARE, (-4, -2, 100))
        for order in itertools.permutations(SQUARE):
            self.assertEqual(evaluate_four_releases({i: SQUARE[i] for i in order}, (-4, -2, 100)), baseline)

    def test_inputs_are_not_mutated(self):
        points = {i: list(p) for i, p in SQUARE.items()}
        before = copy.deepcopy(points)
        evaluate_four_releases(points, [0, 0, 100])
        self.assertEqual(points, before)

    def test_translation_rotation_scale_preserve_diagnostics(self):
        angle = 0.37
        def transform(p):
            x, y, z = p
            return (1000+3*(x*math.cos(angle)-y*math.sin(angle)),
                    -2000+3*(x*math.sin(angle)+y*math.cos(angle)), z+17)
        baseline = evaluate_four_releases(SQUARE, (-4, -2, 100))
        r = evaluate_four_releases({i: transform(p) for i, p in SQUARE.items()}, transform((-4, -2, 100)), 3)
        self.assertEqual(r['geometricallyEligibleIndices'], baseline['geometricallyEligibleIndices'])
        for a, b in zip(r['releases'], baseline['releases']):
            self.assertAlmostEqual(a['footprint']['marginCm'], 3*b['footprint']['marginCm'])

    def test_invalid_full_footprint_and_degenerate_triangles_cannot_pass(self):
        for points in ({i: (0, 0, 0) for i in SQUARE}, {i: (i, 0, 0) for i in SQUARE}):
            r = evaluate_four_releases(points, (0, 0, 100))
            self.assertFalse(r['currentFootprint']['valid'])
            self.assertEqual(r['geometricallyEligibleIndices'], [])
        points = {**SQUARE, 6: SQUARE[4]}
        r = evaluate_four_releases(points, (-5, 0, 0))
        self.assertFalse(r['releases'][0]['footprint']['valid'])

    def test_outside_reference_has_no_eligible_release(self):
        self.assertEqual(evaluate_four_releases(SQUARE, (100, 100, 0))['geometricallyEligibleIndices'], [])

    def test_invalid_slots_coordinates_and_settings_raise(self):
        for points in ({}, {**SQUARE, 1: (0, 0, 0)}, {str(i): p for i, p in SQUARE.items()},
                       {**SQUARE, 0: (0, 0)}, {**SQUARE, 0: (0, 0, float('nan'))}):
            with self.assertRaises(ValueError):
                evaluate_four_releases(points, (0, 0, 0))
        for margin in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                evaluate_four_releases(SQUARE, (0, 0, 0), margin)
        with self.assertRaises(ValueError):
            evaluate_four_releases(SQUARE, (0, float('inf'), 0))

    def test_height_is_not_a_physics_check(self):
        uneven = {i: (p[0], p[1], i*100) for i, p in SQUARE.items()}
        self.assertEqual(evaluate_four_releases(uneven, (0, 0, 100)),
                         evaluate_four_releases(SQUARE, (0, 0, 100)))

    def test_grid_against_independent_barycentric_triangle_oracle(self):
        # Fixed branch ordering, no convex-hull or halfspace helper in oracle.
        for x, y in itertools.product(range(-15, 16, 3), repeat=2):
            r = evaluate_four_releases(SQUARE, (x, y, 100), 1)
            for row in r['releases']:
                a, b, c = [SQUARE[i][:2] for i in row['remainingIndices']]
                denominator = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
                u = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator
                v = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator
                weights = (u, v, 1-u-v)
                opposite_edges = ((b, c), (c, a), (a, b))
                distances = [w*abs(denominator)/math.dist(*edge) for w, edge in zip(weights, opposite_edges)]
                expected = min(distances)
                self.assertAlmostEqual(row['footprint']['marginCm'], expected)
                if abs(expected-1) > 1e-10:
                    self.assertEqual(row['passesGeometry'], expected > 1)
