"""Plans for explicit body-wide sampling and near-surface candidate selection.

Inspect before applying: these plans add new members, not idempotent imports.
They never move the body or command a limb's extension.
"""
import json

from beholder_support_candidate import MIN_NORMAL_Z, MAX_GAP_CM, PENETRATION_TOLERANCE_CM
from build_beholder_plane_graph import Plan
from build_beholder_surface_graph import BP as LEG

BODY = '/Game/BeholderPrototype/Body/BP_BeholderBody_Test'
ARRAYS = [
    ('BodyProbeValid', 'bool', 'bProbeValid'),
    ('BodyProbeHit', 'bool', 'bProbeHit'),
    ('BodyProbePlaneValid', 'bool', 'bProbePlaneValid'),
    ('BodyProbeImpactPoints', 'Vector', 'ProbeImpactPoint'),
    ('BodyProbeNormals', 'Vector', 'ProbePlaneNormal'),
    ('BodyProbePlaneClearances', 'float', 'ProbePlaneClearance'),
    ('BodyProbeGaps', 'float', 'ProbeGap'),
    ('BodySupportCandidates', 'bool', None),
]
SETTINGS_EXPRESSION = ('(BodySupportMinNormalZ >= 0.000000) && (BodySupportMinNormalZ <= 1.000000) '
                       '&& (BodySupportMaxGapCm >= 0.000000) && (BodySupportMaxGapCm <= 100.000000) '
                       '&& (BodySupportPenetrationToleranceCm >= 0.000000) '
                       '&& (BodySupportPenetrationToleranceCm <= 1.000000)')
CANDIDATE_EXPRESSION = (SETTINGS_EXPRESSION + ' && (normalZ >= BodySupportMinNormalZ) '
                        '&& (normalZ <= 1.000010) '
                        '&& (clearance >= -BodySupportPenetrationToleranceCm) '
                        '&& (clearance <= BodySupportMaxGapCm) '
                        '&& (verticalGap >= -BodySupportPenetrationToleranceCm) '
                        '&& (verticalGap <= BodySupportMaxGapCm)')


def reset():
    p = Plan('ResetBodySurfaceProbes')
    variables = [(name, f'Array<{type}>', None) for name, type, _ in ARRAYS]
    variables += [('BodyProbeMeasuredCount', 'int', 0), ('BodySurfaceHitCount', 'int', 0),
                  ('BodySupportCandidateCount', 'int', 0), ('bBodyProbeSettingsValid', 'bool', False),
                  ('BodySupportMinNormalZ', 'float', MIN_NORMAL_Z),
                  ('BodySupportMaxGapCm', 'float', MAX_GAP_CM),
                  ('BodySupportPenetrationToleranceCm', 'float', PENETRATION_TOLERANCE_CM)]
    for name, type, value in variables:
        p.ops.append(dict(edit='add_variable', variableName=name, variableType=type, isPublic=True,
                          category='Body Surface Probe', **({'defaultValue': value} if value is not None else {})))
    p.function('resetentry')
    previous = 'resetentry.then'
    for i, name in enumerate(('BodyProbeMeasuredCount', 'BodySurfaceHitCount', 'BodySupportCandidateCount', 'bBodyProbeSettingsValid')):
        id = f'counter{i}'
        p.setter(id, name, False if name.startswith('b') else 0)
        p.wire(previous, id+'.execute')
        previous = id+'.then'
    for i, (name, _, _) in enumerate(ARRAYS):
        p.getter(f'array{i}', name)
        p.call(f'clear{i}', 'Array_Clear', '/Script/Engine.KismetArrayLibrary')
        p.call(f'resize{i}', 'Array_Resize', '/Script/Engine.KismetArrayLibrary', {'Size': 8})
        p.wire(f'array{i}.{name}', f'clear{i}.TargetArray')
        p.wire(f'array{i}.{name}', f'resize{i}.TargetArray')
        p.wire(previous, f'clear{i}.execute')
        p.wire(f'clear{i}.then', f'resize{i}.execute')
        previous = f'resize{i}.then'
    return p.ops


def classify():
    p = Plan('ClassifyBodySurfaceCandidate')
    p.ops.append(dict(edit='add_function', id='classentry', functionName=p.graph, pure=False, isPublic=True,
                      inputs=[{'name': name, 'type': type} for name, type in
                              [('Valid', 'bool'), ('Hit', 'bool'), ('PlaneValid', 'bool'),
                               ('NormalZ', 'float'), ('Clearance', 'float'), ('VerticalGap', 'float')]],
                      outputs=[{'name': 'Candidate', 'type': 'bool'}]))
    p.node('conditions', 'MathExpression', expression=CANDIDATE_EXPRESSION)
    for param, pin in [('NormalZ', 'normalZ'), ('Clearance', 'clearance'), ('VerticalGap', 'verticalGap')]:
        p.wire('classentry.'+param, 'conditions.'+pin)
    for id in ('flags1', 'flags2', 'decision'):
        p.call(id, 'BooleanAND')
    for a, b in [('classentry.Valid', 'flags1.A'), ('classentry.Hit', 'flags1.B'),
                  ('flags1.ReturnValue', 'flags2.A'), ('classentry.PlaneValid', 'flags2.B'),
                  ('flags2.ReturnValue', 'decision.A'), ('conditions.ReturnValue', 'decision.B'),
                  ('decision.ReturnValue', 'classentry_return.Candidate'),
                  ('classentry.then', 'classentry_return.execute')]:
        p.wire(a, b)
    return p.ops


def sample():
    p = Plan('SampleBodySurfaceLeg')
    p.function('sampleentry', [{'name': 'Component', 'type': 'ChildActorComponent'}, {'name': 'Index', 'type': 'int'}])
    p.node('self', 'Self')
    p.node('indexok', 'MathExpression', expression='(legIndex >= 0) && (legIndex < 8) && bBodyProbeSettingsValid')
    p.wire('sampleentry.Index', 'indexok.legIndex')
    p.node('indexbranch', 'Branch')
    p.wire('indexok.ReturnValue', 'indexbranch.Condition')
    p.wire('sampleentry.then', 'indexbranch.execute')
    p.valid('componentvalid', 'sampleentry.Component', 'indexbranch.then')
    p.node('child', 'VariableGet', memberName='ChildActor', memberClass='/Script/Engine.ChildActorComponent')
    p.wire('sampleentry.Component', 'child.self')
    p.node('cast', 'Cast', targetClass=LEG)
    p.wire('child.ChildActor', 'cast.Object')
    p.wire('componentvalid.Is Valid', 'cast.execute')
    p.call('measure', 'MeasureSurfaceProbe', LEG)
    p.wire('cast.AsBP Beholder Body Leg', 'measure.self')
    p.wire('cast.then', 'measure.execute')
    for i, (_, _, source) in enumerate(ARRAYS):
        if source:
            p.node(f'field{i}', 'VariableGet', memberName=source, memberClass=LEG)
            p.wire('cast.AsBP Beholder Body Leg', f'field{i}.self')
    p.breakvec('normalxyz', 'field4.ProbePlaneNormal')
    p.call('classify', 'ClassifyBodySurfaceCandidate', BODY)
    p.wire('self.self', 'classify.self')
    for a, b in [('field0.bProbeValid', 'classify.Valid'), ('field1.bProbeHit', 'classify.Hit'),
                  ('field2.bProbePlaneValid', 'classify.PlaneValid'), ('normalxyz.Z', 'classify.NormalZ'),
                  ('field5.ProbePlaneClearance', 'classify.Clearance'), ('field6.ProbeGap', 'classify.VerticalGap'),
                  ('measure.then', 'classify.execute')]:
        p.wire(a, b)
    previous = 'classify.then'
    for i, (name, _, source) in enumerate(ARRAYS):
        p.getter(f'target{i}', name)
        p.call(f'publish{i}', 'Array_Set', '/Script/Engine.KismetArrayLibrary', {'bSizeToFit': False})
        p.wire(f'target{i}.{name}', f'publish{i}.TargetArray')
        p.wire('sampleentry.Index', f'publish{i}.Index')
        p.wire(f'field{i}.{source}' if source else 'classify.Candidate', f'publish{i}.Item')
        p.wire(previous, f'publish{i}.execute')
        previous = f'publish{i}.then'
    for id, name, flag in [('measured', 'BodyProbeMeasuredCount', None), ('hits', 'BodySurfaceHitCount', 'field1.bProbeHit'),
                          ('candidates', 'BodySupportCandidateCount', 'classify.Candidate')]:
        p.getter('old'+id, name)
        p.call('add'+id, 'Add_IntInt', defaults={'B': 1})
        p.wire('old'+id+'.'+name, 'add'+id+'.A')
        if flag:
            p.call('delta'+id, 'SelectInt', defaults={'A': 1, 'B': 0})
            p.wire(flag, 'delta'+id+'.bPickA')
            p.wire('delta'+id+'.ReturnValue', 'add'+id+'.B')
        p.setter('set'+id, name)
        p.wire('add'+id+'.ReturnValue', 'set'+id+'.'+name)
        p.wire(previous, 'set'+id+'.execute')
        previous = 'set'+id+'.then'
    assert len(p.ops) <= 200, len(p.ops)
    return p.ops


def update():
    p = Plan('UpdateBodySurfaceProbes')
    p.ops.append(dict(edit='add_function', id='updateentry', functionName=p.graph, pure=False, isPublic=True))
    p.node('self', 'Self')
    p.call('reset', 'ResetBodySurfaceProbes', BODY)
    p.wire('self.self', 'reset.self')
    p.wire('updateentry.then', 'reset.execute')
    p.node('config', 'MathExpression', expression=SETTINGS_EXPRESSION)
    p.setter('setconfig', 'bBodyProbeSettingsValid')
    p.wire('config.ReturnValue', 'setconfig.bBodyProbeSettingsValid')
    p.wire('reset.then', 'setconfig.execute')
    p.node('configbranch', 'Branch')
    p.wire('setconfig.Output_Get', 'configbranch.Condition')
    p.wire('setconfig.then', 'configbranch.execute')
    previous = 'configbranch.then'
    for i in range(8):
        p.getter(f'leg{i}', f'Leg{i}')
        p.call(f'sample{i}', 'SampleBodySurfaceLeg', BODY, {'Index': i})
        p.wire('self.self', f'sample{i}.self')
        p.wire(f'leg{i}.Leg{i}', f'sample{i}.Component')
        p.wire(previous, f'sample{i}.execute')
        previous = f'sample{i}.then'
    return p.ops


if __name__ == '__main__':
    print(json.dumps({'reset': reset(), 'classify': classify(), 'sample': sample(), 'update': update()}))
