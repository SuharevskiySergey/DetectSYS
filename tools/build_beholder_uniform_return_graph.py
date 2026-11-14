"""Explicit ordinary reverse redistribution, not recovery from state 3.

Non-idempotent extension of the separate test Blueprint. Direction +1 packs,
-1 restores uniform stages; existing states and contact ownership are reused.
"""
import json

from build_beholder_plane_graph import Plan
from build_beholder_contact_watch_graph import function
from build_beholder_redistribution_graph import call
from build_beholder_surface_graph import BP as LEG

DIRECTION_VALID = '((RedistributionDirection == 1.000000) || (RedistributionDirection == -1.000000))'


def packed(i):
    return f'clamp(RedistributionExtension*10.000000-{i}.000000,0.000000,1.000000)'


def stage_value(i):
    return (f'RedistributionExtension+({packed(i)}-RedistributionExtension)'
            '*((1.000000-RedistributionDirection)/2.000000+RedistributionDirection*RedistributionProgress)')


def final_value(i):
    return f'RedistributionExtension+({packed(i)}-RedistributionExtension)*(1.000000+RedistributionDirection)/2.000000'


def motion_snapshot():
    checks = [DIRECTION_VALID, '(bSequentialMotion == (RedistributionDirection < 0.000000))',
              '(RedistributionExtension >= 0.100000)', '(RedistributionExtension <= 0.900000)',
              '(abs(ExtensionAmount-RedistributionExtension) <= 0.000001)',
              '(abs(ExtensionPosition-RedistributionExtension) <= 0.000001)',
              '(RedistributionProgress >= 0.000000)', '(RedistributionProgress <= 1.000000)',
              '(ExtensionSeconds >= 0.010000)', '(ExtensionSeconds <= RedistributionDuration)',
              '(RetractionSeconds >= 0.010000)', '(RetractionSeconds <= RedistributionDuration)']
    return ' && '.join(checks+[f'(abs(Stage{i}Position-({stage_value(i)})) <= 0.000001)' for i in range(10)])


def monitor_snapshot():
    checks = ['bRedistributionContactOwned', DIRECTION_VALID,
              '(bSequentialMotion == (RedistributionDirection > 0.000000))',
              '(RedistributionExtension >= 0.100000)', '(RedistributionExtension <= 0.900000)',
              '(abs(ExtensionAmount-RedistributionExtension) <= 0.000001)',
              '(abs(ExtensionPosition-RedistributionExtension) <= 0.000001)',
              '(abs(RedistributionProgress-1.000000) <= 0.000001)']
    return ' && '.join(checks+[f'(abs(Stage{i}Position-({final_value(i)})) <= 0.000001)' for i in range(10)])


def members():
    return [dict(edit='add_variable', variableName='RedistributionDirection', variableType='float',
                 defaultValue=1, isPublic=False, category='Experimental Redistribution')]


def request():
    p = Plan('TryExperimentalUniformRedistribution')
    function(p, 'entry', [('DurationSeconds', 'float')], [('Accepted', 'bool')], public=True)
    p.node('self', 'Self')
    p.node('reject', 'FunctionResult', pinDefaults={'Accepted': False})
    conditions = ['((RedistributionState == 2) || (RedistributionState == 4))',
                  '((RedistributionState == 2) || bRedistributionContactOwned)',
                  '(RedistributionDirection == 1.000000)', 'bEnableStageRedistribution', 'bSequentialMotion',
                  '(RedistributionExtension >= 0.100000)', '(RedistributionExtension <= 0.900000)',
                  '(abs(ExtensionAmount-RedistributionExtension) <= 0.000001)',
                  '(abs(ExtensionPosition-RedistributionExtension) <= 0.000001)',
                  '(abs(RedistributionProgress-1.000000) <= 0.000001)',
                  '(seconds >= 0.100000)', '(seconds <= 60.000000)',
                  '(ExtensionSeconds >= 0.010000)', '(ExtensionSeconds <= seconds)',
                  '(RetractionSeconds >= 0.010000)', '(RetractionSeconds <= seconds)']
    conditions += [f'(abs(Stage{i}Position-({packed(i)})) <= 0.000001)' for i in range(10)]
    p.node('eligible', 'MathExpression', expression=' && '.join(conditions))
    p.wire('entry.DurationSeconds', 'eligible.seconds')
    p.node('branch', 'Branch')
    p.wire('entry.then', 'branch.execute')
    p.wire('eligible.ReturnValue', 'branch.Condition')
    p.wire('branch.else', 'reject.execute')
    p.call('pose', 'GetTransform', '/Script/Engine.Actor')
    p.getter('cached', 'RedistributionPose')
    p.call('same', 'NearlyEqual_TransformTransform', defaults={'LocationTolerance': 0.001,
           'RotationTolerance': 0.000001, 'Scale3DTolerance': 0.000001})
    p.wire('pose.ReturnValue', 'same.A')
    p.wire('cached.RedistributionPose', 'same.B')
    p.node('posebranch', 'Branch')
    p.wire('branch.then', 'posebranch.execute')
    p.wire('same.ReturnValue', 'posebranch.Condition')
    p.wire('posebranch.else', 'reject.execute')
    p.call('safe', 'IsExperimentalContactPoseSafe', LEG)
    p.wire('self.self', 'safe.self')
    p.wire('posebranch.then', 'safe.execute')
    p.node('safebranch', 'Branch')
    p.wire('safe.then', 'safebranch.execute')
    p.wire('safe.Safe', 'safebranch.Condition')
    p.wire('safebranch.else', 'reject.execute')
    call(p, 'contact', 'CheckOwnedRedistributionContact')
    p.wire('safebranch.then', 'contact.execute')
    p.node('commit', 'Branch')
    p.wire('contact.then', 'commit.execute')
    p.wire('contact.Valid', 'commit.Condition')
    p.wire('commit.else', 'reject.execute')
    previous = 'commit.then'
    for id, name, value, source in [('duration', 'RedistributionDuration', None, 'entry.DurationSeconds'),
                                  ('elapsed', 'RedistributionElapsed', 0, None),
                                  ('count', 'RedistributionUpdates', 0, None),
                                  ('progress', 'RedistributionProgress', 0, None),
                                  ('reason', 'RedistributionReason', 0, None),
                                  ('direction', 'RedistributionDirection', -1, None),
                                  ('state', 'RedistributionState', 1, None)]:
        p.setter(id, name, value)
        if source:
            p.wire(source, id+'.'+name)
        p.wire(previous, id+'.execute')
        previous = id+'.then'
    p.wire(previous, 'entry_return.execute')
    p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return', pinName='Accepted', propertyValue=True))
    return p.ops


def integration(ids):
    required = {f'value{i}' for i in range(10)} | {'motion', 'monitor', 'completionmode', 'forwardclear', 'forwardstore'}
    if set(ids) != required or any(not isinstance(v, str) or not v for v in ids.values()):
        raise ValueError('Fresh inspected node IDs required')
    ops = [dict(edit='set_node_property', graphName='ApplyRedistribution'+str(0 if i < 5 else 5),
                nodeId=ids[f'value{i}'], propertyName='Expression', propertyValue=stage_value(i)) for i in range(10)]
    ops += [dict(edit='set_node_property', graphName=graph, nodeId=ids[key], propertyName='Expression', propertyValue=value)
            for graph, key, value in [('UpdateStageRedistribution', 'motion', motion_snapshot()),
                                       ('UpdateRedistributionContactMonitoring', 'monitor', monitor_snapshot())]]
    p = Plan('UpdateStageRedistribution')
    p.node('targetmode', 'MathExpression', expression='RedistributionDirection > 0.000000')
    p.ops.append(dict(edit='connect_pins', **{'from': '$targetmode.ReturnValue',
                     'toNodeId': ids['completionmode'], 'toPinName': 'bSequentialMotion'}))
    ops += p.ops
    p = Plan('TryExperimentalStageRedistribution')
    p.setter('packingdirection', 'RedistributionDirection', 1)
    p.ops.append(dict(edit='connect_pins', fromNodeId=ids['forwardclear'], fromPinName='then', to='$packingdirection.execute'))
    p.ops.append(dict(edit='connect_pins', **{'from': '$packingdirection.then',
                     'toNodeId': ids['forwardstore'], 'toPinName': 'execute'}))
    return ops+p.ops


if __name__ == '__main__':
    plans = dict(members=members(), request=request())
    assert all(len(ops) <= 200 for ops in plans.values())
    print(json.dumps(plans))
