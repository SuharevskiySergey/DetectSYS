import math
from pathlib import Path
import random
import unittest

from beholder_stage_redistribution import plan_straight_redistribution as plan
from generate_beholder_telescope import COUNT, STROKE, bend_angles, fronts_from_stages


ZERO = [(0, 0)]*COUNT


class StageRedistributionTests(unittest.TestCase):
    def test_half_uniform_opens_four_joints_without_endpoint_change(self):
        r = plan([0.5]*COUNT, ZERO)
        self.assertTrue(r['valid'])
        self.assertFalse(r['motionAuthorized'])
        self.assertEqual(r['initialAvailableJoints'], [])
        self.assertEqual(r['targetStages'], [1]*5+[0]*5)
        self.assertEqual(r['targetAvailableJoints'], [dict(index=i, maximumL1Degrees=2) for i in range(1, 5)])
        self.assertLessEqual(r['maximumEndpointDriftLocalCm'], 1e-8)

    def test_all_sampled_stages_bounded_and_endpoint_matches_forward_chain(self):
        rng = random.Random(735)
        for _ in range(100):
            stages = [rng.random() for _ in range(COUNT)]
            r = plan(stages, ZERO)
            expected = fronts_from_stages(stages)[-1]
            for row in r['samples']:
                self.assertTrue(all(0 <= s <= 1 for s in row['stages']))
                self.assertAlmostEqual(fronts_from_stages(row['stages'])[-1], expected, places=9)
                # Existing exposure envelope remains the authority source.
                envelope = bend_angles(row['stages'], 2, 0)
                self.assertEqual(row['availableJoints'], [dict(index=i, maximumL1Degrees=envelope[i][0])
                                                        for i in range(1, COUNT) if envelope[i][0] > 0])

    def test_sequential_input_is_unchanged(self):
        stages = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
        r = plan(stages, ZERO)
        self.assertTrue(all(row['stages'] == tuple(stages) for row in r['samples']))

    def test_fully_folded_has_no_authority_and_full_has_nine(self):
        self.assertEqual(plan([0]*COUNT, ZERO)['targetAvailableJoints'], [])
        self.assertEqual(len(plan([1]*COUNT, ZERO)['targetAvailableJoints']), 9)

    def test_fractional_boundary_uses_existing_smooth_exposure(self):
        r = plan([0.199]*COUNT, ZERO)
        self.assertEqual(r['targetStages'][:3], [1, 0.9900000000000002, 0])
        self.assertEqual(len(r['targetAvailableJoints']), 1)
        self.assertAlmostEqual(r['targetAvailableJoints'][0]['maximumL1Degrees'], 1)

    def test_nonzero_current_bend_rejected_instead_of_straightening(self):
        for joint in range(COUNT):
            angles = list(ZERO)
            angles[joint] = (0.1, 0)
            r = plan([0.5]*COUNT, angles)
            self.assertFalse(r['valid'])
            self.assertEqual(r['reason'], 'articulated_pose_rejected')
            self.assertEqual(r['samples'], [])

    def test_invalid_inputs_raise(self):
        for stages, angles, samples in (([0.5]*9, ZERO, 21), ([math.nan]*10, ZERO, 21),
                                       ([-0.1]*10, ZERO, 21), ([1.1]*10, ZERO, 21),
                                       ([0.5]*10, ZERO[:9], 21), ([0.5]*10, [(0, math.inf)]*10, 21),
                                       ([0.5]*10, ZERO, 1), ([0.5]*10, ZERO, 1002),
                                       ([0.5]*10, ZERO, True)):
            with self.assertRaises(ValueError):
                plan(stages, angles, samples)

    def test_no_editor_commands_and_no_input_mutation(self):
        stages, angles = [0.5]*10, list(ZERO)
        plan(stages, angles)
        self.assertEqual(stages, [0.5]*10)
        self.assertEqual(angles, ZERO)
        source = Path(__file__).with_name('beholder_stage_redistribution.py').read_text(encoding='utf-8')
        self.assertNotIn('import unreal', source)
        self.assertNotIn('call_method', source)

    def test_total_length_is_not_a_timing_certificate(self):
        # Asynchronous runtime movement can violate the constant-sum path.
        r = plan([0.5]*10, ZERO)
        one_stage_first = [0.5]*10
        one_stage_first[0] = r['targetStages'][0]
        self.assertEqual(STROKE*(math.fsum(one_stage_first)-5), 52)
        self.assertFalse(r['motionAuthorized'])
