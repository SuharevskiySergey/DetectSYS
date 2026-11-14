"""Installed plans: explicit monitoring after contact redistribution.

Apply only after fresh editor inspection. State 2 stays passive; new state 4
monitors the captured contact without recapturing it or moving any geometry.
Creation plans are non-idempotent; inspect assets before any further upgrade.
"""
import json

from build_beholder_plane_graph import Plan
from build_beholder_contact_watch_graph import function
from build_beholder_redistribution_graph import call
from build_beholder_surface_graph import BP as LEG

ELIGIBLE = '((RedistributionState == 2) || (RedistributionState == 4)) && bRedistributionContactOwned'
ABORT = '(RedistributionState == 1) || (RedistributionState == 4)'
RELEASE = '(RedistributionState == 2) || (RedistributionState == 4)'
TIME = '(dt >= 0.000000) && (dt <= 10.000000)'
SNAPSHOT = ' && '.join([
    'bRedistributionContactOwned', 'bSequentialMotion',
    '(RedistributionExtension >= 0.100000)', '(RedistributionExtension <= 0.900000)',
    '(abs(ExtensionAmount-RedistributionExtension) <= 0.000001)',
    '(abs(ExtensionPosition-RedistributionExtension) <= 0.000001)',
    '(abs(RedistributionProgress-1.000000) <= 0.000001)',
] + [f'(abs(Stage{i}Position-clamp(RedistributionExtension*10.000000-{i}.000000,0.000000,1.000000)) <= 0.000001)'
     for i in range(10)])


def members():
    return [dict(edit='add_variable', variableName='RedistributionMonitoringUpdates', variableType='int',
                 defaultValue=0, isPublic=True, category='Experimental Redistribution Contact')]


def begin():
    p = Plan('BeginRedistributionContactMonitoring')
    function(p, 'entry', outputs=[('Started', 'bool')], public=True)
    p.node('self', 'Self')
    p.node('reject', 'FunctionResult', pinDefaults={'Started': False})
    p.node('eligible', 'MathExpression', expression=ELIGIBLE)
    p.node('eligiblebranch', 'Branch')
    p.wire('entry.then', 'eligiblebranch.execute')
    p.wire('eligible.ReturnValue', 'eligiblebranch.Condition')
    p.wire('eligiblebranch.else', 'reject.execute')
    p.node('first', 'MathExpression', expression='RedistributionState == 2')
    p.node('firstbranch', 'Branch')
    p.wire('eligiblebranch.then', 'firstbranch.execute')
    p.wire('first.ReturnValue', 'firstbranch.Condition')
    p.setter('resetcount', 'RedistributionMonitoringUpdates', 0)
    p.wire('firstbranch.then', 'resetcount.execute')
    p.setter('state', 'RedistributionState', 4)
    p.wire('resetcount.then', 'state.execute')
    p.wire('firstbranch.else', 'state.execute')
    call(p, 'check', 'UpdateRedistributionContactMonitoring', {'DeltaSeconds': 0})
    p.wire('state.then', 'check.execute')
    p.node('started', 'MathExpression', expression='RedistributionState == 4')
    p.wire('started.ReturnValue', 'entry_return.Started')
    p.wire('check.then', 'entry_return.execute')
    return p.ops


def update():
    p = Plan('UpdateRedistributionContactMonitoring')
    function(p, 'entry', [('DeltaSeconds', 'float')])
    p.node('self', 'Self')
    p.node('active', 'MathExpression', expression='RedistributionState == 4')
    p.node('activebranch', 'Branch')
    p.wire('entry.then', 'activebranch.execute')
    p.wire('active.ReturnValue', 'activebranch.Condition')
    p.getter('count', 'RedistributionMonitoringUpdates')
    p.call('plus', 'Add_IntInt', defaults={'B': 1})
    p.wire('count.RedistributionMonitoringUpdates', 'plus.A')
    p.setter('setcount', 'RedistributionMonitoringUpdates')
    p.wire('plus.ReturnValue', 'setcount.RedistributionMonitoringUpdates')
    p.wire('activebranch.then', 'setcount.execute')
    for id, reason in [('disabled', 1), ('moved', 2), ('invalid', 3), ('badtime', 4), ('contactlost', 6)]:
        call(p, id, 'AbortStageRedistribution', {'Reason': reason})
    p.getter('enabled', 'bEnableStageRedistribution')
    p.node('enabledbranch', 'Branch')
    p.wire('setcount.then', 'enabledbranch.execute')
    p.wire('enabled.bEnableStageRedistribution', 'enabledbranch.Condition')
    p.wire('enabledbranch.else', 'disabled.execute')
    p.node('time', 'MathExpression', expression=TIME)
    p.wire('entry.DeltaSeconds', 'time.dt')
    p.node('timebranch', 'Branch')
    p.wire('enabledbranch.then', 'timebranch.execute')
    p.wire('time.ReturnValue', 'timebranch.Condition')
    p.wire('timebranch.else', 'badtime.execute')
    p.call('pose', 'GetTransform', '/Script/Engine.Actor')
    p.getter('captured', 'RedistributionPose')
    p.call('same', 'NearlyEqual_TransformTransform', defaults={'LocationTolerance': 0.001,
           'RotationTolerance': 0.000001, 'Scale3DTolerance': 0.000001})
    p.wire('pose.ReturnValue', 'same.A')
    p.wire('captured.RedistributionPose', 'same.B')
    p.node('posebranch', 'Branch')
    p.wire('timebranch.then', 'posebranch.execute')
    p.wire('same.ReturnValue', 'posebranch.Condition')
    p.wire('posebranch.else', 'moved.execute')
    p.call('safe', 'IsExperimentalContactPoseSafe', LEG)
    p.wire('self.self', 'safe.self')
    p.wire('posebranch.then', 'safe.execute')
    p.node('snapshot', 'MathExpression', expression=SNAPSHOT)
    p.call('valid', 'BooleanAND')
    p.wire('snapshot.ReturnValue', 'valid.A')
    p.wire('safe.Safe', 'valid.B')
    p.node('validbranch', 'Branch')
    p.wire('safe.then', 'validbranch.execute')
    p.wire('valid.ReturnValue', 'validbranch.Condition')
    p.wire('validbranch.else', 'invalid.execute')
    call(p, 'contact', 'CheckOwnedRedistributionContact')
    p.wire('validbranch.then', 'contact.execute')
    p.node('contactbranch', 'Branch')
    p.wire('contact.then', 'contactbranch.execute')
    p.wire('contact.Valid', 'contactbranch.Condition')
    p.wire('contactbranch.else', 'contactlost.execute')
    return p.ops


def integration(ids):
    """Requires fresh inspected GUIDs; never uses guessed/persisted node IDs.

    ownedbranch: existing Tick dispatch; update: existing Tick call of the
    stage updater; tick: Tick event; self: existing EventGraph self node;
    abortcondition/releasecondition: existing MathExpression node GUIDs.
    """
    required = {'ownedbranch', 'update', 'tick', 'self', 'abortcondition', 'releasecondition'}
    if set(ids) != required or any(not isinstance(v, str) or not v for v in ids.values()):
        raise ValueError('Fresh inspected integration node IDs required')
    p = Plan('EventGraph')
    call(p, 'monitor', 'UpdateRedistributionContactMonitoring')
    p.wire('ownedbranch.then', 'monitor.execute')
    p.wire('tick.DeltaSeconds', 'monitor.DeltaSeconds')
    p.wire('monitor.then', 'update.execute')
    ops = []
    for source in p.ops:
        op = dict(source)
        for key in ('from', 'to'):
            value = op.get(key, '')
            alias = value[1:].split('.')[0] if value.startswith('$') else ''
            if alias in ids:
                op[key+'NodeId'], op[key+'PinName'] = ids[alias], value.split('.', 1)[1]
                del op[key]
        ops.append(op)
    ops.extend([
        dict(edit='set_node_property', graphName='AbortStageRedistribution', nodeId=ids['abortcondition'],
             propertyName='Expression', propertyValue=ABORT),
        dict(edit='set_node_property', graphName='ReleaseStageRedistribution', nodeId=ids['releasecondition'],
             propertyName='Expression', propertyValue=RELEASE),
    ])
    return ops


if __name__ == '__main__':
    plans = dict(members=members(), update=update(), begin=begin())
    assert all(len(ops) <= 200 for ops in plans.values())
    print(json.dumps(plans))
