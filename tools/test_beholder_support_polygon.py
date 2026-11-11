import math
import unittest

from beholder_support_polygon import evaluate_body_candidates, evaluate_footprint
from beholder_support_candidate import candidate


SQUARE = [(-10, -10), (10, -10), (10, 10), (-10, 10)]


class SupportPolygonTests(unittest.TestCase):
    def test_square_encloses_reference_with_measured_margin(self):
        result = evaluate_footprint(SQUARE, (0, 0))
        self.assertTrue(result['valid'] and result['inside'] and result['passesMargin'])
        self.assertEqual(result['marginCm'], 10)
        self.assertEqual(result['areaCm2'], 400)

    def test_reference_outside_even_with_four_candidates(self):
        result = evaluate_footprint(SQUARE, (30, 0))
        self.assertTrue(result['valid'])
        self.assertFalse(result['inside'] or result['passesMargin'])
        self.assertEqual(result['marginCm'], -20)

    def test_far_reference_does_not_cancel_polygon_area(self):
        result = evaluate_footprint(SQUARE, (1e12, 1e12))
        self.assertTrue(result['valid'])
        self.assertFalse(result['inside'])
        self.assertEqual(result['areaCm2'], 400)

    def test_boundary_does_not_pass_zero_margin(self):
        result = evaluate_footprint(SQUARE, (10, 0))
        self.assertTrue(result['inside'])
        self.assertFalse(result['passesMargin'])
        self.assertEqual(result['marginCm'], 0)

    def test_required_margin_is_strict(self):
        self.assertFalse(evaluate_footprint(SQUARE, (0, 0), minimum_margin=10)['passesMargin'])
        self.assertTrue(evaluate_footprint(SQUARE, (0, 0), minimum_margin=9)['passesMargin'])

    def test_three_points_on_one_side_are_not_enough(self):
        result = evaluate_footprint([(10, 0), (20, 10), (20, -10)], (0, 0))
        self.assertTrue(result['valid'])
        self.assertFalse(result['inside'])

    def test_winding_order_duplicates_and_interior_points_do_not_change_hull(self):
        baseline = evaluate_footprint(SQUARE, (0, 0))
        result = evaluate_footprint(list(reversed(SQUARE))+[(0, 0), (10, 10)], (0, 0))
        self.assertEqual(baseline, result)

    def test_collinear_and_duplicate_slots_are_not_polygon(self):
        for points in ([], [(0, 0)], [(0, 0)]*8, [(0, 0), (1, 0), (2, 0), (3, 0)]):
            result = evaluate_footprint(points, (0, 0))
            self.assertFalse(result['valid'] or result['passesMargin'])
            self.assertIsNone(result['marginCm'])

    def test_nearly_collinear_polygon_is_rejected_by_area_guard(self):
        result = evaluate_footprint([(0, 0), (1, 0), (2, 1e-8)], (1, 0))
        self.assertFalse(result['valid'])

    def test_translation_rotation_and_scale(self):
        theta = 0.37
        def transform(p):
            return (100000+3*(p[0]*math.cos(theta)-p[1]*math.sin(theta)),
                    -200000+3*(p[0]*math.sin(theta)+p[1]*math.cos(theta)))
        result = evaluate_footprint([transform(p) for p in SQUARE], transform((0, 0)))
        self.assertTrue(result['passesMargin'])
        self.assertAlmostEqual(result['marginCm'], 30, places=8)
        self.assertAlmostEqual(result['areaCm2'], 3600, places=7)

    def test_removing_a_corner_can_put_reference_on_boundary(self):
        result = evaluate_footprint(SQUARE[:3], (0, 0))
        self.assertTrue(result['inside'])
        self.assertFalse(result['passesMargin'])

    def test_eight_body_slots_only_use_selected_points(self):
        points = [(x, y, 0) for x, y in SQUARE]+[None]*4
        result = evaluate_body_candidates(points, [True]*4+[False]*4, (0, 0, 200))
        self.assertTrue(result['passesMargin'])
        self.assertEqual(result['candidateIndices'], [0, 1, 2, 3])

    def test_body_with_no_candidates_has_no_footprint(self):
        result = evaluate_body_candidates([None]*8, [False]*8, (0, 0, 200))
        self.assertFalse(result['valid'])
        self.assertEqual(result['candidateIndices'], [])

    def test_distant_probe_hits_do_not_become_support_polygon(self):
        points = [(x, y, 0) for x, y in SQUARE]*2
        flags = [candidate(True, True, True, 1, 300, 300) for _ in range(8)]
        result = evaluate_body_candidates(points, flags, (0, 0, 350))
        self.assertFalse(result['valid'])

    def test_failed_new_sample_does_not_reuse_old_margin(self):
        points = [(x, y, 0) for x, y in SQUARE]+[None]*4
        first = evaluate_body_candidates(points, [True]*4+[False]*4, (0, 0, 200))
        second = evaluate_body_candidates(points, [False]*8, (0, 0, 200))
        self.assertTrue(first['passesMargin'])
        self.assertIsNone(second['marginCm'])
        self.assertFalse(second['passesMargin'])

    def test_height_is_not_claimed_as_force_or_contact_validation(self):
        flat = [(x, y, 0) for x, y in SQUARE]+[None]*4
        uneven = [(x, y, i*100) for i, (x, y) in enumerate(SQUARE)]+[None]*4
        self.assertEqual(evaluate_body_candidates(flat, [True]*4+[False]*4, (0, 0, 200)),
                         evaluate_body_candidates(uneven, [True]*4+[False]*4, (0, 0, 200)))

    def test_invalid_coordinates_settings_and_flags_raise(self):
        for points in ([(-10, -10), (10, -10), (0, float('nan'))], [(0, 0, 0)]):
            with self.assertRaises(ValueError):
                evaluate_footprint(points, (0, 0))
        for margin in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                evaluate_footprint(SQUARE, (0, 0), minimum_margin=margin)
        with self.assertRaises(ValueError):
            evaluate_body_candidates([None]*8, [0]*8, (0, 0, 0))
        with self.assertRaises(ValueError):
            evaluate_body_candidates([None]*7, [False]*7, (0, 0, 0))

    def test_numeric_overflow_is_not_accepted(self):
        with self.assertRaises(ValueError):
            evaluate_footprint([(-1e308, -1e308), (1e308, -1e308), (0, 1e308)], (0, 0))
