import math
import json
from pathlib import Path
import unittest

from generate_beholder_telescope import (COUNT, LENGTH, STROKE, WALL, build_sleeve,
                                        fronts, radius, stage_targets, fronts_from_stages, HEAD_OFFSET, HEAD_SCALE)
from generate_beholder_telescope import bend_angles, joint_clearance, BEND_WALL_MARGIN
from generate_beholder_telescope import outer_hull, clip_axial_slab
from generate_beholder_telescope import head_shell_clearance
from generate_beholder_telescope import joint_targets, step_joint, retraction_allowed


class TelescopeGeometryTests(unittest.TestCase):
    def test_equal_lengths_and_radial_clearance(self):
        for i in range(COUNT):
            vertices, _, _, _ = build_sleeve(i, 16)
            self.assertEqual(max(v[0] for v in vertices) - min(v[0] for v in vertices), LENGTH)
            if i + 1 < COUNT:
                self.assertAlmostEqual(radius(i) - WALL - radius(i + 1), 0.75)

    def test_closed_manifold_and_winding(self):
        vertices, normals, _, faces = build_sleeve(0, 16)
        edges = {}
        for face in faces:
            p = [vertices[i - 1] for i in face]
            a, b = [p[1][i] - p[0][i] for i in range(3)], [p[2][i] - p[0][i] for i in range(3)]
            cross = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
            normal = normals[face[0] - 1]
            self.assertGreater(sum(cross[i]*normal[i] for i in range(3)), 0)
            points = [tuple(round(x, 7) for x in row) for row in p]
            for i in range(3):
                edge = tuple(sorted((points[i], points[(i + 1) % 3])))
                edges[edge] = edges.get(edge, 0) + 1
        self.assertEqual(set(edges.values()), {2})

    def test_overlap_and_retracted_envelope(self):
        for amount in (0, 0.1, 0.5, 1):
            positions = fronts(amount)
            for left, right in zip(positions, positions[1:]):
                self.assertGreaterEqual(left - (right - LENGTH), 8)
            self.assertAlmostEqual(positions[-1], COUNT * STROKE * amount)
        self.assertEqual(fronts(0), [0]*COUNT)
        self.assertEqual(fronts(-1), fronts(0))
        self.assertEqual(fronts(2), fronts(1))

    def test_sleeve_is_hollow(self):
        vertices, normals, _, _ = build_sleeve(9)
        radii = {round(math.hypot(v[1], v[2]), 6) for v in vertices}
        self.assertEqual(radii, {radius(9), radius(9)-WALL})
        self.assertTrue(all(abs(sum(x*x for x in n)-1) < 1e-10 for n in normals))

    def test_uv_triangles_are_not_degenerate(self):
        _, _, uvs, faces = build_sleeve(0, 16)
        for face in faces:
            a, b, c = [uvs[i - 1] for i in face]
            area = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
            self.assertGreater(abs(area), 1e-8)

    def test_sequential_stages_preserve_total_stroke(self):
        for extension in (0, 0.05, 0.25, 0.55, 0.95, 1):
            for sequential in (False, True):
                stages = stage_targets(extension, sequential)
                positions = fronts_from_stages(stages)
                self.assertAlmostEqual(positions[-1], extension * COUNT * STROKE)
                for left, right in zip(positions, positions[1:]):
                    self.assertGreaterEqual(left - (right - LENGTH), 8 - 1e-8)
        self.assertEqual(stage_targets(0.55, True), [1]*5 + [0.5] + [0]*4)
        self.assertEqual(stage_targets(0.5, False), [0.5]*COUNT)

    def test_head_shell_fits_but_overlaps_sleeve_axially(self):
        from generate_lapa5_lid import OUTER_RADIUS
        self.assertAlmostEqual(OUTER_RADIUS*HEAD_SCALE, 60)
        self.assertLess(HEAD_OFFSET, OUTER_RADIUS*HEAD_SCALE)
        self.assertGreater(head_shell_clearance(9, (HEAD_OFFSET, 0, 0), OUTER_RADIUS*HEAD_SCALE), 1.8)
        self.assertLess(head_shell_clearance(9, (14, 0, 0), OUTER_RADIUS*HEAD_SCALE), 0)

    def test_claw_fixture_contains_three_non_degenerate_tetrahedra(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/lapa5_claw_vertices.json").read_text(encoding="utf-8"))
        self.assertEqual(set(fixture["bones"]), {"Circle_004", "Circle_003", "Circle_005"})
        for vertices in fixture["bones"].values():
            self.assertEqual(len(vertices), 4)
            self.assertTrue(all(len(v) == 3 and all(math.isfinite(x) for x in v) for v in vertices))
            a, b, c = [[v[i]-vertices[0][i] for i in range(3)] for v in vertices[1:]]
            cross = (b[1]*c[2]-b[2]*c[1], b[2]*c[0]-b[0]*c[2], b[0]*c[1]-b[1]*c[0])
            self.assertGreater(abs(sum(a[i]*cross[i] for i in range(3))), 1e-6)

    def test_bend_only_nearly_exposed_and_root_stays_straight(self):
        for amount in (0, 0.5, 0.98):
            self.assertEqual(bend_angles([amount]*COUNT, 2, 2), [(0, 0)]*COUNT)
        angles = bend_angles([1]*COUNT, 10, -10)
        self.assertEqual(angles[0], (0, 0))
        self.assertEqual(angles[1:], [(1, -1)]*9)
        self.assertEqual(bend_angles([1, 0]+[1]*8, 2, 0)[1:3], [(0, 0), (0, 0)])

    def test_bend_clearance_through_exposure_range(self):
        for step in range(1001):
            extension = step/1000
            for i, (pitch, yaw) in enumerate(bend_angles([extension]*COUNT, 50, -50)):
                if i:
                    self.assertGreaterEqual(joint_clearance(i, extension, pitch, yaw), BEND_WALL_MARGIN)

    def test_axial_clipping_includes_edge_intersections(self):
        clipped = clip_axial_slab([(-120, 0, 0), (10, 30, 0), (10, 0, 30)])
        self.assertTrue(clipped)
        self.assertTrue(all(-112 <= p[0] <= 0 for p in clipped))
        self.assertTrue(any(abs(p[0]) < 1e-9 for p in clipped))
        self.assertTrue(any(abs(p[0]+112) < 1e-9 for p in clipped))
        self.assertEqual(clip_axial_slab([(1, 0, 0), (2, 1, 0), (2, 0, 1)]), [])

    def test_outer_envelope_is_closed(self):
        vertices, faces = outer_hull(9, 16)
        edges = {}
        for face in faces:
            for i in range(3):
                edge = tuple(sorted((face[i], face[(i+1)%3])))
                edges[edge] = edges.get(edge, 0)+1
        self.assertEqual(set(edges.values()), {2})
        self.assertEqual(min(p[0] for p in vertices), -112)

    def test_retraction_requests_straight_joints(self):
        stages = [1]*10
        for sequential in (True, False):
            self.assertEqual(joint_targets(stages, 1, 1, 0, sequential), [(0, 0)]*10)
        self.assertEqual(joint_targets(stages, 1, 1, 1, True)[1:], [(1, 1)]*9)

    def test_joint_step_obeys_angular_speed_and_no_overshoot(self):
        for current, target in [((1, 1), (0, 0)), ((2, 0), (-2, 0)), ((-1, 1), (1, -1))]:
            for dt in (0, 1/120, 1/30, 0.333):
                after = step_joint(current, target, dt, 6)
                self.assertLessEqual(sum(abs(after[i]-current[i]) for i in range(2)), 6*dt+1e-9)
                self.assertTrue(all(min(current[i], target[i]) <= after[i] <= max(current[i], target[i])
                                    for i in range(2)))

    def test_sleeve_waits_for_both_adjacent_joints(self):
        stages = [1]*10
        joints = [(0, 0)]*10
        joints[2] = (0.5, 0)
        self.assertTrue(retraction_allowed(0, stages, 0, False, joints))
        self.assertFalse(retraction_allowed(1, stages, 0, False, joints))
        self.assertFalse(retraction_allowed(2, stages, 0, False, joints))
        joints[2] = (0, 0)
        self.assertTrue(retraction_allowed(1, stages, 0, False, joints))


if __name__ == "__main__":
    unittest.main()
