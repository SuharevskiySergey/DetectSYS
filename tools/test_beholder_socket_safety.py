"""Standalone reference tests for the conservative socket policy."""
import unittest

from beholder_socket_safety import locked, requested_claw, head_outside


class SocketSafetyTests(unittest.TestCase):
    def test_settled_folded_or_outside_poses_unlock(self):
        for sequential in (True, False):
            for value in (0, 1):
                self.assertFalse(locked([value]*10, value, sequential, outside=value == 1))
                self.assertTrue(locked([value]*10, 1-value, sequential, outside=True))
            self.assertTrue(locked([0.1]*10, 0.1, False))

    def test_matching_mean_is_not_settled(self):
        self.assertTrue(locked([1, 0]*5, 0.5, True))

    def test_requests_survive_lock_and_override_reset(self):
        self.assertEqual(requested_claw(0.7, 0.2, True), 0)
        self.assertEqual(requested_claw(0.7, 0.2, False), 0.2)
        self.assertEqual(requested_claw(0.7, -1, False), 0.7)
        self.assertEqual(requested_claw(2, -1, False), 1)

    def test_seated_claws_are_limited_without_losing_requests(self):
        self.assertEqual(requested_claw(1, -1, False, seated=True), 0.75)
        self.assertEqual(requested_claw(0.2, 1, False, seated=True), 0.75)
        self.assertEqual(requested_claw(0.2, 0.1, False, seated=True), 0.1)
        self.assertEqual(requested_claw(1, -1, False, seated=False), 1)

    def test_partial_pose_unlocks_only_when_stationary_and_outside(self):
        stages = [1, 0.5]+[0]*8
        self.assertFalse(locked(stages, 0.15, True, outside=True))
        self.assertTrue(locked(stages, 0.15, True, outside=False))
        self.assertTrue(locked(stages, 0.2, True, outside=True))

    def test_outside_plane_has_envelope_and_margin(self):
        self.assertFalse(head_outside(310.999))
        self.assertTrue(head_outside(311))
        self.assertFalse(head_outside(float('nan')))
