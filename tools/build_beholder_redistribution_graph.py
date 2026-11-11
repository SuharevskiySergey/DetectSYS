"""Non-idempotent plans for a separate unloaded redistribution test Blueprint.

Does not modify the body leg or original telescope. States 0 parent, 1 active,
2 complete/held, 3 aborted/held. Aborted copies require a fresh PIE/reset.
"""
import json

from build_beholder_plane_graph import Plan
from build_beholder_contact_watch_graph import function
from build_beholder_surface_graph import BP as LEG

BP = '/Game/BeholderPrototype/Telescopic/BP_BeholderStageRedistribution_Test'


def call(p, id, name, defaults=None):
    p.call(id, name, BP, defaults)
    p.wire('self.self', id+'.self')


def members():
    fields = [('bEnableStageRedistribution', 'bool', False, True),
              ('RedistributionState', 'int', 0, True), ('RedistributionReason', 'int', 0, True),
              ('RedistributionElapsed', 'float', 0, True), ('RedistributionUpdates', 'int', 0, True),
              ('RedistributionProgress', 'float', 0, True),
              ('RedistributionDuration', 'float', 4, False), ('RedistributionExtension', 'float', 0, False)]
    ops = [dict(edit='add_variable', variableName=n, variableType=t, defaultValue=v,
                isPublic=public, category='Experimental Redistribution') for n, t, v, public in fields]
    ops.append(dict(edit='add_variable', variableName='RedistributionPose', variableType='Transform', isPublic=False))
    return ops


def apply_group(indices):
    p = Plan('ApplyRedistribution'+str(indices[0]))
    function(p, 'entry')
    previous = 'entry.then'
    for i in indices:
        p.node(f'value{i}', 'MathExpression', expression=(
            f'RedistributionExtension+(clamp(RedistributionExtension*10.000000-{i}.000000,0.000000,1.000000)'
            f'-RedistributionExtension)*RedistributionProgress'))
        p.setter(f'stage{i}', f'Stage{i}Position')
        p.wire(f'value{i}.ReturnValue', f'stage{i}.Stage{i}Position')
        p.wire(previous, f'stage{i}.execute')
        p.node(f'vector{i}', 'MathExpression', expression=f'VECT(104.000000*s,0.000000,0.000000)')
        p.wire(f'value{i}.ReturnValue', f'vector{i}.s')
        p.getter(f'part{i}', f'Sleeve{i:02d}')
        p.call(f'move{i}', 'K2_SetRelativeLocation', '/Script/Engine.SceneComponent',
               {'bSweep': False, 'bTeleport': True})
        p.wire(f'part{i}.Sleeve{i:02d}', f'move{i}.self')
        p.wire(f'vector{i}.ReturnValue', f'move{i}.NewLocation')
        p.wire(f'stage{i}.then', f'move{i}.execute')
        previous = f'move{i}.then'
    return p.ops


def request():
    p = Plan('TryExperimentalStageRedistribution')
    function(p, 'entry', [('DurationSeconds', 'float')], [('Accepted', 'bool')], public=True)
    p.node('self', 'Self')
    p.node('reject', 'FunctionResult', pinDefaults={'Accepted': False})
    checks = ['bEnableStageRedistribution', '(RedistributionState == 0)', '(bSequentialMotion == false)',
              '(ExtensionPosition >= 0.100000)', '(ExtensionPosition <= 0.900000)',
              '(abs(ExtensionAmount-ExtensionPosition) <= 0.000001)',
              '(seconds >= 0.100000)', '(seconds <= 60.000000)',
              '(ExtensionSeconds >= 0.010000)', '(ExtensionSeconds <= seconds)',
              '(RetractionSeconds >= 0.010000)', '(RetractionSeconds <= seconds)']
    checks += [f'(abs(Stage{i}Position-ExtensionPosition) <= 0.000001)' for i in range(10)]
    p.node('eligible', 'MathExpression', expression=' && '.join(checks))
    p.wire('entry.DurationSeconds', 'eligible.seconds')
    p.node('branch', 'Branch')
    p.wire('entry.then', 'branch.execute')
    p.wire('eligible.ReturnValue', 'branch.Condition')
    p.wire('branch.else', 'reject.execute')
    p.call('safe', 'IsExperimentalContactPoseSafe', LEG)
    p.wire('self.self', 'safe.self')
    p.wire('branch.then', 'safe.execute')
    p.node('safecheck', 'Branch')
    p.wire('safe.Safe', 'safecheck.Condition')
    p.wire('safe.then', 'safecheck.execute')
    p.wire('safecheck.else', 'reject.execute')
    p.getter('extension', 'ExtensionPosition')
    p.call('pose', 'GetTransform', '/Script/Engine.Actor')
    previous = 'safecheck.then'
    for id, name, value, source in [('extensionstore', 'RedistributionExtension', None, 'extension.ExtensionPosition'),
                                  ('duration', 'RedistributionDuration', None, 'entry.DurationSeconds'),
                                  ('posecache', 'RedistributionPose', None, 'pose.ReturnValue'),
                                  ('elapsed', 'RedistributionElapsed', 0, None), ('count', 'RedistributionUpdates', 0, None),
                                  ('progress', 'RedistributionProgress', 0, None), ('reason', 'RedistributionReason', 0, None),
                                  ('state', 'RedistributionState', 1, None)]:
        p.setter(id, name, value)
        if source:
            p.wire(source, id+'.'+name)
        p.wire(previous, id+'.execute')
        previous = id+'.then'
    p.wire(previous, 'entry_return.execute')
    p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return', pinName='Accepted', propertyValue=True))
    return p.ops


def abort():
    p = Plan('AbortStageRedistribution')
    function(p, 'entry', [('Reason', 'int')])
    p.node('active', 'MathExpression', expression='RedistributionState == 1')
    p.node('branch', 'Branch')
    p.wire('entry.then', 'branch.execute')
    p.wire('active.ReturnValue', 'branch.Condition')
    p.setter('reason', 'RedistributionReason')
    p.wire('entry.Reason', 'reason.RedistributionReason')
    p.wire('branch.then', 'reason.execute')
    p.setter('state', 'RedistributionState', 3)
    p.wire('reason.then', 'state.execute')
    return p.ops


def cancel():
    p = Plan('CancelStageRedistribution')
    function(p, 'entry', public=True)
    p.node('self', 'Self')
    call(p, 'abort', 'AbortStageRedistribution', {'Reason': 5})
    p.wire('entry.then', 'abort.execute')
    return p.ops


def release():
    p = Plan('ReleaseStageRedistribution')
    function(p, 'entry', outputs=[('Released', 'bool')], public=True)
    p.node('reject', 'FunctionResult', pinDefaults={'Released': False})
    p.node('complete', 'MathExpression', expression='RedistributionState == 2')
    p.node('branch', 'Branch')
    p.wire('entry.then', 'branch.execute')
    p.wire('complete.ReturnValue', 'branch.Condition')
    p.wire('branch.else', 'reject.execute')
    p.setter('state', 'RedistributionState', 0)
    p.wire('branch.then', 'state.execute')
    p.wire('state.then', 'entry_return.execute')
    p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return', pinName='Released', propertyValue=True))
    return p.ops


def update():
    p = Plan('UpdateStageRedistribution')
    function(p, 'entry', [('DeltaSeconds', 'float')], public=True)
    p.node('self', 'Self')
    p.node('active', 'MathExpression', expression='RedistributionState == 1')
    p.node('activebranch', 'Branch')
    p.wire('entry.then', 'activebranch.execute')
    p.wire('active.ReturnValue', 'activebranch.Condition')
    p.getter('count', 'RedistributionUpdates')
    p.call('add', 'Add_IntInt', defaults={'B': 1})
    p.wire('count.RedistributionUpdates', 'add.A')
    p.setter('countstore', 'RedistributionUpdates')
    p.wire('add.ReturnValue', 'countstore.RedistributionUpdates')
    p.wire('activebranch.then', 'countstore.execute')
    for id, reason in [('disabled', 1), ('moved', 2), ('invalid', 3), ('badtime', 4)]:
        call(p, id, 'AbortStageRedistribution', {'Reason': reason})
    p.getter('enabled', 'bEnableStageRedistribution')
    p.node('enabledbranch', 'Branch')
    p.wire('countstore.then', 'enabledbranch.execute')
    p.wire('enabled.bEnableStageRedistribution', 'enabledbranch.Condition')
    p.wire('enabledbranch.else', 'disabled.execute')
    p.node('time', 'MathExpression', expression='(dt >= 0.000000) && (dt <= 10.000000) && (RedistributionElapsed >= 0.000000) && (RedistributionElapsed <= 60.000000) && (RedistributionDuration >= 0.100000) && (RedistributionDuration <= 60.000000)')
    p.wire('entry.DeltaSeconds', 'time.dt')
    p.node('timebranch', 'Branch')
    p.wire('time.ReturnValue', 'timebranch.Condition')
    p.wire('enabledbranch.then', 'timebranch.execute')
    p.wire('timebranch.else', 'badtime.execute')
    p.call('pose', 'GetTransform', '/Script/Engine.Actor')
    p.getter('cached', 'RedistributionPose')
    p.call('same', 'NearlyEqual_TransformTransform', defaults={'LocationTolerance': 0.001, 'RotationTolerance': 0.000001, 'Scale3DTolerance': 0.000001})
    p.wire('pose.ReturnValue', 'same.A')
    p.wire('cached.RedistributionPose', 'same.B')
    p.node('posebranch', 'Branch')
    p.wire('same.ReturnValue', 'posebranch.Condition')
    p.wire('timebranch.then', 'posebranch.execute')
    p.wire('posebranch.else', 'moved.execute')
    p.call('safe', 'IsExperimentalContactPoseSafe', LEG)
    p.wire('self.self', 'safe.self')
    p.wire('posebranch.then', 'safe.execute')
    conditions = ['(bSequentialMotion == false)', '(abs(ExtensionAmount-RedistributionExtension) <= 0.000001)',
                  '(abs(ExtensionPosition-RedistributionExtension) <= 0.000001)',
                  '(RedistributionProgress >= 0.000000)', '(RedistributionProgress <= 1.000000)',
                  '(ExtensionSeconds >= 0.010000)', '(ExtensionSeconds <= RedistributionDuration)',
                  '(RetractionSeconds >= 0.010000)', '(RetractionSeconds <= RedistributionDuration)']
    conditions += [f'(abs(Stage{i}Position-(RedistributionExtension+(clamp(RedistributionExtension*10.000000-{i}.000000,0.000000,1.000000)-RedistributionExtension)*RedistributionProgress)) <= 0.000001)' for i in range(10)]
    p.node('snapshot', 'MathExpression', expression=' && '.join(conditions))
    p.call('valid', 'BooleanAND')
    p.wire('safe.Safe', 'valid.A')
    p.wire('snapshot.ReturnValue', 'valid.B')
    p.node('validbranch', 'Branch')
    p.wire('valid.ReturnValue', 'validbranch.Condition')
    p.wire('safe.then', 'validbranch.execute')
    p.wire('validbranch.else', 'invalid.execute')
    p.node('elapsed', 'MathExpression', expression='min(RedistributionElapsed+dt,RedistributionDuration)')
    p.wire('entry.DeltaSeconds', 'elapsed.dt')
    p.setter('elapsedstore', 'RedistributionElapsed')
    p.wire('elapsed.ReturnValue', 'elapsedstore.RedistributionElapsed')
    p.wire('validbranch.then', 'elapsedstore.execute')
    p.node('alpha', 'MathExpression', expression='RedistributionElapsed/RedistributionDuration')
    p.setter('progress', 'RedistributionProgress')
    p.wire('alpha.ReturnValue', 'progress.RedistributionProgress')
    p.wire('elapsedstore.then', 'progress.execute')
    call(p, 'first', 'ApplyRedistribution0')
    call(p, 'second', 'ApplyRedistribution5')
    p.wire('progress.then', 'first.execute')
    p.wire('first.then', 'second.execute')
    p.node('done', 'MathExpression', expression='RedistributionProgress >= 1.000000')
    p.node('donebranch', 'Branch')
    p.wire('done.ReturnValue', 'donebranch.Condition')
    p.wire('second.then', 'donebranch.execute')
    p.setter('sequential', 'bSequentialMotion', True)
    p.wire('donebranch.then', 'sequential.execute')
    p.setter('state', 'RedistributionState', 2)
    p.wire('sequential.then', 'state.execute')
    return p.ops


def tick(ids):
    p = Plan('EventGraph')
    p.node('self', 'Self')
    p.node('owned', 'MathExpression', expression='RedistributionState != 0')
    p.node('dispatch', 'Branch')
    p.wire('tick.then', 'dispatch.execute')
    p.wire('owned.ReturnValue', 'dispatch.Condition')
    p.wire('dispatch.else', 'parent.execute')
    call(p, 'update', 'UpdateStageRedistribution')
    p.wire('tick.DeltaSeconds', 'update.DeltaSeconds')
    p.wire('dispatch.then', 'update.execute')
    result = []
    for source in p.ops:
        op = dict(source)
        for key in ('from', 'to'):
            value = op.get(key, '')
            alias = value[1:].split('.')[0] if value.startswith('$') else ''
            if alias in ids:
                op[key+'NodeId'], op[key+'PinName'] = ids[alias], value.split('.', 1)[1]
                del op[key]
        result.append(op)
    return result


if __name__ == '__main__':
    plans = dict(members=members(), first=apply_group(range(5)), second=apply_group(range(5, 10)),
                 request=request(), abort=abort(), cancel=cancel(), release=release(), update=update())
    assert all(len(ops) <= 200 for ops in plans.values())
    print(json.dumps(plans))
