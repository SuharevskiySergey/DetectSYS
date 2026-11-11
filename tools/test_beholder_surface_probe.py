import unittest

from beholder_surface_probe import downward_segment, lowest_head_point, head_plane_clearance


class SurfaceProbeTests(unittest.TestCase):
    def claws(self, z=0):
        return [[(i, j, z) for j in range(4)] for i in range(3)]

    def test_sphere_is_conservative_fallback(self):
        result = lowest_head_point((10, 20, 100), 15, self.claws(90))
        self.assertEqual(result, {'point': (10, 20, 85), 'source': 'sphereEnvelope'})

    def test_independent_claw_vertex_can_be_lowest(self):
        claws = self.claws(100)
        claws[2][3] = (7, 8, 20)
        result = lowest_head_point((0, 0, 100), 15, claws)
        self.assertEqual(result['point'], (7, 8, 20))
        self.assertEqual(result['source'], 'claw2.vertex3')

    def test_world_radius_and_translation(self):
        self.assertEqual(lowest_head_point((0, 0, 600), 15, self.claws(600))['point'][2], 585)
        self.assertEqual(lowest_head_point((0, 0, 600), 60, self.claws(600))['point'][2], 540)

    def test_tie_is_stable(self):
        self.assertEqual(lowest_head_point((0, 0, 10), 10, self.claws())['source'], 'sphereEnvelope')

    def test_segment_is_world_vertical(self):
        self.assertEqual(downward_segment((7, 8, 20), 100, 2), ((7, 8, 22), (7, 8, -80)))

    def test_invalid_geometry_is_rejected(self):
        for radius in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                lowest_head_point((0, 0, 0), radius, self.claws())
        with self.assertRaises(ValueError):
            lowest_head_point((0, 0, 0), 1, [])
        claws = self.claws()
        claws[0][0] = (0, 0, float('nan'))
        with self.assertRaises(ValueError):
            lowest_head_point((0, 0, 0), 1, claws)

    def test_invalid_trace_settings_are_rejected(self):
        for distance, lift in ((0, 1), (-1, 1), (1, -1), (float('inf'), 0)):
            with self.assertRaises(ValueError):
                downward_segment((0, 0, 0), distance, lift)

    def test_horizontal_plane_matches_lowest_height(self):
        result = head_plane_clearance((0, 0, 100), 15, self.claws(100), (0, 0, 20), (0, 0, 3))
        self.assertAlmostEqual(result['normalClearance'], 65)

    def test_slope_support_differs_from_world_bottom(self):
        result = head_plane_clearance((0, 0, 100), 15, self.claws(100), (0, 0, 0), (3, 0, 4))
        self.assertAlmostEqual(result['normalClearance'], 65)
        self.assertEqual(result['support']['point'], (-9, 0, 88))

    def test_side_claw_can_cross_plane_while_bottom_ray_is_clear(self):
        claws = self.claws(100)
        claws[1][2] = (-200, 0, 100)
        result = head_plane_clearance((0, 0, 100), 15, claws, (0, 0, 0), (3, 0, 4))
        self.assertAlmostEqual(result['normalClearance'], -40)
        self.assertEqual(result['support']['source'], 'claw1.vertex2')
        self.assertEqual(lowest_head_point((0, 0, 100), 15, claws)['point'][2], 85)

    def test_plane_translation_does_not_change_clearance(self):
        result = head_plane_clearance((10, 20, 130), 15,
                                      [[(x+10, y+20, z+30) for x, y, z in c] for c in self.claws(100)],
                                      (10, 20, 30), (3, 0, 4))
        self.assertAlmostEqual(result['normalClearance'], 65)

    def test_degenerate_normal_rejected(self):
        with self.assertRaises(ValueError):
            head_plane_clearance((0, 0, 100), 15, self.claws(100), (0, 0, 0), (0, 0, 0))
