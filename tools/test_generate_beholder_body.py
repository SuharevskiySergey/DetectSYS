import math
import unittest

from generate_beholder_body import build_body, inner_safe_radius, portal_free_margin, DIRECTIONS, dot
from generate_beholder_housing import (APERTURE_ANGLE, OUTER_RADIUS, OUTER_LIP_X,
                                      inner_safe_radius as single_safe)
from generate_beholder_telescope import HEAD_SCALE


class BodyGeometryTests(unittest.TestCase):
    def test_closed_manifold_with_eight_through_sockets(self):
        vertices, _, _, faces = build_body(24, 6)
        edges = {}
        used = set()
        for face in faces:
            points = [tuple(round(x, 7) for x in vertices[i-1]) for i in face]
            used.update(points)
            self.assertEqual(len(set(points)), 3)
            for i in range(3):
                edge = tuple(sorted((points[i], points[(i+1)%3])))
                edges[edge] = edges.get(edge, 0)+1
        self.assertEqual(set(edges.values()), {2})
        # A hollow sphere joined through eight rims has genus seven.
        self.assertEqual(len(used)-len(edges)+len(faces), -12)

    def test_no_surface_spans_any_aperture(self):
        vertices, normals, _, faces = build_body(24, 6)
        for point, normal in zip(vertices, normals):
            radius = math.sqrt(dot(point, point))
            self.assertTrue(radius > 191.999)
            self.assertAlmostEqual(dot(normal, normal), 1)
            for direction in DIRECTIONS:
                self.assertLessEqual(dot(point, direction)/radius, math.cos(APERTURE_ANGLE)+1e-9)
        self.assertTrue(faces)

    def test_inner_cavity_is_at_least_as_safe_as_single_socket(self):
        vertices, _, _, faces = build_body()
        self.assertGreaterEqual(inner_safe_radius(vertices, faces), single_safe())
        self.assertEqual(max(p[0] for p in vertices), OUTER_RADIUS)
        self.assertEqual(min(p[0] for p in vertices), -OUTER_RADIUS)

    def test_invalid_resolution(self):
        with self.assertRaises(ValueError):
            build_body(23, 6)

    def test_all_eight_certified_portal_cylinders_are_free(self):
        vertices, _, _, faces = build_body()
        self.assertGreater(portal_free_margin(vertices, faces), 0)

    def test_folded_eye_spheres_do_not_overlap_each_other(self):
        minimum = min(OUTER_LIP_X*math.sqrt(sum((a-b)**2 for a, b in zip(x, y)))
                      for i, x in enumerate(DIRECTIONS) for y in DIRECTIONS[i+1:])
        self.assertGreater(minimum, 2*27*HEAD_SCALE)
