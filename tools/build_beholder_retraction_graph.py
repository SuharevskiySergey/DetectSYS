"""Explicit monitored return from four contacts. No body support or sweep.

State 5 retracts; state 6 is folded/terminal. Existing state 3 is aborted.
Install after the approach/footprint helpers. Creation plans are not idempotent.
"""
import json

from build_beholder_body_probe_graph import BODY
from build_beholder_contact_request_graph import INDICES, OTHER_INDICES
from build_beholder_contact_watch_graph import function, own_call, fresh_sample_gate
from build_beholder_plane_graph import Plan
from build_beholder_surface_graph import BP as LEG

TIME = ('(dt >= 0.000000) && (dt <= 10.000000) && '
        '(FourContactWatchTimeout >= 0.100000) && (FourContactWatchTimeout <= 60.000000) && '
        '(FourContactRetractionElapsed >= 0.000000) && '
        '(FourContactRetractionElapsed + dt <= FourContactWatchTimeout)')


def members():
    return [dict(edit='add_variable', variableName=name, variableType=type, defaultValue=0,
                 isPublic=True, category='Experimental Retraction')
            for name, type in [('FourContactRetractionElapsed', 'float'), ('FourContactRetractionUpdates', 'int')]]


def leg():
    p = Plan('CheckExperimentalRetractionPose')
    function(p, 'entry', [('UpperLimit', 'float'), ('ExpectedPlaneZ', 'float')],
             [('Valid', 'bool'), ('Folded', 'bool')], public=True)
    p.node('self', 'Self')
    p.call('safe', 'IsExperimentalContactPoseSafe', LEG)
    p.wire('self.self', 'safe.self')
    p.wire('entry.then', 'safe.execute')
    p.getter('normal', 'ProbePlaneNormal')
    p.getter('impact', 'ProbeImpactPoint')
    p.breakvec('n', 'normal.ProbePlaneNormal')
    p.breakvec('q', 'impact.ProbeImpactPoint')
    stages = '+'.join(f'Stage{i}Position' for i in range(10))
    checks = ['bProbeValid', 'bProbeHit', 'bProbePlaneValid', '(abs(ExtensionAmount) <= 0.000001)',
              '(ExtensionPosition >= 0.000000)', '(ExtensionPosition <= upperLimit+0.000001)',
              '(upperLimit >= 0.050000)', '(upperLimit <= 0.950000)',
              '(ProbePlaneClearance >= -0.050000)', '(ProbePlaneClearance <= 100000.000000)',
              '(nz > 0.999990)', '(nz <= 1.000010)', '(abs(qz-expectedZ) <= 0.050000)',
              f'(abs(({stages})/10.000000-ExtensionPosition) <= 0.000001)']
    checks += [f'(Stage{i}Position >= 0.000000) && (Stage{i}Position <= 1.000000)' for i in range(10)]
    p.node('conditions', 'MathExpression', expression=' && '.join(checks))
    for a, b in [('entry.UpperLimit', 'conditions.upperLimit'), ('entry.ExpectedPlaneZ', 'conditions.expectedZ'),
                  ('n.Z', 'conditions.nz'), ('q.Z', 'conditions.qz')]:
        p.wire(a, b)
    p.call('valid', 'BooleanAND')
    p.wire('safe.Safe', 'valid.A')
    p.wire('conditions.ReturnValue', 'valid.B')
    p.wire('valid.ReturnValue', 'entry_return.Valid')
    p.node('folded', 'MathExpression', expression=' && '.join(
        ['(abs(ExtensionPosition) <= 0.000001)']+[f'(abs(Stage{i}Position) <= 0.000001)' for i in range(10)]))
    p.wire('folded.ReturnValue', 'entry_return.Folded')
    p.wire('safe.then', 'entry_return.execute')
    return p.ops


def inspect():
    p = Plan('InspectExperimentalRetractionLeg')
    function(p, 'entry', [('Component', 'ChildActorComponent'), ('UpperLimit', 'float'), ('ExpectedPlaneZ', 'float')],
             [('Valid', 'bool'), ('Folded', 'bool')])
    p.node('reject', 'FunctionResult', pinDefaults={'Valid': False, 'Folded': False})
    p.valid('valid', 'entry.Component', 'entry.then')
    p.wire('valid.Is Not Valid', 'reject.execute')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('entry.Component', 'child.self')
    p.node('cast', 'Cast', targetClass=LEG)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('valid.Is Valid', 'cast.execute')
    p.wire('cast.CastFailed', 'reject.execute')
    p.call('check', 'CheckExperimentalRetractionPose', LEG)
    p.wire('cast.AsBP Beholder Body Leg', 'check.self')
    p.wire('cast.then', 'check.execute')
    for name in ('UpperLimit', 'ExpectedPlaneZ'):
        p.wire('entry.'+name, 'check.'+name)
    p.wire('check.then', 'entry_return.execute')
    for name in ('Valid', 'Folded'):
        p.wire('check.'+name, 'entry_return.'+name)
    return p.ops


def check():
    p = Plan('CheckExperimentalRetraction')
    function(p, 'entry', outputs=[('Valid', 'bool'), ('Folded', 'bool')])
    p.node('self', 'Self')
    previous = 'entry.then'
    valid, folded = [], []
    for i in OTHER_INDICES:
        p.getter(f'leg{i}', f'Leg{i}')
        own_call(p, f'upper{i}', 'IsExperimentalLegFolded')
        p.wire(f'leg{i}.Leg{i}', f'upper{i}.Component')
        p.wire(previous, f'upper{i}.execute')
        previous = f'upper{i}.then'
        valid.append(f'upper{i}.Folded')
    p.getter('plane', 'FourContactWatchPlaneZ')
    for i in INDICES:
        p.getter(f'leg{i}', f'Leg{i}')
        p.getter(f'limit{i}', f'FourContactWatchTarget{i}')
        own_call(p, f'lower{i}', 'InspectExperimentalRetractionLeg')
        p.wire(f'leg{i}.Leg{i}', f'lower{i}.Component')
        p.wire(f'limit{i}.FourContactWatchTarget{i}', f'lower{i}.UpperLimit')
        p.wire('plane.FourContactWatchPlaneZ', f'lower{i}.ExpectedPlaneZ')
        p.wire(previous, f'lower{i}.execute')
        previous = f'lower{i}.then'
        valid.append(f'lower{i}.Valid')
        folded.append(f'lower{i}.Folded')
    for prefix, pins, name in [('valid', valid, 'Valid'), ('folded', folded, 'Folded')]:
        accumulated = pins[0]
        for i, pin in enumerate(pins[1:]):
            id = f'{prefix}{i}'
            p.call(id, 'BooleanAND')
            p.wire(accumulated, id+'.A')
            p.wire(pin, id+'.B')
            accumulated = id+'.ReturnValue'
        p.wire(accumulated, 'entry_return.'+name)
    p.wire(previous, 'entry_return.execute')
    return p.ops


def request():
    p = Plan('TryExperimentalFourRetraction')
    function(p, 'entry', outputs=[('Accepted', 'bool')], public=True)
    p.node('self', 'Self')
    p.node('reject', 'FunctionResult', pinDefaults={'Accepted': False})
    p.node('eligible', 'MathExpression', expression='((FourContactWatchState == 2) || (FourContactWatchState == 4)) && bEnableExperimentalFourContact && (FourContactWatchTimeout >= 0.100000) && (FourContactWatchTimeout <= 60.000000)')
    p.node('branch', 'Branch')
    p.wire('entry.then', 'branch.execute')
    p.wire('eligible.ReturnValue', 'branch.Condition')
    p.wire('branch.else', 'reject.execute')
    p.call('pose', 'GetTransform', '/Script/Engine.Actor')
    p.getter('saved', 'FourContactWatchPose')
    p.call('same', 'NearlyEqual_TransformTransform', defaults={'LocationTolerance': 0.001, 'RotationTolerance': 0.000001, 'Scale3DTolerance': 0.000001})
    p.wire('pose.ReturnValue', 'same.A')
    p.wire('saved.FourContactWatchPose', 'same.B')
    p.node('posebranch', 'Branch')
    p.wire('branch.then', 'posebranch.execute')
    p.wire('same.ReturnValue', 'posebranch.Condition')
    p.wire('posebranch.else', 'reject.execute')
    own_call(p, 'sample', 'UpdateBodySurfaceProbes')
    p.wire('posebranch.then', 'sample.execute')
    own_call(p, 'inspect', 'CheckExperimentalApproach')
    p.wire('sample.then', 'inspect.execute')
    p.call('ready', 'BooleanAND')
    p.wire('inspect.Valid', 'ready.A')
    p.wire('inspect.AtTarget', 'ready.B')
    p.node('readybranch', 'Branch')
    p.wire('inspect.then', 'readybranch.execute')
    p.wire('ready.ReturnValue', 'readybranch.Condition')
    p.wire('readybranch.else', 'reject.execute')
    p.call('location', 'K2_GetActorLocation', '/Script/Engine.Actor')
    p.getter('margin', 'FourContactWatchRequiredMarginCm')
    own_call(p, 'footprint', 'EvaluateExperimentalFourFootprint')
    p.wire('location.ReturnValue', 'footprint.ReferenceWorld')
    p.wire('margin.FourContactWatchRequiredMarginCm', 'footprint.MinimumMargin')
    p.wire('readybranch.then', 'footprint.execute')
    p.call('flags', 'BooleanAND')
    p.call('all', 'BooleanAND')
    for a, b in [('footprint.Valid', 'flags.A'), ('footprint.Inside', 'flags.B'),
                  ('flags.ReturnValue', 'all.A'), ('footprint.PassesMargin', 'all.B')]:
        p.wire(a, b)
    p.node('commit', 'Branch')
    p.wire('footprint.then', 'commit.execute')
    p.wire('all.ReturnValue', 'commit.Condition')
    p.wire('commit.else', 'reject.execute')
    previous = 'commit.then'
    for id, name in [('elapsed', 'FourContactRetractionElapsed'), ('count', 'FourContactRetractionUpdates'),
                     ('reason', 'FourContactWatchReason')]:
        p.setter(id, name, 0)
        p.wire(previous, id+'.execute')
        previous = id+'.then'
    for i in INDICES:
        own_call(p, f'goal{i}', 'SetBodyLegExtension', {'Index': i, 'Amount': 0})
        p.wire(previous, f'goal{i}.execute')
        previous = f'goal{i}.then'
    p.setter('state', 'FourContactWatchState', 5)
    p.wire(previous, 'state.execute')
    p.wire('state.then', 'entry_return.execute')
    p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return', pinName='Accepted', propertyValue=True))
    return p.ops


def update():
    p = Plan('UpdateExperimentalRetractionWatch')
    function(p, 'entry', [('DeltaSeconds', 'float')])
    p.node('self', 'Self')
    p.node('active', 'MathExpression', expression='FourContactWatchState == 5')
    p.node('branch', 'Branch')
    p.wire('entry.then', 'branch.execute')
    p.wire('active.ReturnValue', 'branch.Condition')
    p.getter('count', 'FourContactRetractionUpdates')
    p.call('plus', 'Add_IntInt', defaults={'B': 1})
    p.wire('count.FourContactRetractionUpdates', 'plus.A')
    p.setter('setcount', 'FourContactRetractionUpdates')
    p.wire('plus.ReturnValue', 'setcount.FourContactRetractionUpdates')
    p.wire('branch.then', 'setcount.execute')
    for id, reason in [('disabled', 1), ('badtime', 4), ('moved', 2), ('invalid', 3)]:
        own_call(p, id, 'AbortExperimentalFourContact', {'Reason': reason})
    p.getter('enabled', 'bEnableExperimentalFourContact')
    p.node('enabledbranch', 'Branch')
    p.wire('setcount.then', 'enabledbranch.execute')
    p.wire('enabled.bEnableExperimentalFourContact', 'enabledbranch.Condition')
    p.wire('enabledbranch.else', 'disabled.execute')
    p.node('time', 'MathExpression', expression=TIME)
    p.wire('entry.DeltaSeconds', 'time.dt')
    p.node('timebranch', 'Branch')
    p.wire('enabledbranch.then', 'timebranch.execute')
    p.wire('time.ReturnValue', 'timebranch.Condition')
    p.wire('timebranch.else', 'badtime.execute')
    p.node('elapsed', 'MathExpression', expression='FourContactRetractionElapsed + dt')
    p.wire('entry.DeltaSeconds', 'elapsed.dt')
    p.setter('setelapsed', 'FourContactRetractionElapsed')
    p.wire('elapsed.ReturnValue', 'setelapsed.FourContactRetractionElapsed')
    p.wire('timebranch.then', 'setelapsed.execute')
    p.call('pose', 'GetTransform', '/Script/Engine.Actor')
    p.getter('saved', 'FourContactWatchPose')
    p.call('same', 'NearlyEqual_TransformTransform', defaults={'LocationTolerance': 0.001, 'RotationTolerance': 0.000001, 'Scale3DTolerance': 0.000001})
    p.wire('pose.ReturnValue', 'same.A')
    p.wire('saved.FourContactWatchPose', 'same.B')
    p.node('posebranch', 'Branch')
    p.wire('setelapsed.then', 'posebranch.execute')
    p.wire('same.ReturnValue', 'posebranch.Condition')
    p.wire('posebranch.else', 'moved.execute')
    own_call(p, 'sample', 'UpdateBodySurfaceProbes')
    p.wire('posebranch.then', 'sample.execute')
    own_call(p, 'check', 'CheckExperimentalRetraction')
    fresh_sample_gate(p, 'check.execute')
    p.node('validbranch', 'Branch')
    p.wire('check.then', 'validbranch.execute')
    p.wire('check.Valid', 'validbranch.Condition')
    p.wire('validbranch.else', 'invalid.execute')
    p.node('foldedbranch', 'Branch')
    p.wire('validbranch.then', 'foldedbranch.execute')
    p.wire('check.Folded', 'foldedbranch.Condition')
    p.setter('done', 'FourContactWatchState', 6)
    p.wire('foldedbranch.then', 'done.execute')
    return p.ops


def dispatch(p):
    p.node('retracting', 'MathExpression', expression='FourContactWatchState == 5')
    p.node('retractiondispatch', 'Branch')
    p.wire('entry.then', 'retractiondispatch.execute')
    p.wire('retracting.ReturnValue', 'retractiondispatch.Condition')
    own_call(p, 'retractiontick', 'UpdateExperimentalRetractionWatch')
    p.wire('entry.DeltaSeconds', 'retractiontick.DeltaSeconds')
    p.wire('retractiondispatch.then', 'retractiontick.execute')
    p.wire('retractiondispatch.else', 'activebranch.execute')


def integration(ids):
    p = Plan('UpdateExperimentalContactWatch')
    dispatch(p)
    ops = []
    for source in p.ops:
        op = dict(source)
        for key in ('from', 'to'):
            value = op.get(key, '')
            alias = value[1:].split('.')[0] if value.startswith('$') else ''
            if alias in ids:
                op[key+'NodeId'] = ids[alias]
                op[key+'PinName'] = value.split('.', 1)[1]
                del op[key]
        ops.append(op)
    return ops


if __name__ == '__main__':
    plans = dict(members=members(), leg=leg(), inspect=inspect(), check=check(), request=request(), update=update())
    assert all(len(ops) <= 200 for ops in plans.values())
    print(json.dumps(plans))
