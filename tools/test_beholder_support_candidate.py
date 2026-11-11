import unittest

from beholder_support_candidate import candidate, settings_valid


class SupportCandidateTests(unittest.TestCase):
    def test_near_horizontal_surface_is_only_candidate(self):
        self.assertTrue(candidate(True, True, True, 1, 1, 1))

    def test_suspended_demo_is_not_support(self):
        self.assertFalse(candidate(True, True, True, 0.8944, 333, 373))

    def test_all_sensor_flags_required(self):
        for flags in ((False, True, True), (True, False, True), (True, True, False)):
            self.assertFalse(candidate(*flags, 1, 0, 0))

    def test_steep_downward_and_invalid_normals_rejected(self):
        for z in (0.7, 0, -1, 1.01, float('nan')):
            self.assertFalse(candidate(True, True, True, z, 0, 0))

    def test_signed_clearance_and_vertical_gap_both_required(self):
        for clearance, gap in ((-1, 1), (1, -1), (3, 1), (1, 3), (float('inf'), 1)):
            self.assertFalse(candidate(True, True, True, 1, clearance, gap))

    def test_configured_boundaries_are_inclusive(self):
        for clearance, gap in ((-0.1, -0.1), (2, 2)):
            self.assertTrue(candidate(True, True, True, 0.8, clearance, gap, min_normal_z=0.8))

    def test_bad_configuration_is_not_used(self):
        for config in ((-1, 2, 0.1), (1.1, 2, 0.1), (0.8, -1, 0.1),
                       (0.8, 101, 0.1), (0.8, 2, -1), (0.8, 2, 2), (float('nan'), 2, 0.1)):
            self.assertFalse(settings_valid(*config))
            self.assertFalse(candidate(True, True, True, 1, 0, 0, *config))
