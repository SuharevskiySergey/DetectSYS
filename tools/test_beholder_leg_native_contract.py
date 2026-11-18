"""Standalone-tested supplied native-boundary DTO checks, not engine tests."""
from dataclasses import replace
import unittest

from beholder_dogleg_pipeline import NumericPoseSample
from beholder_dogleg_pose_receipt import FrameEvidence, PoseEvidence, ApplicationProposal
from beholder_leg_native_contract import (
    NativeLegIdentity, NativeOwnerEvidence, NativeCaptureRevision, NativeLegCapture,
    NativeApplyReceipt, NativeReceiptLedger, prepare_native_apply_intent, review_native_receipt_data)
from generate_beholder_telescope import STROKE


def capture(revision=None, subject=None, owner=None):
    subject = subject or NativeLegIdentity('world', 'leg_actor', 'lifetime', 0, 'geometry')
    owner = owner or NativeOwnerEvidence(subject, 'controller', 'epoch', 1)
    revision = revision or NativeCaptureRevision(3, 4, 5, 6)
    root = FrameEvidence((0, 0, 0), (0, 0, 0, 1), (1, 1, 1))
    tip = FrameEvidence((10, 0, 0), (0, 0, 0, 1), (1, 1, 1))
    stages = (1.0,)*5+(0.0,)*5
    pose = PoseEvidence(subject.world_id, subject.actor_id, owner.owner_epoch, subject.geometry_revision,
                        revision.pose_stamp(), revision.pose_stamp(), root, tip, stages,
                        tuple((STROKE*value, 0, 0) for value in stages), ((0, 0, 0),)*10,
                        (10, 0, 0), True, (0, 0, 0), 0)
    return NativeLegCapture(subject, owner, revision, revision, pose, True, True, True)


def intent():
    before = capture()
    sample = NumericPoseSample('sample', 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5,
                               before.pose.stages, ((0.0, 0.0),)*10)
    return prepare_native_apply_intent(ApplicationProposal('transaction', before.pose, sample), before)


def applied_receipt(request):
    after = capture(NativeCaptureRevision(4, 5, 6, 7), request.capture.subject, request.capture.owner)
    return NativeApplyReceipt(request.transaction_id, request.sample.sample_id, request.capture.subject,
                              'applied_reported', 'complete', request.capture, after, False, '')


class NativeContractTests(unittest.TestCase):
    def test_local_ledger_blocks_next_command_and_repeated_receipt_after_metadata_match(self):
        for next_operation in ('begin', 'repeat_receipt'):
            request = intent()
            ledger = NativeReceiptLedger(request.capture.subject, request.capture.owner)
            packet = ledger.begin(request)
            self.assertFalse(packet['nativeCommandSubmitted'])
            self.assertEqual(ledger.state, 'awaiting_native_receipt')
            receipt = applied_receipt(request)
            result = ledger.accept_receipt(receipt)
            self.assertEqual(ledger.state, 'awaiting_actual_pose_review')
            self.assertFalse(result['canContinue'])
            self.assertIs(ledger.pending_intent, request)
            exposed = ledger.last_metadata_review
            exposed['canContinue'] = True
            self.assertFalse(ledger.last_metadata_review['canContinue'])
            with self.subTest(next_operation=next_operation), self.assertRaises(ValueError):
                if next_operation == 'begin':
                    ledger.begin(replace(request, transaction_id='new_transaction'))
                else:
                    ledger.accept_receipt(receipt)
            self.assertEqual(ledger.state, 'held')
            self.assertIsNone(ledger.pending_intent)
            self.assertIsNone(ledger.last_metadata_review)

    def test_local_ledger_rejection_and_partial_stay_held_without_retry(self):
        for outcome, write_state in (('rejected_reported', 'none'), ('partial_failure_reported', 'unknown')):
            request = intent()
            ledger = NativeReceiptLedger(request.capture.subject, request.capture.owner)
            ledger.begin(request)
            receipt = NativeApplyReceipt(request.transaction_id, request.sample.sample_id, request.capture.subject,
                                         outcome, write_state, None, None, False, 'reported_failure')
            with self.subTest(outcome=outcome):
                result = ledger.accept_receipt(receipt)
                self.assertEqual(result['localState'], 'held')
                self.assertFalse(result['autoRetryAllowed'])
                reason = ledger.held_reason
                with self.assertRaises(ValueError):
                    ledger.begin(request)
                self.assertEqual(ledger.held_reason, reason)
                self.assertIsNone(ledger.pending_intent)

    def test_identity_owner_and_coherent_capture_must_match(self):
        before = capture()
        for changes in (dict(leg_index=True), dict(leg_index=8), dict(lifetime_id='')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(before.subject, **changes)
        with self.assertRaises(ValueError):
            replace(before, owner=replace(before.owner, subject=replace(before.subject, lifetime_id='other')))
        with self.assertRaises(ValueError):
            replace(before, after=replace(before.after, command_revision=4))
        with self.assertRaises(ValueError):
            replace(before, before=replace(before.before, capture_sequence=7),
                    after=replace(before.after, capture_sequence=7))
        with self.assertRaises(ValueError):
            replace(before, exclusive_owner_reported=1)

    def test_intent_is_data_and_requires_matching_reported_before(self):
        request = intent()
        packet = request.to_dict()
        self.assertEqual(packet['expectedCommandRevision'], 4)
        self.assertEqual(packet['expectedApplicationRevision'], 5)
        self.assertEqual(packet['suppliedBeforePose']['root']['location'], request.capture.pose.root.location)
        self.assertEqual(packet['suppliedBeforePose']['tip']['location'], request.capture.pose.tip.location)
        self.assertEqual(packet['suppliedBeforePose']['contact_point'], request.capture.pose.contact_point)
        self.assertTrue(packet['nativeGeometryRecheckRequired'])
        packet['suppliedBeforePose']['root']['location'] = (999, 0, 0)
        packet['suppliedBeforeCommandState']['goalsMatchActual'] = False
        self.assertEqual(request.capture.pose.root.location, (0, 0, 0))
        self.assertTrue(request.capture.goals_match_actual_reported)
        for flag in ('nativeCommandSubmitted', 'suppliedEvidenceAuthenticated',
                     'actualPoseConfirmed', 'runtimeReady', 'motionAuthorized'):
            self.assertFalse(packet[flag])
        for field in ('exclusive_owner_reported', 'writers_quiescent_reported', 'goals_match_actual_reported'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(request, capture=replace(request.capture, **{field: False}))
        proposal = ApplicationProposal('transaction', replace(request.capture.pose, contact_point=(11, 0, 0)),
                                       request.sample)
        with self.assertRaises(ValueError):
            prepare_native_apply_intent(proposal, request.capture)

    def test_reported_complete_metadata_does_not_confirm_pose_or_resume(self):
        request = intent()
        result = review_native_receipt_data(request, applied_receipt(request))
        self.assertEqual(result['status'], 'reported_commit_metadata_correlated')
        for flag in ('nativeHoldConfirmed', 'suppliedEvidenceAuthenticated', 'actualPoseCompared',
                     'actualPoseConfirmed', 'canContinue', 'autoRetryAllowed', 'runtimeReady', 'motionAuthorized'):
            self.assertFalse(result[flag])

    def test_wrong_ids_owner_or_commit_revisions_are_rejected(self):
        request = intent()
        receipt = applied_receipt(request)
        for changes in (dict(transaction_id='other'), dict(sample_id='other'),
                        dict(requested_subject=replace(request.capture.subject, lifetime_id='other'))):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                review_native_receipt_data(request, replace(receipt, **changes))
        for revision in (NativeCaptureRevision(3, 5, 6, 7), NativeCaptureRevision(4, 6, 6, 7),
                         NativeCaptureRevision(4, 5, 5, 7), NativeCaptureRevision(4, 5, 6, 6)):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                review_native_receipt_data(request, replace(receipt, observed_after=capture(revision)))
        changed_owner = replace(request.capture.owner, owner_epoch='other_epoch')
        with self.assertRaises(ValueError):
            review_native_receipt_data(request, replace(receipt, observed_after=capture(
                NativeCaptureRevision(4, 5, 6, 7), owner=changed_owner)))

    def test_rejection_can_observe_a_stale_request_but_not_change_counters(self):
        request = intent()
        newer = capture(NativeCaptureRevision(9, 9, 9, 9))
        fresh_after = capture(NativeCaptureRevision(9, 9, 9, 10))
        rejected = NativeApplyReceipt(request.transaction_id, request.sample.sample_id, request.capture.subject,
                                      'rejected_reported', 'none', newer, fresh_after, False, 'stale_before')
        result = review_native_receipt_data(request, rejected)
        self.assertTrue(result['suppliedNoWriteCountersMatch'])
        self.assertFalse(result['canContinue'])
        for revision in (NativeCaptureRevision(9, 9, 9, 9), NativeCaptureRevision(9, 9, 8, 10)):
            with self.subTest(revision=revision), self.assertRaisesRegex(ValueError, 'fresh, nonregressing'):
                review_native_receipt_data(request, replace(rejected, observed_after=capture(revision)))
        changed = capture(NativeCaptureRevision(10, 9, 9, 10))
        with self.assertRaises(ValueError):
            review_native_receipt_data(request, replace(rejected, observed_after=changed))
        unavailable = replace(rejected, observed_before=None, observed_after=None)
        self.assertIsNone(review_native_receipt_data(request, unavailable)['suppliedNoWriteCountersMatch'])

    def test_partial_or_unknown_requires_recovery_without_assuming_hold(self):
        request = intent()
        for state in ('partial', 'unknown'):
            receipt = NativeApplyReceipt(request.transaction_id, request.sample.sample_id, request.capture.subject,
                                         'partial_failure_reported', state, None, None, True, 'incomplete_write')
            with self.subTest(state=state):
                result = review_native_receipt_data(request, receipt)
                self.assertTrue(result['requiresNativeRecovery'])
                self.assertTrue(result['suppliedNativeHoldReported'])
                self.assertFalse(result['nativeHoldConfirmed'])
                self.assertFalse(result['autoRetryAllowed'])
        with self.assertRaises(ValueError):
            replace(receipt, outcome_reported='rejected_reported')
        with self.assertRaises(ValueError):
            replace(receipt, reason='')
        with self.assertRaises(ValueError):
            replace(receipt, outcome_reported='applied_reported', write_state_reported='complete')
