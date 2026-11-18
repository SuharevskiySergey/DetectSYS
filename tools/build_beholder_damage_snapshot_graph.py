"""Installed damage graphs; compilation and limited editor numeric cases verified.

No actors, setters, damage, hit-window commands, state, clocks or Unreal access.
This is NOT the Python ledger: no action IDs, revisions or completion history.
Non-idempotent: do not reapply. Separately authorized numeric run passed 174
direct cases; no gameplay/motion validation. Further calls need permission.
Python generator itself has not been executed or tested.
"""
from build_beholder_plane_graph import Plan


BP = '/Game/BeholderPrototype/Damage/BP_BeholderDamageSnapshot'
FUNCTION = 'EvaluateDamageSnapshot'
HELPER = 'EvaluateLegDamageSnapshot'
PARENT = '/Script/Engine.BlueprintFunctionLibrary'
INPUT_LAYOUT = tuple((f'Leg{i}HealthPercent', 'float') for i in range(8))+tuple(
    (f'Leg{i}MeleeActive', 'bool') for i in range(8))+(
    ('NeutralizationLatched', 'bool'), ('PreviouslyNeutralized', 'bool'))
OUTPUT_LAYOUT = (
    ('NumericInputsAccepted', 'bool'), ('MotionAuthorized', 'bool'),
    ('FailedLegCount', 'int'), ('NeutralizationRequired', 'bool'),
    ('RejectNewAttacks', 'bool'), ('HasSurvivingMelee', 'bool'),
    ('PreserveCurrentMainEyeState', 'bool'), ('RequestCloseMainEye', 'bool'),
    ('RequestDisableAntimagic', 'bool'), ('GameplayNeutralizedConfirmed', 'bool'),
    ('BeamTransitionUnresolved', 'bool'))+tuple(
    (f'Leg{i}{field}', 'bool') for i in range(8)
    for field in ('Failed', 'AbortMelee', 'RequestSafeRetraction', 'FinishExistingMelee'))


def _returns(p, layout, literal_fields=None):
    defaults = {name: 0 if kind == 'int' else False for name, kind in layout}
    p.node('reject', 'FunctionResult', pinDefaults=defaults)
    for name, value in dict(defaults, NumericInputsAccepted=True).items():
        if literal_fields is not None and name not in literal_fields:
            continue
        p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return',
                          pinName=name, propertyValue=value))


def _function_plan(p, inputs, outputs, dependencies=()):
    # Guard is evaluated only when explicitly generating the source plan.
    # It is not a recorded measurement or permission to generate/install it.
    if len(p.ops) > 200:
        raise ValueError('Complete function body exceeds editor batch limit: '+p.graph)
    return dict(graphName=p.graph, functionDeclaration=dict(
        blueprintPath=BP, functionName=p.graph, pure=False, isPublic=True,
        inputs=[dict(name=name, type=kind) for name, kind in inputs],
        outputs=[dict(name=name, type=kind) for name, kind in outputs]),
        operations=p.ops, dependencies=tuple(dependencies),
        requiresExistingEntryReturnBinding=True, installBodyAsSingleBatch=True)


def leg_plan():
    p = Plan(HELPER)
    inputs = (('HealthPercent', 'float'), ('MeleeActive', 'bool'))
    outputs = (('NumericInputsAccepted', 'bool'), ('Failed', 'bool'),
               ('AbortMelee', 'bool'), ('RequestSafeRetraction', 'bool'),
               ('FinishExistingMelee', 'bool'), ('FailedContribution', 'int'))
    _returns(p, outputs)
    p.node('valid', 'MathExpression', expression='(hp >= 0.000000) && (hp <= 100.000000)')
    p.wire('entry.HealthPercent', 'valid.hp')
    p.node('branch', 'Branch')
    p.wire('entry.then', 'branch.execute')
    p.wire('valid.ReturnValue', 'branch.Condition')
    p.wire('branch.else', 'reject.execute')
    p.wire('branch.then', 'entry_return.execute')
    p.node('failed', 'MathExpression', expression='hp == 0.000000')
    p.wire('entry.HealthPercent', 'failed.hp')
    p.call('abort', 'BooleanAND')
    p.wire('failed.ReturnValue', 'abort.A')
    p.wire('entry.MeleeActive', 'abort.B')
    p.node('positive', 'MathExpression', expression='hp > 0.000000')
    p.wire('entry.HealthPercent', 'positive.hp')
    p.call('finish', 'BooleanAND')
    p.wire('positive.ReturnValue', 'finish.A')
    p.wire('entry.MeleeActive', 'finish.B')
    for field, source in (('Failed', 'failed'), ('RequestSafeRetraction', 'failed'),
                          ('AbortMelee', 'abort'), ('FinishExistingMelee', 'finish')):
        p.wire(source+'.ReturnValue', 'entry_return.'+field)
    p.call('count', 'SelectInt', defaults={'A': 1, 'B': 0})
    p.wire('failed.ReturnValue', 'count.bPickA')
    p.wire('count.ReturnValue', 'entry_return.FailedContribution')
    return _function_plan(p, inputs, outputs)


def snapshot_plan():
    p = Plan(FUNCTION)
    _returns(p, OUTPUT_LAYOUT, literal_fields=(
        'NumericInputsAccepted', 'MotionAuthorized', 'GameplayNeutralizedConfirmed'))
    previous_exec = 'entry.then'
    for i in range(8):
        p.call(f'leg{i}', HELPER, BP)
        p.wire('entry.__WorldContext', f'leg{i}.__WorldContext')
        p.wire(previous_exec, f'leg{i}.execute')
        previous_exec = f'leg{i}.then'
        p.wire(f'entry.Leg{i}HealthPercent', f'leg{i}.HealthPercent')
        p.wire(f'entry.Leg{i}MeleeActive', f'leg{i}.MeleeActive')
        for field in ('Failed', 'AbortMelee', 'RequestSafeRetraction', 'FinishExistingMelee'):
            p.wire(f'leg{i}.{field}', f'entry_return.Leg{i}{field}')
    accepted = 'leg0.NumericInputsAccepted'
    for i in range(1, 8):
        p.call(f'accepted{i}', 'BooleanAND')
        p.wire(accepted, f'accepted{i}.A')
        p.wire(f'leg{i}.NumericInputsAccepted', f'accepted{i}.B')
        accepted = f'accepted{i}.ReturnValue'
    p.node('health_branch', 'Branch')
    p.wire(previous_exec, 'health_branch.execute')
    p.wire(accepted, 'health_branch.Condition')
    p.wire('health_branch.else', 'reject.execute')
    previous = 'leg0.FailedContribution'
    for i in range(1, 8):
        p.call(f'sum{i}', 'Add_IntInt')
        p.wire(previous, f'sum{i}.A')
        p.wire(f'leg{i}.FailedContribution', f'sum{i}.B')
        previous = f'sum{i}.ReturnValue'
    p.wire(previous, 'entry_return.FailedLegCount')
    surviving = 'leg0.FinishExistingMelee'
    for i in range(1, 8):
        p.call(f'surviving{i}', 'BooleanOR')
        p.wire(surviving, f'surviving{i}.A')
        p.wire(f'leg{i}.FinishExistingMelee', f'surviving{i}.B')
        surviving = f'surviving{i}.ReturnValue'
    p.node('threshold', 'MathExpression', expression='count >= 5')
    p.wire(previous, 'threshold.count')
    p.call('latched', 'BooleanOR')
    p.wire('entry.NeutralizationLatched', 'latched.A')
    p.wire('entry.PreviouslyNeutralized', 'latched.B')
    p.call('required', 'BooleanOR')
    p.wire('threshold.ReturnValue', 'required.A')
    p.wire('latched.ReturnValue', 'required.B')
    p.call('inconsistent', 'BooleanAND')
    p.wire('entry.PreviouslyNeutralized', 'inconsistent.A')
    p.wire(surviving, 'inconsistent.B')
    p.node('consistency_branch', 'Branch')
    p.wire('health_branch.then', 'consistency_branch.execute')
    p.wire('inconsistent.ReturnValue', 'consistency_branch.Condition')
    p.wire('consistency_branch.then', 'reject.execute')
    p.wire('consistency_branch.else', 'entry_return.execute')
    for field in ('NeutralizationRequired', 'RejectNewAttacks', 'BeamTransitionUnresolved'):
        p.wire('required.ReturnValue', 'entry_return.'+field)
    p.wire(surviving, 'entry_return.HasSurvivingMelee')
    p.call('no_surviving', 'Not_PreBool')
    p.wire(surviving, 'no_surviving.A')
    for name, source, fields in (
            ('preserve', surviving, ('PreserveCurrentMainEyeState',)),
            ('close', 'no_surviving.ReturnValue', ('RequestCloseMainEye', 'RequestDisableAntimagic'))):
        p.call(name, 'BooleanAND')
        p.wire('required.ReturnValue', name+'.A')
        p.wire(source, name+'.B')
        for field in fields:
            p.wire(name+'.ReturnValue', 'entry_return.'+field)
    return _function_plan(p, INPUT_LAYOUT, OUTPUT_LAYOUT, dependencies=(HELPER,))


def plans():
    return dict(blueprintPath=BP, parentClass=PARENT,
                functions=[leg_plan(), snapshot_plan()], installationOrder=(HELPER, FUNCTION),
                requiresSeparateFunctionDeclarations=True,
                installed=True, compilationPerformed=True, compilationVerified=True,
                numericVerificationPerformed=True, numericVerificationCases=174,
                numericVerificationReport='Saved/BeholderDamageNumeric_0c06750a432441b99108be51c3615387.json',
                verificationPerformed=True,
                gameplayConnected=False, motionAuthorized=False)
