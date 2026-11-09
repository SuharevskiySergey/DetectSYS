import unittest

from generate_beholder_telescope import bend_angles, joint_targets


class JointCommandTests(unittest.TestCase):
    def test_overrides_are_local_and_keep_direction_when_clamped(self):
        angles = bend_angles([1]*10, 1, 1, {2: (-8, 4), 7: (0, -2)})
        self.assertEqual(angles[0], (0, 0))
        self.assertEqual(angles[1], (1, 1))
        self.assertAlmostEqual(angles[2][0], -4/3)
        self.assertAlmostEqual(angles[2][1], 2/3)
        self.assertEqual(angles[7], (0, -2))
        self.assertEqual(angles[8], (1, 1))

    def test_override_cannot_bend_nested_joint_or_bypass_retraction(self):
        self.assertEqual(bend_angles([0]*10, 1, 1, {2: (2, 0)}), [(0, 0)]*10)
        for sequential in (True, False):
            self.assertEqual(joint_targets([1]*10, 1, 1, 0, sequential, {2: (2, 0)}), [(0, 0)]*10)

    def test_clearing_override_recovers_global_target(self):
        angles = bend_angles([1]*10, 1, -1, {})
        self.assertEqual(angles[1:], [(1, -1)]*9)

    def test_root_is_not_an_overrideable_joint(self):
        with self.assertRaises(ValueError):
            bend_angles([1]*10, 1, 1, {0: (2, 0)})
