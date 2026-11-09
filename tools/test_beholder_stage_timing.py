import random
import unittest

from beholder_stage_timing import step
from generate_beholder_telescope import stage_targets


class StageTimingTests(unittest.TestCase):
    def assertStages(self, actual, expected):
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=10)

    def test_no_boundary_frame_is_lost(self):
        self.assertStages(step([0]*10, 1, True, 0.15), [1, 1, 0.5]+[0]*7)
        self.assertStages(step([1]*10, 0, True, 0.15), [1]*7+[0.5, 0, 0])

    def test_full_stroke_matches_elapsed_time_at_different_rates(self):
        for fps in (10, 15, 30, 60, 120, 240):
            for start, target in ((0, 1), (1, 0)):
                stages = [start]*10
                for frame in range(round(0.6*fps)):
                    stages = step(stages, target, True, 1/fps)
                    amount = min(1, (frame+1)/fps/0.6)
                    self.assertStages(stages, stage_targets(amount if target else 1-amount, True))

    def test_partition_invariance_with_mixed_mode_pose(self):
        random.seed(834)
        for _ in range(50):
            stages = [random.random() for _ in range(10)]
            target, elapsed = random.random(), random.random()*0.6
            one = step(stages, target, True, elapsed)
            split = stages
            for _ in range(17):
                split = step(split, target, True, elapsed/17)
            self.assertStages(one, split)

    def test_retraction_queue_does_not_skip_a_blocked_stage(self):
        ready = [True]*10
        ready[8] = False
        after = step([1]*10, 0, True, 10, retract_ready=ready)
        self.assertStages(after, [1]*9+[0])
        self.assertStages(step(after, 0, True, 0, retract_ready=[True]*10), after)

    def test_motion_lock_never_banks_time(self):
        stages = step([0]*10, 1, True, 10, motion_ready=False)
        self.assertStages(stages, [0]*10)
        self.assertStages(step(stages, 1, True, 0.03), [0.5]+[0]*9)

    def test_simultaneous_mode_and_reversal(self):
        stages = step([0]*10, 1, False, 0.15)
        self.assertStages(stages, [0.25]*10)
        self.assertStages(step(stages, 0, False, 0.075), [0.125]*10)
        for sequential in (True, False):
            self.assertStages(step(stages, 0.7, sequential, 0), stages)

    def test_distinct_durations_scale_travel_not_geometry(self):
        for duration in (0.3, 0.8, 1.2, 2.0):
            for sequential in (True, False):
                self.assertStages(step([0]*10, 1, sequential, duration, transition=duration), [1]*10)
                self.assertStages(step([1]*10, 0, sequential, duration, transition=duration), [0]*10)
                after = step([0]*10, 1, sequential, duration/4, transition=duration)
                self.assertAlmostEqual(sum(after)/10, 0.25)

    def test_fast_profile_cannot_bypass_safety_wait(self):
        self.assertStages(step([1]*10, 0, False, 1, transition=0.3,
                               motion_ready=False), [1]*10)
        self.assertStages(step([1]*10, 0, False, 1, transition=0.3,
                               retract_ready=[False]*10), [1]*10)
