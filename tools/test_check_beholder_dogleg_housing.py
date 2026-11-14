import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from beholder_contact_dogleg import dogleg_pose
from beholder_transfer_shell import check_branch_pose
from check_beholder_dogleg_housing import branch_certificate, primitive_bounds, run
from generate_beholder_housing import OUTER_RADIUS, PORTAL_START_X
from generate_beholder_telescope import clip_axial_slab
from test_check_beholder_dogleg_shell import capture


def geometry():
    return capture()['contactPositionIK'][0]['contacts'][0]['result']['shellGeometryInput']


class DoglegHousingIntervalTests(unittest.TestCase):
    def test_expanded_regions_cover_points_that_enter_between_samples(self):
        g=geometry();faces=[(0,1,2)]
        # The midpoint triangle is beyond the shell, but a <=0.05 shift could
        # move it back into the portal. Ordinary sampled clipping sees nothing.
        vertices=[(OUTER_RADIUS+0.02,70,-1),(OUTER_RADIUS+0.02,70,1),(OUTER_RADIUS+0.03,71,0)]
        self.assertFalse(clip_axial_slab(vertices,PORTAL_START_X,OUTER_RADIUS))
        bound=primitive_bounds(vertices,faces,0.05,g)['marginsLowerLocalCm']
        self.assertLess(bound['portal'],0)
        vertices=[(PORTAL_START_X+0.02,70,-1),(PORTAL_START_X+0.02,70,1),(PORTAL_START_X+0.03,71,0)]
        self.assertFalse(clip_axial_slab(vertices,-1e8,PORTAL_START_X))
        self.assertLess(primitive_bounds(vertices,faces,0.05,g)['marginsLowerLocalCm']['interior'],0)
        vertices=[(PORTAL_START_X-0.02,200,-1),(PORTAL_START_X-0.02,200,1),(PORTAL_START_X-0.03,201,0)]
        self.assertFalse(clip_axial_slab(vertices,PORTAL_START_X,1e8))
        self.assertLess(primitive_bounds(vertices,faces,0.05,g)['marginsLowerLocalCm']['outboard'],0)

    def test_interval_bounds_are_below_dense_sampled_predicates(self):
        g=geometry()
        result=branch_certificate(0.5,1,'yaw',g,intervals=2)
        self.assertTrue(result['passed'])
        for interval in result['intervals']:
            for k in range(5):
                f=interval['fractionStart']+(interval['fractionEnd']-interval['fractionStart'])*k/4
                pose=dogleg_pose(0.5,f,'yaw')
                sample=check_branch_pose(pose['stages'],pose['angles'],**g)
                self.assertTrue(sample['passed'])
                for name,lower in interval['meshMarginsLowerLocalCm'].items():
                    if lower is not None and sample['marginsLocalCm'][name] is not None:
                        self.assertLessEqual(lower,sample['marginsLocalCm'][name]+1e-9)
        self.assertFalse(result['continuousCollisionCertified'])

    def test_bad_geometry_and_incompatible_body_centres_are_not_accepted(self):
        g=geometry();g['octant_signs']=tuple(-v for v in g['octant_signs'])
        self.assertFalse(branch_certificate(0.5,1,'pitch',g,intervals=1)['passed'])
        g=geometry();g['claw_vertices_tip']=[(-1500,0,0)]*12
        self.assertFalse(branch_certificate(0.5,1,'pitch',g,intervals=1)['passed'])
        g=geometry();g['socket_origin_body']=(1,0,0)
        with self.assertRaises(ValueError):
            branch_certificate(0.5,1,'pitch',g,intervals=1)
        with self.assertRaises(ValueError):
            primitive_bounds([(0,0,0)],[(0,0,-1)],0.1,geometry())
        with self.assertRaises(ValueError):
            branch_certificate(0.5,1,'pitch',geometry(),cushion=0)

    def test_all_branch_sign_axis_cases_preserve_capture_and_failure(self):
        source=capture();before=copy.deepcopy(source)
        result=dict(passed=True,minimumMeshMarginsLowerLocalCm=dict(interior=3,portal=9,outboard=60),
                    triangleIntervalEnvelopesChecked=100)
        with patch('check_beholder_dogleg_housing.branch_certificate',return_value=result) as check:
            report=run(source,intervals=3)
        self.assertTrue(report['passed'])
        self.assertEqual(check.call_count,16)
        self.assertEqual(report['triangleIntervalEnvelopesChecked'],1600)
        self.assertEqual(source,before)
        self.assertFalse(report['motionAuthorized'])
        failed=dict(result,passed=False)
        with patch('check_beholder_dogleg_housing.branch_certificate',return_value=failed):
            self.assertFalse(run(source,intervals=3)['passed'])

    def test_checker_is_offline_with_explicit_source_provenance(self):
        source=Path(__file__).with_name('check_beholder_dogleg_housing.py').read_text(encoding='utf-8')
        for forbidden in ('import unreal','call_method','set_editor_property'):
            self.assertNotIn(forbidden,source)
        self.assertIn('PORTAL_START_X+displacement',source)
        self.assertIn('PORTAL_START_X-displacement,OUTER_RADIUS+displacement',source)
        self.assertIn('sourceSha256=hashlib.sha256(data).hexdigest()',source)
        self.assertIn('args.source.resolve() == args.output.resolve()',source)
