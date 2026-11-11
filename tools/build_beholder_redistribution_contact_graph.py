"""Opt-in fresh contact checks for the separate redistribution test asset.

Non-idempotent extension of installed base graphs, not body integration.
Contact ownership ends at Release; complete state 2 remains passive for now.
"""
import json

from build_beholder_plane_graph import Plan
from build_beholder_contact_watch_graph import function
from build_beholder_redistribution_graph import BP, call
from build_beholder_surface_graph import BP as LEG


def members():
    return [dict(edit='add_variable', variableName=n, variableType=t, isPublic=public,
                 defaultValue=value, category='Experimental Redistribution Contact') for n, t, value, public in (
        ('bRedistributionContactOwned', 'bool', False, False),
        ('RedistributionContactPoint', 'Vector', '0,0,0', False),
        ('RedistributionContactNormal', 'Vector', '0,0,0', False),
        ('RedistributionContactPlaneZ', 'float', 0, False),
        ('RedistributionContactSamples', 'int', 0, True))]


def sample():
    p = Plan('SampleRedistributionContact')
    function(p, 'entry', [('EnforceAnchor', 'bool')], [('Valid', 'bool')])
    p.node('self', 'Self')
    p.node('reject', 'FunctionResult', pinDefaults={'Valid': False})
    p.getter('count', 'RedistributionContactSamples')
    p.call('plus', 'Add_IntInt', defaults={'B': 1})
    p.wire('count.RedistributionContactSamples', 'plus.A')
    p.setter('countstore', 'RedistributionContactSamples')
    p.wire('plus.ReturnValue', 'countstore.RedistributionContactSamples')
    p.wire('entry.then', 'countstore.execute')
    p.call('measure', 'MeasureSurfaceProbe', LEG)
    p.wire('self.self', 'measure.self')
    p.wire('countstore.then', 'measure.execute')
    p.getter('point', 'ProbePlanePoint')
    p.getter('normal', 'ProbePlaneNormal')
    p.breakvec('q', 'point.ProbePlanePoint')
    p.breakvec('n', 'normal.ProbePlaneNormal')
    p.node('valid', 'MathExpression', expression='bProbeValid && bProbeHit && bProbePlaneValid && (bProbeInitialOverlap == false) && (abs(ProbePlaneClearance) <= 0.050000) && (abs(ProbeGap) <= 0.050000) && (nz > 0.999990) && (nz <= 1.000010)')
    p.wire('n.Z', 'valid.nz')
    p.node('validbranch', 'Branch')
    p.wire('measure.then', 'validbranch.execute')
    p.wire('valid.ReturnValue', 'validbranch.Condition')
    p.wire('validbranch.else', 'reject.execute')
    for id, sign in [('start', '+'), ('end', '-')]:
        p.node(id, 'MathExpression', expression=f'VECT(qx,qy,qz{sign}2.000000)')
        for axis in 'XYZ':
            p.wire('q.'+axis, id+'.q'+axis.lower())
    p.getter('ignored', 'ProbeIgnoreActors')
    p.call('trace', 'LineTraceSingle', '/Script/Engine.KismetSystemLibrary',
           {'TraceChannel': 'TraceTypeQuery1', 'bTraceComplex': True, 'DrawDebugType': 'None', 'bIgnoreSelf': True})
    p.wire('start.ReturnValue', 'trace.Start')
    p.wire('end.ReturnValue', 'trace.End')
    p.wire('ignored.ProbeIgnoreActors', 'trace.ActorsToIgnore')
    p.wire('validbranch.then', 'trace.execute')
    p.call('hit', 'BreakHitResult', '/Script/Engine.GameplayStatics')
    p.wire('trace.OutHit', 'hit.Hit')
    p.call('distance', 'Vector_Distance')
    p.wire('point.ProbePlanePoint', 'distance.V1')
    p.wire('hit.ImpactPoint', 'distance.V2')
    p.breakvec('hn', 'hit.ImpactNormal')
    p.node('endpoint', 'MathExpression', expression='(distanceCm >= 0.000000) && (distanceCm <= 0.050000) && (normalZ > 0.999990) && (normalZ <= 1.000010)')
    p.wire('distance.ReturnValue', 'endpoint.distanceCm')
    p.wire('hn.Z', 'endpoint.normalZ')
    p.call('nonoverlap', 'Not_PreBool')
    p.wire('hit.bInitialOverlap', 'nonoverlap.A')
    p.call('traceok', 'BooleanAND')
    p.wire('trace.ReturnValue', 'traceok.A')
    p.wire('nonoverlap.ReturnValue', 'traceok.B')
    p.call('endpointok', 'BooleanAND')
    p.wire('traceok.ReturnValue', 'endpointok.A')
    p.wire('endpoint.ReturnValue', 'endpointok.B')
    p.node('endpointbranch', 'Branch')
    p.wire('trace.then', 'endpointbranch.execute')
    p.wire('endpointok.ReturnValue', 'endpointbranch.Condition')
    p.wire('endpointbranch.else', 'reject.execute')
    p.getter('anchor', 'RedistributionContactPoint')
    p.getter('cachednormal', 'RedistributionContactNormal')
    for id, a, b in [('drift', 'point.ProbePlanePoint', 'anchor.RedistributionContactPoint'),
                      ('normaldiff', 'normal.ProbePlaneNormal', 'cachednormal.RedistributionContactNormal')]:
        p.call(id, 'Vector_Distance')
        p.wire(a, id+'.V1')
        p.wire(b, id+'.V2')
    p.getter('impact', 'ProbeImpactPoint')
    p.breakvec('impactxyz', 'impact.ProbeImpactPoint')
    p.node('anchorok', 'MathExpression', expression='(driftCm >= 0.000000) && (driftCm <= 0.010000) && (normalDifference >= 0.000000) && (normalDifference <= 0.000100) && (abs(planeZ-RedistributionContactPlaneZ) <= 0.050000)')
    p.wire('drift.ReturnValue', 'anchorok.driftCm')
    p.wire('normaldiff.ReturnValue', 'anchorok.normalDifference')
    p.wire('impactxyz.Z', 'anchorok.planeZ')
    p.call('notrequired', 'Not_PreBool')
    p.wire('entry.EnforceAnchor', 'notrequired.A')
    p.call('accepted', 'BooleanOR')
    p.wire('notrequired.ReturnValue', 'accepted.A')
    p.wire('anchorok.ReturnValue', 'accepted.B')
    p.wire('accepted.ReturnValue', 'entry_return.Valid')
    p.wire('endpointbranch.then', 'entry_return.execute')
    return p.ops


def owned():
    p = Plan('CheckOwnedRedistributionContact')
    function(p, 'entry', outputs=[('Valid', 'bool')])
    p.node('self', 'Self')
    p.node('notowned', 'FunctionResult', pinDefaults={'Valid': True})
    p.getter('owned', 'bRedistributionContactOwned')
    p.node('branch', 'Branch')
    p.wire('entry.then', 'branch.execute')
    p.wire('owned.bRedistributionContactOwned', 'branch.Condition')
    p.wire('branch.else', 'notowned.execute')
    call(p, 'sample', 'SampleRedistributionContact', {'EnforceAnchor': True})
    p.wire('branch.then', 'sample.execute')
    p.wire('sample.Valid', 'entry_return.Valid')
    p.wire('sample.then', 'entry_return.execute')
    return p.ops


def request():
    p = Plan('TryExperimentalContactRedistribution')
    function(p, 'entry', [('DurationSeconds', 'float')], [('Accepted', 'bool')], public=True)
    p.node('self', 'Self')
    p.node('reject', 'FunctionResult', pinDefaults={'Accepted': False})
    p.node('idle', 'MathExpression', expression='(RedistributionState == 0) && bEnableStageRedistribution')
    p.node('idlebranch', 'Branch')
    p.wire('entry.then', 'idlebranch.execute')
    p.wire('idle.ReturnValue', 'idlebranch.Condition')
    p.wire('idlebranch.else', 'reject.execute')
    call(p, 'sample', 'SampleRedistributionContact', {'EnforceAnchor': False})
    p.wire('idlebranch.then', 'sample.execute')
    p.node('freshbranch', 'Branch')
    p.wire('sample.then', 'freshbranch.execute')
    p.wire('sample.Valid', 'freshbranch.Condition')
    p.wire('freshbranch.else', 'reject.execute')
    call(p, 'start', 'TryExperimentalStageRedistribution')
    p.wire('entry.DurationSeconds', 'start.DurationSeconds')
    p.wire('freshbranch.then', 'start.execute')
    p.node('acceptedbranch', 'Branch')
    p.wire('start.Accepted', 'acceptedbranch.Condition')
    p.wire('start.then', 'acceptedbranch.execute')
    p.wire('acceptedbranch.else', 'reject.execute')
    p.getter('point', 'ProbePlanePoint')
    p.getter('normal', 'ProbePlaneNormal')
    p.getter('impact', 'ProbeImpactPoint')
    p.breakvec('impactxyz', 'impact.ProbeImpactPoint')
    previous = 'acceptedbranch.then'
    for id, name, source, value in [('anchor', 'RedistributionContactPoint', 'point.ProbePlanePoint', None),
                                    ('normalstore', 'RedistributionContactNormal', 'normal.ProbePlaneNormal', None),
                                    ('plane', 'RedistributionContactPlaneZ', 'impactxyz.Z', None),
                                    ('owned', 'bRedistributionContactOwned', None, True)]:
        p.setter(id, name, value)
        if source:
            p.wire(source, id+'.'+name)
        p.wire(previous, id+'.execute')
        previous = id+'.then'
    p.wire(previous, 'entry_return.execute')
    p.ops.append(dict(edit='set_pin_default_value', nodeId='$entry_return', pinName='Accepted', propertyValue=True))
    return p.ops


def integration(ids):
    """Insert checks around the existing synchronous writes; actual GUIDs only."""
    p = Plan('UpdateStageRedistribution')
    call(p, 'contactabort', 'AbortStageRedistribution', {'Reason': 6})
    for prefix, previous, following in [('pre', 'validbranch.then', 'elapsedstore.execute'),
                                         ('post', 'second.then', 'donebranch.execute')]:
        call(p, prefix+'contact', 'CheckOwnedRedistributionContact')
        p.node(prefix+'branch', 'Branch')
        p.wire(previous, prefix+'contact.execute')
        p.wire(prefix+'contact.then', prefix+'branch.execute')
        p.wire(prefix+'contact.Valid', prefix+'branch.Condition')
        p.wire(prefix+'branch.then', following)
        p.wire(prefix+'branch.else', 'contactabort.execute')
    ops = p.ops
    for graph, previous, following in [('TryExperimentalStageRedistribution', 'requestsafe.then', 'extensionstore.execute'),
                                      ('ReleaseStageRedistribution', 'releasestate.then', 'releasereturn.execute')]:
        p = Plan(graph)
        p.setter('clear'+graph, 'bRedistributionContactOwned', False)
        p.wire(previous, 'clear'+graph+'.execute')
        p.wire('clear'+graph+'.then', following)
        ops += p.ops
    result = []
    for source in ops:
        op = dict(source)
        for key in ('from', 'to'):
            value = op.get(key, '')
            alias = value[1:].split('.')[0] if value.startswith('$') else ''
            if alias in ids:
                op[key+'NodeId'], op[key+'PinName'] = ids[alias], value.split('.', 1)[1]
                del op[key]
        if op.get('from') == '$self.self':
            op['fromNodeId'], op['fromPinName'] = ids['self'], 'self'
            del op['from']
        result.append(op)
    return result


if __name__ == '__main__':
    plans = dict(members=members(), sample=sample(), owned=owned(), request=request())
    assert all(len(ops) <= 200 for ops in plans.values())
    print(json.dumps(plans))
