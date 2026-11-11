"""Generate EngineWire graph operations; applying them requires editor MCP.

Only builds the new MeasureSurfaceProbe function. ResetSurfaceProbe,
ConsiderSurfacePoint and IsSurfacePoseCoherent must already exist. Callers
must inspect the target and never apply twice to an existing function.
"""
import json
from pathlib import Path

BP = '/Game/BeholderPrototype/Body/BP_BeholderBodyLeg'
HEAD = '/Game/BeholderPrototype/BP_Lapa5_Head'
GRAPH = 'MeasureSurfaceProbe'
CONFIG_EXPRESSION = ('(ProbeTraceDistance > 0.000001) && (ProbeTraceDistance <= 100000.000000) '
                     '&& (ProbeTraceLift >= 0.000000) && (ProbeTraceLift <= 100.000000) '
                     '&& (max(abs(scaleX), max(abs(scaleY), abs(scaleZ))) > 0.000001) '
                     '&& (abs(scaleX) <= 10000.000000) && (abs(scaleY) <= 10000.000000) '
                     '&& (abs(scaleZ) <= 10000.000000)')


def operations():
    ops = []

    def node(id, node_type, **extra):
        ops.append(dict(edit='create_node', graphName=GRAPH, id=id, nodeType=node_type, **extra))

    def wire(source, target):
        ops.append(dict(edit='connect_pins', **{'from': '$'+source, 'to': '$'+target}))

    def call(id, name, cls='KismetMathLibrary', defaults=None):
        node(id, 'CallFunction', memberName=name, memberClass=cls,
             **({'pinDefaults': defaults} if defaults else {}))

    def setvar(id, name, value=None):
        node(id, 'VariableSet', memberName=name,
             **({'pinDefaults': {name: value}} if value is not None else {}))

    def valid(id, value, previous):
        node(id, 'K2Node_IsValid')
        wire(value, id+'.InputObject')
        wire(previous, id+'.exec')

    ops.append(dict(edit='add_function', id='entry', functionName=GRAPH, pure=False, isPublic=True))
    node('self', 'Self')
    call('reset', 'ResetSurfaceProbe', BP)
    wire('self.self', 'reset.self')
    wire('entry.then', 'reset.execute')
    call('coherence', 'IsSurfacePoseCoherent', BP)
    # Same-class call uses its implicit self; keep this creation batch at 200.
    wire('reset.then', 'coherence.execute')
    node('coherentbranch', 'Branch')
    wire('coherence.then', 'coherentbranch.execute')
    wire('coherence.Coherent', 'coherentbranch.Condition')
    node('hm', 'VariableGet', memberName='HeadModule')
    valid('hmvalid', 'hm.HeadModule', 'coherentbranch.then')
    node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    wire('hm.HeadModule', 'child.self')
    node('cast', 'Cast', targetClass=HEAD)
    wire('child.ChildActor', 'cast.Object')
    wire('hmvalid.Is Valid', 'cast.execute')
    node('mesh', 'VariableGet', memberName='HeadMesh', memberClass=HEAD)
    wire('cast.AsBP Lapa 5 Head', 'mesh.self')
    valid('meshvalid', 'mesh.HeadMesh', 'cast.then')
    call('parent', 'GetParentActor', '/Script/Engine.Actor')
    valid('parentvalid', 'parent.ReturnValue', 'meshvalid.Is Valid')
    node('config', 'MathExpression', expression=CONFIG_EXPRESSION)
    node('cfgbranch', 'Branch')
    wire('config.ReturnValue', 'cfgbranch.Condition')
    wire('parentvalid.Is Valid', 'cfgbranch.execute')
    bones = json.loads((Path(__file__).parent/'fixtures/lapa5_claw_vertices.json').read_text())['bones']
    for i, bone in enumerate(bones):
        call('exists'+str(i), 'DoesSocketExist', '/Script/Engine.SceneComponent', {'InSocketName': bone})
        wire('mesh.HeadMesh', f'exists{i}.self')
    call('and1', 'BooleanAND')
    call('and2', 'BooleanAND')
    for source, target in [('exists0.ReturnValue', 'and1.A'), ('exists1.ReturnValue', 'and1.B'),
                           ('and1.ReturnValue', 'and2.A'), ('exists2.ReturnValue', 'and2.B')]:
        wire(source, target)
    node('sockets', 'Branch')
    wire('and2.ReturnValue', 'sockets.Condition')
    wire('cfgbranch.then', 'sockets.execute')
    call('loc', 'K2_GetActorLocation', '/Script/Engine.Actor')
    call('scale', 'GetActorScale3D', '/Script/Engine.Actor')
    wire('cast.AsBP Lapa 5 Head', 'loc.self')
    wire('cast.AsBP Lapa 5 Head', 'scale.self')
    call('xyz', 'BreakVector')
    call('sxyz', 'BreakVector')
    wire('loc.ReturnValue', 'xyz.InVec')
    wire('scale.ReturnValue', 'sxyz.InVec')
    for axis in 'XYZ':
        wire('sxyz.'+axis, 'config.scale'+axis)
    node('seed', 'MathExpression', expression='VECT(cx, cy, cz - 27.000000 * max(abs(sx), max(abs(sy), abs(sz))))')
    for axis in 'XYZ':
        wire('xyz.'+axis, 'seed.c'+axis.lower())
        wire('sxyz.'+axis, 'seed.s'+axis.lower())
    setvar('setlow', 'ProbeLowest')
    wire('seed.ReturnValue', 'setlow.ProbeLowest')
    wire('sockets.then', 'setlow.execute')
    previous = 'setlow.then'
    for i, (bone, vertices) in enumerate(bones.items()):
        call(f'socket{i}', 'GetSocketTransform', '/Script/Engine.SceneComponent',
             {'InSocketName': bone, 'TransformSpace': 'RTS_World'})
        wire('mesh.HeadMesh', f'socket{i}.self')
        for j, vertex in enumerate(vertices):
            id = f'p{i}{j}'
            call(id, 'TransformLocation', defaults={'Location': ','.join(map(str, vertex))})
            wire(f'socket{i}.ReturnValue', id+'.T')
            call('consider'+id, 'ConsiderSurfacePoint', BP)
            wire('self.self', 'consider'+id+'.self')
            wire(id+'.ReturnValue', 'consider'+id+'.Candidate')
            wire(previous, 'consider'+id+'.execute')
            previous = 'consider'+id+'.then'
    call('children', 'GetAllChildActors', '/Script/Engine.Actor', {'bIncludeDescendants': True})
    wire('parent.ReturnValue', 'children.self')
    setvar('setignore', 'ProbeIgnoreActors')
    wire('children.ChildActors', 'setignore.ProbeIgnoreActors')
    wire(previous, 'setignore.execute')
    call('addparent', 'Array_AddUnique', '/Script/Engine.KismetArrayLibrary')
    wire('setignore.Output_Get', 'addparent.TargetArray')
    wire('parent.ReturnValue', 'addparent.NewItem')
    wire('setignore.then', 'addparent.execute')
    setvar('valid', 'bProbeValid', True)
    wire('addparent.then', 'valid.execute')
    call('lowxyz', 'BreakVector')
    # VariableSet.Output_Get reads the property after the sequential point
    # helpers, not a repeated evaluation of the original seed expression.
    wire('setlow.Output_Get', 'lowxyz.InVec')
    node('start', 'MathExpression', expression='VECT(px, py, pz + ProbeTraceLift)')
    node('end', 'MathExpression', expression='VECT(px, py, pz - ProbeTraceDistance)')
    for axis in 'XYZ':
        wire('lowxyz.'+axis, 'start.p'+axis.lower())
        wire('lowxyz.'+axis, 'end.p'+axis.lower())
    call('trace', 'LineTraceSingle', '/Script/Engine.KismetSystemLibrary',
         {'TraceChannel': 'TraceTypeQuery1', 'bTraceComplex': True, 'DrawDebugType': 'None', 'bIgnoreSelf': True})
    for source, target in [('start.ReturnValue', 'trace.Start'), ('end.ReturnValue', 'trace.End'),
                            ('setignore.Output_Get', 'trace.ActorsToIgnore'), ('valid.then', 'trace.execute')]:
        wire(source, target)
    call('hit', 'BreakHitResult', '/Script/Engine.GameplayStatics')
    wire('trace.OutHit', 'hit.Hit')
    node('overlap', 'Branch')
    wire('hit.bInitialOverlap', 'overlap.Condition')
    wire('trace.then', 'overlap.execute')
    setvar('invalid', 'bProbeValid', False)
    setvar('overlapflag', 'bProbeInitialOverlap', True)
    wire('overlap.then', 'invalid.execute')
    wire('invalid.then', 'overlapflag.execute')
    node('hitbranch', 'Branch')
    wire('trace.ReturnValue', 'hitbranch.Condition')
    wire('overlap.else', 'hitbranch.execute')
    setvar('sethit', 'bProbeHit', True)
    wire('hitbranch.then', 'sethit.execute')
    setvar('impact', 'ProbeImpactPoint')
    wire('hit.ImpactPoint', 'impact.ProbeImpactPoint')
    wire('sethit.then', 'impact.execute')
    setvar('normal', 'ProbeImpactNormal')
    wire('hit.ImpactNormal', 'normal.ProbeImpactNormal')
    wire('impact.then', 'normal.execute')
    call('impactxyz', 'BreakVector')
    wire('hit.ImpactPoint', 'impactxyz.InVec')
    node('gap', 'MathExpression', expression='lowZ - groundZ')
    wire('lowxyz.Z', 'gap.lowZ')
    wire('impactxyz.Z', 'gap.groundZ')
    setvar('setgap', 'ProbeGap')
    wire('gap.ReturnValue', 'setgap.ProbeGap')
    wire('normal.then', 'setgap.execute')
    assert len(ops) <= 200
    return ops


if __name__ == '__main__':
    print(json.dumps(operations()))
