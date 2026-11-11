import copy
import math
from pathlib import Path
import unittest

from beholder_contact_path import check_contact_path
from generate_beholder_telescope import COUNT, stage_targets


ZERO = [(0, 0)]*COUNT


def fixture():
    return dict(initial_stages=stage_targets(0.5, True), final_stages=stage_targets(0.5, True),
                final_angles=list(ZERO), contact_tip=(56, 0, 0),
                claw_vertices_tip=[(56, 0, 0)]*12, sphere_center_tip=(56, 0, 0), sphere_radius_world=1,
                origin_world=(0, 0, 0), basis_world=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                translation_world=(0, 0, 0), plane_point=(0, 0, -1000), plane_normal=(0, 0, 1), samples=5)


class ContactPathTests(unittest.TestCase):
    def test_stationary_path_passes_without_motion_permission(self):
        r = check_contact_path(**fixture())
        self.assertTrue(r['sampledChecksPass'])
        self.assertFalse(r['continuousCollisionCertified'])
        self.assertFalse(r['motionAuthorized'])
        self.assertEqual(r['maximumContactDriftCm'], 0)

    def test_perpendicular_body_motion_is_detected(self):
        f = fixture()
        f['translation_world'] = (0, 1, 0)
        r = check_contact_path(**f)
        self.assertIn('contact_drift', r['reasons'])
        self.assertAlmostEqual(r['maximumContactDriftCm'], 1)

    def test_axial_compensation_keeps_contact(self):
        f = fixture()
        f['final_stages'] = stage_targets(0.51, True)
        f['translation_world'] = (-10.4, 0, 0)
        r = check_contact_path(**f)
        self.assertTrue(r['sampledChecksPass'], r)
        self.assertLess(r['maximumContactDriftCm'], 1e-8)

    def test_matching_endpoints_can_hide_intermediate_contact_drift(self):
        f = fixture()
        f['final_angles'][1] = (0, 2)
        lever = 4*104+56
        angle = math.radians(2)
        f['translation_world'] = (lever*(1-math.cos(angle)), -lever*math.sin(angle), 0)
        r = check_contact_path(**f)
        self.assertLess(r['samples'][0]['contactDriftCm'], 1e-8)
        self.assertLess(r['samples'][-1]['contactDriftCm'], 1e-8)
        self.assertGreater(r['maximumContactDriftCm'], 0.01)
        self.assertIn('contact_drift', r['reasons'])

    def test_direct_parent_wall_bound_rejects_excessive_bend(self):
        f = fixture()
        f['final_angles'][1] = (60, 0)
        self.assertIn('direct_parent_wall', check_contact_path(**f)['reasons'])

    def test_retracting_adjacent_to_bent_joint_is_rejected(self):
        f = fixture()
        f['final_stages'] = stage_targets(0.499, True)
        f['final_angles'][4] = (0, 0.1)
        r = check_contact_path(**f)
        self.assertIn('retraction_interlock', r['reasons'])
        self.assertTrue(any(4 in row['blockedRetractingStages'] for row in r['samples']))

    def test_retracting_distal_stage_with_straight_adjacent_joints_is_allowed(self):
        f = fixture()
        f['final_stages'] = stage_targets(0.499, True)
        f['final_angles'][1] = (0, 0.1)
        r = check_contact_path(**f)
        self.assertNotIn('retraction_interlock', r['reasons'])

    def test_nested_bend_envelope_and_root_are_checked(self):
        for index in (0, 9):
            f = fixture()
            f['final_angles'][index] = (0, 0.1)
            self.assertIn('bend_envelope', check_contact_path(**f)['reasons'])

    def test_full_sleeve_floor_geometry_is_checked_not_just_contact(self):
        f = fixture()
        f['plane_point'] = (0, 0, -10)
        r = check_contact_path(**f)
        self.assertNotIn('head_plane', r['reasons'])
        self.assertIn('sleeve_plane', r['reasons'])
        self.assertAlmostEqual(r['minimumSleevePlaneCm'], -40)

    def test_sphere_and_other_claw_vertices_are_checked(self):
        for sphere, vertex in ((2, (56, 0, 0)), (0.5, (56, 0, -2))):
            f = fixture()
            f['plane_point'] = (0, 0, -1)
            f['sphere_radius_world'] = sphere
            f['claw_vertices_tip'][0] = vertex
            self.assertIn('head_plane', check_contact_path(**f)['reasons'])

    def test_initial_and_final_samples_and_no_mutation(self):
        f = fixture()
        before = copy.deepcopy(f)
        r = check_contact_path(**f)
        self.assertEqual(r['samples'][0]['fraction'], 0)
        self.assertEqual(r['samples'][-1]['fraction'], 1)
        self.assertEqual(len(r['samples']), 5)
        self.assertEqual(f, before)

    def test_world_rotation_scale_and_translation_apply_to_all_sleeves(self):
        f = fixture()
        f['origin_world'] = (0, 0, 200)
        f['basis_world'] = ((0, 0, -0.25), (0.25, 0, 0), (0, -0.25, 0))
        f['plane_point'] = (0, 0, 0)
        r = check_contact_path(**f)
        self.assertTrue(r['sampledChecksPass'])
        self.assertAlmostEqual(r['minimumSleevePlaneCm'], 70)
        self.assertAlmostEqual(r['minimumHeadPlaneCm'], 55)
        self.assertEqual(r['maximumContactDriftCm'], 0)

    def test_large_world_coordinates_do_not_get_tiny_numeric_cushion(self):
        f = fixture()
        f['origin_world'] = (1e16, 0, 0)
        r = check_contact_path(**f)['continuousContactPlane']
        self.assertGreater(r['numericalCushionWorldCm'], 0.01)
        self.assertFalse(r['contactBoundPasses'])

    def test_invalid_inputs_raise(self):
        for key, value in (('samples', 1), ('samples', True), ('plane_normal', (0, 0, 2)),
                           ('sphere_radius_world', math.nan), ('claw_vertices_tip', []),
                           ('contact_tolerance', math.inf), ('translation_world', (math.nan, 0, 0)),
                           ('basis_world', ((1, 0, 0), (1, 1, 0), (0, 0, 1))),
                           ('final_stages', [0.5]*10)):
            f = fixture()
            f[key] = value
            with self.assertRaises(ValueError):
                check_contact_path(**f)

    def test_no_editor_actuation(self):
        source = Path(__file__).with_name('beholder_contact_path.py').read_text(encoding='utf-8')
        self.assertNotIn('import unreal', source)
        self.assertNotIn('call_method', source)
