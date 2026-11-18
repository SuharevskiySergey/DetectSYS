"""Installed facade; compilation and 68 limited editor numeric cases verified.

No actors, component writes, time source, Tick, interpolation or motion admission.
Do not reapply this non-idempotent plan to the existing asset. Compilation does
not authorize further function execution; runtime/precision gaps remain.
For a NEW Function Library add functionDeclaration separately, then graph batch.
"""
import json

from build_beholder_plane_graph import Plan
from beholder_dogleg_job_contract import (
    SAMPLE_BLUEPRINT, SAMPLE_FUNCTION, SAMPLE_INPUT_LAYOUT, SAMPLE_OUTPUT_LAYOUT,
    CLOCK_BLUEPRINT, CLOCK_FUNCTION, CLOCK_INPUT_LAYOUT, CLOCK_OUTPUT_LAYOUT,
    TARGETS_BLUEPRINT, TARGETS_FUNCTION, TARGETS_INPUT_LAYOUT, TARGETS_OUTPUT_LAYOUT)

BP = SAMPLE_BLUEPRINT
PARENT = '/Script/Engine.BlueprintFunctionLibrary'
FUNCTION = SAMPLE_FUNCTION


def plans():
    p = Plan(FUNCTION)
    p.ops.append(dict(edit='add_function', id='entry', functionName=FUNCTION,
                      pure=False, isPublic=True,
                      inputs=[dict(name=n, type=t) for n,t in SAMPLE_INPUT_LAYOUT],
                      outputs=[dict(name=n, type=t) for n,t in SAMPLE_OUTPUT_LAYOUT]))
    defaults = {name: False if kind == 'bool' else 0 for name,kind in SAMPLE_OUTPUT_LAYOUT}
    p.node('reject', 'FunctionResult', pinDefaults=defaults)
    for name, value in dict(defaults, NumericInputsAccepted=True).items():
        p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return',
                          pinName=name, propertyValue=value))

    # Both are impure numeric functions. Their outputs belong to the ONE call
    # in this exec chain, not to independently re-evaluated pure expressions.
    p.call('clock', CLOCK_FUNCTION, CLOCK_BLUEPRINT)
    p.wire('entry.__WorldContext', 'clock.__WorldContext')
    for name, _kind in CLOCK_INPUT_LAYOUT:
        p.wire('entry.'+name, 'clock.'+name)
    p.wire('entry.then', 'clock.execute')
    p.node('clock_inputs_accepted', 'Branch')
    p.wire('clock.then', 'clock_inputs_accepted.execute')
    p.wire('clock.NumericInputsAccepted', 'clock_inputs_accepted.Condition')
    p.wire('clock_inputs_accepted.else', 'reject.execute')
    p.node('clock_unexpected_authorization', 'Branch')
    p.wire('clock_inputs_accepted.then', 'clock_unexpected_authorization.execute')
    p.wire('clock.MotionAuthorized', 'clock_unexpected_authorization.Condition')
    p.wire('clock_unexpected_authorization.then', 'reject.execute')

    p.call('targets', TARGETS_FUNCTION, TARGETS_BLUEPRINT)
    p.wire('entry.__WorldContext', 'targets.__WorldContext')
    p.wire('clock_unexpected_authorization.else', 'targets.execute')
    for name, _kind in TARGETS_INPUT_LAYOUT:
        source = 'clock.Phase' if name == 'Phase' else 'entry.'+name
        p.wire(source, 'targets.'+name)
    p.node('targets_inputs_accepted', 'Branch')
    p.wire('targets.then', 'targets_inputs_accepted.execute')
    p.wire('targets.NumericInputsAccepted', 'targets_inputs_accepted.Condition')
    p.wire('targets_inputs_accepted.else', 'reject.execute')
    p.node('targets_unexpected_authorization', 'Branch')
    p.wire('targets_inputs_accepted.then', 'targets_unexpected_authorization.execute')
    p.wire('targets.MotionAuthorized', 'targets_unexpected_authorization.Condition')
    p.wire('targets_unexpected_authorization.then', 'reject.execute')
    p.wire('targets_unexpected_authorization.else', 'entry_return.execute')

    # Do not forward either callee's authorization flag. The facade's own
    # accepted/reject returns have MotionAuthorized=false as a literal.
    flags = ('NumericInputsAccepted', 'MotionAuthorized')
    for name, _kind in CLOCK_OUTPUT_LAYOUT:
        if name not in flags:
            p.wire('clock.'+name, 'entry_return.'+name)
    for name, _kind in TARGETS_OUTPUT_LAYOUT:
        if name not in flags:
            p.wire('targets.'+name, 'entry_return.'+name)

    declaration = {k: v for k,v in p.ops[0].items() if k not in ('edit', 'id')}
    declaration['blueprintPath'] = BP
    return dict(blueprintPath=BP, parentClass=PARENT, graphName=FUNCTION,
                functionDeclaration=declaration, operations=p.ops,
                installed=True, compilationPerformed=True, compilationVerified=True,
                numericVerificationPerformed=True, numericVerificationCases=68,
                numericVerificationReport='Saved/BeholderDoglegNumeric_1aaefde320124c11b27cfbc2333055c1.json',
                runtimeIKExecuted=False, motionAuthorized=False)


if __name__ == '__main__':
    print(json.dumps(plans(), indent=2))
