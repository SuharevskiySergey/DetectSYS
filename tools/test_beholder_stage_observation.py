import math
import unittest

from beholder_stage_observation import StageObservation
from beholder_native_stage_observation import NativeStageObservation, TOLERANCE


def telemetry(samples=0, update=0, direction=0, last=0, maximum=0, **extra):
    return dict(Samples=samples, LastUpdate=update, Direction=direction, Last=last,
                Maximum=maximum, MaximumExcess=0, Violation=False, Invalid=False, **extra)


class StageObservationTests(unittest.TestCase):
    def test_fractional_paths_both_directions_and_irregular_observation(self):
        for e in (0.1, 0.2, 0.333333, 0.5, 0.9):
            uniform = [e]*10
            packed = [max(0, min(1, 10*e-i)) for i in range(10)]
            for a, b in ((uniform, packed), (packed, uniform)):
                audit = StageObservation(a, b, 1, 0.5, 0.5)
                for t in (0, 0.01, 0.01, 0.2, 0.7, 1, 1):
                    audit.observe([x+(y-x)*t for x, y in zip(a, b)], t)
                self.assertEqual(audit.report['sampledWindows'], 4)
                self.assertFalse(audit.report['continuousCertified'])
                self.assertLess(audit.report['maximumAffineError'], 1e-12)
        # Two legal native updates can exceed a ONE-update cap when an
        # observer snapshot is missing, while profile/affine audits still pass.
        a = [max(0, min(1, 10*0.333333-i)) for i in range(10)]
        b = [0.333333]*10
        audit = StageObservation(a, b, 1, 0.5, 0.5)
        at = lambda t: [x+(y-x)*t for x,y in zip(a,b)]
        audit.observe(at(0.015), 0.015)
        self.assertLessEqual(audit.report['maximumStageDelta'], 0.01+2e-6)
        audit.observe(at(0.045), 0.045)
        self.assertGreater(audit.report['maximumStageDelta'], 0.01+2e-6)
        self.assertLess(audit.report['maximumAffineError'], 1e-12)
        native = NativeStageObservation(telemetry(), [0]*10, 1, 0.01)
        native.observe(telemetry(3, 3, 1, 0.01, 0.01), [0.03]+[0]*9, 3)
        self.assertEqual(native.report['skippedNativeObservations'], 2)
        self.assertTrue(native.report['perAppliedUpdateStepCapVerified'])
        self.assertAlmostEqual(native.report['maximumSampledWindowDelta'], 0.03)
        # A reverse motion gets its own baseline; lifetime maxima are not reset.
        reverse = NativeStageObservation(telemetry(100, 50, 1, 0.1, 0.1), [0.4]*10, -1, 0.01)
        reverse.observe(telemetry(103, 3, -1, 0.01, 0.1), [0.37]+[0.4]*9, 3)
        self.assertEqual(reverse.report['sampleBaseline'], 100)

    def test_profile_overrun_rejected_even_on_correct_affine_path(self):
        audit = StageObservation([0.5]*10, [1]*5+[0]*5, 0.1, 1, 1)
        with self.assertRaisesRegex(ValueError, 'profile budget'):
            audit.observe([1]*5+[0]*5, 0.1)
        native = NativeStageObservation(telemetry(), [0]*10, 1, 0.01)
        for changed in (dict(Violation=True), dict(Invalid=True), dict(MaximumExcess=3e-6),
                        dict(Samples=0), dict(LastUpdate=0), dict(Direction=-1),
                        dict(Last=0.02, Maximum=0.02), dict(Last=math.nan)):
            sample = telemetry(1, 1, 1, 0.01, 0.01); sample.update(changed)
            with self.assertRaises(ValueError):
                native.observe(sample, [0.01]+[0]*9, 1)
            self.assertEqual(native.updates, 0)
        # Native claims alone cannot excuse an inconsistent observed window.
        with self.assertRaisesRegex(ValueError, 'window_budget'):
            native.observe(telemetry(1, 1, 1, 0.01, 0.01), [0.03]+[0]*9, 1)

    def test_teleport_and_nonconservation_rejected_without_advancing(self):
        audit = StageObservation([0.5]*10, [1]*5+[0]*5, 1, 0.5, 0.5)
        for stages, t in (([1]*5+[0]*5, 0), ([0.6]*10, 0.2), ([math.nan]*10, 0.2), ([0.5]*9, 0.2)):
            with self.assertRaises(ValueError):
                audit.observe(stages, t)
            self.assertEqual(audit.elapsed, 0)
        native = NativeStageObservation(telemetry(), [0]*10, 1, 0.01)
        sample = telemetry(1, 1, 1, 0.01, 0.01)
        native.observe(sample, [0.01]+[0]*9, 1)
        native.observe(sample, [0.01]+[0]*9, 1)
        for bad in ({}, dict(sample, Samples=True), dict(sample, Invalid=0)):
            with self.assertRaises(ValueError):
                native.observe(bad, [0.01]+[0]*9, 1)
        with self.assertRaisesRegex(ValueError, 'update_regression'):
            native.observe(sample, [0.01]+[0]*9, 0)
        with self.assertRaisesRegex(ValueError, 'window_budget'):
            native.observe(sample, [0.02]+[0]*9, 1)
        baseline = telemetry(5, 5, 1, 0.01, 0.02)
        native = NativeStageObservation(baseline, [0]*10, 1, 0.01)
        with self.assertRaisesRegex(ValueError, 'counter_regression'):
            native.observe(telemetry(6, 1, 1, 0.01, 0.01), [0.01]+[0]*9, 1)

    def test_invalid_profiles_and_snapshots(self):
        for args in (([0]*9, [0]*10, 1, 1, 1), ([0]*10, [1]*10, 1, 1, 1),
                     ([0]*10, [0]*10, math.inf, 1, 1), ([0]*10, [0]*10, 1, 0, 1)):
            with self.assertRaises(ValueError):
                StageObservation(*args)
        self.assertEqual(TOLERANCE, 2e-6)
        for direction, cap in ((True, 0.01), (0, 0.01), (1, math.nan), (1, 0), (1, True)):
            with self.assertRaises(ValueError):
                NativeStageObservation(telemetry(), [0]*10, direction, cap)
