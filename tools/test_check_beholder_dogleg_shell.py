import copy
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from beholder_contact_dogleg import plan_cycle
from check_beholder_dogleg_shell import captured_branches, run
from generate_beholder_body import DIRECTIONS
from generate_beholder_housing import inner_safe_radius
from generate_beholder_telescope import stage_targets


def capture():
    stages = stage_targets(0.5, True)
    contacts = []
    for index in (0, 2, 4, 6):
        n = DIRECTIONS[index]
        xy = math.hypot(n[0], n[1])
        u = (n[1]/xy, -n[0]/xy, 0)
        v = (n[1]*u[2]-n[2]*u[1], n[2]*u[0]-n[0]*u[2], n[0]*u[1]-n[1]*u[0])
        g = dict(claw_vertices_tip=[(111, 0, 0)]*12, sphere_center_tip=(56, 0, 0), sphere_radius_local=60,
                 socket_origin_body=(0, 0, 0), socket_axes_body=(n, u, v),
                 octant_signs=tuple(1 if x > 0 else -1 for x in n))
        contacts.append(dict(index=index, result=dict(initialStages=stages, liveFKErrorLocalCm=0, shellGeometryInput=g)))
    return dict(passed=True, running=False, restored=True,
        transferShellCertificate=dict(innerSafeRadius=inner_safe_radius(), minimumPortalSupportMargin=0.04),
        stageRedistributionGeometry=[dict(index=i, plan=dict(valid=True, initialStages=stages, targetStages=stages))
                                    for i in (0, 2, 4, 6)],
        contactPositionIK=[dict(removedIndex=i, contacts=copy.deepcopy(contacts)) for i in (0, 2, 4, 6)])


class DoglegShellCaptureTests(unittest.TestCase):
    def test_checks_both_axes_for_every_branch_without_mutating_capture(self):
        source = capture()
        before = copy.deepcopy(source)
        cycle = plan_cycle(samples_per_half=3, check_nested=False)
        shell = dict(passed=True, reasons=[], marginsLocalCm=dict(interior=3, portal=9, outboard=60))
        with patch('check_beholder_dogleg_shell.plan_cycle', return_value=cycle) as planner, \
             patch('check_beholder_dogleg_shell.check_branch_pose', return_value=shell) as checker:
            report = run(source, samples_per_half=3)
        self.assertTrue(report['passed'])
        self.assertEqual(len(report['cases']), 8)
        self.assertEqual(planner.call_count, 8)
        self.assertEqual(checker.call_count, 40)
        self.assertTrue(all('head_geometry' in c.kwargs for c in planner.call_args_list))
        self.assertFalse(report['freshLiveGeometry'])
        self.assertFalse(report['motionAuthorized'])
        self.assertEqual(source, before)

    def test_incomplete_mismatched_and_nonfinite_captures_are_rejected(self):
        variants = []
        for key, value in (('passed', False), ('passed', 'true'), ('running', True), ('restored', False)):
            source = capture();source[key] = value;variants.append(source)
        source = capture();source['transferShellCertificate']['innerSafeRadius'] = math.nan;variants.append(source)
        source = capture();source['transferShellCertificate']['innerSafeRadius'] += 1;variants.append(source)
        source = capture();source['contactPositionIK'][0]['contacts'].pop();variants.append(source)
        source = capture();source['contactPositionIK'][1]['contacts'][0]['result']['shellGeometryInput']['sphere_radius_local'] = 61;variants.append(source)
        source = capture();source['stageRedistributionGeometry'][0]['plan']['targetStages'] = [0]*10;variants.append(source)
        source = capture();source['contactPositionIK'][0]['contacts'][0]['result']['shellGeometryInput']['octant_signs'] = (1, 1, 1);variants.append(source)
        for source in variants:
            with self.assertRaises(ValueError):
                captured_branches(source)

    def test_failed_shell_bound_cannot_be_hidden_by_valid_dogleg(self):
        cycle = plan_cycle(samples_per_half=2, check_nested=False)
        shell = dict(passed=False, reasons=['portal'], marginsLocalCm=dict(interior=3, portal=-1, outboard=60))
        with patch('check_beholder_dogleg_shell.plan_cycle', return_value=cycle), \
             patch('check_beholder_dogleg_shell.check_branch_pose', return_value=shell):
            report = run(capture(), samples_per_half=2)
        self.assertFalse(report['passed'])
        self.assertIn('portal', report['reasons'])

    def test_shared_body_certificate_can_be_larger_but_not_smaller_than_model_ball(self):
        source = capture()
        source['transferShellCertificate']['innerSafeRadius'] += 0.1
        self.assertEqual(set(captured_branches(source)), {0, 2, 4, 6})
        source['transferShellCertificate']['innerSafeRadius'] = inner_safe_radius()-0.01
        with self.assertRaises(ValueError):
            captured_branches(source)

    def test_offline_only_and_cli_preserves_source_capture(self):
        for name in ('beholder_contact_dogleg.py', 'check_beholder_dogleg_shell.py'):
            source = Path(__file__).with_name(name).read_text(encoding='utf-8')
            self.assertNotIn('import unreal', source)
            self.assertNotIn('call_method', source)
            self.assertNotIn('set_editor_property', source)
        source = Path(__file__).with_name('check_beholder_dogleg_shell.py').read_text(encoding='utf-8')
        self.assertIn('args.source.resolve() == args.output.resolve()', source)
        self.assertIn('sourceSha256=hashlib.sha256(data).hexdigest()', source)
