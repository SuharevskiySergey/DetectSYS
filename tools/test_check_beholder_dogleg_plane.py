import copy
import math
from pathlib import Path
import unittest

from beholder_contact_dogleg import dogleg_pose
from beholder_contact_ik import forward_contact
from check_beholder_dogleg_plane import (archived_world_frame, certificate, mapped, run,
                                         sleeve_curvature_bound, socket_scale_bound, split_fractions, to_body)
from test_check_beholder_dogleg_shell import capture


def world_capture():
    source = capture()
    origin = (-100, 200, 120)
    a = math.radians(30)
    basis = ((0.25*math.cos(a),0.25*math.sin(a),0),
             (-0.25*math.sin(a),0.25*math.cos(a),0),(0,0,0.25))
    for transfer in source['contactPositionIK']:
        for row in transfer['contacts']:
            pose = row['result']
            pose['tipPointLocal'] = (222,0,0)
            pose['shellGeometryInput']['claw_vertices_tip'] = [(222,0,0)]*12
    source['singleContactReleaseGeometry'] = dict(referenceWorld=origin)
    source['contacts'] = []
    for row in source['contactPositionIK'][0]['contacts']:
        pose = row['result']
        local = forward_contact(pose['initialStages'],[(0,0)]*10,pose['tipPointLocal'])
        point = mapped(to_body(local,pose['shellGeometryInput']),origin,basis)
        source['contacts'].append(dict(index=row['index'],point=point,verticalGapCm=0,clearanceCm=0))
    return source, origin, basis


class DoglegPlaneTests(unittest.TestCase):
    def test_world_map_is_reconstructed_from_all_four_anchors(self):
        source,origin,basis = world_capture()
        result = archived_world_frame(source)
        self.assertEqual(tuple(result['bodyOriginWorld']),origin)
        self.assertLess(result['maximumAnchorResidualWorldCm'],1e-10)
        for a,b in zip(result['bodyBasisWorld'],basis):
            self.assertLess(math.dist(a,b),1e-12)
        self.assertGreaterEqual(result['bodyScaleBound'],0.25)

    def test_inconsistent_reference_plane_world_map_and_socket_are_rejected(self):
        source,_,_ = world_capture()
        bad = copy.deepcopy(source)
        bad['contacts'][0]['point'] = tuple(v+20 if k==0 else v for k,v in enumerate(bad['contacts'][0]['point']))
        with self.assertRaises(ValueError):
            archived_world_frame(bad)
        bad = copy.deepcopy(source)
        bad['contacts'][0]['verticalGapCm'] = 0.001
        bad['contacts'][0]['clearanceCm'] = 0.001
        with self.assertRaises(ValueError):
            archived_world_frame(bad)
        g = copy.deepcopy(source['contactPositionIK'][0]['contacts'][0]['result']['shellGeometryInput'])
        g['socket_axes_body'] = [(1,0,0),(1,0,0),(0,0,1)]
        with self.assertRaises(ValueError):
            socket_scale_bound(g)
        bad = copy.deepcopy(source)
        for transfer in bad['contactPositionIK']:
            for row in transfer['contacts']:
                row['result']['shellGeometryInput']['sphere_radius_local'] = -60
        with self.assertRaises(ValueError):
            run(bad,samples=2)

    def test_stage_boundary_kink_is_split_and_cannot_be_ignored(self):
        fractions,critical = split_fractions(0.49999,1,samples=2)
        self.assertEqual(len(critical),1)
        self.assertTrue(0<critical[0]<1)
        self.assertEqual(fractions,[0,critical[0],1])
        def row(f):
            return dict(fraction=f,contactDriftCm=0,headPlaneMinimumCm=0,sleevePlaneMinimumCm=1)
        with self.assertRaisesRegex(ValueError,'kink'):
            certificate(0.49999,1,[row(0),row(1)],0.25,1e-5)
        bound = certificate(0.49999,1,[row(f) for f in fractions],0.25,1e-5)
        self.assertTrue(bound['contactAndReferencePlaneBoundPasses'])
        self.assertFalse(bound['linearStageInterpolationAssumed'])
        self.assertFalse(bound['continuousCollisionCertified'])

    def test_curvature_bounds_dominate_numerical_second_derivatives(self):
        point=(-112,45,17)
        h=0.001
        for axis in ('pitch','yaw'):
            for i in range(10):
                bound=sleeve_curvature_bound(i,point,1)
                for f in (0.1,0.3,0.9):
                    values=[]
                    for t in (f-h,f,f+h):
                        pose=dogleg_pose(0.49999,t,axis)
                        values.append(forward_contact(pose['stages'],pose['angles'],point,i))
                    derivative=math.hypot(*( (values[0][k]-2*values[1][k]+values[2][k])/(h*h) for k in range(3)))
                    self.assertLessEqual(derivative,bound+1e-5)

    def test_plane_failure_and_invalid_metrics_cannot_pass(self):
        rows=[dict(fraction=f,contactDriftCm=0,headPlaneMinimumCm=0,sleevePlaneMinimumCm=1) for f in (0,1)]
        rows[-1]['sleevePlaneMinimumCm']=-1
        self.assertFalse(certificate(0.5,1,rows,0.25,1e-5)['contactAndReferencePlaneBoundPasses'])
        rows[-1]['sleevePlaneMinimumCm']=math.nan
        with self.assertRaises(ValueError):
            certificate(0.5,1,rows,0.25,1e-5)
        with self.assertRaises(ValueError):
            sleeve_curvature_bound(1,(math.inf,0,0),1)

    def test_reference_plane_pipeline_preserves_capture_and_never_authorizes_runtime(self):
        source,_,_=world_capture()
        before=copy.deepcopy(source)
        report=run(source,samples=2)
        self.assertTrue(report['passed'])
        self.assertEqual(len(report['cases']),16)
        self.assertEqual(source,before)
        self.assertTrue(report['horizontalReferencePlaneOnly'])
        for key in ('freshLiveGeometry','terrainMeshChecked','continuousCollisionCertified','runtimeIKExecuted','motionAuthorized'):
            self.assertFalse(report[key])

    def test_offline_checker_does_not_reuse_linear_path_certificate_or_actuate(self):
        source = Path(__file__).with_name('check_beholder_dogleg_plane.py').read_text(encoding='utf-8')
        for forbidden in ('import unreal','call_method','set_editor_property','contact_plane_certificate'):
            self.assertNotIn(forbidden,source)
        self.assertIn('args.source.resolve() == args.output.resolve()',source)
        self.assertIn('sourceSha256=hashlib.sha256(data).hexdigest()',source)
