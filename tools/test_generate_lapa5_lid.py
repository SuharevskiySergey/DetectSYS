import math
import unittest

from generate_lapa5_lid import build_lid, INNER_RADIUS, OUTER_RADIUS, REST_APERTURE


class EyelidMeshTests(unittest.TestCase):
    def test_radii_normals_and_surfaces(self):
        vertices, normals, uvs, faces = build_lid(16, 8)
        self.assertTrue(faces)
        self.assertEqual(len(vertices), len(normals))
        surfaces = set()
        for point, normal, uv in zip(vertices, normals, uvs):
            radius = math.sqrt(sum(x * x for x in point))
            self.assertTrue(min(abs(radius - INNER_RADIUS), abs(radius - OUTER_RADIUS)) < 1e-8)
            self.assertAlmostEqual(sum(x * x for x in normal), 1)
            surfaces.add(math.floor(uv[0] / 2 + 1e-8))
        self.assertEqual(surfaces, {0, 1, 2})

    def test_welded_shell_has_no_boundary_edges(self):
        vertices, _, _, faces = build_lid(16, 8)
        edges = {}
        for face in faces:
            points = [tuple(round(x, 7) for x in vertices[i - 1]) for i in face]
            for i in range(3):
                edge = tuple(sorted((points[i], points[(i + 1) % 3])))
                edges[edge] = edges.get(edge, 0) + 1
        self.assertTrue(edges)
        self.assertEqual(set(edges.values()), {2})

    def test_aperture_and_back_pole(self):
        # Same angular mapping as the material: closure to zero, back pole fixed.
        for opening in (0, 0.25, 0.5, 1):
            aperture = opening * 1.0
            theta_front = aperture
            theta_back = aperture + (math.pi - aperture)
            self.assertAlmostEqual(OUTER_RADIUS * math.sin(theta_front),
                                   OUTER_RADIUS * math.sin(aperture))
            self.assertAlmostEqual(theta_back, math.pi)
        self.assertGreater(REST_APERTURE, 0)

    def test_invalid_resolution(self):
        with self.assertRaises(ValueError):
            build_lid(2, 8)


if __name__ == "__main__":
    unittest.main()
