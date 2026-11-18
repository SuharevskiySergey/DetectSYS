"""UNEXECUTED draft: approved damage/melee precedence as plain decision data.

No Unreal, damage application, hit windows, actors, clocks, ownership or motion.
Snapshots/attack IDs are caller-supplied, not authenticated gameplay evidence.
Recovery eligibility is advisory data; no transition out of Neutralized is applied.
"""
from dataclasses import asdict, dataclass, replace

from beholder_dogleg_job import finite


LEG_COUNT = 8


@dataclass(frozen=True)
class DamageSnapshot:
    health_percent: tuple[float, ...]
    active_melee_ids: tuple[str | None, ...]
    subject_identity: tuple[str, str, str]

    def __post_init__(self):
        if isinstance(self.subject_identity, (str, bytes, bytearray, dict)):
            raise ValueError('World/actor/lifetime identity must be a three-part collection')
        identity = tuple(self.subject_identity)
        if len(identity) != 3 or any(type(value) is not str or not value for value in identity):
            raise ValueError('Nonempty supplied world, actor instance and lifetime IDs required')
        health = tuple(self.health_percent)
        attacks = tuple(self.active_melee_ids)
        if len(health) != LEG_COUNT or len(attacks) != LEG_COUNT:
            raise ValueError('Exactly eight health values and eight active melee IDs required')
        if any(not finite(value) or not 0 <= value <= 100 for value in health):
            raise ValueError('Finite health percentages in 0..100 required')
        if any(value is not None and (type(value) is not str or not value) for value in attacks):
            raise ValueError('Active melee IDs must be nonempty strings or None')
        identifiers = [value for value in attacks if value is not None]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError('Each active melee action must have a distinct ID')
        object.__setattr__(self, 'health_percent', health)
        object.__setattr__(self, 'active_melee_ids', attacks)
        object.__setattr__(self, 'subject_identity', identity)


@dataclass(frozen=True)
class DamageTransitionDecision:
    subject_identity: tuple[str, str, str]
    failed_legs: tuple[int, ...]
    abort_melee: tuple[tuple[int, str], ...]
    request_safe_retraction: tuple[int, ...]
    finish_existing_melee: tuple[tuple[int, str], ...]
    neutralization_required: bool
    neutralization_phase: str
    reject_new_attacks: bool
    remaining_melee: tuple[tuple[int, str], ...]
    preserve_current_main_eye_state: bool
    request_close_main_eye: bool
    request_disable_antimagic: bool
    source_snapshot_revision: int | None = None

    def to_dict(self):
        return dict(**asdict(self), status='draft_damage_policy_decision',
                    commandsApplied=False, attacksActuallyStopped=False,
                    retractionConfirmed=False, nativeOwnershipConfirmed=False,
                    mainEyeClosedConfirmed=False, antimagicDisabledConfirmed=False,
                    gameplayNeutralizedConfirmed=False,
                    beamTransitionPolicy='unresolved' if self.neutralization_required else 'not_applicable',
                    runtimeReady=False, motionAuthorized=False)


def decide_damage_transition(snapshot, *, previously_neutralized=False, drain_commitments=None,
                             completed_melee_ids=()):
    """Evaluate one supplied snapshot; never apply the resulting requests.

    drain_commitments=None means threshold entry has not yet been recorded.
    After entry, callers must pass the PREVIOUS decision's remaining_melee,
    including an empty tuple, so new IDs cannot join the completion set.
    A surviving committed action disappearing from the active snapshot must be
    named in completed_melee_ids; disappearance alone is not completion.
    previously_neutralized is sticky external state, not a health-based exit.
    """
    if type(snapshot) is not DamageSnapshot or type(previously_neutralized) is not bool:
        raise ValueError('Typed damage snapshot and Boolean neutralized state required')
    if isinstance(completed_melee_ids, (str, bytes, bytearray, dict)):
        raise ValueError('Completion IDs require a collection, not text or a mapping')
    completed = tuple(completed_melee_ids)
    if (any(type(action) is not str or not action for action in completed)
            or len(set(completed)) != len(completed)):
        raise ValueError('Completion IDs must be distinct nonempty strings')
    commitments = None
    if drain_commitments is not None:
        if isinstance(drain_commitments, (str, bytes, bytearray, dict)):
            raise ValueError('Drain commitments require a collection of leg/action pairs')
        commitments = tuple(tuple(pair) for pair in drain_commitments)
        for pair in commitments:
            if (len(pair) != 2 or type(pair[0]) is not int or not 0 <= pair[0] < LEG_COUNT
                    or type(pair[1]) is not str or not pair[1]):
                raise ValueError('Drain commitments must contain leg-index/action-ID pairs')
        if (len({leg for leg, _ in commitments}) != len(commitments)
                or len({action for _, action in commitments}) != len(commitments)):
            raise ValueError('Drain commitments cannot repeat legs or action IDs')
    failed = tuple(i for i, health in enumerate(snapshot.health_percent) if health == 0)
    active = tuple((i, action) for i, action in enumerate(snapshot.active_melee_ids) if action is not None)
    abort = tuple(pair for pair in active if pair[0] in failed)
    surviving = tuple(pair for pair in active if pair[0] not in failed)
    active_ids = {action for _, action in active}
    if any(action in active_ids for action in completed):
        raise ValueError('An action cannot be both active and completed in the same snapshot')
    if completed and commitments is None:
        raise ValueError('Completion receipts require an existing drain commitment set')
    if commitments is not None:
        committed_ids = {action for _, action in commitments}
        if any(action not in committed_ids for action in completed):
            raise ValueError('Unknown or repeated completion receipt outside remaining commitments')
        for leg, action in commitments:
            if leg not in failed and (leg, action) not in surviving and action not in completed:
                raise ValueError('Surviving committed melee disappeared without a completion receipt')
    # A retained commitment set (even empty) also latches neutralization. This
    # avoids recovery/health changes silently releasing the no-new-attack rule.
    required = previously_neutralized or len(failed) >= 5 or commitments is not None
    if previously_neutralized:
        if commitments:
            raise ValueError('Final Neutralized cannot retain unfinished melee commitments')
        if surviving:
            raise ValueError('Supplied active melee conflicts with final Neutralized')
        remaining = ()
        phase = 'neutralized'
    elif required:
        if commitments is None:
            remaining = surviving
        else:
            permitted = set(commitments)
            if any(pair not in permitted for pair in surviving):
                raise ValueError('New or replaced melee ID appeared after neutralization threshold')
            remaining = surviving
        # Empty drain means closing/disable intents may now be requested. It is
        # NOT confirmation of the full gameplay state (or unresolved beam path).
        phase = 'finishing_existing_melee' if remaining else 'awaiting_neutralization_effects'
    else:
        remaining = ()
        phase = 'not_requested'
    return DamageTransitionDecision(
        subject_identity=snapshot.subject_identity,
        failed_legs=failed, abort_melee=abort, request_safe_retraction=failed,
        finish_existing_melee=surviving, neutralization_required=required,
        neutralization_phase=phase, reject_new_attacks=required, remaining_melee=remaining,
        preserve_current_main_eye_state=required and bool(remaining),
        request_close_main_eye=required and not remaining,
        request_disable_antimagic=required and not remaining)


def assess_recovery_eligibility(snapshot, *, in_combat, previously_neutralized):
    """Assess only Task.md's health/combat gates, never apply a recovery.

    Health above zero is the draft functional-leg criterion from the approved
    0 HP rule, not a contact/load-capacity or gradual-damage capability model.
    in_combat is supplied by a future combat system: distance/contact thresholds
    are not invented here. The caller still needs authenticated native state.
    """
    if (type(snapshot) is not DamageSnapshot or type(in_combat) is not bool
            or type(previously_neutralized) is not bool):
        raise ValueError('Typed damage snapshot and Boolean combat/neutralized states required')
    functional = tuple(i for i, health in enumerate(snapshot.health_percent) if health > 0)
    blockers = []
    if not previously_neutralized:
        blockers.append('not_in_final_neutralized')
    if in_combat:
        blockers.append('still_in_combat')
    if len(functional) < 4:
        blockers.append('fewer_than_four_nonzero_health_legs')
    if any(action is not None for action in snapshot.active_melee_ids):
        blockers.append('active_melee_conflicts_with_final_neutralized')
    return dict(status='draft_recovery_eligibility', subjectIdentity=snapshot.subject_identity,
                functionalLegs=tuple(functional),
                functionalLegCount=len(functional), inCombat=in_combat,
                suppliedPreviouslyNeutralized=previously_neutralized,
                healthAndCombatCriteriaMet=not in_combat and len(functional) >= 4,
                eligibleForNativeRecoveryAssessment=not blockers, blockers=tuple(blockers),
                neutralizationExitApplied=False, nativeStateConfirmed=False,
                supportConfirmed=False, runtimeReady=False, motionAuthorized=False)


class DamagePolicyLedger:
    """Local sequencing for supplied snapshots; not native state or ownership.

    Keeps the completion set after threshold entry, including the empty latch.
    There is deliberately no reset/recover method: a health change cannot clear
    neutralization. A future authenticated gameplay handoff is separate work.
    """
    def __init__(self, *, previously_neutralized=False):
        if type(previously_neutralized) is not bool:
            raise ValueError('Boolean supplied initial neutralization state required')
        self._previously_neutralized = previously_neutralized
        self._remaining = () if previously_neutralized else None
        self._decision = None
        self._held_reason = None
        self._last_snapshot_revision = None
        self._subject_identity = None

    @property
    def last_decision(self):
        return self._decision

    @property
    def held_reason(self):
        return self._held_reason

    def hold(self, reason):
        if type(reason) is not str or not reason:
            raise ValueError('Nonempty local hold reason required')
        if self._held_reason is None:
            self._held_reason = reason
        self._decision = None
        # Retain the latch/commitments for diagnosis, but publish no decision.

    def evaluate(self, snapshot, *, snapshot_revision=None, completed_melee_ids=()):
        """Consume one newer supplied revision; gaps are not coverage evidence.

        The revision must come from the snapshot producer, not be generated on
        each read of unchanged data. It is not authenticated by this ledger.
        None is an invalid sentinel so omission is rejected INSIDE the guarded
        method, clearing a previous published decision through local hold.
        """
        try:
            if self._held_reason is not None:
                raise ValueError('Damage policy ledger is locally held: '+self._held_reason)
            if type(snapshot) is not DamageSnapshot:
                raise ValueError('Typed damage snapshot required')
            if (self._subject_identity is not None
                    and snapshot.subject_identity != self._subject_identity):
                raise ValueError('Damage snapshot world/actor/lifetime identity changed')
            if (type(snapshot_revision) is not int or snapshot_revision < 0
                    or (self._last_snapshot_revision is not None
                        and snapshot_revision <= self._last_snapshot_revision)):
                raise ValueError('Strictly increasing nonnegative snapshot revision required')
            decision = decide_damage_transition(
                snapshot, previously_neutralized=self._previously_neutralized,
                drain_commitments=self._remaining, completed_melee_ids=completed_melee_ids)
            # The stateless helper has no ordered source revision. Bind the
            # immutable result only after all ledger input checks succeeded.
            decision = replace(decision, source_snapshot_revision=snapshot_revision)
            if decision.neutralization_required:
                self._remaining = decision.remaining_melee
            self._last_snapshot_revision = snapshot_revision
            self._subject_identity = snapshot.subject_identity
            self._decision = decision
            return decision
        except Exception as exc:
            self.hold('damage_policy: '+type(exc).__name__+': '+str(exc))
            raise
