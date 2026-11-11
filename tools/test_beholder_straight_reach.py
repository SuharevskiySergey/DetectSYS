import unittest

from beholder_straight_reach import straight_plane_target as solve
from beholder_straight_reach import shared_vertical_offset


class StraightReachTests(unittest.TestCase):
    def test_extend_down_to_plane(self):
        result = solve(0.2, 30, -100)
        self.assertTrue(result['valid'] and result['reachable'])
        self.assertAlmostEqual(result['target'], 0.5)
        self.assertEqual(result['foldedClearance'], 50)
        self.assertEqual(result['extendedClearance'], -50)

    def test_retract_toward_plane(self):
        result = solve(0.8, 30, 100)
        self.assertTrue(result['reachable'])
        self.assertAlmostEqual(result['target'], 0.5)

    def test_already_at_plane_retains_current_amount(self):
        self.assertEqual(solve(0.4, 0, -100)['target'], 0.4)

    def test_both_stroke_boundaries_are_reachable(self):
        self.assertEqual(solve(0, 100, -100)['target'], 1)
        self.assertTrue(solve(1, 100, 100)['reachable'])
        self.assertEqual(solve(1, 100, 100)['target'], 0)

    def test_distant_surface_is_not_reachable_by_clamping(self):
        result = solve(0, 400, -150)
        self.assertTrue(result['valid'])
        self.assertFalse(result['reachable'])
        self.assertEqual(result['target'], 0)
        self.assertEqual(result['extendedClearance'], 250)

    def test_wrong_direction_is_not_reachable(self):
        self.assertFalse(solve(0, 10, 100)['reachable'])

    def test_parallel_or_invalid_snapshot_is_cleared(self):
        for values in ((0, 0, 0), (0, 1, 1e-7), (-1, 1, -100), (2, 1, -100),
                       (0, -1, -100), (0, float('nan'), -100), (0, 1, float('inf'))):
            result = solve(*values)
            self.assertFalse(result['valid'] or result['reachable'])
            self.assertTrue(all(result[key] == 0 for key in ('target', 'projectedStroke', 'foldedClearance', 'extendedClearance')))

    def test_predicted_target_zeroes_linear_plane_clearance(self):
        for extension, clearance, stroke in ((0.1, 35, -120), (0.9, 12, 80), (0.5, 5, -75)):
            result = solve(extension, clearance, stroke)
            self.assertTrue(result['reachable'])
            self.assertAlmostEqual(clearance+(result['target']-extension)*stroke, 0)

    def test_vertical_fixture_shift_makes_partial_target_reachable(self):
        clearance, stroke, normal_z, desired = 333.0, -200.0, 0.8, 0.2
        offset_z = (-desired*stroke-clearance)/normal_z
        result = solve(0, clearance+offset_z*normal_z, stroke)
        self.assertTrue(result['reachable'])
        self.assertAlmostEqual(result['target'], desired)

    def test_linear_approach_does_not_cross_plane_before_target(self):
        for extension, clearance, stroke in ((0.2, 30, -100), (0.8, 30, 100)):
            result = solve(extension, clearance, stroke)
            for i in range(21):
                amount = extension+(result['target']-extension)*i/20
                self.assertGreaterEqual(clearance+(amount-extension)*stroke, -1e-12)

    def test_common_height_keeps_every_branch_in_requested_stroke_interval(self):
        clearances, strokes, nz = [333, 379, 333, 379], [-201, -67, -201, -67], 0.8944
        result = shared_vertical_offset(clearances, strokes, nz)
        self.assertTrue(result['feasible'])
        for c, p in zip(clearances, strokes):
            target = solve(0, c+nz*result['offset'], p)
            self.assertTrue(target['reachable'])
            self.assertGreaterEqual(target['target'], 0.05)
            self.assertLessEqual(target['target'], 0.95)

    def test_incompatible_heights_do_not_create_clamped_solution(self):
        result = shared_vertical_offset([10, 1000], [-100, -100], 1)
        self.assertFalse(result['feasible'])
        self.assertIsNone(result['offset'])

    def test_shared_height_rejects_wrong_direction_or_invalid_data(self):
        for args in (([], [], 1), ([1], [-1, -2], 1), ([1], [1], 1),
                     ([1], [-1], 0), ([float('nan')], [-1], 1), ([-1], [-1], 1)):
            with self.assertRaises(ValueError):
                shared_vertical_offset(*args)
