"""Non-idempotent Blueprint plans for snapshot straight-plane reachability."""
import json

from build_beholder_plane_graph import Plan
from build_beholder_surface_graph import BP, HEAD
from generate_beholder_telescope import COUNT, STROKE

FIELDS = [('bStraightPlanValid', 'bool', False), ('bStraightPlaneReachable', 'bool', False),
          ('StraightTargetExtension', 'float', 0), ('StraightProjectedStroke', 'float', 0),
          ('StraightFoldedClearance', 'float', 0), ('StraightExtendedClearance', 'float', 0)]


def reset():
    p = Plan('ResetStraightSurfacePlan')
    for name, type, value in FIELDS:
        p.ops.append(dict(edit='add_variable', variableName=name, variableType=type, defaultValue=value,
                          isPublic=True, category='Straight Surface Plan'))
    p.function('entry')
    previous = 'entry.then'
    for i, (name, _, value) in enumerate(FIELDS):
        p.setter(f'reset{i}', name, value)
        p.wire(previous, f'reset{i}.execute')
        previous = f'reset{i}.then'
    return p.ops


def solve():
    p = Plan('SolveStraightPlaneTarget')
    p.ops.append(dict(edit='add_function', id='entry', functionName=p.graph, pure=False, isPublic=True,
                      inputs=[{'name': name, 'type': 'float'} for name in ('Current', 'Clearance', 'ProjectedStroke')]))
    p.node('self', 'Self')
    p.call('reset', 'ResetStraightSurfacePlan', BP)
    p.wire('self.self', 'reset.self')
    p.wire('entry.then', 'reset.execute')
    p.node('valid', 'MathExpression', expression='(amount >= 0.000000) && (amount <= 1.000000) && (gap >= 0.000000) && (gap <= 10000000.000000) && (abs(projected) > 0.000001) && (abs(projected) <= 100000000.000000)')
    for param, pin in [('Current', 'amount'), ('Clearance', 'gap'), ('ProjectedStroke', 'projected')]:
        p.wire('entry.'+param, 'valid.'+pin)
    p.node('branch', 'Branch')
    p.wire('valid.ReturnValue', 'branch.Condition')
    p.wire('reset.then', 'branch.execute')
    previous = 'branch.then'
    for id, name, expression in [('folded', 'StraightFoldedClearance', 'gap - amount*projected'),
                                  ('extended', 'StraightExtendedClearance', 'gap + (1.000000-amount)*projected')]:
        p.node(id, 'MathExpression', expression=expression)
        for param, pin in [('Current', 'amount'), ('Clearance', 'gap'), ('ProjectedStroke', 'projected')]:
            p.wire('entry.'+param, id+'.'+pin)
        p.setter('set'+id, name)
        p.wire(id+'.ReturnValue', 'set'+id+'.'+name)
        p.wire(previous, 'set'+id+'.execute')
        previous = 'set'+id+'.then'
    p.setter('stroke', 'StraightProjectedStroke')
    p.wire('entry.ProjectedStroke', 'stroke.StraightProjectedStroke')
    p.wire(previous, 'stroke.execute')
    p.setter('setvalid', 'bStraightPlanValid', True)
    p.wire('stroke.then', 'setvalid.execute')
    p.node('target', 'MathExpression', expression='amount - gap/projected')
    for param, pin in [('Current', 'amount'), ('Clearance', 'gap'), ('ProjectedStroke', 'projected')]:
        p.wire('entry.'+param, 'target.'+pin)
    p.node('inrange', 'MathExpression', expression='(targetAmount >= 0.000000) && (targetAmount <= 1.000000)')
    p.wire('target.ReturnValue', 'inrange.targetAmount')
    p.node('reachable', 'Branch')
    p.wire('inrange.ReturnValue', 'reachable.Condition')
    p.wire('setvalid.then', 'reachable.execute')
    p.setter('settarget', 'StraightTargetExtension')
    p.wire('target.ReturnValue', 'settarget.StraightTargetExtension')
    p.wire('reachable.then', 'settarget.execute')
    p.setter('setreachable', 'bStraightPlaneReachable', True)
    p.wire('settarget.then', 'setreachable.execute')
    return p.ops


def plan():
    p = Plan('PlanStraightSurfaceContact')
    p.ops.append(dict(edit='add_function', id='entry', functionName=p.graph, pure=False, isPublic=True))
    p.node('self', 'Self')
    p.call('reset', 'ResetStraightSurfacePlan', BP)
    p.wire('self.self', 'reset.self')
    p.wire('entry.then', 'reset.execute')
    joints = ' && '.join(f'(abs(Joint{i}Magnitude) <= 0.000001)' for i in range(1, COUNT))
    stages = '+'.join(f'Stage{i}Position' for i in range(COUNT))
    expression = (f'bProbeValid && bProbeHit && bProbePlaneValid && (bProbeInitialOverlap == false) '
                  f'&& (abs(ExtensionAmount-ExtensionPosition) <= 0.000001) '
                  f'&& (abs(({stages})/{COUNT}.000000-ExtensionPosition) <= 0.000001) && '+joints)
    p.node('conditions', 'MathExpression', expression=expression)
    p.node('ready', 'Branch')
    p.wire('conditions.ReturnValue', 'ready.Condition')
    p.wire('reset.then', 'ready.execute')
    p.getter('hm', 'HeadModule')
    p.valid('hmvalid', 'hm.HeadModule', 'ready.then')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('hm.HeadModule', 'child.self')
    p.node('cast', 'Cast', targetClass=HEAD)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('hmvalid.Is Valid', 'cast.execute')
    for i in range(3):
        p.node(f'claw{i}', 'VariableGet', memberName=f'Claw{i}Position', memberClass=HEAD)
        p.wire('cast.AsBP Lapa 5 Head', f'claw{i}.self')
    p.node('closed', 'MathExpression', expression='(abs(c0) <= 0.000001) && (abs(c1) <= 0.000001) && (abs(c2) <= 0.000001)')
    for i in range(3):
        p.wire(f'claw{i}.Claw{i}Position', f'closed.c{i}')
    p.node('closedbranch', 'Branch')
    p.wire('closed.ReturnValue', 'closedbranch.Condition')
    p.wire('cast.then', 'closedbranch.execute')
    p.call('scale', 'GetActorScale3D', '/Script/Engine.Actor')
    p.breakvec('s', 'scale.ReturnValue')
    p.node('uniform', 'MathExpression', expression='(sx > 0.000001) && (sx <= 10000.000000) && (abs(sx-sy) <= 0.000001) && (abs(sx-sz) <= 0.000001)')
    for axis in 'XYZ':
        p.wire('s.'+axis, 'uniform.s'+axis.lower())
    p.node('uniformbranch', 'Branch')
    p.wire('uniform.ReturnValue', 'uniformbranch.Condition')
    p.wire('closedbranch.then', 'uniformbranch.execute')
    p.call('forward', 'GetActorForwardVector', '/Script/Engine.Actor')
    p.breakvec('f', 'forward.ReturnValue')
    p.getter('normal', 'ProbePlaneNormal')
    p.breakvec('n', 'normal.ProbePlaneNormal')
    p.node('projected', 'MathExpression', expression=f'{float(COUNT*STROKE):.6f}*worldScale*(fx*nx + fy*ny + fz*nz)')
    p.wire('s.X', 'projected.worldScale')
    for prefix in 'fn':
        for axis in 'XYZ':
            p.wire(prefix+'.'+axis, 'projected.'+prefix+axis.lower())
    p.getter('current', 'ExtensionPosition')
    p.getter('clearance', 'ProbePlaneClearance')
    p.call('solve', 'SolveStraightPlaneTarget', BP)
    p.wire('self.self', 'solve.self')
    p.wire('current.ExtensionPosition', 'solve.Current')
    p.wire('clearance.ProbePlaneClearance', 'solve.Clearance')
    p.wire('projected.ReturnValue', 'solve.ProjectedStroke')
    p.wire('uniformbranch.then', 'solve.execute')
    assert len(p.ops) <= 200
    return p.ops


def integration(reset_plane_tail, evaluate_plane_tail):
    ops = []
    for graph, id, function, tail in [('ResetSurfacePlane', 'resetplan', 'ResetStraightSurfacePlan', reset_plane_tail),
                                      ('EvaluateSurfacePlane', 'plan', 'PlanStraightSurfaceContact', evaluate_plane_tail)]:
        ops.extend([
            dict(edit='create_node', graphName=graph, id=id+'self', nodeType='Self'),
            dict(edit='create_node', graphName=graph, id=id, nodeType='CallFunction', memberName=function, memberClass=BP),
            dict(edit='connect_pins', **{'from': '$'+id+'self.self', 'to': '$'+id+'.self'}),
            dict(edit='connect_pins', fromNodeId=tail, fromPinName='then', **{'to': '$'+id+'.execute'}),
        ])
    return ops


if __name__ == '__main__':
    print(json.dumps({'reset': reset(), 'solve': solve(), 'plan': plan()}))
