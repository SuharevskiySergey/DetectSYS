import math
import unittest

from generate_beholder_housing import (build_shell, INNER_RADIUS, OUTER_RADIUS,
                                      APERTURE_ANGLE, CENTER_X, OUTER_LIP_X,
                                      inner_safe_radius, sphere_clearance)
from generate_beholder_telescope import HEAD_OFFSET, HEAD_SCALE, outer_hull


class HousingTests(unittest.TestCase):
    def test_head_matches_aperture_and_throat_does_not_narrow(self):
        from generate_beholder_housing import (APERTURE_RADIUS, INNER_APERTURE_ANGLE,
                                              PORTAL_START_X, INNER_LIP_X, PORTAL_RADIUS)
        self.assertAlmostEqual(27*HEAD_SCALE, APERTURE_RADIUS)
        self.assertAlmostEqual(INNER_RADIUS*math.sin(INNER_APERTURE_ANGLE), APERTURE_RADIUS)
        self.assertLess(PORTAL_START_X, INNER_LIP_X)
        self.assertGreater(math.sqrt(inner_safe_radius()**2-PORTAL_START_X**2), PORTAL_RADIUS)
        self.assertLess(APERTURE_RADIUS-PORTAL_RADIUS, 0.1)

    def test_welded_shell_is_closed_and_hollow(self):
        vertices, normals, _, faces = build_shell(16, 8)
        edges = {}
        for face in faces:
            points = [tuple(round(x, 7) for x in vertices[i-1]) for i in face]
            for i in range(3):
                edge = tuple(sorted((points[i], points[(i+1)%3])))
                edges[edge] = edges.get(edge, 0)+1
        self.assertEqual(set(edges.values()), {2})
        for p, n in zip(vertices, normals):
            self.assertTrue(min(abs(math.sqrt(sum(x*x for x in p))-r) for r in (INNER_RADIUS, OUTER_RADIUS)) < 1e-7)
            self.assertAlmostEqual(sum(x*x for x in n), 1)

    def test_real_aperture_and_valid_uvs(self):
        vertices, _, uvs, faces = build_shell(16, 8)
        self.assertAlmostEqual(max(v[0] for v in vertices), OUTER_RADIUS*math.cos(APERTURE_ANGLE))
        self.assertLess(max(v[0] for v in vertices), OUTER_RADIUS)
        for face in faces:
            a, b, c = [uvs[i-1] for i in face]
            self.assertGreater(abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])), 1e-10)

    def test_folded_pack_is_inside_and_eye_is_seated_at_equator(self):
        free = inner_safe_radius()
        self.assertGreater(free, 191)
        for i in range(10):
            vertices, _ = outer_hull(i)
            self.assertTrue(all(math.sqrt((p[0]-CENTER_X)**2+p[1]**2+p[2]**2) < free for p in vertices))
        self.assertAlmostEqual(HEAD_OFFSET-CENTER_X, OUTER_LIP_X)
        self.assertTrue(all(v is None or v >= -0.1 for v in
                            sphere_clearance((HEAD_OFFSET-CENTER_X, 0, 0), 27*HEAD_SCALE).values()))

    def test_invalid_resolution(self):
        with self.assertRaises(ValueError):
            build_shell(2, 8)

    def test_eye_sphere_clears_body_along_straight_stroke(self):
        for i in range(1001):
            bounds = sphere_clearance((HEAD_OFFSET-CENTER_X+1040*i/1000, 0, 0), 27*HEAD_SCALE)
            self.assertTrue(all(v is None or v >= -0.1 for v in bounds.values()))


if __name__ == "__main__":
    unittest.main()
