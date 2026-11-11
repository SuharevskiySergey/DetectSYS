import math
from pathlib import Path
import unittest

from beholder_contact_ik import forward_contact, rotate, solve_contact_position
from generate_beholder_telescope import COUNT, STROKE, bend_angles, stage_targets


ZERO = [(0, 0)]*COUNT


class ContactIKTests(unittest.TestCase):
    def test_straight_fk_matches_sum_and_rigid_tip_offset(self):
        stages = [0.5]*COUNT
        self.assertEqual(forward_contact(stages, ZERO, (56, 10, -20)), (576, 10, -20))
        self.assertEqual(forward_contact(stage_targets(0.5, True), ZERO, (56, 10, -20)), (576, 10, -20))

    def test_ue_pitch_yaw_sign_and_composition(self):
        for actual, expected in zip(rotate((1, 0, 0), 90, 0), (0, 0, 1)):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(rotate((1, 0, 0), 0, 90), (0, 1, 0)):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(math.hypot(*rotate((3, -4, 5), 17, -23)), math.sqrt(50))

    def test_single_joint_rotation_has_expected_lever(self):
        angles = list(ZERO)
        angles[1] = (0, 2)
        stages = [1]*5+[0]*5
        point = forward_contact(stages, angles, (56, 0, 0))
        lever = 4*STROKE+56
        self.assertAlmostEqual(point[0], STROKE+lever*math.cos(math.radians(2)))
        self.assertAlmostEqual(point[1], lever*math.sin(math.radians(2)))

    def test_identity_target_needs_no_iterations(self):
        r = solve_contact_position(0.5, (56, 0, 0), (576, 0, 0))
        self.assertTrue(r['converged'])
        self.assertEqual(r['iterations'], 0)
        self.assertFalse(r['motionAuthorized'])
        self.assertFalse(r['headOrientationConstrained'])

    def test_small_xyz_targets_converge_within_existing_envelope(self):
        for delta in ((0, 4, 0), (0, 0, 4), (2, -3, 2), (-2, 2, -3), (0, -4, -4)):
            target = tuple(a+b for a, b in zip((576, 0, 0), delta))
            r = solve_contact_position(0.5, (56, 0, 0), target)
            self.assertTrue(r['converged'], r)
            self.assertLessEqual(r['residualLocalCm'], 0.001)
            limits = bend_angles(r['stages'], 2, 0)
            for i, (pitch, yaw) in enumerate(r['angles']):
                self.assertLessEqual(abs(pitch)+abs(yaw), limits[i][0]+1e-12)
            self.assertAlmostEqual(sum(r['stages'])/COUNT, r['extension'])

    def test_fully_folded_cannot_correct_transverse_target(self):
        r = solve_contact_position(0, (56, 0, 0), (56, 20, 0))
        self.assertFalse(r['converged'])
        self.assertGreater(r['residualLocalCm'], 1)

    def test_unreachable_retains_error_and_iteration_bound(self):
        r = solve_contact_position(0.5, (56, 0, 0), (5000, 5000, 5000), iterations=5)
        self.assertFalse(r['converged'])
        self.assertLessEqual(r['iterations'], 5)
        self.assertGreater(r['residualLocalCm'], 1000)

    def test_reported_residual_is_recomputed_from_returned_pose(self):
        for target in ((576, 4, -3), (10, 0, 100), (5000, -5000, 30)):
            r = solve_contact_position(0.5, (56, 13, -17), target, iterations=7)
            actual = forward_contact(r['stages'], r['angles'], (56, 13, -17))
            self.assertEqual(actual, r['pointLocal'])
            self.assertAlmostEqual(math.dist(actual, target), r['residualLocalCm'])
            self.assertEqual(r['converged'], r['residualLocalCm'] <= r['toleranceLocalCm'])
            self.assertTrue(all(0 <= s <= 1 for s in r['stages']))
            caps = bend_angles(r['stages'], 2, 0)
            self.assertTrue(all(abs(p)+abs(y) <= caps[i][0]+1e-12 for i, (p, y) in enumerate(r['angles'])))

    def test_deterministic_and_no_input_mutation(self):
        tip, target = [56, 0, 0], [576, 4, 2]
        a = solve_contact_position(0.5, tip, target)
        b = solve_contact_position(0.5, tip, target)
        self.assertEqual(a, b)
        self.assertEqual(tip, [56, 0, 0])
        self.assertEqual(target, [576, 4, 2])

    def test_forward_invalid_snapshot_raises(self):
        for stages, angles in (([0.5]*9, ZERO), ([math.nan]*10, ZERO), ([0.5]*10, ZERO[:9]),
                               ([0.5]*10, [(0, math.inf)]*10)):
            with self.assertRaises(ValueError):
                forward_contact(stages, angles, (56, 0, 0))

    def test_invalid_inputs_raise(self):
        for extension, tip, target, kwargs in ((math.nan, (56, 0, 0), (0, 0, 0), {}),
                                             (1.1, (56, 0, 0), (0, 0, 0), {}),
                                             (0.5, (56, math.inf, 0), (0, 0, 0), {}),
                                             (0.5, (56, 0, 0), (1e7, 0, 0), {}),
                                             (0.5, (56, 0, 0), (0, 0, 0), {'iterations': 0}),
                                             (0.5, (56, 0, 0), (0, 0, 0), {'tolerance': 0})):
            with self.assertRaises(ValueError):
                solve_contact_position(extension, tip, target, **kwargs)

    def test_no_editor_calls(self):
        source = Path(__file__).with_name('beholder_contact_ik.py').read_text(encoding='utf-8')
        self.assertNotIn('import unreal', source)
        self.assertNotIn('call_method', source)

    def test_editor_cross_check_does_not_apply_solved_poses(self):
        source = Path(__file__).with_name('exercise_beholder_contact_ik.py').read_text(encoding='utf-8')
        self.assertNotIn('call_method', source)
        self.assertNotIn('set_editor_property', source)
        self.assertNotIn('set_actor_', source)
        self.assertIn('predictedHeadPlanePasses', source)
        self.assertIn('headPlaneCheckIsEndpointOnly=True', source)
