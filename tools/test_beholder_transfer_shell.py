import copy
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from beholder_transfer_shell import check_branch_pose, check_transfer
from check_beholder_transfer_shell import run
from generate_beholder_telescope import stage_targets


ZERO = [(0, 0)]*10


def geometry():
    a, b = 1/math.sqrt(3), 1/math.sqrt(2)
    return dict(claw_vertices_tip=[(56, 0, 0)]*12, sphere_center_tip=(56, 0, 0), sphere_radius_local=60,
                socket_origin_body=(0, 0, 0),
                socket_axes_body=((a, a, a), (b, -b, 0), (a*b, a*b, -2*a*b)), octant_signs=(1, 1, 1))


class TransferShellTests(unittest.TestCase):
    def test_offline_runner_checks_initial_redistribution_and_all_ik_paths(self):
        stages = stage_targets(0.5, True)
        pose = dict(converged=True, initialStages=stages, stages=stages, angles=ZERO,
                    sampledTransition={'sampledChecksPass': True}, shellGeometryInput=geometry())
        source = dict(passed=True, running=False, restored=True,
                      transferShellCertificate=dict(minimumPortalSupportMargin=0.04, innerSafeRadius=191),
                      stageRedistributionGeometry=[dict(index=i, plan=dict(valid=True, initialStages=stages)) for i in (0, 2, 4, 6)],
                      contactPositionIK=[dict(removedIndex=i, contacts=[dict(index=j, result=pose) for j in (0, 2, 4, 6)])
                                         for i in (0, 2, 4, 6)])
        with patch('check_beholder_transfer_shell.check_transfer', return_value={'passed': True}) as check:
            result = run(source)
            self.assertEqual(check.call_count, 20)
            self.assertEqual(len(result['redistributions']), 4)
            self.assertEqual(len(result['checks']), 16)
            self.assertTrue(result['passed'])
        bad = copy.deepcopy(source)
        bad['stageRedistributionGeometry'][0]['plan']['initialStages'] = [0.9]+stages[1:]
        with self.assertRaises(ValueError):
            run(bad)

    def test_straight_half_extension_fits_shell_and_sector(self):
        r = check_branch_pose(stage_targets(0.5, True), ZERO, **geometry())
        self.assertTrue(r['passed'], r)
        self.assertEqual(r['trianglesChecked'], 2572)
        self.assertFalse(r['motionAuthorized'])
        self.assertFalse(r['continuousCollisionCertified'])
        self.assertGreater(r['marginsLocalCm']['outboard'], 0)

    def test_folded_sphere_preserves_existing_polygon_seat_allowance(self):
        r = check_branch_pose([0]*10, ZERO, **geometry())
        self.assertTrue(r['passed'], r)
        self.assertLess(r['sphereClearanceLocalCm']['portal'], 0)
        self.assertGreaterEqual(r['sphereClearanceLocalCm']['portal'], -0.1)

    def test_small_bend_can_stay_inside_separating_octant(self):
        angles = list(ZERO)
        angles[1] = (0.1, -0.1)
        self.assertTrue(check_branch_pose(stage_targets(0.5, True), angles, **geometry())['passed'])

    def test_wrong_octant_is_rejected(self):
        g = geometry()
        g['octant_signs'] = (-1, -1, -1)
        r = check_branch_pose(stage_targets(0.5, True), ZERO, **g)
        self.assertIn('outboard_octant', r['reasons'])
        self.assertIn('sphere_octant', r['reasons'])

    def test_claw_escaping_inner_ball_is_rejected(self):
        g = geometry()
        g['claw_vertices_tip'][0] = (-1500, 0, 0)
        self.assertIn('inner_cavity', check_branch_pose(stage_targets(0.5, True), ZERO, **g)['reasons'])

    def test_sleeves_crossing_portal_are_rejected(self):
        angles = list(ZERO)
        angles[0] = (0, 25)
        self.assertIn('portal', check_branch_pose(stage_targets(0.5, True), angles, **geometry())['reasons'])

    def test_sphere_seat_allowance_is_not_unbounded(self):
        g = geometry()
        g['sphere_radius_local'] = 61
        self.assertIn('sphere_portal', check_branch_pose([0]*10, ZERO, **g)['reasons'])

    def test_transfer_samples_endpoints_and_preserves_inputs(self):
        g, stages = geometry(), stage_targets(0.5, True)
        before = copy.deepcopy(g)
        r = check_transfer(stages, stages, ZERO, g, samples=3)
        self.assertTrue(r['passed'])
        self.assertEqual([s['fraction'] for s in r['samples']], [0, 0.5, 1])
        self.assertEqual(g, before)

    def test_bad_map_geometry_and_sample_count_raise(self):
        for key, value in (('socket_axes_body', ((2, 0, 0), (0, 1, 0), (0, 0, 1))),
                           ('socket_axes_body', ((1, 0, 0), (1, 0, 0), (0, 0, 1))),
                           ('claw_vertices_tip', []), ('sphere_radius_local', math.nan),
                           ('sphere_center_tip', (0, math.inf, 0)), ('octant_signs', (1, 0, 1))):
            g = geometry()
            g[key] = value
            with self.assertRaises(ValueError):
                check_branch_pose(stage_targets(0.5, True), ZERO, **g)
        with self.assertRaises(ValueError):
            check_transfer([0]*10, [0]*10, ZERO, geometry(), samples=1)
        with self.assertRaises(ValueError):
            check_transfer([0]*9, [0]*10, ZERO, geometry())

    def test_incomplete_or_failed_capture_cannot_pass_offline_regression(self):
        for source in ({}, {'passed': True, 'running': True, 'restored': True},
                       {'passed': True, 'running': False, 'restored': False},
                       {'passed': True, 'running': False, 'restored': True, 'contactPositionIK': []}):
            with self.assertRaises(ValueError):
                run(source)

    def test_no_editor_actuation(self):
        for filename in ('beholder_transfer_shell.py', 'check_beholder_transfer_shell.py'):
            source = Path(__file__).with_name(filename).read_text(encoding='utf-8')
            self.assertNotIn('import unreal', source)
            self.assertNotIn('call_method', source)
