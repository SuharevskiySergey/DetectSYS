import copy
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from beholder_nested_clearance import check_nested_pose, check_nested_transfer
from check_beholder_transfer_nesting import run
from generate_beholder_telescope import WALL, radius, stage_targets


ZERO = [(0, 0)]*10


class NestedClearanceTests(unittest.TestCase):
    def test_head_and_claws_clear_sleeves_in_folded_pose(self):
        head = dict(claw_vertices_tip=[(56, 0, 0)]*12, sphere_center_tip=(56, 0, 0), sphere_radius_local=60)
        r = check_nested_pose([0]*10, ZERO, head_geometry=head)
        self.assertTrue(r['passed'])
        self.assertTrue(r['headChecked'])
        self.assertEqual(r['head']['minimumClawAxialLocalCm'], 56)
        self.assertGreater(r['head']['minimumShellClearanceLocalCm'], 0)

    def test_sleeve_only_success_cannot_hide_invalid_head(self):
        for point, radius in (((-1, 0, 0), 60), ((56, 0, 0), 100)):
            head = dict(claw_vertices_tip=[point]*12, sphere_center_tip=(56, 0, 0), sphere_radius_local=radius)
            r = check_nested_pose([0]*10, ZERO, head_geometry=head)
            self.assertTrue(all(p['boundPasses'] for p in r['pairs']))
            self.assertFalse(r['passed'])
            self.assertFalse(r['head']['passed'])

    def test_folded_nested_tubes_are_not_treated_as_solid_collisions(self):
        r = check_nested_pose([0]*10, ZERO)
        self.assertTrue(r['passed'])
        self.assertEqual(len(r['pairs']), 45)
        self.assertEqual(r['overlappingPairs'], 45)
        self.assertEqual(r['nonadjacentOverlappingPairs'], 36)
        for pair in r['pairs']:
            expected = (radius(pair['ancestor'])-WALL)*math.cos(math.pi/64)-radius(pair['child'])
            self.assertAlmostEqual(pair['clearanceLocalCm'], expected)
        self.assertFalse(r['motionAuthorized'])
        self.assertFalse(r['continuousCollisionCertified'])

    def test_fully_extended_nonadjacent_slabs_do_not_overlap(self):
        r = check_nested_pose([1]*10, ZERO)
        self.assertTrue(r['passed'])
        self.assertEqual(r['overlappingPairs'], 9)
        self.assertEqual(r['nonadjacentOverlappingPairs'], 0)

    def test_half_sequential_checks_all_ancestor_pairs(self):
        r = check_nested_pose(stage_targets(0.5, True), ZERO)
        self.assertTrue(r['passed'])
        self.assertEqual({(p['child'], p['ancestor']) for p in r['pairs']},
                         {(i, j) for i in range(1, 10) for j in range(i)})
        self.assertGreater(r['nonadjacentOverlappingPairs'], 0)

    def test_bent_nested_sleeve_can_violate_wall_certificate(self):
        angles = list(ZERO)
        angles[9] = (2, 0)
        r = check_nested_pose([0]*10, angles)
        self.assertFalse(r['passed'])
        self.assertTrue(any(not p['boundPasses'] for p in r['pairs'] if p['child'] == 9))

    def test_outboard_bend_with_no_ancestor_overlap_is_not_false_solid_hit(self):
        angles = list(ZERO)
        angles[1] = (0.1, 0.1)
        self.assertTrue(check_nested_pose([1]*10, angles)['passed'])

    def test_transfer_samples_endpoints_and_does_not_mutate(self):
        initial, final = [0.5]*10, stage_targets(0.5, True)
        before = copy.deepcopy((initial, final))
        r = check_nested_transfer(initial, final, ZERO, samples=3)
        self.assertTrue(r['passed'])
        self.assertEqual([s['fraction'] for s in r['samples']], [0, 0.5, 1])
        self.assertEqual((initial, final), before)

    def test_existing_wall_margin_cannot_be_weakened(self):
        for margin in (0.249, -1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                check_nested_pose([0]*10, ZERO, margin)

    def test_invalid_snapshots_and_samples_raise(self):
        for stages, angles in (([0]*9, ZERO), ([math.nan]*10, ZERO), ([0]*10, ZERO[:9])):
            with self.assertRaises(ValueError):
                check_nested_pose(stages, angles)
        with self.assertRaises(ValueError):
            check_nested_transfer([0]*10, [0]*10, ZERO, samples=1)
        with self.assertRaises(ValueError):
            check_nested_transfer([0]*9, [0]*10, ZERO)

    def test_runner_refuses_old_failed_or_incomplete_capture(self):
        for source in ({}, {'passed': True, 'running': True, 'restored': True},
                       {'passed': True, 'running': False, 'restored': False},
                       {'passed': True, 'running': False, 'restored': True, 'contactPositionIK': []}):
            with self.assertRaises(ValueError):
                run(source)

    def test_runner_checks_twenty_paths_and_inconsistent_snapshots(self):
        stages = stage_targets(0.5, True)
        pose = dict(converged=True, initialStages=stages, stages=stages, angles=ZERO,
                    sampledTransition={'sampledChecksPass': True},
                    shellGeometryInput=dict(claw_vertices_tip=[(56, 0, 0)]*12,
                                            sphere_center_tip=(56, 0, 0), sphere_radius_local=60))
        source = dict(passed=True, running=False, restored=True,
                      contactPositionIK=[dict(removedIndex=i, contacts=[dict(index=j, result=copy.deepcopy(pose))
                                                                       for j in (0, 2, 4, 6)]) for i in (0, 2, 4, 6)])
        with patch('check_beholder_transfer_nesting.check_nested_transfer', return_value={'passed': True}) as check:
            r = run(source)
            self.assertTrue(r['passed'])
            self.assertEqual(check.call_count, 20)
        source['contactPositionIK'][1]['contacts'][0]['result']['initialStages'][0] = 0.9
        with patch('check_beholder_transfer_nesting.check_nested_transfer', return_value={'passed': True}):
            with self.assertRaises(ValueError):
                run(source)

    def test_no_editor_calls(self):
        for filename in ('beholder_nested_clearance.py', 'check_beholder_transfer_nesting.py'):
            source = Path(__file__).with_name(filename).read_text(encoding='utf-8')
            self.assertNotIn('import unreal', source)
            self.assertNotIn('call_method', source)
