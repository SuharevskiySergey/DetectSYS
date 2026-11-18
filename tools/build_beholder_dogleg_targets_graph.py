"""Installed targets; compilation and 80 limited editor numeric cases verified.

No actor/component writes, motion admission, Tick, interpolation or actuation.
Do not reapply this non-idempotent plan to the existing asset. A new empty
Function Library needs functionDeclaration through add_function FIRST: the
batch handler needs an existing graph. Then use graphName and operations;
the declaration step in the batch reuses the matching function signature.
NumericInputsAccepted never authorizes motion. Remaining precision/geometry
cases are untested; further numeric calls require separate permission.
"""
import json

from build_beholder_plane_graph import Plan
from beholder_dogleg_job_contract import TARGETS_INPUT_LAYOUT, TARGETS_OUTPUT_LAYOUT

BP = '/Game/BeholderPrototype/Telescopic/BP_BeholderDoglegTargets'
PARENT = '/Script/Engine.BlueprintFunctionLibrary'
FUNCTION = 'CalculateDoglegTargets'
HALF_DEGREES_TO_RADIANS = '0.0087266462599716479'


def outputs():
    return list(TARGETS_OUTPUT_LAYOUT)


def plans():
    p = Plan(FUNCTION)
    p.ops.append(dict(edit='add_function', id='entry', functionName=FUNCTION,
                      pure=False, isPublic=True,
                      inputs=[dict(name=n, type=t) for n,t in TARGETS_INPUT_LAYOUT],
                      outputs=[dict(name=n, type=t) for n,t in outputs()]))
    defaults = {n: False if t == 'bool' else 0 for n,t in outputs()}
    p.node('reject', 'FunctionResult', pinDefaults=defaults)
    accepted_defaults = dict(defaults, NumericInputsAccepted=True)
    p.node('yaw_return', 'FunctionResult', pinDefaults=accepted_defaults)
    # The function's automatically created return is the pitch path. Explicit
    # zero defaults include every unused joint, not just the three bent ones.
    for name, value in accepted_defaults.items():
        p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return',
                          pinName=name, propertyValue=value))

    p.node('numeric_inputs', 'MathExpression', expression=(
        '(base >= 0.400000) && (base <= 0.900000) && '
        '(phase >= 0.000000) && (phase <= 1.000000) && '
        '(amplitude >= -1.000000) && (amplitude <= 1.000000)'))
    for source, target in [('BaseExtension', 'base'), ('Phase', 'phase'),
                           ('AmplitudeDegrees', 'amplitude')]:
        p.wire('entry.'+source, 'numeric_inputs.'+target)
    p.node('valid_branch', 'Branch')
    p.wire('entry.then', 'valid_branch.execute')
    p.wire('numeric_inputs.ReturnValue', 'valid_branch.Condition')
    p.wire('valid_branch.else', 'reject.execute')

    p.node('angle', 'MathExpression', expression='amplitude*phase')
    p.wire('entry.AmplitudeDegrees', 'angle.amplitude')
    p.wire('entry.Phase', 'angle.phase')
    # Stable 4*sin^2(a/2)/10 compensation, NOT constant-total redistribution.
    p.node('extension', 'MathExpression', expression=(
        f'base+0.400000*sin(angle*{HALF_DEGREES_TO_RADIANS})'
        f'*sin(angle*{HALF_DEGREES_TO_RADIANS})'))
    p.wire('entry.BaseExtension', 'extension.base')
    p.wire('angle.ReturnValue', 'extension.angle')
    p.node('middle_angle', 'MathExpression', expression='-2.000000*angle')
    p.wire('angle.ReturnValue', 'middle_angle.angle')
    p.node('axis_branch', 'Branch')
    p.wire('valid_branch.then', 'axis_branch.execute')
    p.wire('entry.UseYaw', 'axis_branch.Condition')
    p.wire('axis_branch.then', 'yaw_return.execute')
    p.wire('axis_branch.else', 'entry_return.execute')

    for result in ('entry_return', 'yaw_return'):
        p.wire('extension.ReturnValue', result+'.CompensatedExtension')
    for i in range(10):
        p.node(f'stage{i}', 'MathExpression',
               expression=f'clamp(10.000000*extension-{i}.000000,0.000000,1.000000)')
        p.wire('extension.ReturnValue', f'stage{i}.extension')
        for result in ('entry_return', 'yaw_return'):
            p.wire(f'stage{i}.ReturnValue', f'{result}.Stage{i}Target')
    for result, axis in [('entry_return', 'Pitch'), ('yaw_return', 'Yaw')]:
        for joint in (1, 2, 3):
            source = 'middle_angle.ReturnValue' if joint == 2 else 'angle.ReturnValue'
            p.wire(source, f'{result}.Joint{joint}{axis}Target')
    declaration = {k: v for k,v in p.ops[0].items() if k not in ('edit', 'id')}
    declaration['blueprintPath'] = BP
    return dict(blueprintPath=BP, parentClass=PARENT, graphName=FUNCTION,
                functionDeclaration=declaration, operations=p.ops,
                installed=True, compilationVerified=True, numericVerificationPerformed=True,
                numericVerificationCases=80,
                numericVerificationReport='Saved/BeholderDoglegNumeric_1aaefde320124c11b27cfbc2333055c1.json',
                runtimeIKExecuted=False, motionAuthorized=False)


if __name__ == '__main__':
    print(json.dumps(plans(), indent=2))
