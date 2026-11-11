"""Opt-in experimental Blueprint batch request, not a support controller.

Checks all four targets before any extension call. No body movement, Tick,
physics, general swept collision or ongoing feedback is added by these plans.
Inspect first: applying an existing member again is not idempotent.
CalculateOrderedFourFootprint must be installed before the request plan.
"""
import json

from build_beholder_body_probe_graph import BODY
from build_beholder_plane_graph import Plan
from build_beholder_surface_graph import BP as LEG
from generate_beholder_telescope import COUNT, STROKE
from generate_beholder_body import OUTER_RADIUS

INDICES = (0, 2, 4, 6)
OTHER_INDICES = (1, 3, 5, 7)
# Perimeter order differs from the octant-based branch numbering.
FOOTPRINT_INDICES = (0, 2, 6, 4)


def folded():
    p = Plan('IsExperimentalLegFolded')
    p.ops.append(dict(edit='add_function', id='entry', functionName=p.graph, pure=False, isPublic=False,
                      inputs=[{'name': 'Component', 'type': 'ChildActorComponent'}],
                      outputs=[{'name': 'Folded', 'type': 'bool'}]))
    p.node('reject', 'FunctionResult', pinDefaults={'Folded': False})
    p.valid('valid', 'entry.Component', 'entry.then')
    p.wire('valid.Is Not Valid', 'reject.execute')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('entry.Component', 'child.self')
    p.node('cast', 'Cast', targetClass=LEG)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('valid.Is Valid', 'cast.execute')
    p.wire('cast.CastFailed', 'reject.execute')
    for id, name in [('auto', 'bAutoDemo'), ('current', 'ExtensionPosition'), ('goal', 'ExtensionAmount')]:
        p.node(id, 'VariableGet', memberName=name, memberClass=LEG)
        p.wire('cast.AsBP Beholder Body Leg', id+'.self')
    p.node('autobranch', 'Branch')
    p.wire('auto.bAutoDemo', 'autobranch.Condition')
    p.wire('cast.then', 'autobranch.execute')
    p.wire('autobranch.then', 'reject.execute')
    p.wire('autobranch.else', 'entry_return.execute')
    p.node('condition', 'MathExpression', expression='(abs(current) <= 0.000001) && (abs(goal) <= 0.000001)')
    p.wire('current.ExtensionPosition', 'condition.current')
    p.wire('goal.ExtensionAmount', 'condition.goal')
    p.wire('condition.ReturnValue', 'entry_return.Folded')
    return p.ops


def prepare():
    p = Plan('PrepareExperimentalContactLeg')
    p.ops.append(dict(edit='add_function', id='entry', functionName=p.graph, pure=False, isPublic=False,
                      inputs=[{'name': 'Component', 'type': 'ChildActorComponent'}],
                      outputs=[{'name': 'Ready', 'type': 'bool'}, {'name': 'Target', 'type': 'float'},
                               {'name': 'Point', 'type': 'Vector'}]))
    p.node('reject', 'FunctionResult', pinDefaults={'Ready': False, 'Target': 0, 'Point': '0,0,0'})
    p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return', pinName='Ready', propertyValue=True))
    p.valid('componentvalid', 'entry.Component', 'entry.then')
    p.wire('componentvalid.Is Not Valid', 'reject.execute')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('entry.Component', 'child.self')
    p.node('cast', 'Cast', targetClass=LEG)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('componentvalid.Is Valid', 'cast.execute')
    p.wire('cast.CastFailed', 'reject.execute')

    def field(id, name):
        p.node(id, 'VariableGet', memberName=name, memberClass=LEG)
        p.wire('cast.AsBP Beholder Body Leg', id+'.self')

    field('auto', 'bAutoDemo')
    p.node('autobranch', 'Branch')
    p.wire('auto.bAutoDemo', 'autobranch.Condition')
    p.wire('cast.then', 'autobranch.execute')
    p.wire('autobranch.then', 'reject.execute')
    field('valid', 'bStraightPlanValid')
    field('reachable', 'bStraightPlaneReachable')
    p.call('planflags', 'BooleanAND')
    p.wire('valid.bStraightPlanValid', 'planflags.A')
    p.wire('reachable.bStraightPlaneReachable', 'planflags.B')
    p.node('planbranch', 'Branch')
    p.wire('planflags.ReturnValue', 'planbranch.Condition')
    p.wire('autobranch.else', 'planbranch.execute')
    p.wire('planbranch.else', 'reject.execute')
    checks = ['(abs(current) <= 0.000001)', '(abs(goal) <= 0.000001)',
              '(target >= 0.050000)', '(target <= 0.950000)', '(projected < -0.000001)',
              '(normalZ > 0.999990)', '(abs(pitch) <= 0.000001)', '(abs(yaw) <= 0.000001)',
              '(abs(livePitch) <= 0.000001)', '(abs(liveYaw) <= 0.000001)',
              '(abs(opening) <= 0.000001)']
    scalars = [('current', 'ExtensionPosition'), ('goal', 'ExtensionAmount'), ('target', 'StraightTargetExtension'),
               ('projected', 'StraightProjectedStroke'), ('pitch', 'BendPitchDegrees'), ('yaw', 'BendYawDegrees'),
               ('livePitch', 'LiveBendPitchDegrees'), ('liveYaw', 'LiveBendYawDegrees'),
               ('opening', 'SocketRequestedOpening')]
    for i in range(3):
        scalars.append((f'claw{i}', f'SocketRequestedClaw{i}'))
        checks += [f'(claw{i} >= -1.000000)', f'(claw{i} <= 0.000000)']
    for i in range(1, COUNT):
        for axis in ('Pitch', 'Yaw'):
            pin = f'j{i}{axis.lower()}'
            scalars.append((pin, f'Joint{i}{axis}Request'))
            checks.append(f'(abs({pin}) <= 0.000001)')
    p.node('conditions', 'MathExpression', expression=' && '.join(checks))
    for pin, name in scalars:
        field(pin, name)
        p.wire(pin+'.'+name, 'conditions.'+pin)
    field('normal', 'ProbePlaneNormal')
    p.breakvec('n', 'normal.ProbePlaneNormal')
    p.wire('n.Z', 'conditions.normalZ')
    p.node('posebranch', 'Branch')
    p.wire('conditions.ReturnValue', 'posebranch.Condition')
    p.wire('planbranch.then', 'posebranch.execute')
    p.wire('posebranch.else', 'reject.execute')
    p.call('forward', 'GetActorForwardVector', '/Script/Engine.Actor')
    p.wire('cast.AsBP Beholder Body Leg', 'forward.self')
    p.breakvec('f', 'forward.ReturnValue')
    p.call('scale', 'GetActorScale3D', '/Script/Engine.Actor')
    p.wire('cast.AsBP Beholder Body Leg', 'scale.self')
    p.breakvec('s', 'scale.ReturnValue')
    field('support', 'ProbePlanePoint')
    p.breakvec('q', 'support.ProbePlanePoint')
    p.node('predicted', 'MathExpression', expression=f'VECT(qx + fx*{float(COUNT*STROKE):.6f}*worldScale*amount, qy + fy*{float(COUNT*STROKE):.6f}*worldScale*amount, qz + fz*{float(COUNT*STROKE):.6f}*worldScale*amount)')
    for prefix in 'qf':
        for axis in 'XYZ':
            p.wire(prefix+'.'+axis, 'predicted.'+prefix+axis.lower())
    p.wire('s.X', 'predicted.worldScale')
    p.wire('target.StraightTargetExtension', 'predicted.amount')
    p.breakvec('point', 'predicted.ReturnValue')
    for id, delta in [('start', '+ 2.000000'), ('end', '- 2.000000')]:
        p.node(id, 'MathExpression', expression=f'VECT(px, py, pz {delta})')
        for axis in 'XYZ':
            p.wire('point.'+axis, id+'.p'+axis.lower())
    field('ignore', 'ProbeIgnoreActors')
    p.call('trace', 'LineTraceSingle', '/Script/Engine.KismetSystemLibrary',
           {'TraceChannel': 'TraceTypeQuery1', 'bTraceComplex': True, 'DrawDebugType': 'None', 'bIgnoreSelf': True})
    for a, b in [('start.ReturnValue', 'trace.Start'), ('end.ReturnValue', 'trace.End'),
                  ('ignore.ProbeIgnoreActors', 'trace.ActorsToIgnore'), ('posebranch.then', 'trace.execute')]:
        p.wire(a, b)
    p.node('hitbranch', 'Branch')
    p.wire('trace.ReturnValue', 'hitbranch.Condition')
    p.wire('trace.then', 'hitbranch.execute')
    p.wire('hitbranch.else', 'reject.execute')
    p.call('hit', 'BreakHitResult', '/Script/Engine.GameplayStatics')
    p.wire('trace.OutHit', 'hit.Hit')
    p.node('overlap', 'Branch')
    p.wire('hit.bInitialOverlap', 'overlap.Condition')
    p.wire('hitbranch.then', 'overlap.execute')
    p.wire('overlap.then', 'reject.execute')
    p.breakvec('h', 'hit.ImpactPoint')
    p.breakvec('hn', 'hit.ImpactNormal')
    p.node('onface', 'MathExpression', expression='(abs(hx-px) <= 0.050000) && (abs(hy-py) <= 0.050000) && (abs(hz-pz) <= 0.050000) && (nz > 0.999990)')
    for prefix, source in [('h', 'h'), ('p', 'point')]:
        for axis in 'XYZ':
            p.wire(source+'.'+axis, 'onface.'+prefix+axis.lower())
    p.wire('hn.Z', 'onface.nz')
    p.node('facebranch', 'Branch')
    p.wire('onface.ReturnValue', 'facebranch.Condition')
    p.wire('overlap.else', 'facebranch.execute')
    p.wire('facebranch.else', 'reject.execute')
    p.wire('facebranch.then', 'entry_return.execute')
    p.wire('target.StraightTargetExtension', 'entry_return.Target')
    p.wire('predicted.ReturnValue', 'entry_return.Point')
    assert len(p.ops) <= 200, len(p.ops)
    return p.ops


def request():
    p = Plan('TryExperimentalFourContact')
    for name, type, value in [('bEnableExperimentalFourContact', 'bool', False),
                              ('FourContactCompletionMinimumMarginCm', 'float', 1.0),
                              ('bLastFourContactRequestAccepted', 'bool', False)]+[(f'LastFourContactTarget{i}', 'float', 0) for i in INDICES]:
        p.ops.append(dict(edit='add_variable', variableName=name, variableType=type, defaultValue=value,
                          isPublic=True, category='Experimental Four Contact'))
    p.ops.append(dict(edit='add_function', id='entry', functionName=p.graph, pure=False, isPublic=True))
    p.node('self', 'Self')
    p.setter('reset', 'bLastFourContactRequestAccepted', False)
    p.wire('entry.then', 'reset.execute')
    previous = 'reset.then'
    for i in INDICES:
        p.setter(f'reset{i}', f'LastFourContactTarget{i}', 0)
        p.wire(previous, f'reset{i}.execute')
        previous = f'reset{i}.then'
    p.getter('enabled', 'bEnableExperimentalFourContact')
    p.node('enabledbranch', 'Branch')
    p.wire('enabled.bEnableExperimentalFourContact', 'enabledbranch.Condition')
    p.wire(previous, 'enabledbranch.execute')
    p.call('update', 'UpdateBodySurfaceProbes', BODY)
    p.wire('self.self', 'update.self')
    p.wire('enabledbranch.then', 'update.execute')
    previous = 'update.then'
    for i in OTHER_INDICES:
        p.getter(f'leg{i}', f'Leg{i}')
        p.call(f'folded{i}', 'IsExperimentalLegFolded', BODY)
        p.wire('self.self', f'folded{i}.self')
        p.wire(f'leg{i}.Leg{i}', f'folded{i}.Component')
        p.wire(previous, f'folded{i}.execute')
        previous = f'folded{i}.then'
    for i in INDICES:
        p.getter(f'leg{i}', f'Leg{i}')
        p.call(f'prepare{i}', 'PrepareExperimentalContactLeg', BODY)
        p.wire('self.self', f'prepare{i}.self')
        p.wire(f'leg{i}.Leg{i}', f'prepare{i}.Component')
        p.wire(previous, f'prepare{i}.execute')
        previous = f'prepare{i}.then'
        p.breakvec(f'p{i}', f'prepare{i}.Point')
    for id in ('flags1', 'flags2', 'flags3', 'allready'):
        p.call(id, 'BooleanAND')
    for a, b in [('prepare0.Ready', 'flags1.A'), ('prepare2.Ready', 'flags1.B'),
                  ('prepare4.Ready', 'flags2.A'), ('prepare6.Ready', 'flags2.B'),
                  ('flags1.ReturnValue', 'flags3.A'), ('flags2.ReturnValue', 'flags3.B')]:
        p.wire(a, b)
    p.call('up', 'GetActorUpVector', '/Script/Engine.Actor')
    p.call('scale', 'GetActorScale3D', '/Script/Engine.Actor')
    p.call('location', 'K2_GetActorLocation', '/Script/Engine.Actor')
    p.breakvec('u', 'up.ReturnValue')
    p.breakvec('s', 'scale.ReturnValue')
    p.breakvec('b', 'location.ReturnValue')
    p.node('bodyok', 'MathExpression', expression=f'(upZ > 0.999990) && (sx > 0.000001) && (sx <= 10000.000000) && (abs(sx-sy) <= 0.000001) && (abs(sx-sz) <= 0.000001) && (abs(z0-z2) <= 0.050000) && (abs(z0-z4) <= 0.050000) && (abs(z0-z6) <= 0.050000) && (bodyZ - max(max(z0,z2),max(z4,z6)) > {float(OUTER_RADIUS):.6f}*sx + 1.000000) && (FourContactCompletionMinimumMarginCm >= 0.000000) && (FourContactCompletionMinimumMarginCm <= 1000000.000000)')
    p.wire('u.Z', 'bodyok.upZ')
    p.wire('b.Z', 'bodyok.bodyZ')
    for axis in 'XYZ':
        p.wire('s.'+axis, 'bodyok.s'+axis.lower())
    for i in INDICES:
        p.wire(f'p{i}.Z', f'bodyok.z{i}')
    for id in ('upper1', 'upper2', 'upper3', 'groups'):
        p.call(id, 'BooleanAND')
    for a, b in [('folded1.Folded', 'upper1.A'), ('folded3.Folded', 'upper1.B'),
                  ('folded5.Folded', 'upper2.A'), ('folded7.Folded', 'upper2.B'),
                  ('upper1.ReturnValue', 'upper3.A'), ('upper2.ReturnValue', 'upper3.B'),
                  ('flags3.ReturnValue', 'groups.A'), ('upper3.ReturnValue', 'groups.B'),
                  ('groups.ReturnValue', 'allready.A')]:
        p.wire(a, b)
    p.wire('bodyok.ReturnValue', 'allready.B')
    p.node('commitgate', 'Branch')
    p.wire('allready.ReturnValue', 'commitgate.Condition')
    p.wire(previous, 'commitgate.execute')
    prediction_gate(p)
    previous = 'predictedgate.then'
    for i in INDICES:
        p.setter(f'cache{i}', f'LastFourContactTarget{i}')
        p.wire(f'prepare{i}.Target', f'cache{i}.LastFourContactTarget{i}')
        p.wire(previous, f'cache{i}.execute')
        previous = f'cache{i}.then'
    for i in INDICES:
        p.call(f'command{i}', 'SetBodyLegExtension', BODY, {'Index': i})
        p.wire('self.self', f'command{i}.self')
        p.wire(f'prepare{i}.Target', f'command{i}.Amount')
        p.wire(previous, f'command{i}.execute')
        previous = f'command{i}.then'
    p.setter('accepted', 'bLastFourContactRequestAccepted', True)
    p.wire(previous, 'accepted.execute')
    assert len(p.ops) <= 200, len(p.ops)
    return p.ops


def prediction_gate(p):
    """No goals until the four traced predicted points pass the XY gate."""
    p.getter('predictionmargin', 'FourContactCompletionMinimumMarginCm')
    p.call('predictedfootprint', 'CalculateOrderedFourFootprint', BODY)
    p.wire('self.self', 'predictedfootprint.self')
    for rank, i in enumerate(FOOTPRINT_INDICES):
        p.wire(f'prepare{i}.Point', f'predictedfootprint.Point{rank}')
    p.wire('location.ReturnValue', 'predictedfootprint.ReferenceWorld')
    p.wire('predictionmargin.FourContactCompletionMinimumMarginCm', 'predictedfootprint.MinimumMargin')
    p.wire('commitgate.then', 'predictedfootprint.execute')
    p.call('predictedflags', 'BooleanAND')
    p.call('predictedready', 'BooleanAND')
    for a, b in [('predictedfootprint.Valid', 'predictedflags.A'), ('predictedfootprint.Inside', 'predictedflags.B'),
                  ('predictedflags.ReturnValue', 'predictedready.A'), ('predictedfootprint.PassesMargin', 'predictedready.B')]:
        p.wire(a, b)
    p.node('predictedgate', 'Branch')
    p.wire('predictedfootprint.then', 'predictedgate.execute')
    p.wire('predictedready.ReturnValue', 'predictedgate.Condition')


def prediction_upgrade(ids):
    """One-time delta; inspect the existing request and resolve its node IDs."""
    p = Plan('TryExperimentalFourContact')
    prediction_gate(p)
    p.wire('predictedgate.then', 'cache0.execute')
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
    print(json.dumps({'folded': folded(), 'prepare': prepare(), 'request': request()}))
