import math
from pathlib import Path
import unittest

from beholder_continuous_bounds import point_curvature_bound, contact_plane_certificate
from beholder_contact_ik import forward_contact
from generate_beholder_telescope import stage_targets


ZERO = [(0, 0)]*10


def rows():
    return [dict(fraction=f, contactDriftCm=0, headPlaneMinimumCm=0, sleevePlaneMinimumCm=10) for f in (0, 1)]


class ContinuousBoundsTests(unittest.TestCase):
    def test_zero_bend_linear_stages_have_zero_curvature_except_rounding(self):
        b = point_curvature_bound([0.5]*10, stage_targets(0.5, True), ZERO, (56, 0, 0))
        self.assertAlmostEqual(b, 0, places=10)

    def test_single_yaw_joint_matches_analytic_second_derivative(self):
        stages = stage_targets(0.5, True)
        angles = list(ZERO)
        angles[1] = (0, 2)
        b = point_curvature_bound(stages, stages, angles, (56, 0, 0))
        expected = (4*104+56)*math.radians(2)**2
        self.assertGreaterEqual(b, expected)
        self.assertAlmostEqual(b, expected, places=10)

    def test_rotating_linear_stroke_includes_mixed_derivative(self):
        a, b, angles = [0]*10, [0]*10, list(ZERO)
        a[1], b[1], angles[1] = 0.3, 0.8, (0, 2)
        bound = point_curvature_bound(a, b, angles, (0, 0, 0))
        expected = 104*(0.8*math.radians(2)**2+math.radians(2))
        self.assertGreaterEqual(bound, expected)
        self.assertAlmostEqual(bound, expected, places=10)

    def test_bound_contains_dense_nonlinear_chord_errors(self):
        initial, final = stage_targets(0.5, True), stage_targets(0.499, True)
        angles = [(0, 0), (0.4, -0.6), (-0.3, 0.5), (0.7, -0.2)]+[(0, 0)]*6
        tip = (56, 12, -17)
        bound = point_curvature_bound(initial, final, angles, tip)
        def at(f):
            stages = [(1-f)*a+f*b for a, b in zip(initial, final)]
            return forward_contact(stages, [(f*p, f*y) for p, y in angles], tip)
        for left, right in ((0, 1), (0.2, 0.3), (0.5, 0.9)):
            a, b = at(left), at(right)
            for j in range(101):
                f = j/100
                chord = tuple((1-f)*x+f*y for x, y in zip(a, b))
                actual = at(left+(right-left)*f)
                self.assertLessEqual(math.dist(actual, chord), bound*(right-left)**2/8+1e-10)

    def test_ancestor_curvature_does_not_include_descendant_angles(self):
        angles = list(ZERO)
        angles[9] = (2, 0)
        b = point_curvature_bound([1]*10, [1]*10, angles, (-112, 50, 0), sleeve_index=0)
        self.assertAlmostEqual(b, 0, places=10)

    def test_dense_second_differences_stay_below_analytic_bound(self):
        initial, final = stage_targets(0.5, True), stage_targets(0.51, True)
        angles = [(0, 0), (0.5, -0.7), (-0.6, 0.8), (0.4, 1.0)]+[(0, 0)]*6
        for point, index in (((56, 12, -17), 9), ((-112, 40, 0), 4), ((0, 50, 0), 0)):
            bound = point_curvature_bound(initial, final, angles, point, index)
            def at(f):
                return forward_contact([(1-f)*a+f*b for a, b in zip(initial, final)],
                                       [(f*p, f*y) for p, y in angles], point, index)
            h = 1e-3
            for j in range(1, 100):
                f = j/100
                a, b, c = at(f-h), at(f), at(f+h)
                second = math.hypot(*((x-2*y+z)/(h*h) for x, y, z in zip(a, b, c)))
                self.assertLessEqual(second, bound+1e-6)

    def test_matching_endpoints_do_not_hide_large_unsampled_arc(self):
        stages = stage_targets(0.5, True)
        angles = list(ZERO)
        angles[1] = (0, 2)
        r = contact_plane_certificate(stages, stages, angles, (56, 0, 0), [(56, 0, 0)]*12,
                                      (56, 0, 0), 1, rows(), 0.01, 0.05)
        self.assertFalse(r['contactBoundPasses'])
        self.assertGreater(r['contactDriftUpperBoundCm'], 0.01)
        self.assertFalse(r['motionAuthorized'])
        self.assertFalse(r['continuousCollisionCertified'])

    def test_finer_sampling_reduces_error_quadratically(self):
        stages, angles = stage_targets(0.5, True), list(ZERO)
        angles[1] = (0, 2)
        def certificate(fractions):
            samples = [dict(fraction=f, contactDriftCm=0, headPlaneMinimumCm=10, sleevePlaneMinimumCm=10) for f in fractions]
            return contact_plane_certificate(stages, stages, angles, (56, 0, 0), [(56, 0, 0)]*12,
                                              (56, 0, 0), 1, samples, 0.01, 0.05)
        a, b = certificate((0, 1)), certificate((0, 0.5, 1))
        self.assertAlmostEqual(a['betweenSampleErrorWorldCm']['contact']-1e-8,
                               4*(b['betweenSampleErrorWorldCm']['contact']-1e-8))

    def test_plane_margin_is_reduced_not_increased(self):
        stages, angles = stage_targets(0.5, True), list(ZERO)
        angles[1] = (2, 0)
        sample_rows = rows()
        for row in sample_rows:
            row['headPlaneMinimumCm'] = -0.049
        r = contact_plane_certificate(stages, stages, angles, (56, 0, 0), [(56, 0, 0)]*12,
                                      (56, 0, 0), 1, sample_rows, 1, 0.05)
        self.assertLess(r['headPlaneLowerBoundCm'], -0.049)
        self.assertFalse(r['headPlaneBoundPasses'])

    def test_invalid_samples_and_metrics_raise(self):
        for sample_rows in ([], rows()[:1], list(reversed(rows())), [rows()[0], rows()[0], rows()[1]],
                            [dict(rows()[0], fraction=math.nan), rows()[1]],
                            [dict(rows()[0], contactDriftCm=-1), rows()[1]]):
            with self.assertRaises(ValueError):
                contact_plane_certificate([0]*10, [0]*10, ZERO, (56, 0, 0), [(56, 0, 0)]*12,
                                          (56, 0, 0), 1, sample_rows, 0.01, 0.05)

    def test_invalid_geometry_scale_and_tolerances_raise(self):
        for scale, vertices, tolerance in ((0, [(0, 0, 0)]*12, 0.01), (math.inf, [(0, 0, 0)]*12, 0.01),
                                            (1, [], 0.01), (1, [(0, 0, 0)]*12, math.nan)):
            with self.assertRaises(ValueError):
                contact_plane_certificate([0]*10, [0]*10, ZERO, (56, 0, 0), vertices,
                                          (56, 0, 0), scale, rows(), tolerance, 0.05)

    def test_no_editor_calls(self):
        source = Path(__file__).with_name('beholder_continuous_bounds.py').read_text(encoding='utf-8')
        self.assertNotIn('import unreal', source)
        self.assertNotIn('call_method', source)
