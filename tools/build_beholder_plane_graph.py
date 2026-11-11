"""EngineWire operation plans for the runtime plane-clearance extension.

These plans add new members; inspect the Blueprint before applying, do not
reapply to an existing implementation. They do not edit assets themselves.
"""
import json
from pathlib import Path

from build_beholder_surface_graph import BP, HEAD


class Plan:
    def __init__(self, graph):
        self.graph = graph
        self.ops = []

    def node(self, id, node_type, **extra):
        self.ops.append(dict(edit='create_node', graphName=self.graph, id=id, nodeType=node_type, **extra))

    def wire(self, source, target):
        self.ops.append(dict(edit='connect_pins', **{'from': '$'+source, 'to': '$'+target}))

    def call(self, id, name, cls='KismetMathLibrary', defaults=None):
        self.node(id, 'CallFunction', memberName=name, memberClass=cls,
                  **({'pinDefaults': defaults} if defaults else {}))

    def getter(self, id, name):
        self.node(id, 'VariableGet', memberName=name)

    def setter(self, id, name, value=None):
        self.node(id, 'VariableSet', memberName=name,
                  **({'pinDefaults': {name: value}} if value is not None else {}))

    def function(self, id, inputs=None):
        self.ops.append(dict(edit='add_function', id=id, functionName=self.graph,
                             pure=False, isPublic=False, **({'inputs': inputs} if inputs else {})))

    def valid(self, id, value, previous):
        self.node(id, 'K2Node_IsValid')
        self.wire(value, id+'.InputObject')
        self.wire(previous, id+'.exec')

    def breakvec(self, id, source):
        self.call(id, 'BreakVector')
        self.wire(source, id+'.InVec')


def helpers():
    p = Plan('ResetSurfacePlane')
    for name, type, value in [('bProbePlaneValid', 'bool', False), ('ProbePlaneClearance', 'float', 0),
                              ('ProbePlanePoint', 'Vector', '0,0,0'), ('ProbePlaneNormal', 'Vector', '0,0,0')]:
        p.ops.append(dict(edit='add_variable', variableName=name, variableType=type, defaultValue=value,
                          isPublic=True, category='Surface Probe'))
    p.function('resetplane')
    previous = 'resetplane.then'
    for id, name, value in [('valid', 'bProbePlaneValid', False), ('clear', 'ProbePlaneClearance', 0),
                            ('point', 'ProbePlanePoint', '0,0,0'), ('normal', 'ProbePlaneNormal', '0,0,0')]:
        p.setter(id, name, value)
        p.wire(previous, id+'.execute')
        previous = id+'.then'
    result = p.ops
    p = Plan('ConsiderSurfacePlanePoint')
    p.function('consider', [{'name': 'Candidate', 'type': 'Vector'}])
    p.getter('plane', 'ProbeImpactPoint')
    p.getter('normal', 'ProbePlaneNormal')
    for id, source in [('c', 'consider.Candidate'), ('p', 'plane.ProbeImpactPoint'), ('n', 'normal.ProbePlaneNormal')]:
        p.breakvec(id, source)
    p.node('distance', 'MathExpression', expression='(cx - px)*nx + (cy - py)*ny + (cz - pz)*nz')
    for prefix in 'cpn':
        for axis in 'XYZ':
            p.wire(prefix+'.'+axis, 'distance.'+prefix+axis.lower())
    p.node('less', 'MathExpression', expression='candidateDistance < ProbePlaneClearance')
    p.wire('distance.ReturnValue', 'less.candidateDistance')
    p.node('branch', 'Branch')
    p.wire('less.ReturnValue', 'branch.Condition')
    p.wire('consider.then', 'branch.execute')
    p.setter('setclear', 'ProbePlaneClearance')
    p.wire('distance.ReturnValue', 'setclear.ProbePlaneClearance')
    p.wire('branch.then', 'setclear.execute')
    p.setter('setpoint', 'ProbePlanePoint')
    p.wire('consider.Candidate', 'setpoint.ProbePlanePoint')
    p.wire('setclear.then', 'setpoint.execute')
    return result+p.ops


def evaluate():
    p = Plan('EvaluateSurfacePlane')
    p.function('entry')
    p.node('self', 'Self')
    p.call('reset', 'ResetSurfacePlane', BP)
    p.wire('self.self', 'reset.self')
    p.wire('entry.then', 'reset.execute')
    p.node('ready', 'MathExpression', expression='bProbeValid && bProbeHit && (bProbeInitialOverlap == false)')
    p.node('readybranch', 'Branch')
    p.wire('ready.ReturnValue', 'readybranch.Condition')
    p.wire('reset.then', 'readybranch.execute')
    p.getter('rawnormal', 'ProbeImpactNormal')
    p.breakvec('raw', 'rawnormal.ProbeImpactNormal')
    p.node('length', 'MathExpression', expression='sqrt(nx*nx + ny*ny + nz*nz)')
    for axis in 'XYZ':
        p.wire('raw.'+axis, 'length.n'+axis.lower())
    p.node('usable', 'MathExpression', expression='(normalLength > 0.000001) && (normalLength <= 2.000000)')
    p.wire('length.ReturnValue', 'usable.normalLength')
    p.node('normalbranch', 'Branch')
    p.wire('usable.ReturnValue', 'normalbranch.Condition')
    p.wire('readybranch.then', 'normalbranch.execute')
    p.getter('hm', 'HeadModule')
    p.valid('hmvalid', 'hm.HeadModule', 'normalbranch.then')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('hm.HeadModule', 'child.self')
    p.node('cast', 'Cast', targetClass=HEAD)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('hmvalid.Is Valid', 'cast.execute')
    p.node('mesh', 'VariableGet', memberName='HeadMesh', memberClass=HEAD)
    p.wire('cast.AsBP Lapa 5 Head', 'mesh.self')
    p.valid('meshvalid', 'mesh.HeadMesh', 'cast.then')
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
    p.wire('and2.ReturnValue', 'sockets.Condition')
    p.wire('meshvalid.Is Valid', 'sockets.execute')
    p.call('loc', 'K2_GetActorLocation', '/Script/Engine.Actor')
    p.call('scale', 'GetActorScale3D', '/Script/Engine.Actor')
    p.wire('cast.AsBP Lapa 5 Head', 'loc.self')
    p.wire('cast.AsBP Lapa 5 Head', 'scale.self')
    p.breakvec('c', 'loc.ReturnValue')
    p.breakvec('s', 'scale.ReturnValue')
    p.node('scaleok', 'MathExpression', expression='(max(abs(sx), max(abs(sy), abs(sz))) > 0.000001) && (abs(sx) <= 10000.000000) && (abs(sy) <= 10000.000000) && (abs(sz) <= 10000.000000)')
    for axis in 'XYZ':
        p.wire('s.'+axis, 'scaleok.s'+axis.lower())
    p.node('scalebranch', 'Branch')
    p.wire('scaleok.ReturnValue', 'scalebranch.Condition')
    p.wire('sockets.then', 'scalebranch.execute')
    p.node('unit', 'MathExpression', expression='VECT(nx/normalLength, ny/normalLength, nz/normalLength)')
    for axis in 'XYZ':
        p.wire('raw.'+axis, 'unit.n'+axis.lower())
    p.wire('length.ReturnValue', 'unit.normalLength')
    p.setter('setnormal', 'ProbePlaneNormal')
    p.wire('unit.ReturnValue', 'setnormal.ProbePlaneNormal')
    p.wire('scalebranch.then', 'setnormal.execute')
    p.getter('normal', 'ProbePlaneNormal')
    p.breakvec('n', 'normal.ProbePlaneNormal')
    p.node('sphere', 'MathExpression', expression='VECT(cx - 27.000000*max(abs(sx), max(abs(sy), abs(sz)))*nx, cy - 27.000000*max(abs(sx), max(abs(sy), abs(sz)))*ny, cz - 27.000000*max(abs(sx), max(abs(sy), abs(sz)))*nz)')
    for prefix in 'csn':
        for axis in 'XYZ':
            p.wire(prefix+'.'+axis, 'sphere.'+prefix+axis.lower())
    p.setter('seedpoint', 'ProbePlanePoint')
    p.wire('sphere.ReturnValue', 'seedpoint.ProbePlanePoint')
    p.wire('setnormal.then', 'seedpoint.execute')
    p.breakvec('q', 'seedpoint.Output_Get')
    p.getter('impact', 'ProbeImpactPoint')
    p.breakvec('p', 'impact.ProbeImpactPoint')
    p.node('distance', 'MathExpression', expression='(qx - px)*nx + (qy - py)*ny + (qz - pz)*nz')
    for prefix in 'qpn':
        for axis in 'XYZ':
            p.wire(prefix+'.'+axis, 'distance.'+prefix+axis.lower())
    p.setter('seedclear', 'ProbePlaneClearance')
    p.wire('distance.ReturnValue', 'seedclear.ProbePlaneClearance')
    p.wire('seedpoint.then', 'seedclear.execute')
    previous = 'seedclear.then'
    for i, (bone, vertices) in enumerate(bones.items()):
        p.call(f'socket{i}', 'GetSocketTransform', '/Script/Engine.SceneComponent',
               {'InSocketName': bone, 'TransformSpace': 'RTS_World'})
        p.wire('mesh.HeadMesh', f'socket{i}.self')
        for j, vertex in enumerate(vertices):
            id = f'v{i}{j}'
            p.call(id, 'TransformLocation', defaults={'Location': ','.join(map(str, vertex))})
            p.wire(f'socket{i}.ReturnValue', id+'.T')
            p.call('consider'+id, 'ConsiderSurfacePlanePoint', BP)
            p.wire('self.self', 'consider'+id+'.self')
            p.wire(id+'.ReturnValue', 'consider'+id+'.Candidate')
            p.wire(previous, 'consider'+id+'.execute')
            previous = 'consider'+id+'.then'
    p.setter('valid', 'bProbePlaneValid', True)
    p.wire(previous, 'valid.execute')
    assert len(p.ops) <= 200, len(p.ops)
    return p.ops


def integration(reset_gap_guid, measure_gap_guid):
    """Append calls to inspected, previously unwired tail exec pins."""
    ops = []
    for graph, id, function, tail in [('ResetSurfaceProbe', 'resetplane', 'ResetSurfacePlane', reset_gap_guid),
                                      ('MeasureSurfaceProbe', 'evalplane', 'EvaluateSurfacePlane', measure_gap_guid)]:
        ops.extend([
            dict(edit='create_node', graphName=graph, id=id+'self', nodeType='Self'),
            dict(edit='create_node', graphName=graph, id=id, nodeType='CallFunction', memberName=function, memberClass=BP),
            dict(edit='connect_pins', **{'from': '$'+id+'self.self', 'to': '$'+id+'.self'}),
            dict(edit='connect_pins', fromNodeId=tail, fromPinName='then', **{'to': '$'+id+'.execute'}),
        ])
    return ops


if __name__ == '__main__':
    print(json.dumps({'helpers': helpers(), 'evaluate': evaluate()}))
