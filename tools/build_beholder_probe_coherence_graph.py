"""Fail-closed gross pose-envelope checks before the sensor's first trace.

81 cm is the original-head local conservative orbit envelope:
180 / (60/27). It is NOT a timestamp or an exact animation-pose test.
Inspect before applying these non-idempotent creation plans.
"""
import json
from pathlib import Path

from build_beholder_contact_watch_graph import function
from build_beholder_plane_graph import Plan
from build_beholder_surface_graph import BP as LEG, HEAD

LOCAL_ENVELOPE_RADIUS = 81.0
WORLD_TOLERANCE_CM = 0.01
CONDITION = ('(radius >= 0.000001) && (radius <= 1000000.000000) && '
             '((px-cx)*(px-cx)+(py-cy)*(py-cy)+(pz-cz)*(pz-cz) '
             f'<= (radius+{WORLD_TOLERANCE_CM:.6f})*(radius+{WORLD_TOLERANCE_CM:.6f}))')


def point():
    p = Plan('IsSurfacePointCoherent')
    function(p, 'entry', [('Candidate', 'Vector'), ('Center', 'Vector'), ('Radius', 'float')],
             [('Coherent', 'bool')], public=True)
    p.node('reject', 'FunctionResult', pinDefaults={'Coherent': False})
    for id, param in [('pointnan', 'Candidate'), ('centernan', 'Center')]:
        p.call(id, 'Vector_IsNAN')
        p.wire('entry.'+param, id+'.A')
    p.call('bad', 'BooleanOR')
    p.wire('pointnan.ReturnValue', 'bad.A')
    p.wire('centernan.ReturnValue', 'bad.B')
    p.node('branch', 'Branch')
    p.wire('entry.then', 'branch.execute')
    p.wire('bad.ReturnValue', 'branch.Condition')
    p.wire('branch.then', 'reject.execute')
    p.wire('branch.else', 'entry_return.execute')
    p.breakvec('p', 'entry.Candidate')
    p.breakvec('c', 'entry.Center')
    p.node('inside', 'MathExpression', expression=CONDITION)
    for prefix in 'pc':
        for axis in 'XYZ':
            p.wire(prefix+'.'+axis, 'inside.'+prefix+axis.lower())
    p.wire('entry.Radius', 'inside.radius')
    p.wire('inside.ReturnValue', 'entry_return.Coherent')
    return p.ops


def pose():
    p = Plan('IsSurfacePoseCoherent')
    function(p, 'entry', outputs=[('Coherent', 'bool')], public=True)
    p.node('self', 'Self')
    p.node('reject', 'FunctionResult', pinDefaults={'Coherent': False})
    p.getter('hm', 'HeadModule')
    p.valid('hmvalid', 'hm.HeadModule', 'entry.then')
    p.wire('hmvalid.Is Not Valid', 'reject.execute')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('hm.HeadModule', 'child.self')
    p.node('cast', 'Cast', targetClass=HEAD)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('hmvalid.Is Valid', 'cast.execute')
    p.wire('cast.CastFailed', 'reject.execute')
    p.node('mesh', 'VariableGet', memberName='HeadMesh', memberClass=HEAD)
    p.wire('cast.AsBP Lapa 5 Head', 'mesh.self')
    p.valid('meshvalid', 'mesh.HeadMesh', 'cast.then')
    p.wire('meshvalid.Is Not Valid', 'reject.execute')
    p.call('center', 'K2_GetActorLocation', '/Script/Engine.Actor')
    p.call('scale', 'GetActorScale3D', '/Script/Engine.Actor')
    p.wire('cast.AsBP Lapa 5 Head', 'center.self')
    p.wire('cast.AsBP Lapa 5 Head', 'scale.self')
    p.breakvec('s', 'scale.ReturnValue')
    p.node('radius', 'MathExpression', expression=f'{LOCAL_ENVELOPE_RADIUS:.6f}*max(abs(sx),max(abs(sy),abs(sz)))')
    for axis in 'XYZ':
        p.wire('s.'+axis, 'radius.s'+axis.lower())
    bones = json.loads((Path(__file__).parent/'fixtures/lapa5_claw_vertices.json').read_text())['bones']
    for i, bone in enumerate(bones):
        p.call(f'exists{i}', 'DoesSocketExist', '/Script/Engine.SceneComponent', {'InSocketName': bone})
        p.wire('mesh.HeadMesh', f'exists{i}.self')
    p.call('and1', 'BooleanAND')
    p.call('and2', 'BooleanAND')
    for a, b in [('exists0.ReturnValue', 'and1.A'), ('exists1.ReturnValue', 'and1.B'),
                  ('and1.ReturnValue', 'and2.A'), ('exists2.ReturnValue', 'and2.B')]:
        p.wire(a, b)
    p.node('sockets', 'Branch')
    p.wire('meshvalid.Is Valid', 'sockets.execute')
    p.wire('and2.ReturnValue', 'sockets.Condition')
    p.wire('sockets.else', 'reject.execute')
    previous = 'sockets.then'
    for i, (bone, vertices) in enumerate(bones.items()):
        p.call(f'socket{i}', 'GetSocketTransform', '/Script/Engine.SceneComponent',
               {'InSocketName': bone, 'TransformSpace': 'RTS_World'})
        p.wire('mesh.HeadMesh', f'socket{i}.self')
        for j, vertex in enumerate(vertices):
            id = f'p{i}{j}'
            p.call(id, 'TransformLocation', defaults={'Location': ','.join(map(str, vertex))})
            p.wire(f'socket{i}.ReturnValue', id+'.T')
            p.call('check'+id, 'IsSurfacePointCoherent', LEG)
            for a, b in [('self.self', 'self'), (id+'.ReturnValue', 'Candidate'),
                          ('center.ReturnValue', 'Center'), ('radius.ReturnValue', 'Radius')]:
                p.wire(a, 'check'+id+'.'+b)
            p.wire(previous, 'check'+id+'.execute')
            p.node('branch'+id, 'Branch')
            p.wire('check'+id+'.then', 'branch'+id+'.execute')
            p.wire('check'+id+'.Coherent', 'branch'+id+'.Condition')
            p.wire('branch'+id+'.else', 'reject.execute')
            previous = 'branch'+id+'.then'
    p.wire(previous, 'entry_return.execute')
    p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return', pinName='Coherent', propertyValue=True))
    return p.ops


def integration(reset_id, next_id):
    graph = 'MeasureSurfaceProbe'
    return [
        dict(edit='create_node', graphName=graph, id='coherenceself', nodeType='Self'),
        dict(edit='create_node', graphName=graph, id='coherence', nodeType='CallFunction',
             memberName='IsSurfacePoseCoherent', memberClass=LEG),
        dict(edit='connect_pins', **{'from': '$coherenceself.self', 'to': '$coherence.self'}),
        dict(edit='connect_pins', fromNodeId=reset_id, fromPinName='then', to='$coherence.execute'),
        dict(edit='create_node', graphName=graph, id='coherentbranch', nodeType='Branch'),
        dict(edit='connect_pins', **{'from': '$coherence.then', 'to': '$coherentbranch.execute'}),
        dict(edit='connect_pins', **{'from': '$coherence.Coherent', 'to': '$coherentbranch.Condition'}),
        dict(edit='connect_pins', **{'from': '$coherentbranch.then'}, toNodeId=next_id, toPinName='exec'),
    ]


if __name__ == '__main__':
    plans = dict(point=point(), pose=pose())
    assert all(len(ops) <= 200 for ops in plans.values())
    print(json.dumps(plans))
