import copy
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from beholder_contact_dogleg import dogleg_pose
from beholder_contact_ik import forward_contact
from check_beholder_dogleg_nesting import DoglegMotion, head_certificate, mapped, run, tube_certificate
from generate_beholder_telescope import radius
from test_check_beholder_dogleg_shell import capture


class DoglegNestingIntervalTests(unittest.TestCase):
    def test_relative_frames_agree_with_full_chain_fk(self):
        point=(-112,45,17)
        for e in (0.4,0.49999):
            for axis in ('pitch','yaw'):
                for amplitude in (-1,1):
                    motion=DoglegMotion(e,amplitude,axis)
                    for f in (0.3,0.8):
                        pose=dogleg_pose(e,amplitude*f,axis)
                        for parent in range(10):
                            origin=forward_contact(pose['stages'],pose['angles'],(0,0,0),parent)
                            axes=[]
                            for unit in ((1,0,0),(0,1,0),(0,0,1)):
                                p=forward_contact(pose['stages'],pose['angles'],unit,parent)
                                axes.append(tuple(a-b for a,b in zip(p,origin)))
                            for child in range(parent,10):
                                p=forward_contact(pose['stages'],pose['angles'],point,child)
                                expected=tuple(sum((p[k]-origin[k])*a[k] for k in range(3)) for a in axes)
                                actual=mapped(motion.relative_frame(parent,child,f),point)
                                self.assertLess(math.dist(actual,expected),1e-8)

    def test_relative_motion_bounds_cover_clamp_kinks_and_both_axes(self):
        for axis in ('pitch','yaw'):
            for amplitude in (-1,1):
                motion=DoglegMotion(0.49999,amplitude,axis)
                for parent in range(10):
                    for child in range(parent,10):
                        points=[(-112,radius(child),0),(0,radius(child),0)]
                        speed=motion.speed_bound(parent,child,points)
                        for left,right in ((0,0.2),(0.5,0.7),(0.9,1)):
                            a=motion.relative_frame(parent,child,left)
                            b=motion.relative_frame(parent,child,right)
                            for point in points:
                                self.assertLessEqual(math.dist(mapped(a,point),mapped(b,point)),speed*(right-left)+1e-9)

    def test_expanded_slab_certifies_all_pairs_but_coarse_bound_can_reject(self):
        report=tube_certificate(0.5,1,'yaw',intervals=20)
        self.assertTrue(report['passed'])
        self.assertEqual(report['intervalPairsChecked'],900)
        self.assertGreaterEqual(report['minimumClearanceLowerBoundLocalCm'],0.25)
        self.assertFalse(report['continuousCollisionCertified'])
        coarse=tube_certificate(0.5,1,'yaw',intervals=1)
        self.assertFalse(coarse['passed'])
        self.assertLess(coarse['minimumClearanceLowerBoundLocalCm'],0.25)

    def test_head_sphere_and_claw_bounds_reject_bad_geometry(self):
        geometry=dict(sphere_center_tip=(56,0,0),sphere_radius_local=60,claw_vertices_tip=[(111,0,0)]*12)
        self.assertTrue(head_certificate(0.5,1,'pitch',geometry,intervals=4)['passed'])
        bad=copy.deepcopy(geometry);bad['sphere_radius_local']=120
        self.assertFalse(head_certificate(0.5,1,'pitch',bad,intervals=4)['passed'])
        bad=copy.deepcopy(geometry);bad['claw_vertices_tip']=[(-5,0,0)]*12
        self.assertFalse(head_certificate(0.5,1,'pitch',bad,intervals=4)['passed'])
        far=copy.deepcopy(geometry);far['sphere_center_tip']=(1000,0,0)
        result=head_certificate(0.5,1,'pitch',far,intervals=4)
        self.assertTrue(result['passed'])
        self.assertIsNone(result['minimumSphereClearanceLowerBoundLocalCm'])

    def test_invalid_inputs_cannot_reduce_existing_margin(self):
        for kwargs in (dict(required_margin=0),dict(intervals=True),dict(intervals=0),dict(cushion=0)):
            with self.assertRaises(ValueError):
                tube_certificate(0.5,1,'yaw',**kwargs)
        with self.assertRaises(ValueError):
            DoglegMotion(0.39,1,'yaw')
        with self.assertRaises(ValueError):
            DoglegMotion(0.5,1,'yaw').speed_bound(1,0,[(0,0,0)])
        with self.assertRaises(ValueError):
            DoglegMotion(0.5,1,'yaw').speed_bound(0,1,[(math.nan,0,0)])

    def test_capture_pipeline_reuses_only_identical_tube_geometry(self):
        source=capture();before=copy.deepcopy(source)
        tube=dict(passed=True,intervalPairsChecked=135)
        head=dict(passed=True,intervalSleevesChecked=30)
        with patch('check_beholder_dogleg_nesting.tube_certificate',return_value=tube) as t, \
             patch('check_beholder_dogleg_nesting.head_certificate',return_value=head) as h:
            report=run(source,intervals=3)
        self.assertTrue(report['passed'])
        self.assertEqual(t.call_count,4)
        self.assertEqual(h.call_count,16)
        self.assertEqual(report['tubeIntervalPairsChecked'],540)
        self.assertEqual(source,before)
        self.assertFalse(report['motionAuthorized'])
        with patch('check_beholder_dogleg_nesting.tube_certificate',return_value=tube), \
             patch('check_beholder_dogleg_nesting.head_certificate',return_value=dict(passed=False,intervalSleevesChecked=30)):
            self.assertFalse(run(source,intervals=3)['passed'])

    def test_offline_checker_uses_expanded_slab_and_preserves_source(self):
        source=Path(__file__).with_name('check_beholder_dogleg_nesting.py').read_text(encoding='utf-8')
        for forbidden in ('import unreal','call_method','set_editor_property'):
            self.assertNotIn(forbidden,source)
        self.assertIn('-LENGTH-displacement,displacement',source)
        self.assertIn('args.source.resolve() == args.output.resolve()',source)
        self.assertIn('sourceSha256=hashlib.sha256(data).hexdigest()',source)
