"""Explicit runtime four-contact XY diagnostic; no commands or physics.

Already-created members must not be recreated. Ordered quadrilateral only,
not an arbitrary eight-point convex hull. Reference is supplied, not a COM.
"""
import json

from build_beholder_body_probe_graph import BODY
from build_beholder_contact_request_graph import INDICES, FOOTPRINT_INDICES
from build_beholder_contact_watch_graph import function, own_call
from build_beholder_plane_graph import Plan
from build_beholder_surface_graph import BP as LEG

OUTPUTS = [('Valid', 'bool'), ('Inside', 'bool'), ('PassesMargin', 'bool'),
           ('MarginCm', 'float'), ('AreaCm2', 'float')]
ZERO = {'Valid': False, 'Inside': False, 'PassesMargin': False, 'MarginCm': 0, 'AreaCm2': 0}


def cross(a, b, c):
    return f'(({b}x-{a}x)*({c}y-{a}y)-({b}y-{a}y)*({c}x-{a}x))'


def kernel():
    p = Plan('CalculateOrderedFourFootprint')
    function(p, 'entry', [(f'Point{i}', 'Vector') for i in range(4)]+
             [('ReferenceWorld', 'Vector'), ('MinimumMargin', 'float')], OUTPUTS, public=True)
    p.node('reject', 'FunctionResult', pinDefaults=ZERO)
    previous = 'entry.then'
    for i, name in enumerate(['ReferenceWorld']+[f'Point{i}' for i in range(4)]):
        p.call(f'nan{i}', 'Vector_IsNAN')
        p.wire('entry.'+name, f'nan{i}.A')
        p.node(f'nanbranch{i}', 'Branch')
        p.wire(f'nan{i}.ReturnValue', f'nanbranch{i}.Condition')
        p.wire(previous, f'nanbranch{i}.execute')
        p.wire(f'nanbranch{i}.then', 'reject.execute')
        previous = f'nanbranch{i}.else'
    p.breakvec('r', 'entry.ReferenceWorld')
    for i, prefix in enumerate('abcd'):
        p.breakvec('world'+prefix, f'entry.Point{i}')
        p.node('local'+prefix, 'MathExpression', expression='VECT(px-rx, py-ry, pz-rz)')
        for axis in 'XYZ':
            p.wire('world'+prefix+'.'+axis, 'local'+prefix+'.p'+axis.lower())
            p.wire('r.'+axis, 'local'+prefix+'.r'+axis.lower())
        p.breakvec(prefix, 'local'+prefix+'.ReturnValue')
    # Bounded comparisons also reject NaN/Inf before division is reachable.
    bounds = ['(required >= 0.000000)', '(required <= 1000000.000000)']
    bounds += [f'(({prefix}{axis} >= -10000000.000000) && ({prefix}{axis} <= 10000000.000000))'
               for prefix in 'rabcd' for axis in 'xyz']
    p.node('bounds', 'MathExpression', expression=' && '.join(bounds))
    p.wire('entry.MinimumMargin', 'bounds.required')
    for prefix in 'rabcd':
        for axis in 'XYZ':
            p.wire(prefix+'.'+axis, 'bounds.'+prefix+axis.lower())
    p.node('boundsbranch', 'Branch')
    p.wire(previous, 'boundsbranch.execute')
    p.wire('bounds.ReturnValue', 'boundsbranch.Condition')
    p.wire('boundsbranch.else', 'reject.execute')
    turns = [cross(*seq) for seq in ('abc', 'bcd', 'cda', 'dab')]
    positive = ' && '.join(f'({t} > 0.000001)' for t in turns)
    negative = ' && '.join(f'({t} < -0.000001)' for t in turns)
    area2 = f'({cross("a", "b", "c")}+{cross("a", "c", "d")})'
    edge_sq = [f'(({b}x-{a}x)*({b}x-{a}x)+({b}y-{a}y)*({b}y-{a}y))' for a, b in ('ab', 'bc', 'cd', 'da')]
    geometry = f'(({positive}) || ({negative})) && (abs({area2}) > 0.000002)'
    geometry += ' && '+' && '.join(f'({e} > 0.000000000001)' for e in edge_sq)
    p.node('geometry', 'MathExpression', expression=geometry)
    p.node('area', 'MathExpression', expression=f'abs({area2})/2.000000')
    edges = [f'(({a}x*{b}y-{a}y*{b}x)*{area2}/abs({area2})/sqrt({e}))'
             for (a, b), e in zip(('ab', 'bc', 'cd', 'da'), edge_sq)]
    p.node('margin', 'MathExpression', expression=f'min(min({edges[0]},{edges[1]}),min({edges[2]},{edges[3]}))')
    for id in ('geometry', 'area', 'margin'):
        for prefix in 'abcd':
            for axis in 'XY':
                p.wire(prefix+'.'+axis, id+'.'+prefix+axis.lower())
    p.node('geometrybranch', 'Branch')
    p.wire('boundsbranch.then', 'geometrybranch.execute')
    p.wire('geometry.ReturnValue', 'geometrybranch.Condition')
    p.wire('geometrybranch.else', 'reject.execute')
    p.wire('geometrybranch.then', 'entry_return.execute')
    p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return', pinName='Valid', propertyValue=True))
    p.wire('margin.ReturnValue', 'entry_return.MarginCm')
    p.wire('area.ReturnValue', 'entry_return.AreaCm2')
    p.node('inside', 'MathExpression', expression='margin >= 0.000000')
    p.node('passes', 'MathExpression', expression='margin > required')
    p.wire('margin.ReturnValue', 'inside.margin')
    p.wire('margin.ReturnValue', 'passes.margin')
    p.wire('entry.MinimumMargin', 'passes.required')
    p.wire('inside.ReturnValue', 'entry_return.Inside')
    p.wire('passes.ReturnValue', 'entry_return.PassesMargin')
    return p.ops


def point():
    p = Plan('ReadExperimentalFootprintPoint')
    function(p, 'entry', [('Component', 'ChildActorComponent')], [('Ready', 'bool'), ('Point', 'Vector')])
    p.node('self', 'Self')
    p.node('reject', 'FunctionResult', pinDefaults={'Ready': False, 'Point': '0,0,0'})
    p.valid('valid', 'entry.Component', 'entry.then')
    p.wire('valid.Is Not Valid', 'reject.execute')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('entry.Component', 'child.self')
    p.node('cast', 'Cast', targetClass=LEG)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('valid.Is Valid', 'cast.execute')
    p.wire('cast.CastFailed', 'reject.execute')
    fields = [('validflag', 'bProbeValid'), ('hitflag', 'bProbeHit'), ('planeflag', 'bProbePlaneValid'),
              ('normal', 'ProbePlaneNormal'), ('clearance', 'ProbePlaneClearance'), ('gap', 'ProbeGap'),
              ('point', 'ProbePlanePoint'), ('ignore', 'ProbeIgnoreActors')]
    for id, name in fields:
        p.node(id, 'VariableGet', memberName=name, memberClass=LEG)
        p.wire('cast.AsBP Beholder Body Leg', id+'.self')
    p.breakvec('n', 'normal.ProbePlaneNormal')
    own_call(p, 'classify', 'ClassifyBodySurfaceCandidate')
    for a, b in [('validflag.bProbeValid', 'Valid'), ('hitflag.bProbeHit', 'Hit'),
                  ('planeflag.bProbePlaneValid', 'PlaneValid'), ('n.Z', 'NormalZ'),
                  ('clearance.ProbePlaneClearance', 'Clearance'), ('gap.ProbeGap', 'VerticalGap')]:
        p.wire(a, 'classify.'+b)
    p.wire('cast.then', 'classify.execute')
    p.node('candidate', 'Branch')
    p.wire('classify.Candidate', 'candidate.Condition')
    p.wire('classify.then', 'candidate.execute')
    p.wire('candidate.else', 'reject.execute')
    p.breakvec('q', 'point.ProbePlanePoint')
    for id, delta in [('start', '+ 2.000000'), ('end', '- 2.000000')]:
        p.node(id, 'MathExpression', expression=f'VECT(px, py, pz {delta})')
        for axis in 'XYZ':
            p.wire('q.'+axis, id+'.p'+axis.lower())
    p.call('trace', 'LineTraceSingle', '/Script/Engine.KismetSystemLibrary',
           {'TraceChannel': 'TraceTypeQuery1', 'bTraceComplex': True, 'DrawDebugType': 'None', 'bIgnoreSelf': True})
    for a, b in [('start.ReturnValue', 'trace.Start'), ('end.ReturnValue', 'trace.End'),
                  ('ignore.ProbeIgnoreActors', 'trace.ActorsToIgnore'), ('candidate.then', 'trace.execute')]:
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
    p.node('onface', 'MathExpression', expression='(abs(hx-qx) <= 0.050000) && (abs(hy-qy) <= 0.050000) && (abs(hz-qz) <= 0.050000) && (nz > 0.999990)')
    for prefix in 'hq':
        for axis in 'XYZ':
            p.wire(prefix+'.'+axis, 'onface.'+prefix+axis.lower())
    p.wire('hn.Z', 'onface.nz')
    p.node('facebranch', 'Branch')
    p.wire('onface.ReturnValue', 'facebranch.Condition')
    p.wire('overlap.else', 'facebranch.execute')
    p.wire('facebranch.else', 'reject.execute')
    p.wire('facebranch.then', 'entry_return.execute')
    p.wire('point.ProbePlanePoint', 'entry_return.Point')
    p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return', pinName='Ready', propertyValue=True))
    return p.ops


def evaluate():
    p = Plan('EvaluateExperimentalFourFootprint')
    function(p, 'entry', [('ReferenceWorld', 'Vector'), ('MinimumMargin', 'float')], OUTPUTS, public=True)
    p.node('self', 'Self')
    p.node('reject', 'FunctionResult', pinDefaults=ZERO)
    own_call(p, 'sample', 'UpdateBodySurfaceProbes')
    p.wire('entry.then', 'sample.execute')
    p.node('complete', 'MathExpression', expression='bBodyProbeSettingsValid && (BodyProbeMeasuredCount == 8) && (BodySupportCandidateCount == 4)')
    p.node('completebranch', 'Branch')
    p.wire('sample.then', 'completebranch.execute')
    p.wire('complete.ReturnValue', 'completebranch.Condition')
    p.wire('completebranch.else', 'reject.execute')
    previous = 'completebranch.then'
    for i in INDICES:
        p.getter(f'leg{i}', f'Leg{i}')
        own_call(p, f'point{i}', 'ReadExperimentalFootprintPoint')
        p.wire(f'leg{i}.Leg{i}', f'point{i}.Component')
        p.wire(previous, f'point{i}.execute')
        p.node(f'ready{i}', 'Branch')
        p.wire(f'point{i}.then', f'ready{i}.execute')
        p.wire(f'point{i}.Ready', f'ready{i}.Condition')
        p.wire(f'ready{i}.else', 'reject.execute')
        previous = f'ready{i}.then'
        p.breakvec(f'p{i}', f'point{i}.Point')
    p.node('level', 'MathExpression', expression='(abs(z0-z2) <= 0.050000) && (abs(z0-z4) <= 0.050000) && (abs(z0-z6) <= 0.050000)')
    for i in INDICES:
        p.wire(f'p{i}.Z', f'level.z{i}')
    p.node('levelbranch', 'Branch')
    p.wire(previous, 'levelbranch.execute')
    p.wire('level.ReturnValue', 'levelbranch.Condition')
    p.wire('levelbranch.else', 'reject.execute')
    own_call(p, 'calculate', 'CalculateOrderedFourFootprint')
    for rank, i in enumerate(FOOTPRINT_INDICES):
        p.wire(f'point{i}.Point', f'calculate.Point{rank}')
    for name in ('ReferenceWorld', 'MinimumMargin'):
        p.wire('entry.'+name, 'calculate.'+name)
    p.wire('levelbranch.then', 'calculate.execute')
    p.wire('calculate.then', 'entry_return.execute')
    for name, _ in OUTPUTS:
        p.wire('calculate.'+name, 'entry_return.'+name)
    return p.ops


if __name__ == '__main__':
    plans = dict(kernel=kernel(), point=point(), evaluate=evaluate())
    assert all(len(ops) <= 200 for ops in plans.values())
    print(json.dumps(plans))
