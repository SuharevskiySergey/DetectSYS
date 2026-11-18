"""Numeric case DATA; exercised in authorized 228-case editor run, not a runner.

No Unreal import, adapters, editor calls, files, CLI or import-time generation.
Every future execution needs separate user permission and confirmed binding.
"""
import hashlib
import json

from beholder_dogleg_job_contract import (
    CLOCK_BLUEPRINT, CLOCK_FUNCTION, TARGETS_BLUEPRINT, TARGETS_FUNCTION,
    SAMPLE_BLUEPRINT, SAMPLE_FUNCTION)
from beholder_dogleg_timing import quintic


def plan_fingerprint(plan):
    """Deterministic identity of case/comparison data, not a signature.

    Excludes execution status and prose. Covers function bindings, argument
    values, case expectations and companion links. No file or editor access.
    """
    cases = [{key: value for key, value in case.items() if key != 'executionPerformed'}
             for case in plan['cases']]
    payload = dict(schemaVersion=plan['schemaVersion'], cases=cases,
                   comparisons=plan['comparisons'])
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=True, allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def validation_plan():
    """Fresh plain-data cases; no claim that any result was observed.

    Finite binary-exact boundary inputs keep this first plan distinct from the
    still-unresolved float32 rounding, tiny-duration and nonfinite-input probes.
    """
    bindings = dict(clock=(CLOCK_BLUEPRINT, CLOCK_FUNCTION),
                    targets=(TARGETS_BLUEPRINT, TARGETS_FUNCTION),
                    sample=(SAMPLE_BLUEPRINT, SAMPLE_FUNCTION))
    cases = []

    def add(kind, label, arguments, accepted):
        path, function = bindings[kind]
        cases.append(dict(caseId=kind+':'+label, kind=kind, blueprintPath=path,
                          functionName=function, arguments=dict(arguments),
                          expectedNumericInputsAccepted=accepted,
                          expectedMotionAuthorized=False,
                          expectedRejectOutputsAllZero=not accepted,
                          expectedResultSource='python_reference' if accepted else 'literal_rejection',
                          executionPerformed=False))

    clock = dict(SegmentElapsedSeconds=0.0, SegmentDurationSeconds=2.0,
                 PhaseStart=0.0, PhaseEnd=1.0, Returning=False)
    targets = dict(BaseExtension=0.5, Phase=0.5, AmplitudeDegrees=1.0, UseYaw=False)
    for returning in (False, True):
        for elapsed in (0.0, 0.5, 1.0, 1.5, 2.0):
            arguments = dict(clock, Returning=returning, SegmentElapsedSeconds=elapsed)
            label = f'{returning}:{elapsed}'
            add('clock', label, arguments, True)
            for yaw in (False, True):
                add('sample', label+f':yaw={yaw}',
                    dict(arguments, BaseExtension=0.5, AmplitudeDegrees=1.0, UseYaw=yaw), True)
    for yaw in (False, True):
        for amplitude in (-1.0, 0.0, 1.0):
            for phase in (0.0, 0.5, 1.0):
                add('targets', f'{yaw}:{amplitude}:{phase}',
                    dict(targets, UseYaw=yaw, AmplitudeDegrees=amplitude, Phase=phase), True)
    # Non-unit phase span exercises scaling and offset independently of the
    # original full-span cases. Reuse binary-exact inputs, not guessed UE roots.
    for returning in (False, True):
        for elapsed in (0.0, 1.0, 2.0):
            arguments = dict(clock, PhaseStart=0.25, PhaseEnd=0.75,
                             Returning=returning, SegmentElapsedSeconds=elapsed)
            label = f'internal_span:{returning}:{elapsed}'
            add('clock', label, arguments, True)
            for yaw in (False, True):
                for amplitude in (-1.0, 0.0, 1.0):
                    add('sample', label+f':yaw={yaw}:amplitude={amplitude}',
                        dict(arguments, BaseExtension=0.5,
                             AmplitudeDegrees=amplitude, UseYaw=yaw), True)
    clock_rejections = (
        ('elapsed_negative', dict(SegmentElapsedSeconds=-0.5)),
        ('elapsed_overrun', dict(SegmentElapsedSeconds=2.5)),
        ('duration_zero', dict(SegmentDurationSeconds=0.0)),
        ('duration_over_limit', dict(SegmentDurationSeconds=64.0)),
        ('phase_equal', dict(PhaseStart=0.5, PhaseEnd=0.5)),
        ('phase_reversed', dict(PhaseStart=1.0, PhaseEnd=0.0)),
        ('phase_negative', dict(PhaseStart=-0.5)),
        ('phase_over_unit', dict(PhaseEnd=1.5)))
    for label, changes in clock_rejections:
        arguments = dict(clock, **changes)
        add('clock', label, arguments, False)
        add('sample', 'clock_'+label,
            dict(arguments, BaseExtension=0.5, AmplitudeDegrees=1.0, UseYaw=False), False)
    for label, changes in (
            ('base_low', dict(BaseExtension=0.25)), ('base_high', dict(BaseExtension=1.0)),
            ('amplitude_low', dict(AmplitudeDegrees=-1.5)),
            ('amplitude_high', dict(AmplitudeDegrees=1.5))):
        add('targets', label, dict(targets, **changes), False)
        add('sample', 'targets_'+label,
            dict(clock, BaseExtension=0.5, AmplitudeDegrees=1.0, UseYaw=False) | changes, False)
    for label, phase in (('phase_low', -0.5), ('phase_high', 1.5)):
        add('targets', label, dict(targets, Phase=phase), False)
    # Companion calls use the canonical reference Phase, NOT an assertion that
    # a supplied/rounded engine Phase has identical bits. The reviewer separately
    # checks facade targets at its supplied Phase.
    comparisons = []
    samples = [case for case in cases if case['kind'] == 'sample'
               and case['expectedNumericInputsAccepted']]
    for index, sample in enumerate(samples):
        arguments = sample['arguments']
        clock_arguments = {name: arguments[name] for name in clock}
        q, _dq, _ddq = quintic(arguments['SegmentElapsedSeconds']/arguments['SegmentDurationSeconds'])
        span = arguments['PhaseEnd']-arguments['PhaseStart']
        phase = (arguments['PhaseEnd']-span*q if arguments['Returning']
                 else arguments['PhaseStart']+span*q)
        target_arguments = {name: arguments[name] for name in targets if name != 'Phase'}
        target_arguments['Phase'] = phase
        add('clock', f'companion:{index}', clock_arguments, True)
        clock_id = cases[-1]['caseId']
        add('targets', f'companion:{index}', target_arguments, True)
        comparisons.append(dict(sampleCaseId=sample['caseId'], clockCaseId=clock_id,
                                targetsCaseId=cases[-1]['caseId'],
                                targetPhaseSource='canonical_python_clock_reference'))
    return dict(schemaVersion=1, status='prepared_unexecuted', cases=cases,
                comparisons=comparisons, executionPerformed=False,
                motionAuthorized=False, runtimeReady=False,
                prerequisites=['separate_user_permission', 'edit_mode_no_game_world',
                               'confirmed_reflected_signature_and_hidden_context',
                               'verified_state_free_library_bodies'],
                comparisonPolicy=dict(flags='exact bool', outputLayout='exact declared signature',
                                      acceptedReference='quintic then dogleg_pose at returned Phase',
                                      facadeConsistency='same-input clock and targets snapshots',
                                      tolerances='must be agreed before execution; never auto-relax'),
                deferred=['NaN/Infinity binding', 'float32-near-boundary rounding',
                          'minimum-duration derivatives', 'clamp-root float32 representation',
                          'physical_support', 'motion_admission'])
