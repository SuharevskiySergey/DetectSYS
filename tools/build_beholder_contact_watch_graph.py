"""Opt-in approach watchdog plans. No force support or terrain sweep.

States: 0 idle/released, 1 approaching, 2 reached (terminal by default),
3 aborted, 4 explicitly enabled geometric contact monitoring,
5 controlled retraction, 6 retracted/terminal.
Reasons: 1 disabled, 2 body moved, 3 leg/surface, 4 time/input, 5 cancel,
6 footprint rejected. Monitoring never supplies physical support.
Inspect before applying: creation plans are not idempotent.
"""
import json

from build_beholder_body_probe_graph import BODY
from build_beholder_contact_request_graph import INDICES, OTHER_INDICES
from build_beholder_plane_graph import Plan
from build_beholder_surface_graph import BP as LEG, HEAD
from generate_beholder_telescope import COUNT

ACTIVE_EXPRESSION = '(FourContactWatchState == 1) || (FourContactWatchState == 4)'
ABORT_EXPRESSION = '(FourContactWatchState == 1) || (FourContactWatchState == 2) || (FourContactWatchState == 4) || (FourContactWatchState == 5)'
TIME_EXPRESSION = ('(dt >= 0.000000) && (dt <= 10.000000) '
                   '&& (FourContactWatchElapsed >= 0.000000) && (FourContactWatchElapsed <= 60.000000) '
                   '&& ((FourContactWatchState == 4) || ((FourContactWatchTimeout >= 0.100000) '
                   '&& (FourContactWatchTimeout <= 60.000000) '
                   '&& (FourContactWatchElapsed + dt <= FourContactWatchTimeout)))')


def function(p, id, inputs=(), outputs=(), public=False):
    p.ops.append(dict(edit='add_function', id=id, functionName=p.graph, pure=False, isPublic=public,
                      inputs=[dict(name=n, type=t) for n, t in inputs],
                      outputs=[dict(name=n, type=t) for n, t in outputs]))


def own_call(p, id, name, defaults=None):
    p.call(id, name, BODY, defaults)
    p.wire('self.self', id+'.self')


def pose():
    p = Plan('IsExperimentalContactPoseSafe')
    function(p, 'entry', outputs=[('Safe', 'bool')], public=True)
    p.node('reject', 'FunctionResult', pinDefaults={'Safe': False})
    p.getter('hm', 'HeadModule')
    p.valid('valid', 'hm.HeadModule', 'entry.then')
    p.wire('valid.Is Not Valid', 'reject.execute')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('hm.HeadModule', 'child.self')
    p.node('cast', 'Cast', targetClass=HEAD)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('valid.Is Valid', 'cast.execute')
    p.wire('cast.CastFailed', 'reject.execute')
    p.wire('cast.then', 'entry_return.execute')
    checks = ['(bAutoDemo == false)', '(abs(SocketRequestedOpening) <= 0.000001)']
    for n in ('BendPitchDegrees', 'BendYawDegrees', 'LiveBendPitchDegrees', 'LiveBendYawDegrees'):
        checks.append(f'(abs({n}) <= 0.000001)')
    for i in range(3):
        checks += [f'(SocketRequestedClaw{i} >= -1.000000)', f'(SocketRequestedClaw{i} <= 0.000000)',
                   f'(abs(c{i}) <= 0.000001)']
    for i in range(1, COUNT):
        for suffix in ('Magnitude', 'PitchRequest', 'YawRequest'):
            checks.append(f'(abs(Joint{i}{suffix}) <= 0.000001)')
    p.node('conditions', 'MathExpression', expression=' && '.join(checks))
    for i in range(3):
        p.node(f'c{i}', 'VariableGet', memberName=f'Claw{i}Position', memberClass=HEAD)
        p.wire('cast.AsBP Lapa 5 Head', f'c{i}.self')
        p.wire(f'c{i}.Claw{i}Position', f'conditions.c{i}')
    p.wire('conditions.ReturnValue', 'entry_return.Safe')
    return p.ops


def inspect_leg():
    p = Plan('InspectExperimentalContactLeg')
    function(p, 'entry', [('Component', 'ChildActorComponent'), ('Target', 'float'), ('PlaneZ', 'float')],
             [('Valid', 'bool'), ('AtTarget', 'bool')])
    p.node('reject', 'FunctionResult', pinDefaults={'Valid': False, 'AtTarget': False})
    p.valid('componentvalid', 'entry.Component', 'entry.then')
    p.wire('componentvalid.Is Not Valid', 'reject.execute')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('entry.Component', 'child.self')
    p.node('cast', 'Cast', targetClass=LEG)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('componentvalid.Is Valid', 'cast.execute')
    p.wire('cast.CastFailed', 'reject.execute')
    p.call('safe', 'IsExperimentalContactPoseSafe', LEG)
    p.wire('cast.AsBP Beholder Body Leg', 'safe.self')
    p.wire('cast.then', 'safe.execute')
    fields = [('valid', 'bProbeValid'), ('hit', 'bProbeHit'), ('planevalid', 'bProbePlaneValid'),
              ('current', 'ExtensionPosition'), ('goal', 'ExtensionAmount'),
              ('clearance', 'ProbePlaneClearance'), ('impact', 'ProbeImpactPoint'), ('normal', 'ProbePlaneNormal')]
    for id, name in fields:
        p.node(id, 'VariableGet', memberName=name, memberClass=LEG)
        p.wire('cast.AsBP Beholder Body Leg', id+'.self')
    for id in ('and1', 'and2', 'and3'):
        p.call(id, 'BooleanAND')
    for a, b in [('valid.bProbeValid', 'and1.A'), ('hit.bProbeHit', 'and1.B'),
                  ('planevalid.bProbePlaneValid', 'and2.A'), ('safe.Safe', 'and2.B'),
                  ('and1.ReturnValue', 'and3.A'), ('and2.ReturnValue', 'and3.B')]:
        p.wire(a, b)
    p.node('flagsbranch', 'Branch')
    p.wire('safe.then', 'flagsbranch.execute')
    p.wire('and3.ReturnValue', 'flagsbranch.Condition')
    p.wire('flagsbranch.else', 'reject.execute')
    p.breakvec('p', 'impact.ProbeImpactPoint')
    p.breakvec('n', 'normal.ProbePlaneNormal')
    p.node('conditions', 'MathExpression', expression='(abs(goal-target) <= 0.000001) && (current >= 0.000000) && (current <= target + 0.000001) && (target >= 0.050000) && (target <= 0.950000) && (clearance >= -0.050000) && (clearance <= 100000.000000) && (nz > 0.999990) && (abs(pz-planeZ) <= 0.050000)')
    for a, b in [('entry.Target', 'conditions.target'), ('entry.PlaneZ', 'conditions.planeZ'),
                  ('current.ExtensionPosition', 'conditions.current'), ('goal.ExtensionAmount', 'conditions.goal'),
                  ('clearance.ProbePlaneClearance', 'conditions.clearance'), ('p.Z', 'conditions.pz'), ('n.Z', 'conditions.nz')]:
        p.wire(a, b)
    p.node('branch', 'Branch')
    p.wire('flagsbranch.then', 'branch.execute')
    p.wire('conditions.ReturnValue', 'branch.Condition')
    p.wire('branch.else', 'reject.execute')
    p.wire('branch.then', 'entry_return.execute')
    p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return', pinName='Valid', propertyValue=True))
    p.node('complete', 'MathExpression', expression='(abs(current-target) <= 0.000001) && (abs(clearance) <= 0.050000)')
    p.wire('current.ExtensionPosition', 'complete.current')
    p.wire('entry.Target', 'complete.target')
    p.wire('clearance.ProbePlaneClearance', 'complete.clearance')
    p.wire('complete.ReturnValue', 'entry_return.AtTarget')
    return p.ops


def check_all():
    p = Plan('CheckExperimentalApproach')
    function(p, 'entry', outputs=[('Valid', 'bool'), ('AtTarget', 'bool')])
    p.node('self', 'Self')
    previous = 'entry.then'
    valid_pins, complete_pins = [], []
    for i in OTHER_INDICES:
        p.getter(f'leg{i}', f'Leg{i}')
        own_call(p, f'upper{i}', 'IsExperimentalLegFolded')
        p.wire(f'leg{i}.Leg{i}', f'upper{i}.Component')
        p.wire(previous, f'upper{i}.execute')
        previous = f'upper{i}.then'
        valid_pins.append(f'upper{i}.Folded')
    p.getter('plane', 'FourContactWatchPlaneZ')
    for i in INDICES:
        p.getter(f'leg{i}', f'Leg{i}')
        p.getter(f'target{i}', f'FourContactWatchTarget{i}')
        own_call(p, f'lower{i}', 'InspectExperimentalContactLeg')
        p.wire(f'leg{i}.Leg{i}', f'lower{i}.Component')
        p.wire(f'target{i}.FourContactWatchTarget{i}', f'lower{i}.Target')
        p.wire('plane.FourContactWatchPlaneZ', f'lower{i}.PlaneZ')
        p.wire(previous, f'lower{i}.execute')
        previous = f'lower{i}.then'
        valid_pins.append(f'lower{i}.Valid')
        complete_pins.append(f'lower{i}.AtTarget')
    for prefix, pins, output in [('valid', valid_pins, 'Valid'), ('done', complete_pins, 'AtTarget')]:
        accumulated = pins[0]
        for i, pin in enumerate(pins[1:]):
            id = f'{prefix}{i}'
            p.call(id, 'BooleanAND')
            p.wire(accumulated, id+'.A')
            p.wire(pin, id+'.B')
            accumulated = id+'.ReturnValue'
        p.wire(accumulated, 'entry_return.'+output)
    p.wire(previous, 'entry_return.execute')
    return p.ops


def hold_leg():
    p = Plan('HoldExperimentalContactLeg')
    function(p, 'entry', [('Component', 'ChildActorComponent'), ('Index', 'int')])
    p.node('self', 'Self')
    p.valid('valid', 'entry.Component', 'entry.then')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('entry.Component', 'child.self')
    p.node('cast', 'Cast', targetClass=LEG)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('valid.Is Valid', 'cast.execute')
    p.node('amount', 'VariableGet', memberName='ExtensionPosition', memberClass=LEG)
    p.wire('cast.AsBP Beholder Body Leg', 'amount.self')
    p.node('range', 'MathExpression', expression='(amount >= 0.000000) && (amount <= 1.000000)')
    p.wire('amount.ExtensionPosition', 'range.amount')
    p.node('branch', 'Branch')
    p.wire('range.ReturnValue', 'branch.Condition')
    p.wire('cast.then', 'branch.execute')
    own_call(p, 'hold', 'SetBodyLegExtension')
    p.wire('entry.Index', 'hold.Index')
    p.wire('amount.ExtensionPosition', 'hold.Amount')
    p.wire('branch.then', 'hold.execute')
    return p.ops


def abort():
    p = Plan('AbortExperimentalFourContact')
    function(p, 'entry', [('Reason', 'int')])
    p.node('self', 'Self')
    p.node('active', 'MathExpression', expression=ABORT_EXPRESSION)
    p.node('branch', 'Branch')
    p.wire('active.ReturnValue', 'branch.Condition')
    p.wire('entry.then', 'branch.execute')
    p.setter('state', 'FourContactWatchState', 3)
    p.wire('branch.then', 'state.execute')
    p.setter('reason', 'FourContactWatchReason')
    p.wire('entry.Reason', 'reason.FourContactWatchReason')
    p.wire('state.then', 'reason.execute')
    previous = 'reason.then'
    for i in INDICES:
        p.getter(f'leg{i}', f'Leg{i}')
        own_call(p, f'hold{i}', 'HoldExperimentalContactLeg', {'Index': i})
        p.wire(f'leg{i}.Leg{i}', f'hold{i}.Component')
        p.wire(previous, f'hold{i}.execute')
        previous = f'hold{i}.then'
    return p.ops


def start():
    p = Plan('StartExperimentalContactWatch')
    fields = [('FourContactWatchState', 'int', 0, True), ('FourContactWatchReason', 'int', 0, True),
              ('FourContactWatchElapsed', 'float', 0, True), ('FourContactWatchUpdates', 'int', 0, True),
              ('FourContactWatchTimeout', 'float', 10, True), ('FourContactWatchPose', 'Transform', None, False),
              ('FourContactWatchPlaneZ', 'float', 0, False),
              ('FourContactWatchRequiredMarginCm', 'float', 1, False)]
    fields += [(f'FourContactWatchTarget{i}', 'float', 0, False) for i in INDICES]
    for name, type, value, public in fields:
        p.ops.append(dict(edit='add_variable', variableName=name, variableType=type, isPublic=public,
                          category='Experimental Contact Watch', **({'defaultValue': value} if value is not None else {})))
    function(p, 'entry')
    p.node('self', 'Self')
    previous = 'entry.then'
    for id, name, value in [('elapsed', 'FourContactWatchElapsed', 0), ('updates', 'FourContactWatchUpdates', 0),
                            ('reason', 'FourContactWatchReason', 0)]:
        p.setter(id, name, value)
        p.wire(previous, id+'.execute')
        previous = id+'.then'
    for i in INDICES:
        p.getter(f'target{i}', f'LastFourContactTarget{i}')
        p.setter(f'cache{i}', f'FourContactWatchTarget{i}')
        p.wire(f'target{i}.LastFourContactTarget{i}', f'cache{i}.FourContactWatchTarget{i}')
        p.wire(previous, f'cache{i}.execute')
        previous = f'cache{i}.then'
    p.getter('requiredmargin', 'FourContactCompletionMinimumMarginCm')
    p.setter('cachemargin', 'FourContactWatchRequiredMarginCm')
    p.wire('requiredmargin.FourContactCompletionMinimumMarginCm', 'cachemargin.FourContactWatchRequiredMarginCm')
    p.wire(previous, 'cachemargin.execute')
    previous = 'cachemargin.then'
    p.call('pose', 'GetTransform', '/Script/Engine.Actor')
    p.setter('cachepose', 'FourContactWatchPose')
    p.wire('pose.ReturnValue', 'cachepose.FourContactWatchPose')
    p.wire(previous, 'cachepose.execute')
    p.setter('state', 'FourContactWatchState', 1)
    p.wire('cachepose.then', 'state.execute')
    p.getter('leg', 'Leg0')
    p.valid('legvalid', 'leg.Leg0', 'state.then')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('leg.Leg0', 'child.self')
    p.node('cast', 'Cast', targetClass=LEG)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('legvalid.Is Valid', 'cast.execute')
    own_call(p, 'abort', 'AbortExperimentalFourContact', {'Reason': 3})
    p.wire('cast.CastFailed', 'abort.execute')
    p.wire('legvalid.Is Not Valid', 'abort.execute')
    p.node('point', 'VariableGet', memberName='ProbeImpactPoint', memberClass=LEG)
    p.wire('cast.AsBP Beholder Body Leg', 'point.self')
    p.breakvec('p', 'point.ProbeImpactPoint')
    p.setter('plane', 'FourContactWatchPlaneZ')
    p.wire('p.Z', 'plane.FourContactWatchPlaneZ')
    p.wire('cast.then', 'plane.execute')
    return p.ops


def controls():
    p = Plan('ReleaseExperimentalFourContact')
    function(p, 'entry', public=True)
    previous = 'entry.then'
    for id, name in [('state', 'FourContactWatchState'), ('reason', 'FourContactWatchReason'), ('elapsed', 'FourContactWatchElapsed')]:
        p.setter(id, name, 0)
        p.wire(previous, id+'.execute')
        previous = id+'.then'
    ops = p.ops
    p = Plan('CancelExperimentalFourContact')
    function(p, 'cancelentry', public=True)
    p.node('cancelself', 'Self')
    p.call('cancel', 'AbortExperimentalFourContact', BODY, {'Reason': 5})
    p.wire('cancelself.self', 'cancel.self')
    p.wire('cancelentry.then', 'cancel.execute')
    return ops+p.ops


def update():
    p = Plan('UpdateExperimentalContactWatch')
    function(p, 'entry', [('DeltaSeconds', 'float')], public=True)
    p.node('self', 'Self')
    p.node('active', 'MathExpression', expression=ACTIVE_EXPRESSION)
    p.node('activebranch', 'Branch')
    p.wire('active.ReturnValue', 'activebranch.Condition')
    p.wire('entry.then', 'activebranch.execute')
    p.getter('count', 'FourContactWatchUpdates')
    p.call('increment', 'Add_IntInt', defaults={'B': 1})
    p.wire('count.FourContactWatchUpdates', 'increment.A')
    p.setter('setcount', 'FourContactWatchUpdates')
    p.wire('increment.ReturnValue', 'setcount.FourContactWatchUpdates')
    p.wire('activebranch.then', 'setcount.execute')
    p.getter('enabled', 'bEnableExperimentalFourContact')
    p.node('enabledbranch', 'Branch')
    p.wire('enabled.bEnableExperimentalFourContact', 'enabledbranch.Condition')
    p.wire('setcount.then', 'enabledbranch.execute')
    for id, reason in [('disabled', 1), ('badtime', 4), ('moved', 2), ('invalid', 3)]:
        own_call(p, id, 'AbortExperimentalFourContact', {'Reason': reason})
    p.wire('enabledbranch.else', 'disabled.execute')
    p.node('timeok', 'MathExpression', expression=TIME_EXPRESSION)
    p.wire('entry.DeltaSeconds', 'timeok.dt')
    p.node('timebranch', 'Branch')
    p.wire('timeok.ReturnValue', 'timebranch.Condition')
    p.wire('enabledbranch.then', 'timebranch.execute')
    p.wire('timebranch.else', 'badtime.execute')
    p.node('elapsed', 'MathExpression', expression='FourContactWatchElapsed + dt')
    p.wire('entry.DeltaSeconds', 'elapsed.dt')
    p.setter('setelapsed', 'FourContactWatchElapsed')
    p.wire('elapsed.ReturnValue', 'setelapsed.FourContactWatchElapsed')
    p.wire('timebranch.then', 'setelapsed.execute')
    p.call('pose', 'GetTransform', '/Script/Engine.Actor')
    p.getter('savedpose', 'FourContactWatchPose')
    p.call('samepose', 'NearlyEqual_TransformTransform', defaults={'LocationTolerance': 0.001, 'RotationTolerance': 0.000001, 'Scale3DTolerance': 0.000001})
    p.wire('pose.ReturnValue', 'samepose.A')
    p.wire('savedpose.FourContactWatchPose', 'samepose.B')
    p.node('posebranch', 'Branch')
    p.wire('samepose.ReturnValue', 'posebranch.Condition')
    p.wire('setelapsed.then', 'posebranch.execute')
    p.wire('posebranch.else', 'moved.execute')
    own_call(p, 'sample', 'UpdateBodySurfaceProbes')
    p.wire('posebranch.then', 'sample.execute')
    own_call(p, 'inspect', 'CheckExperimentalApproach')
    fresh_sample_gate(p, 'inspect.execute')
    p.node('validbranch', 'Branch')
    p.wire('inspect.Valid', 'validbranch.Condition')
    p.wire('inspect.then', 'validbranch.execute')
    p.wire('validbranch.else', 'invalid.execute')
    p.node('donebranch', 'Branch')
    p.wire('inspect.AtTarget', 'donebranch.Condition')
    p.wire('validbranch.then', 'donebranch.execute')
    p.setter('done', 'FourContactWatchState', 2)
    completion_gate(p)
    monitor_update_extension(p)
    # Install the retraction helpers before rebuilding this full graph.
    from build_beholder_retraction_graph import dispatch
    dispatch(p)
    return p.ops


def fresh_sample_gate(p, next_exec):
    """Invalid body settings can skip leg sampling: never reuse old rows."""
    p.node('freshsnapshot', 'MathExpression', expression='bBodyProbeSettingsValid && (BodyProbeMeasuredCount == 8)')
    p.node('freshbranch', 'Branch')
    p.wire('sample.then', 'freshbranch.execute')
    p.wire('freshsnapshot.ReturnValue', 'freshbranch.Condition')
    p.wire('freshbranch.then', next_exec)
    p.wire('freshbranch.else', 'invalid.execute')


def freshness_upgrade(graph_name, ids, next_alias):
    p = Plan(graph_name)
    fresh_sample_gate(p, next_alias+'.execute')
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


def begin_monitor():
    p = Plan('BeginExperimentalContactMonitoring')
    function(p, 'entry', outputs=[('Started', 'bool')], public=True)
    p.node('self', 'Self')
    p.node('reject', 'FunctionResult', pinDefaults={'Started': False})
    p.node('eligible', 'MathExpression', expression='(FourContactWatchState == 2) || (FourContactWatchState == 4)')
    p.node('branch', 'Branch')
    p.wire('eligible.ReturnValue', 'branch.Condition')
    p.wire('entry.then', 'branch.execute')
    p.wire('branch.else', 'reject.execute')
    p.setter('monitorstate', 'FourContactWatchState', 4)
    p.wire('branch.then', 'monitorstate.execute')
    own_call(p, 'validate', 'UpdateExperimentalContactWatch', {'DeltaSeconds': 0})
    p.wire('monitorstate.then', 'validate.execute')
    p.node('started', 'MathExpression', expression='FourContactWatchState == 4')
    p.wire('validate.then', 'entry_return.execute')
    p.wire('started.ReturnValue', 'entry_return.Started')
    return p.ops


def monitor_update_extension(p):
    """Reuse the approach checks, but keep monitoring distinct from arrival."""
    p.node('monitorapproach', 'MathExpression', expression='FourContactWatchState == 1')
    p.getter('monitoroldelapsed', 'FourContactWatchElapsed')
    p.call('monitorclock', 'SelectFloat')
    p.wire('monitorapproach.ReturnValue', 'monitorclock.bPickA')
    p.wire('elapsed.ReturnValue', 'monitorclock.A')
    p.wire('monitoroldelapsed.FourContactWatchElapsed', 'monitorclock.B')
    p.wire('monitorclock.ReturnValue', 'setelapsed.FourContactWatchElapsed')
    p.node('monitorcomplete', 'Branch')
    p.wire('monitorapproach.ReturnValue', 'monitorcomplete.Condition')
    p.wire('finalbranch.then', 'monitorcomplete.execute')
    p.wire('monitorcomplete.then', 'done.execute')
    p.node('monitoractive', 'MathExpression', expression='FourContactWatchState == 4')
    p.node('monitordrift', 'Branch')
    p.wire('donebranch.else', 'monitordrift.execute')
    p.wire('monitoractive.ReturnValue', 'monitordrift.Condition')
    p.wire('monitordrift.then', 'invalid.execute')


def monitor_upgrade(ids):
    """One-time delta against the inspected completed approach watchdog."""
    ops = []
    for name, expression, graph in [('active', ACTIVE_EXPRESSION, 'UpdateExperimentalContactWatch'),
                                     ('timeok', TIME_EXPRESSION, 'UpdateExperimentalContactWatch'),
                                     ('abortactive', ABORT_EXPRESSION, 'AbortExperimentalFourContact')]:
        ops.append(dict(edit='set_node_property', graphName=graph, nodeId=ids[name],
                        propertyName='Expression', propertyValue=expression))
    p = Plan('UpdateExperimentalContactWatch')
    monitor_update_extension(p)
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


def completion_gate(p):
    """Append only this gate to an inspected existing Update graph.

    The caller resolves self, donebranch and done aliases to existing GUIDs.
    Keeping this separate avoids reapplying the whole non-idempotent plan.
    """
    p.call('finalreference', 'K2_GetActorLocation', '/Script/Engine.Actor')
    p.getter('finalrequired', 'FourContactWatchRequiredMarginCm')
    own_call(p, 'finalfootprint', 'EvaluateExperimentalFourFootprint')
    p.wire('finalreference.ReturnValue', 'finalfootprint.ReferenceWorld')
    p.wire('finalrequired.FourContactWatchRequiredMarginCm', 'finalfootprint.MinimumMargin')
    p.wire('donebranch.then', 'finalfootprint.execute')
    p.call('finalflags', 'BooleanAND')
    p.call('finalready', 'BooleanAND')
    for a, b in [('finalfootprint.Valid', 'finalflags.A'), ('finalfootprint.Inside', 'finalflags.B'),
                  ('finalflags.ReturnValue', 'finalready.A'), ('finalfootprint.PassesMargin', 'finalready.B')]:
        p.wire(a, b)
    p.node('finalbranch', 'Branch')
    p.wire('finalfootprint.then', 'finalbranch.execute')
    p.wire('finalready.ReturnValue', 'finalbranch.Condition')
    p.wire('finalbranch.then', 'done.execute')
    own_call(p, 'badfootprint', 'AbortExperimentalFourContact', {'Reason': 6})
    p.wire('finalbranch.else', 'badfootprint.execute')


def completion_upgrade(ids):
    """One-time delta for the inspected pre-footprint-gate implementation."""
    from build_beholder_contact_request_graph import request
    request_ops = request()
    ops = [next(o for o in request_ops if o.get('variableName') == 'FourContactCompletionMinimumMarginCm'),
           next(o for o in start() if o.get('variableName') == 'FourContactWatchRequiredMarginCm')]
    expression = next(o['expression'] for o in request_ops if o.get('id') == 'bodyok')
    ops.append(dict(edit='set_node_property', graphName='TryExperimentalFourContact',
                    nodeId=ids['bodyok'], propertyName='Expression', propertyValue=expression))
    p = Plan('StartExperimentalContactWatch')
    p.getter('requiredmargin', 'FourContactCompletionMinimumMarginCm')
    p.setter('cachemargin', 'FourContactWatchRequiredMarginCm')
    p.wire('requiredmargin.FourContactCompletionMinimumMarginCm', 'cachemargin.FourContactWatchRequiredMarginCm')
    p.ops += [dict(edit='connect_pins', fromNodeId=ids['cache6'], fromPinName='then', to='$cachemargin.execute'),
              dict(edit='connect_pins', **{'from': '$cachemargin.then'}, toNodeId=ids['cachepose'], toPinName='execute')]
    ops += p.ops
    p = Plan('UpdateExperimentalContactWatch')
    completion_gate(p)
    for source in p.ops:
        op = dict(source)
        for key in ('from', 'to'):
            value = op.get(key, '')
            alias = value[1:].split('.')[0] if value.startswith('$') else ''
            if alias in ('self', 'donebranch', 'done'):
                op[key+'NodeId'] = ids[alias]
                op[key+'PinName'] = value.split('.', 1)[1]
                del op[key]
        ops.append(op)
    return ops


def integration(accepted_tail, tick_node):
    return [
        dict(edit='create_node', graphName='TryExperimentalFourContact', id='startself', nodeType='Self'),
        dict(edit='create_node', graphName='TryExperimentalFourContact', id='startwatch', nodeType='CallFunction',
             memberName='StartExperimentalContactWatch', memberClass=BODY),
        dict(edit='connect_pins', **{'from': '$startself.self', 'to': '$startwatch.self'}),
        dict(edit='connect_pins', fromNodeId=accepted_tail, fromPinName='then', **{'to': '$startwatch.execute'}),
        dict(edit='create_node', graphName='EventGraph', id='tickself', nodeType='Self'),
        dict(edit='create_node', graphName='EventGraph', id='watchtick', nodeType='CallFunction',
             memberName='UpdateExperimentalContactWatch', memberClass=BODY),
        dict(edit='connect_pins', **{'from': '$tickself.self', 'to': '$watchtick.self'}),
        dict(edit='connect_pins', fromNodeId=tick_node, fromPinName='then', **{'to': '$watchtick.execute'}),
        dict(edit='connect_pins', fromNodeId=tick_node, fromPinName='DeltaSeconds', **{'to': '$watchtick.DeltaSeconds'}),
    ]


if __name__ == '__main__':
    start_ops = start()
    plans = dict(members=[o for o in start_ops if o['edit'] == 'add_variable'], pose=pose(),
                 inspect=inspect_leg(), check=check_all(), hold=hold_leg(), abort=abort(),
                 start=[o for o in start_ops if o['edit'] != 'add_variable'],
                  controls=controls(), update=update(), begin_monitor=begin_monitor())
    assert all(len(ops) <= 200 for ops in plans.values())
    print(json.dumps(plans))
