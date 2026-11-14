"""UNINSTALLED, UNVERIFIED Blueprint plan for one numeric dogleg target snapshot.

No actor/component writes, motion admission, Tick, interpolation or actuation.
Create/inspect an isolated Blueprint Function Library before applying this
non-idempotent plan. NumericInputsAccepted never authorizes motion.
"""
import json

from build_beholder_plane_graph import Plan

BP = '/Game/BeholderPrototype/Telescopic/BP_BeholderDoglegTargets'
PARENT = '/Script/Engine.BlueprintFunctionLibrary'
FUNCTION = 'CalculateDoglegTargets'
HALF_DEGREES_TO_RADIANS = '0.0087266462599716479'


def outputs():
    return [('NumericInputsAccepted', 'bool'), ('MotionAuthorized', 'bool'),
            ('CompensatedExtension', 'float')]+[
        (f'Stage{i}Target', 'float') for i in range(10)]+[
        (f'Joint{i}{axis}Target', 'float') for i in range(1, 10) for axis in ('Pitch', 'Yaw')]


def plans():
    p = Plan(FUNCTION)
    p.ops.append(dict(edit='add_function', id='entry', functionName=FUNCTION,
                      pure=False, isPublic=True,
                      inputs=[dict(name=n, type=t) for n,t in
                              [('BaseExtension', 'float'), ('Phase', 'float'),
                               ('AmplitudeDegrees', 'float'), ('UseYaw', 'bool')]],
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
    return dict(blueprintPath=BP, parentClass=PARENT, operations=p.ops,
                installed=False, verificationPerformed=False,
                runtimeIKExecuted=False, motionAuthorized=False)


if __name__ == '__main__':
    print(json.dumps(plans(), indent=2))
