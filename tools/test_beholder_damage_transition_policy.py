"""Prepared, NOT RUN: approved damage precedence on synthetic snapshots."""
from dataclasses import FrozenInstanceError, replace
import unittest

from beholder_damage_transition_policy import (
    DamageSnapshot, decide_damage_transition, assess_recovery_eligibility, DamagePolicyLedger)


SUBJECT = ('synthetic_world', 'synthetic_actor_instance', 'synthetic_lifetime')


def snapshot(failed=(), attacks=None):
    health = [100]*8
    active = [None]*8
    for leg in failed:
        health[leg] = 0
    for leg, action in (attacks or {}).items():
        active[leg] = action
    return DamageSnapshot(health, active, SUBJECT)


class DamageTransitionPolicyTests(unittest.TestCase):
    def test_ledger_rejects_mixed_world_actor_or_lifetime_without_advancing(self):
        for component in range(3):
            ledger = DamagePolicyLedger()
            baseline = snapshot()
            ledger.evaluate(baseline, snapshot_revision=0)
            identity = list(SUBJECT)
            identity[component] = 'different'
            with self.subTest(component=component), self.assertRaisesRegex(ValueError, 'identity changed'):
                ledger.evaluate(replace(baseline, subject_identity=identity), snapshot_revision=1)
            self.assertEqual(ledger._subject_identity, SUBJECT)
            self.assertEqual(ledger._last_snapshot_revision, 0)
            self.assertIsNotNone(ledger.held_reason)
            self.assertIsNone(ledger.last_decision)

    def test_ledger_retains_empty_latch_without_caller_carrying_commitments(self):
        ledger = DamagePolicyLedger()
        entry = ledger.evaluate(snapshot(range(5), {5: 'existing'}), snapshot_revision=0)
        self.assertEqual(entry.source_snapshot_revision, 0)
        self.assertEqual(entry.to_dict()['source_snapshot_revision'], 0)
        self.assertEqual(entry.remaining_melee, ((5, 'existing'),))
        completed = ledger.evaluate(snapshot(range(5)), snapshot_revision=1, completed_melee_ids=('existing',))
        self.assertEqual(completed.source_snapshot_revision, 1)
        self.assertEqual(entry.source_snapshot_revision, 0)
        self.assertEqual(completed.neutralization_phase, 'awaiting_neutralization_effects')
        improved_health = ledger.evaluate(snapshot(), snapshot_revision=2)
        self.assertTrue(improved_health.reject_new_attacks)
        with self.assertRaises(ValueError):
            ledger.evaluate(snapshot(attacks={0: 'new'}), snapshot_revision=3)
        self.assertIsNotNone(ledger.held_reason)
        self.assertIsNone(ledger.last_decision)

    def test_ledger_missing_completion_holds_without_auto_resume(self):
        ledger = DamagePolicyLedger()
        ledger.evaluate(snapshot(range(5), {5: 'existing'}), snapshot_revision=0)
        with self.assertRaises(ValueError):
            ledger.evaluate(snapshot(range(5)), snapshot_revision=1)
        reason = ledger.held_reason
        with self.assertRaises(ValueError):
            ledger.evaluate(snapshot(range(5)), snapshot_revision=2, completed_melee_ids=('existing',))
        self.assertEqual(ledger.held_reason, reason)
        self.assertIsNone(ledger.last_decision)

    def test_ledger_rejects_stale_and_invalid_snapshot_revisions(self):
        for revision in (4, 3, -1, True, 5.0, '5', None):
            ledger = DamagePolicyLedger()
            ledger.evaluate(snapshot(), snapshot_revision=4)
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                ledger.evaluate(snapshot(), snapshot_revision=revision)
            self.assertIsNotNone(ledger.held_reason)
            self.assertIsNone(ledger.last_decision)
            self.assertEqual(ledger._last_snapshot_revision, 4)
        ledger = DamagePolicyLedger()
        ledger.evaluate(snapshot(), snapshot_revision=0)
        ledger.evaluate(snapshot(), snapshot_revision=2)
        # Monotonic acceptance does not certify what happened in the gap.
        self.assertEqual(ledger._last_snapshot_revision, 2)
        missing = DamagePolicyLedger()
        self.assertIsNotNone(missing.evaluate(snapshot(), snapshot_revision=0))
        with self.assertRaisesRegex(ValueError, 'snapshot revision'):
            missing.evaluate(snapshot())
        self.assertIsNotNone(missing.held_reason)
        self.assertIsNone(missing.last_decision)
        self.assertEqual(missing._last_snapshot_revision, 0)

    def test_recovery_requires_out_of_combat_and_four_functional_legs(self):
        for functional_count in range(9):
            for in_combat in (False, True):
                with self.subTest(functional_count=functional_count, in_combat=in_combat):
                    packet = assess_recovery_eligibility(
                        snapshot(range(8-functional_count)), in_combat=in_combat,
                        previously_neutralized=True)
                    self.assertEqual(packet['functionalLegCount'], functional_count)
                    self.assertEqual(packet['subjectIdentity'], SUBJECT)
                    expected = not in_combat and functional_count >= 4
                    self.assertEqual(packet['healthAndCombatCriteriaMet'], expected)
                    self.assertEqual(packet['eligibleForNativeRecoveryAssessment'], expected)
                    for flag in ('neutralizationExitApplied', 'nativeStateConfirmed',
                                 'supportConfirmed', 'runtimeReady', 'motionAuthorized'):
                        self.assertFalse(packet[flag])

    def test_recovery_does_not_complete_transition_or_accept_inconsistent_actions(self):
        packet = assess_recovery_eligibility(snapshot(), in_combat=False, previously_neutralized=False)
        self.assertTrue(packet['healthAndCombatCriteriaMet'])
        self.assertFalse(packet['eligibleForNativeRecoveryAssessment'])
        self.assertIn('not_in_final_neutralized', packet['blockers'])
        packet = assess_recovery_eligibility(snapshot(attacks={0: 'unexpected'}),
                                             in_combat=False, previously_neutralized=True)
        self.assertFalse(packet['eligibleForNativeRecoveryAssessment'])
        self.assertIn('active_melee_conflicts_with_final_neutralized', packet['blockers'])
        for changes in (dict(in_combat=1, previously_neutralized=True),
                        dict(in_combat=False, previously_neutralized=1)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                assess_recovery_eligibility(snapshot(), **changes)

    def test_zero_hp_aborts_only_that_leg_and_requests_retraction(self):
        decision = decide_damage_transition(snapshot((0,), {0: 'failed_stab', 1: 'healthy_slash'}))
        self.assertEqual(decision.subject_identity, SUBJECT)
        self.assertIsNone(decision.source_snapshot_revision)
        self.assertEqual(decision.abort_melee, ((0, 'failed_stab'),))
        self.assertEqual(decision.request_safe_retraction, (0,))
        self.assertEqual(decision.finish_existing_melee, ((1, 'healthy_slash'),))
        self.assertFalse(decision.neutralization_required)
        self.assertFalse(decision.reject_new_attacks)
        self.assertEqual(decision.neutralization_phase, 'not_requested')

    def test_threshold_drains_healthy_melee_then_latches_neutralization(self):
        entry = decide_damage_transition(snapshot(range(5), {4: 'failed', 5: 'finish_this'}))
        self.assertEqual(entry.abort_melee, ((4, 'failed'),))
        self.assertEqual(entry.remaining_melee, ((5, 'finish_this'),))
        self.assertEqual(entry.neutralization_phase, 'finishing_existing_melee')
        self.assertTrue(entry.reject_new_attacks)
        self.assertTrue(entry.preserve_current_main_eye_state)
        self.assertFalse(entry.request_close_main_eye)
        self.assertFalse(entry.request_disable_antimagic)
        done = decide_damage_transition(snapshot(range(5)), drain_commitments=entry.remaining_melee,
                                        completed_melee_ids=('finish_this',))
        self.assertEqual(done.neutralization_phase, 'awaiting_neutralization_effects')
        self.assertFalse(done.preserve_current_main_eye_state)
        self.assertTrue(done.request_close_main_eye)
        self.assertTrue(done.request_disable_antimagic)
        self.assertFalse(done.to_dict()['gameplayNeutralizedConfirmed'])
        self.assertEqual(done.to_dict()['beamTransitionPolicy'], 'unresolved')
        # Improved HP alone must not silently reset the neutralization latch.
        recovered_health = decide_damage_transition(snapshot(), drain_commitments=done.remaining_melee)
        self.assertTrue(recovered_health.neutralization_required)
        self.assertTrue(recovered_health.reject_new_attacks)
        self.assertEqual(recovered_health.neutralization_phase, 'awaiting_neutralization_effects')

    def test_missing_completion_or_new_action_during_drain_is_rejected(self):
        committed = ((5, 'original'),)
        for active in ({}, {5: 'replacement'}, {5: 'original', 6: 'new_attack'}):
            with self.subTest(active=active), self.assertRaises(ValueError):
                decide_damage_transition(snapshot(range(5), active), drain_commitments=committed)

    def test_committed_leg_at_zero_hp_is_not_required_to_finish_its_attack(self):
        decision = decide_damage_transition(snapshot(range(6), {5: 'original'}),
                                             drain_commitments=((5, 'original'),))
        self.assertEqual(decision.abort_melee, ((5, 'original'),))
        self.assertEqual(decision.remaining_melee, ())
        self.assertEqual(decision.neutralization_phase, 'awaiting_neutralization_effects')
        # Policy completion is not an actual shutdown/retraction receipt.
        packet = decision.to_dict()
        for flag in ('commandsApplied', 'attacksActuallyStopped', 'retractionConfirmed',
                     'nativeOwnershipConfirmed', 'mainEyeClosedConfirmed',
                     'antimagicDisabledConfirmed', 'gameplayNeutralizedConfirmed',
                     'runtimeReady', 'motionAuthorized'):
            self.assertFalse(packet[flag])

    def test_completion_ids_must_be_current_unique_and_not_active(self):
        committed = ((5, 'original'),)
        # Do not interpret a scalar string or mapping as an iterable of IDs.
        for completions in ('x', b'x', bytearray(b'x'), {'x': True}):
            with self.subTest(container_type=type(completions).__name__), self.assertRaises(ValueError):
                decide_damage_transition(snapshot(range(5)), drain_commitments=((5, 'x'),),
                                         completed_melee_ids=completions)
        for malformed in ('5x', b'5x', bytearray(b'5x'), {5: 'x'}):
            with self.subTest(container_type=type(malformed).__name__), self.assertRaises(ValueError):
                decide_damage_transition(snapshot(range(5)), drain_commitments=malformed)
        for completions, active in ((('unknown',), {}),
                                    (('original', 'original'), {}),
                                    (('original',), {5: 'original'})):
            with self.subTest(completions=completions), self.assertRaises(ValueError):
                decide_damage_transition(snapshot(range(5), active), drain_commitments=committed,
                                         completed_melee_ids=completions)
        with self.assertRaises(ValueError):
            decide_damage_transition(snapshot(), completed_melee_ids=('original',))
        with self.assertRaises(ValueError):
            decide_damage_transition(snapshot(range(5)), drain_commitments=(),
                                     completed_melee_ids=('original',))

    def test_final_neutralized_does_not_resume_attack_on_health_recovery(self):
        decision = decide_damage_transition(snapshot(), previously_neutralized=True)
        self.assertEqual(decision.neutralization_phase, 'neutralized')
        self.assertTrue(decision.reject_new_attacks)
        with self.assertRaises(ValueError):
            decide_damage_transition(snapshot(attacks={0: 'forbidden'}), previously_neutralized=True)
        with self.assertRaises(ValueError):
            decide_damage_transition(snapshot(), previously_neutralized=True,
                                     drain_commitments=((0, 'unfinished'),))

    def test_snapshot_freezes_inputs_and_rejects_invalid_data(self):
        health, attacks = [100]*8, [None]*8
        identity = list(SUBJECT)
        original = DamageSnapshot(health, attacks, identity)
        identity.clear()
        self.assertEqual(original.subject_identity, SUBJECT)
        health[0] = 0
        attacks[0] = 'later'
        self.assertEqual(original.health_percent, (100,)*8)
        self.assertEqual(original.active_melee_ids, (None,)*8)
        with self.assertRaises(FrozenInstanceError):
            original.health_percent = (0,)*8
        for value in (True, float('nan'), float('inf'), 10**1000, -1, 101):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                DamageSnapshot([value]+[100]*7, [None]*8, SUBJECT)
        with self.assertRaises(ValueError):
            DamageSnapshot([100]*7, [None]*8, SUBJECT)
        with self.assertRaises(ValueError):
            DamageSnapshot([100]*8, ['same', 'same']+[None]*6, SUBJECT)
        for identity in ('abc', ('world', 'actor'), ('world', 'actor', ''), ('world', 'actor', 1)):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                DamageSnapshot([100]*8, [None]*8, identity)
        with self.assertRaises(ValueError):
            decide_damage_transition(original, drain_commitments=((True, 'action'),))
