import math
import unittest

from beholder_dogleg_timing import DoglegTiming
from check_beholder_dogleg_playback import audit, chord_tip_bound


class DoglegPlaybackTests(unittest.TestCase):
    def test_secant_remainder_bound_covers_dense_angles_and_fractions(self):
        from generate_beholder_telescope import STROKE
        for a,b in ((-1,1),(0,1),(-1,0),(0.3,0.9),(0.9,0.3),(1,1)):
            bound=chord_tip_bound(a,b)
            a,b=math.radians(a),math.radians(b)
            for k in range(1001):
                u=k/1000
                error=2*STROKE*abs(math.cos((1-u)*a+u*b)-(1-u)*math.cos(a)-u*math.cos(b))
                self.assertLessEqual(error,bound)

    def test_conditional_bound_covers_fk_and_scales_quadratically(self):
        self.assertAlmostEqual(chord_tip_bound(0,1)-1e-9,4*(chord_tip_bound(0,0.5)-1e-9))
        for e in (0.4,0.49999,0.5,0.9):
            for axis in ('pitch','yaw'):
                schedule=DoglegTiming(e,-1,axis)
                result=audit(schedule,[0,0.37,1,1.63,2],subdivisions=100)
                self.assertTrue(result['sampledErrorsWithinConditionalBound'])
                self.assertLessEqual(result['maximumSampledChordTipErrorLocalCm'],result['conditionalAllFractionChordTipBoundLocalCm'])
                self.assertFalse(result['continuousErrorBoundCertified'])

    def test_bound_rejects_unsupported_angles_and_reduced_cushion(self):
        for a,b in ((True,0),(0,math.nan),(0,1.01)):
            with self.assertRaises(ValueError):
                chord_tip_bound(a,b)
        with self.assertRaises(ValueError):
            chord_tip_bound(0,1,0)

    def test_exact_phase_preserves_tip_but_chord_does_not(self):
        for axis in ('pitch','yaw'):
            for sign in (-1,1):
                schedule=DoglegTiming(0.49999,sign,axis)
                report=audit(schedule,[0,1,2])
                self.assertTrue(report['passed'])
                self.assertGreater(report['maximumSampledChordTipErrorLocalCm'],0.001)
                self.assertLess(report['maximumSampledExactPhaseTipErrorLocalCm'],1e-9)
                self.assertFalse(report['motionAuthorized'])
                self.assertFalse(report['engineInterpolationReproduced'])

    def test_smaller_chords_reduce_sampled_error(self):
        schedule=DoglegTiming()
        coarse=audit(schedule,[k/8 for k in range(17)])
        fine=audit(schedule,[k/32 for k in range(65)])
        self.assertLess(fine['maximumSampledChordTipErrorLocalCm'],coarse['maximumSampledChordTipErrorLocalCm'])
        self.assertGreater(fine['maximumSampledChordTipErrorLocalCm'],0)

    def test_irregular_frames_and_stops_preserve_exact_reference(self):
        schedule=DoglegTiming.fit_duration(0.49999,joint_acceleration_limit=12)
        end=2*schedule.half_duration
        times=sorted(set([0,end*0.013,end*0.17,end*0.71,end]+schedule.report()['stopTimesSeconds']))
        before=list(times)
        report=audit(schedule,times)
        self.assertTrue(report['passed'])
        self.assertEqual(times,before)
        self.assertEqual(report['samples'],(len(times)-1)*9)

    def test_invalid_times_and_sampling_are_rejected(self):
        schedule=DoglegTiming()
        for times in ([0,1],[0,1,1,2],[0,math.nan,2],[0,3,2],[False,1,2]):
            with self.assertRaises(ValueError):
                audit(schedule,times)
        for n in (True,1,101):
            with self.assertRaises(ValueError):
                audit(schedule,[0,2],n)
