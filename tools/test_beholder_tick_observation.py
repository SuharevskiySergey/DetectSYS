import math
import unittest

from beholder_tick_observation import observe


class TickObservationTests(unittest.TestCase):
    def test_single_windows_and_passive_duplicates(self):
        t = {}
        observe(t, 0, 0)
        observe(t, 1, 0.02)
        observe(t, 2, 0.05)
        before = dict(t)
        observe(t, 2, 0.05)
        self.assertEqual(t, before)
        self.assertEqual(t['singleUpdateWindows'], 2)
        self.assertAlmostEqual(t['maximumSingleUpdateElapsedSeconds'], 0.03)
        self.assertEqual(t['skippedNativeUpdates'], 0)

    def test_missed_updates_are_not_claimed_as_single_frame_measurements(self):
        t = {}
        observe(t, 3, 1)
        self.assertEqual(t['skippedNativeUpdates'], 2)
        self.assertNotIn('maximumSingleUpdateElapsedSeconds', t)
        self.assertEqual(t['maximumObservedWindowSeconds'], 1)
        self.assertAlmostEqual(t['meanGameSecondsPerUpdate'], 1/3)

    def test_invalid_and_reset_samples_rejected_without_mutation(self):
        t = {}
        observe(t, 2, 0.2)
        for count, elapsed in ((1, 0.3), (3, 0.1), (2, 0.3), (-1, 0), (True, 0.3), (3, math.nan), (3, math.inf)):
            before = dict(t)
            with self.assertRaises(ValueError):
                observe(t, count, elapsed)
            self.assertEqual(t, before)
