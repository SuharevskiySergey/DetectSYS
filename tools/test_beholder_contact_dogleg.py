import math
import unittest

from beholder_contact_dogleg import dogleg_pose, plan_cycle
from beholder_contact_ik import forward_contact
from generate_beholder_telescope import stage_targets


class ContactDoglegTests(unittest.TestCase):
    def test_whole_tip_frame_and_arbitrary_material_points_stay_fixed(self):
        for extension in (0.4, 0.45, 0.49999, 0.5, 0.9):
            initial = stage_targets(extension, True)
            for axis in ('pitch', 'yaw'):
                for angle in (-1, -0.5, 0, 0.5, 1):
                    pose = dogleg_pose(extension, angle, axis)
                    for point in ((0, 0, 0), (56, 12, -17), (116, -60, 60)):
                        self.assertLess(math.dist(forward_contact(initial, [(0, 0)]*10, point),
                                                 forward_contact(pose['stages'], pose['angles'], point)), 1e-9)
                    self.assertAlmostEqual(math.fsum(pose['stages'])-math.fsum(initial), pose['addedNormalisedStroke'])

    def test_return_reverses_the_same_geometry_and_keeps_interlocks(self):
        for extension in (0.4, 0.49999, 0.9):
            report = plan_cycle(extension, samples_per_half=11, check_nested=False)
            self.assertTrue(report['valid'])
            rows = report['samples']
            for a, b in zip(rows, reversed(rows)):
                self.assertTrue(all(abs(x-y) < 1e-12 for x, y in zip(a['stages'], b['stages'])))
                self.assertFalse(a['blockedReturnStages'])
            self.assertEqual(rows[0]['stages'], stage_targets(extension, True))
            self.assertEqual(rows[-1]['stages'], rows[0]['stages'])
            self.assertGreater(report['peakExtension'], extension)
            self.assertFalse(report['motionAuthorized'])
            self.assertFalse(report['continuousCollisionCertified'])

    def test_full_nested_bounds_include_nonadjacent_pairs(self):
        report = plan_cycle(0.5, axis='pitch', samples_per_half=3)
        self.assertTrue(report['valid'], report['reasons'])
        self.assertEqual(report['nestedPairsChecked'], 5*45)
        self.assertGreaterEqual(report['minimumNestedClearanceLocalCm'], 0.25)
        self.assertFalse(report['headGeometryChecked'])

    def test_existing_profile_and_input_bounds_are_not_bypassed(self):
        for args in ((0.39, 1, 'yaw'), (0.91, 1, 'yaw'), (0.5, 1.1, 'yaw'),
                     (0.5, math.nan, 'yaw'), (True, 1, 'yaw'), (0.5, 1, 'both')):
            with self.assertRaises(ValueError):
                dogleg_pose(*args)
        with self.assertRaises(ValueError):
            plan_cycle(half_duration=0.2, check_nested=False)
        with self.assertRaises(ValueError):
            plan_cycle(transition_seconds=math.inf, check_nested=False)

    def test_head_geometry_is_checked_against_each_moving_sleeve(self):
        head = dict(claw_vertices_tip=[(111, 0, 0)]*12, sphere_center_tip=(56, 0, 0), sphere_radius_local=60)
        report = plan_cycle(samples_per_half=3, head_geometry=head)
        self.assertTrue(report['valid'])
        self.assertTrue(report['headGeometryChecked'])
        self.assertTrue(report['headGeometryPassed'])
        self.assertTrue(all(r['minimumHeadShellClearanceLocalCm'] > 0 for r in report['samples']))

    def test_head_shell_intersection_rejects_cycle(self):
        head = dict(claw_vertices_tip=[(111, 0, 0)]*12, sphere_center_tip=(0, 0, 0), sphere_radius_local=60)
        report = plan_cycle(samples_per_half=3, head_geometry=head)
        self.assertFalse(report['valid'])
        self.assertFalse(report['headGeometryPassed'])
        self.assertIn('nested_walls', report['reasons'])
