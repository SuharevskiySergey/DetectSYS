import unittest

from beholder_octant_clearance import outboard_margin, signed_margin


class OctantClearanceTests(unittest.TestCase):
    def test_hidden_geometry_may_cross_sector_planes(self):
        triangle = [(0, -100, -100), (1, 100, 0), (2, 0, 100)]
        self.assertIsNone(outboard_margin(triangle, lambda p: p, (1, 1, 1)))

    def test_visible_geometry_cannot_cross_to_neighbour(self):
        triangle = [(200, -1, 5), (200, 2, 5), (210, 2, 6)]
        self.assertEqual(outboard_margin(triangle, lambda p: p, (1, 1, 1)), -1)

    def test_clipping_excludes_hidden_negative_extreme(self):
        triangle = [(0, -20, 10), (200, 10, 10), (200, 20, 10)]
        self.assertGreater(outboard_margin(triangle, lambda p: p, (1, 1, 1)), 0)

    def test_sector_signs_and_linear_mapping(self):
        triangle = [(190, 0, 0), (200, 2, 1), (200, -2, 1)]
        transform = lambda p: (-p[0], p[1]+10, -p[2]-10)
        self.assertGreater(outboard_margin(triangle, transform, (-1, 1, -1)), 0)

    def test_sphere_support_margin(self):
        center, radius = (110, -110, 110), 60
        self.assertEqual(signed_margin([center], (1, -1, 1))-radius, 50)

    def test_invalid_inputs_are_not_certified(self):
        with self.assertRaises(ValueError):
            signed_margin([(1, 2, float('nan'))], (1, 1, 1))
        with self.assertRaises(ValueError):
            signed_margin([(1, 2, 3)], (0, 1, 1))
