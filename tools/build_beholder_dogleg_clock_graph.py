"""Installed clock; compilation and 80 limited editor numeric cases verified.

No game-time reads, Tick, persistent state, target-function calls or actuation.
This is a future executor building block, not an executor or motion admission.
Do not reapply this non-idempotent plan to the existing asset. For a NEW empty
Function Library, add functionDeclaration separately first; then use graphName
and operations on its graph. Extreme UE precision/duration cases remain untested;
further execution needs separate permission. See numeric-verification document.
"""
import json

from build_beholder_plane_graph import Plan
from beholder_dogleg_job_contract import (CLOCK_BLUEPRINT, CLOCK_FUNCTION,
                                         MIN_SEGMENT_DURATION_TEXT, MAX_SEGMENT_DURATION_TEXT,
                                         CLOCK_INPUT_LAYOUT, CLOCK_OUTPUT_LAYOUT)

BP = CLOCK_BLUEPRINT
PARENT = '/Script/Engine.BlueprintFunctionLibrary'
FUNCTION = CLOCK_FUNCTION
# Proposed arithmetic floor only; not a physical/controller acceleration limit.
MIN_SEGMENT_SECONDS = MIN_SEGMENT_DURATION_TEXT


def outputs():
    return list(CLOCK_OUTPUT_LAYOUT)


def plans():
    p = Plan(FUNCTION)
    p.ops.append(dict(edit='add_function', id='entry', functionName=FUNCTION,
                      pure=False, isPublic=True,
                      inputs=[dict(name=n, type=t) for n,t in CLOCK_INPUT_LAYOUT],
                      outputs=[dict(name=n, type=t) for n,t in outputs()]))
    defaults = {n: False if t == 'bool' else 0 for n,t in outputs()}
    accepted = dict(defaults, NumericInputsAccepted=True)
    p.node('reject', 'FunctionResult', pinDefaults=defaults)
    returns = [('entry_return', False, False), ('early_reverse', False, True),
               ('late_forward', True, False), ('late_reverse', True, True)]
    for result, _late, _reverse in returns:
        if result == 'entry_return':
            for name, value in accepted.items():
                p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return',
                                  pinName=name, propertyValue=value))
        else:
            p.node(result, 'FunctionResult', pinDefaults=accepted)

    p.node('numeric_inputs', 'MathExpression', expression=(
        f'(duration >= {MIN_SEGMENT_SECONDS}) && (duration <= {MAX_SEGMENT_DURATION_TEXT}) && '
        '(elapsed >= 0.000000) && (elapsed <= duration) && '
        '(lo >= 0.000000) && (lo < hi) && (hi <= 1.000000)'))
    arguments = [('SegmentElapsedSeconds', 'elapsed'), ('SegmentDurationSeconds', 'duration'),
                 ('PhaseStart', 'lo'), ('PhaseEnd', 'hi')]
    for source, target in arguments:
        p.wire('entry.'+source, 'numeric_inputs.'+target)
    p.node('valid_branch', 'Branch')
    p.wire('entry.then', 'valid_branch.execute')
    p.wire('numeric_inputs.ReturnValue', 'valid_branch.Condition')
    p.wire('valid_branch.else', 'reject.execute')

    p.node('unit_time', 'MathExpression', expression='elapsed/duration')
    p.wire('entry.SegmentElapsedSeconds', 'unit_time.elapsed')
    p.wire('entry.SegmentDurationSeconds', 'unit_time.duration')
    p.node('tail', 'MathExpression', expression='min(u,1.000000-u)')
    p.wire('unit_time.ReturnValue', 'tail.u')
    p.node('early_q', 'MathExpression', expression='v*v*v*(10.000000-15.000000*v+6.000000*v*v)')
    p.wire('tail.ReturnValue', 'early_q.v')
    p.node('late_q', 'MathExpression', expression='1.000000-q')
    p.wire('early_q.ReturnValue', 'late_q.q')
    # u always increases chronologically, including a returning segment.
    # Return phase is hi-span*q(u), so BOTH derivatives negate in this form.
    p.node('velocity', 'MathExpression', expression=(
        '(hi-lo)*30.000000*u*u*(1.000000-u)*(1.000000-u)/duration'))
    p.node('acceleration', 'MathExpression', expression=(
        '(hi-lo)*60.000000*u*(1.000000-u)*(1.000000-2.000000*u)/(duration*duration)'))
    for node in ('velocity', 'acceleration'):
        p.wire('entry.PhaseStart', node+'.lo')
        p.wire('entry.PhaseEnd', node+'.hi')
        p.wire('entry.SegmentDurationSeconds', node+'.duration')
        p.wire('unit_time.ReturnValue', node+'.u')
    for name in ('velocity', 'acceleration'):
        p.node('negative_'+name, 'MathExpression', expression='0.000000-value')
        p.wire(name+'.ReturnValue', 'negative_'+name+'.value')
    p.node('complete', 'MathExpression', expression='elapsed >= duration')
    p.wire('entry.SegmentElapsedSeconds', 'complete.elapsed')
    p.wire('entry.SegmentDurationSeconds', 'complete.duration')
    p.node('late', 'MathExpression', expression='u > 0.500000')
    p.wire('unit_time.ReturnValue', 'late.u')
    p.node('half_branch', 'Branch')
    p.wire('valid_branch.then', 'half_branch.execute')
    p.wire('late.ReturnValue', 'half_branch.Condition')
    for half, output in [('early', 'else'), ('late', 'then')]:
        p.node(half+'_direction', 'Branch')
        p.wire('half_branch.'+output, half+'_direction.execute')
        p.wire('entry.Returning', half+'_direction.Condition')
    p.wire('early_direction.else', 'entry_return.execute')
    p.wire('early_direction.then', 'early_reverse.execute')
    p.wire('late_direction.else', 'late_forward.execute')
    p.wire('late_direction.then', 'late_reverse.execute')

    for result, late, reverse in returns:
        node = result+'_phase'
        expression = 'hi-(hi-lo)*q' if reverse else 'lo+(hi-lo)*q'
        p.node(node, 'MathExpression', expression=f'clamp({expression},lo,hi)')
        p.wire('entry.PhaseStart', node+'.lo')
        p.wire('entry.PhaseEnd', node+'.hi')
        p.wire(('late_q' if late else 'early_q')+'.ReturnValue', node+'.q')
        p.wire(node+'.ReturnValue', result+'.Phase')
        p.wire(('negative_velocity' if reverse else 'velocity')+'.ReturnValue', result+'.PhaseVelocityPerSecond')
        p.wire(('negative_acceleration' if reverse else 'acceleration')+'.ReturnValue', result+'.PhaseAccelerationPerSecond2')
        p.wire('complete.ReturnValue', result+'.SegmentComplete')
    declaration = {k: v for k,v in p.ops[0].items() if k not in ('edit', 'id')}
    declaration['blueprintPath'] = BP
    return dict(blueprintPath=BP, parentClass=PARENT, graphName=FUNCTION,
                functionDeclaration=declaration, operations=p.ops,
                installed=True, compilationPerformed=True, compilationVerified=True,
                numericVerificationPerformed=True, numericVerificationCases=80,
                numericVerificationReport='Saved/BeholderDoglegNumeric_1aaefde320124c11b27cfbc2333055c1.json',
                runtimeIKExecuted=False, motionAuthorized=False)


if __name__ == '__main__':
    print(json.dumps(plans(), indent=2))
