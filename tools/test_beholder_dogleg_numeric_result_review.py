"""Targeted standalone tests; no engine observations or Unreal API."""
import copy
import unittest

from beholder_dogleg_numeric_result_review import _expected, review_supplied_results
from beholder_dogleg_numeric_validation_plan import validation_plan, plan_fingerprint


def synthetic_records():
    # Deliberately reuse the reference for protocol fixtures, NOT an independent
    # oracle for the underlying math or Blueprint arithmetic.
    return [dict(caseId=case['caseId'], outputs=_expected(case))
            for case in validation_plan()['cases']]


def review(records, **changes):
    # Synthetic fixtures are created from the same current plan. Real callers
    # must retain the fingerprint selected before collecting engine answers.
    options = dict(submitted_plan_sha256=plan_fingerprint(validation_plan()),
                   absolute_tolerance=1e-6, derivative_relative_tolerance=1e-5)
    options.update(changes)
    return review_supplied_results(records, **options)


class NumericResultReviewTests(unittest.TestCase):
    def test_wrong_plan_fingerprint_rejected_before_consuming_records(self):
        # Included in the subsequent separately authorized 17/17 run.
        class UnreadableRecords:
            def __iter__(self):
                raise AssertionError('Results consumed before plan identity check')

        for fingerprint in (None, '', '0'*64, True):
            with self.subTest(fingerprint=fingerprint), self.assertRaisesRegex(ValueError, 'fingerprint'):
                review(UnreadableRecords(), submitted_plan_sha256=fingerprint)
        with self.assertRaises(TypeError):
            review_supplied_results([], absolute_tolerance=1e-6,
                                    derivative_relative_tolerance=1e-5)

    def test_inter_library_disagreement_rejected_even_when_each_is_near_reference(self):
        # Added after 10/10; included in the later authorized 17/17 run.
        records = synthetic_records()
        by_id = {record['caseId']: record['outputs'] for record in records}
        pair = validation_plan()['comparisons'][0]
        # Independent reference comparisons accept both perturbations; their
        # difference exceeds the common tolerance. Derivative can have either sign.
        by_id[pair['sampleCaseId']]['PhaseVelocityPerSecond'] += 0.75e-6
        by_id[pair['clockCaseId']]['PhaseVelocityPerSecond'] -= 0.75e-6
        with self.assertRaisesRegex(ValueError, 'Inter-library mismatch'):
            review(records)

    def test_every_accepted_facade_has_matching_companion_input_data(self):
        # Added after 10/10; included in the later authorized 17/17 run.
        plan = validation_plan()
        cases = {case['caseId']: case for case in plan['cases']}
        samples = {case['caseId'] for case in cases.values()
                   if case['kind'] == 'sample' and case['expectedNumericInputsAccepted']}
        self.assertEqual({pair['sampleCaseId'] for pair in plan['comparisons']}, samples)
        self.assertEqual(len(plan['comparisons']), len(samples))
        for pair in plan['comparisons']:
            sample = cases[pair['sampleCaseId']]
            clock = cases[pair['clockCaseId']]
            targets = cases[pair['targetsCaseId']]
            self.assertEqual(clock['kind'], 'clock')
            self.assertEqual(targets['kind'], 'targets')
            for name, value in clock['arguments'].items():
                self.assertEqual(value, sample['arguments'][name])
            for name, value in targets['arguments'].items():
                if name != 'Phase':
                    self.assertEqual(value, sample['arguments'][name])
            self.assertEqual(targets['arguments']['Phase'], _expected(sample)['Phase'])

    def test_facade_targets_must_also_match_returned_phase(self):
        records = synthetic_records()
        cases = {case['caseId']: case for case in validation_plan()['cases']}
        record = next(record for record in records
                      if cases[record['caseId']]['kind'] == 'sample'
                      and record['outputs']['Phase'] == 0.5
                      and cases[record['caseId']]['arguments']['AmplitudeDegrees'] == 1.0)
        # Keep every target within the independent-reference tolerance while
        # making it inconsistent with a similarly tolerated phase perturbation.
        record['outputs']['Phase'] += 0.75e-6
        joint = 'Joint2YawTarget' if cases[record['caseId']]['arguments']['UseYaw'] else 'Joint2PitchTarget'
        record['outputs'][joint] += 0.75e-6
        with self.assertRaisesRegex(ValueError, 'returned Phase'):
            review(records)

    def test_facade_phase_outside_segment_is_not_accepted_by_large_tolerance(self):
        records = synthetic_records()
        cases = {case['caseId']: case for case in validation_plan()['cases']}
        record = next(record for record in records
                      if cases[record['caseId']]['kind'] == 'sample'
                      and cases[record['caseId']]['expectedNumericInputsAccepted'])
        record['outputs']['Phase'] = -0.25
        with self.assertRaisesRegex(ValueError, 'left its segment'):
            review(records, absolute_tolerance=100)

    def test_plan_ids_layouts_and_internal_span_coverage(self):
        from beholder_dogleg_job_contract import (
            CLOCK_INPUT_LAYOUT, TARGETS_INPUT_LAYOUT, SAMPLE_INPUT_LAYOUT)
        cases = validation_plan()['cases']
        self.assertEqual(len({case['caseId'] for case in cases}), len(cases))
        layouts = dict(clock=CLOCK_INPUT_LAYOUT, targets=TARGETS_INPUT_LAYOUT,
                       sample=SAMPLE_INPUT_LAYOUT)
        for case in cases:
            self.assertEqual(set(case['arguments']), {name for name, _ in layouts[case['kind']]})
            self.assertFalse(case['executionPerformed'])
        internal = [case for case in cases if case['kind'] == 'sample'
                    and case['arguments']['PhaseStart'] == 0.25]
        coverage = {(case['arguments']['Returning'], case['arguments']['UseYaw'],
                     case['arguments']['AmplitudeDegrees'], case['arguments']['SegmentElapsedSeconds'])
                    for case in internal}
        self.assertEqual(coverage, {(r, yaw, amplitude, elapsed)
                                    for r in (False, True) for yaw in (False, True)
                                    for amplitude in (-1.0, 0.0, 1.0) for elapsed in (0.0, 1.0, 2.0)})

    def test_complete_synthetic_records_are_only_supplied_data_confirmation(self):
        records = synthetic_records()
        packet = review(records)
        self.assertEqual(packet['casesCompared'], len(records))
        self.assertEqual(packet['planSha256'], plan_fingerprint(validation_plan()))
        self.assertEqual(packet['planSchemaVersion'], 1)
        for flag in ('engineExecutionAuthenticated', 'blueprintNumericValidationConfirmed',
                     'runtimeReady', 'motionAuthorized'):
            self.assertFalse(packet[flag])

    def test_missing_duplicate_unknown_and_bad_record_shape_are_rejected(self):
        records = synthetic_records()
        malformed = (records[:-1], records+[records[0]],
                     [dict(caseId='unknown', outputs={})]+records[1:],
                     [dict(records[0], extra=True)]+records[1:])
        for candidate in malformed:
            with self.subTest(first=candidate[0]['caseId']), self.assertRaises(ValueError):
                review(candidate)

    def test_output_layout_and_exact_boolean_types_are_required(self):
        for change in ('missing', 'extra', 'integer_flag', 'authorization', 'bool_number'):
            records = synthetic_records()
            outputs = records[0]['outputs']
            if change == 'missing':
                del outputs['Phase']
            elif change == 'extra':
                outputs['extra'] = 0
            elif change == 'integer_flag':
                outputs['NumericInputsAccepted'] = 1
            elif change == 'authorization':
                outputs['MotionAuthorized'] = True
            else:
                outputs['Phase'] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                review(records)

    def test_nonfinite_or_changed_accepted_numbers_are_rejected(self):
        for value in (float('nan'), float('inf'), 10**1000, '0', 0.1):
            records = synthetic_records()
            records[0]['outputs']['Phase'] = value
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                review(records)

    def test_rejection_requires_literal_zero_even_inside_large_tolerance(self):
        records = synthetic_records()
        refused = next(record for record in records if record['outputs']['NumericInputsAccepted'] is False)
        numeric = next(name for name, value in refused['outputs'].items() if type(value) is not bool)
        refused['outputs'][numeric] = 1e-15
        with self.assertRaises(ValueError):
            review(records, absolute_tolerance=1.0)

    def test_tolerances_are_explicit_finite_and_nonnegative(self):
        for name in ('absolute_tolerance', 'derivative_relative_tolerance'):
            for value in (-1, True, float('nan'), float('inf'), 10**1000, None):
                with self.subTest(name=name, value_type=type(value).__name__), self.assertRaises(ValueError):
                    review(synthetic_records(), **{name: value})
        with self.assertRaises(TypeError):
            review_supplied_results(synthetic_records())

    def test_records_are_not_mutated_and_plan_is_fresh(self):
        records = synthetic_records()
        before = copy.deepcopy(records)
        review(records)
        self.assertEqual(records, before)
        plan = validation_plan()
        original_fingerprint = plan_fingerprint(plan)
        self.assertEqual(original_fingerprint, plan_fingerprint(validation_plan()))
        reordered_keys = {key: plan[key] for key in reversed(tuple(plan))}
        self.assertEqual(original_fingerprint, plan_fingerprint(reordered_keys))
        changed_status = copy.deepcopy(plan)
        changed_status['status'] = 'supplied_results_available'
        changed_status['executionPerformed'] = True
        for case in changed_status['cases']:
            case['executionPerformed'] = True
        self.assertEqual(original_fingerprint, plan_fingerprint(changed_status))
        self.assertFalse(plan['executionPerformed'])
        self.assertTrue(all(case['executionPerformed'] is False for case in plan['cases']))
        changed = copy.deepcopy(plan)
        changed['cases'][0]['arguments']['SegmentElapsedSeconds'] = 0.125
        self.assertNotEqual(original_fingerprint, plan_fingerprint(changed))
        changed = copy.deepcopy(plan)
        changed['comparisons'][0]['clockCaseId'] = 'changed'
        self.assertNotEqual(original_fingerprint, plan_fingerprint(changed))
        plan['cases'][0]['arguments'].clear()
        plan['cases'].clear()
        self.assertEqual(synthetic_records(), before)
