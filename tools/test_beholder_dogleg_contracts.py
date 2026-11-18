"""Standalone protocol tests with synthetic results/evidence; no Unreal calls."""
from dataclasses import FrozenInstanceError, replace
import math
import unittest
from unittest.mock import patch

from beholder_contact_dogleg import dogleg_pose
from beholder_dogleg_job import finite, prepare_job, Segment
from beholder_dogleg_job_contract import SAMPLE_INPUT_LAYOUT, SAMPLE_OUTPUT_LAYOUT
from beholder_dogleg_numeric_adapter import NumericBlueprintAdapter
from beholder_dogleg_pipeline import DoglegCalculationPipeline
from beholder_dogleg_pose_receipt import CaptureStamp, FrameEvidence, PoseEvidence
from beholder_dogleg_sample_adapter import DoglegSamplePipeline, NumericSampleAdapter
from beholder_dogleg_sample_session import DoglegSampleSession
from beholder_dogleg_timing import quintic
from generate_beholder_telescope import STROKE


def result_for(job, index=0, elapsed=0):
    """Synthetic Python reference response, NOT a Blueprint observation."""
    segment = job.segments[index]
    q, dq, ddq = quintic(elapsed/segment.duration_seconds)
    span = segment.phase_end-segment.phase_start
    sign = -1 if segment.returning else 1
    phase = segment.phase_end-span*q if segment.returning else segment.phase_start+span*q
    pose = dogleg_pose(job.extension, job.amplitude_degrees*phase, job.axis)
    result = dict(NumericInputsAccepted=True, MotionAuthorized=False, Phase=phase,
                  PhaseVelocityPerSecond=sign*span*dq/segment.duration_seconds,
                  PhaseAccelerationPerSecond2=sign*span*ddq/segment.duration_seconds**2,
                  SegmentComplete=elapsed == segment.duration_seconds,
                  CompensatedExtension=pose['extension'])
    result.update({f'Stage{i}Target': value for i, value in enumerate(pose['stages'])})
    result.update({f'Joint{i}{axis}Target': pose['angles'][i][component]
                   for i in range(1, 10) for component, axis in enumerate(('Pitch', 'Yaw'))})
    return result


def evidence(job, stamp, sample=None):
    """Caller-supplied DTO with fixed arbitrary frames; not native capture."""
    initial = dogleg_pose(job.extension, 0, job.axis)
    stages = initial['stages'] if sample is None else sample.stages
    angles = initial['angles'] if sample is None else sample.angles
    frame = FrameEvidence((0, 0, 0), (0, 0, 0, 1), (1, 1, 1))
    return PoseEvidence('synthetic_world', 'synthetic_actor', 'owner', 'geometry',
                        stamp, stamp, frame, frame, tuple(stages),
                        tuple((STROKE*v, 0, 0) for v in stages),
                        tuple((pitch, yaw, 0) for pitch, yaw in angles),
                        (0, 0, 0), True, (0, 0, 0), 0)


class JobContractTests(unittest.TestCase):
    def test_factory_rejects_bad_scalars_before_calling_timing(self):
        # Included in the subsequent authorized 24/24 two-module run.
        for name in ('extension', 'amplitude_degrees', 'joint_speed_degrees',
                     'transition_seconds', 'half_duration', 'joint_acceleration_limit'):
            for value in (True, float('nan'), float('inf'), 10**1000, '1'):
                with self.subTest(name=name, value_type=type(value).__name__):
                    with patch('beholder_dogleg_job.DoglegTiming') as timing:
                        with self.assertRaises(ValueError):
                            prepare_job(**{name: value})
                        timing.assert_not_called()
                        timing.fit_duration.assert_not_called()
        for changes in (dict(extension=0.3), dict(amplitude_degrees=2),
                        dict(joint_speed_degrees=0), dict(transition_seconds=0),
                        dict(half_duration=0), dict(joint_acceleration_limit=0), dict(axis='roll')):
            with self.subTest(changes=changes), patch('beholder_dogleg_job.DoglegTiming') as timing:
                with self.assertRaises(ValueError):
                    prepare_job(**changes)
                timing.assert_not_called()
                timing.fit_duration.assert_not_called()

    def test_finite_rejects_bool_nonfinite_and_oversized_integer(self):
        for value in (True, False, float('nan'), float('inf'), 10**1000, '1', None):
            with self.subTest(value_type=type(value).__name__):
                self.assertFalse(finite(value))
        self.assertTrue(finite(1))
        self.assertTrue(finite(0.5))

    def test_factory_and_direct_constructor_capture_immutable_segments(self):
        job = prepare_job(half_duration=2)
        segments = list(job.segments)
        copied = replace(job, segments=segments)
        segments.clear()
        self.assertEqual(copied.segments, job.segments)
        with self.assertRaises(FrozenInstanceError):
            copied.extension = 0.6
        packet = copied.to_dict()
        packet['segments'].clear()
        self.assertEqual(copied.segments, job.segments)
        self.assertFalse(packet['motionAuthorized'])

    def test_invalid_direct_job_shape_and_parameters_are_rejected(self):
        job = prepare_job(half_duration=2)
        for changes in (dict(segments=[]), dict(axis='roll'), dict(extension=0.3),
                        dict(amplitude_degrees=2), dict(duration_fitted=1),
                        dict(half_duration_seconds=math.inf),
                        dict(segments=(replace(job.segments[0], index=1),)+job.segments[1:])):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(job, **changes)

    def test_direct_constructor_checks_maxima_and_budgets(self):
        job = prepare_job(half_duration=2)
        b = job.reference_bounds
        for name in ('maximum_joint_speed_degrees_per_second',
                     'maximum_joint_acceleration_degrees_per_second2',
                     'maximum_stage_speed_per_second', 'maximum_stage_acceleration_per_second2'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'understate'):
                replace(job, reference_bounds=replace(b, **{name: 0}))
        for changes in (dict(single_axis_joint_speed_budget_degrees_per_second=0),
                        dict(stage_speed_budget_per_second=1e-20),
                        dict(optional_joint_acceleration_limit=1e-20)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(job, reference_bounds=replace(b, **changes))

    def test_missing_clamp_stop_is_rejected_on_either_half(self):
        job = prepare_job(extension=0.59999, half_duration=2)
        forward = [s for s in job.segments if not s.returning]
        returning = [s for s in job.segments if s.returning]
        self.assertGreater(len(forward), 1, 'Fixture must contain an interior clamp stop')
        bad_halves = ([Segment(0, 0, 2, 0, 1, False)]+returning,
                      forward+[Segment(0, 2, 4, 0, 1, True)])
        for segments in bad_halves:
            with self.subTest(segments=segments), self.assertRaisesRegex(ValueError, 'clamp-kink'):
                replace(job, segments=tuple(replace(s, index=i) for i, s in enumerate(segments)))


class FacadePipelineTests(unittest.TestCase):
    def test_full_cycle_for_axes_and_signs_preserves_id_and_denies_motion(self):
        for axis in ('pitch', 'yaw'):
            for amplitude, extension in ((-1, 0.5), (1, 0.5), (-1, 0.59999), (1, 0.59999)):
                with self.subTest(axis=axis, amplitude=amplitude, extension=extension):
                    job = prepare_job(extension=extension, axis=axis,
                                      amplitude_degrees=amplitude, half_duration=2)
                    pipeline = DoglegSamplePipeline(job)
                    for index, segment in enumerate(job.segments):
                        for elapsed in (0, segment.duration_seconds/2, segment.duration_seconds):
                            request = pipeline.begin_sample(index, elapsed)
                            self.assertEqual(tuple(dict(request.arguments)), tuple(n for n, _ in SAMPLE_INPUT_LAYOUT))
                            self.assertNotIn('Phase', dict(request.arguments))
                            with patch.object(pipeline, '_request', side_effect=AssertionError('intermediate request')):
                                sample = pipeline.accept_sample(request.request_id, result_for(job, index, elapsed))
                            self.assertEqual(sample.sample_id, request.request_id)
                            self.assertIsNone(pipeline.pending_request)
                            for flag in ('runtimeReady', 'actualPoseConfirmed', 'motionAuthorized'):
                                self.assertFalse(sample.to_dict()[flag])
                    self.assertEqual(sample.phase, 0)

    def test_bad_numeric_receipt_holds_and_clears_sample(self):
        changes = (dict(NumericInputsAccepted=False), dict(MotionAuthorized=True),
                   dict(Phase=float('nan')), dict(PhaseVelocityPerSecond=1),
                   dict(PhaseAccelerationPerSecond2=1), dict(SegmentComplete=True),
                   dict(Stage0Target=-1), dict(Joint1YawTarget=1), dict(CompensatedExtension=0))
        for change in changes:
            with self.subTest(change=change):
                job = prepare_job(half_duration=2)
                pipeline = DoglegSamplePipeline(job)
                request = pipeline.begin_sample(0, 0)
                with self.assertRaises(ValueError):
                    pipeline.accept_sample(request.request_id, dict(result_for(job), **change))
                self.assertEqual(pipeline.state, 'held')
                self.assertIsNone(pipeline.numeric_sample)
                self.assertIsNone(pipeline.pending_request)

    def test_schema_types_tuple_and_stale_receipts(self):
        job = prepare_job(half_duration=2)
        good = result_for(job)
        malformed = (dict(good, unexpected=0), {k: v for k, v in good.items() if k != 'Phase'},
                     dict(good, NumericInputsAccepted=1), dict(good, Phase=True), (0,))
        for result in malformed:
            pipeline = DoglegSamplePipeline(job)
            request = pipeline.begin_sample(0, 0)
            with self.subTest(result=result), self.assertRaises(ValueError):
                pipeline.accept_sample(request.request_id, result)
            self.assertEqual(pipeline.state, 'held')
        pipeline = DoglegSamplePipeline(job)
        request = pipeline.begin_sample(0, 0)
        sample = pipeline.accept_sample(request.request_id, tuple(good[n] for n, _ in SAMPLE_OUTPUT_LAYOUT))
        self.assertEqual(sample.phase, 0)
        with self.assertRaises(ValueError):
            pipeline.accept_sample(request.request_id, good)
        self.assertEqual(pipeline.state, 'held')

    def test_separate_receipts_and_skipped_boundaries_are_rejected(self):
        job = prepare_job(half_duration=2)
        for operation in ('accept_clock', 'accept_targets'):
            pipeline = DoglegSamplePipeline(job)
            request = pipeline.begin_sample(0, 0)
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                getattr(pipeline, operation)(request.request_id, result_for(job))
        pipeline = DoglegSamplePipeline(job)
        request = pipeline.begin_sample(0, 0)
        pipeline.accept_sample(request.request_id, result_for(job))
        with self.assertRaises(ValueError):
            pipeline.begin_sample(1, 0)
        self.assertEqual(pipeline.state, 'held')

    def test_two_function_protocol_still_completes(self):
        job = prepare_job(half_duration=2)
        pipeline = DoglegCalculationPipeline(job)
        clock = pipeline.begin_sample(0, 0)
        targets = pipeline.accept_clock(clock.request_id, result_for(job))
        self.assertEqual(targets.kind, 'targets')
        self.assertEqual(dict(targets.arguments)['Phase'], 0)
        sample = pipeline.accept_targets(targets.request_id, result_for(job))
        self.assertEqual(sample.sample_id, targets.request_id)
        self.assertEqual(pipeline.state, 'idle')

    def test_adapters_default_to_disabled_without_importing_unreal(self):
        job = prepare_job(half_duration=2)
        import builtins
        original = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == 'unreal' or name.startswith('unreal.'):
                raise AssertionError('Unreal import attempted')
            return original(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=guarded_import):
            for adapter, pipeline in ((NumericSampleAdapter, DoglegSamplePipeline(job)),
                                      (NumericBlueprintAdapter, DoglegCalculationPipeline(job))):
                with self.subTest(adapter=adapter.__name__), self.assertRaises(PermissionError):
                    adapter(pipeline)


class SampleSessionTests(unittest.TestCase):
    def test_full_supplied_evidence_round_trip_with_clamp_stops(self):
        # Included in the subsequent authorized 24/24 two-module run.
        for axis, amplitude in (('pitch', -1), ('pitch', 1), ('yaw', -1), ('yaw', 1)):
            with self.subTest(axis=axis, amplitude=amplitude):
                job = prepare_job(extension=0.59999, axis=axis,
                                  amplitude_degrees=amplitude, half_duration=2)
                self.assertGreater(len(job.segments), 2)
                baseline = evidence(job, CaptureStamp(0, 0, 0))
                session = DoglegSampleSession(job, baseline)
                previous_sample = None
                application = probe = capture = 0
                transaction_ids, sample_ids = set(), set()
                for index, segment in enumerate(job.segments):
                    for elapsed in (0, segment.duration_seconds/2, segment.duration_seconds):
                        request = session.begin_sample(index, elapsed)
                        sample = session.accept_numeric(request.request_id, result_for(job, index, elapsed))
                        capture += 1
                        before = evidence(job, CaptureStamp(application, probe, capture), previous_sample)
                        proposal = session.propose(before)
                        self.assertNotIn(proposal.transaction_id, transaction_ids)
                        self.assertNotIn(sample.sample_id, sample_ids)
                        transaction_ids.add(proposal.transaction_id)
                        sample_ids.add(sample.sample_id)
                        self.assertEqual(proposal.sample.sample_id, request.request_id)
                        self.assertEqual(proposal.to_dict()['expectedApplicationRevision'], application+1)
                        application += 1
                        probe += 1
                        capture += 1
                        after = evidence(job, CaptureStamp(application, probe, capture), sample)
                        receipt = session.compare_after(proposal.transaction_id, after)
                        self.assertEqual(receipt['sampleId'], request.request_id)
                        self.assertEqual(session.state, 'idle')
                        for flag in ('actualPoseConfirmed', 'runtimeReady', 'motionAuthorized'):
                            self.assertFalse(receipt[flag])
                        previous_sample = sample
                self.assertEqual(previous_sample.phase, 0)
                self.assertEqual(previous_sample.stages, baseline.stages)
                self.assertEqual(previous_sample.angles, ((0.0, 0.0),)*10)
                self.assertEqual(len(transaction_ids), 3*len(job.segments))

    def setUp(self):
        self.job = prepare_job(half_duration=2)
        self.baseline = evidence(self.job, CaptureStamp(0, 0, 0))

    def ready_proposal(self, session):
        request = session.begin_sample(0, 0)
        sample = session.accept_numeric(request.request_id, result_for(self.job))
        before = evidence(self.job, CaptureStamp(0, 0, 1))
        proposal = session.propose(before)
        return sample, proposal

    def test_supplied_receipt_cycle_returns_idle_without_authorizing_pose(self):
        session = DoglegSampleSession(self.job, self.baseline)
        sample, proposal = self.ready_proposal(session)
        self.assertFalse(proposal.to_dict()['motionAuthorized'])
        after = evidence(self.job, CaptureStamp(1, 1, 2), sample)
        receipt = session.compare_after(proposal.transaction_id, after)
        self.assertEqual(session.state, 'idle')
        self.assertTrue(receipt['suppliedPoseEvidenceCompared'])
        for flag in ('actualPoseConfirmed', 'runtimeReady', 'motionAuthorized'):
            self.assertFalse(receipt[flag])
        session.begin_sample(0, self.job.segments[0].duration_seconds/2)
        self.assertEqual(session.state, 'awaiting_numeric')

    def test_next_request_is_blocked_before_and_after_proposal(self):
        for proposed in (False, True):
            session = DoglegSampleSession(self.job, self.baseline)
            request = session.begin_sample(0, 0)
            session.accept_numeric(request.request_id, result_for(self.job))
            if proposed:
                session.propose(evidence(self.job, CaptureStamp(0, 0, 1)))
            with self.subTest(proposed=proposed), self.assertRaises(ValueError):
                session.begin_sample(0, 0)
            self.assertEqual(session.state, 'held')
            self.assertIsNone(session._pipeline.numeric_sample)
            self.assertIsNone(session._ledger.pending_proposal)

    def test_bad_identity_revision_pose_or_transaction_holds(self):
        for fault in ('identity', 'revision', 'pose', 'transaction', 'contact'):
            session = DoglegSampleSession(self.job, self.baseline)
            sample, proposal = self.ready_proposal(session)
            after = evidence(self.job, CaptureStamp(1, 1, 2), sample)
            transaction = proposal.transaction_id
            if fault == 'identity':
                after = replace(after, actor_id='different')
            elif fault == 'revision':
                after = replace(after, stamp_before=CaptureStamp(0, 1, 2), stamp_after=CaptureStamp(0, 1, 2))
            elif fault == 'pose':
                after = replace(after, sleeve_offsets=((0, 0, 0),)*10)
            elif fault == 'contact':
                after = replace(after, contact_valid=False)
            else:
                transaction = 'stale'
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                session.compare_after(transaction, after)
            self.assertEqual(session.state, 'held')
            self.assertIsNone(session._pipeline.numeric_sample)

    def test_repeated_receipt_and_sticky_hold_cannot_resume(self):
        session = DoglegSampleSession(self.job, self.baseline)
        sample, proposal = self.ready_proposal(session)
        after = evidence(self.job, CaptureStamp(1, 1, 2), sample)
        session.compare_after(proposal.transaction_id, after)
        with self.assertRaises(ValueError):
            session.compare_after(proposal.transaction_id, after)
        reason = session.held_reason
        session.hold('another reason')
        self.assertEqual(session.held_reason, reason)
        with self.assertRaises(ValueError):
            session.begin_sample(0, 0)


if __name__ == '__main__':
    unittest.main()
