"""PIE-only coherent-envelope and fail-closed sensor regression.

The mesh offset is a synchronous injected bad pose, restored in finally,
not a claim that the underlying ControlRig teleport issue was repaired.
"""
import json
import math
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve()/'tools'))
import validate_beholder_body as geometry
from lapa5_geometry import claw_vertices_world
from build_beholder_probe_coherence_graph import LOCAL_ENVELOPE_RADIUS


def xyz(v):
    return (v.x, v.y, v.z)


def flag(value):
    return value[0] if isinstance(value, tuple) else value


def run():
    body = geometry.find_body()
    legs = geometry.legs(body)
    leg = legs[0]
    report = dict(passed=False, numericalChecks=0, healthyLegs=0, poisonedSamples=0,
                  restored=False, error=None)
    mesh = None
    original_relative = None
    try:
        center = (1, 2, 3)
        cases = [((1, 2, 3), center, 10, True), ((11, 2, 3), center, 10, True),
                 ((11.005, 2, 3), center, 10, True), ((11.1, 2, 3), center, 10, False),
                 ((1001, 2, 3), center, 10, False)]
        for radius in (0, -1, float('nan'), float('inf'), 1000001):
            cases.append((center, center, radius, False))
        for bad in (float('nan'), float('inf'), -float('inf')):
            cases += [((1, 2, bad), center, 10, False), (center, (1, 2, bad), 10, False)]
        for candidate, c, radius, expected in cases:
            actual = flag(leg.call_method('IsSurfacePointCoherent',
                          (unreal.Vector(*candidate), unreal.Vector(*c), radius)))
            assert actual is expected, (candidate, c, radius, actual)
            report['numericalChecks'] += 1
        for limb in legs:
            assert flag(limb.call_method('IsSurfacePoseCoherent', ()))
            limb.call_method('MeasureSurfaceProbe', ())
            assert limb.get_editor_property('bProbeValid')
            report['healthyLegs'] += 1
        assert leg.get_editor_property('bProbeHit'), 'Seed a successful old hit before the injected failure'
        head = next(c for c in leg.get_components_by_class(unreal.ChildActorComponent)
                    if c.get_name() == 'HeadModule').get_editor_property('child_actor')
        center_before = xyz(head.get_actor_location())
        mesh = head.get_editor_property('HeadMesh')
        original_relative = xyz(mesh.get_editor_property('relative_location'))
        mesh.set_relative_location(unreal.Vector(original_relative[0]+10000,
                                                original_relative[1], original_relative[2]), False, True)
        assert xyz(head.get_actor_location()) == center_before, 'Do not shift the actor reference with the mesh'
        s = head.get_actor_scale3d()
        radius = LOCAL_ENVELOPE_RADIUS*max(abs(v) for v in xyz(s))
        observed = max(math.dist(xyz(v), center_before) for claw in claw_vertices_world(head) for v in claw)
        assert observed > radius+1, 'The injected mesh offset must reach the actual socket transforms'
        report.update(injectedMaximumPointRadiusCm=observed, allowedRadiusCm=radius)
        assert not flag(leg.call_method('IsSurfacePoseCoherent', ()))
        leg.call_method('MeasureSurfaceProbe', ())
        for name in ('bProbeValid', 'bProbeHit', 'bProbePlaneValid', 'bStraightPlanValid', 'bStraightPlaneReachable'):
            assert not leg.get_editor_property(name), name
        for name in ('ProbeLowest', 'ProbeImpactPoint', 'ProbeImpactNormal', 'ProbePlanePoint', 'ProbePlaneNormal'):
            assert xyz(leg.get_editor_property(name)) == (0, 0, 0), name
        for name in ('ProbeGap', 'ProbePlaneClearance', 'StraightTargetExtension'):
            assert leg.get_editor_property(name) == 0, name
        report['poisonedSamples'] += 1
        report['passed'] = True
    except Exception as exc:
        report['error'] = repr(exc)
    finally:
        try:
            if mesh is not None and original_relative is not None:
                mesh.set_relative_location(unreal.Vector(*original_relative), False, True)
                actual_relative = xyz(mesh.get_editor_property('relative_location'))
                assert math.dist(actual_relative, original_relative) < 1e-6, (actual_relative, original_relative)
            body.call_method('UpdateBodySurfaceProbes', ())
            rows = [(l.get_name(), flag(l.call_method('IsSurfacePoseCoherent', ())),
                     l.get_editor_property('bProbeValid')) for l in legs]
            assert all(coherent and valid for _, coherent, valid in rows), rows
            report['restored'] = True
        except Exception as exc:
            report.update(passed=False, error=report['error'] or repr(exc))
    path = Path(unreal.Paths.project_dir())/'Saved/BeholderProbeCoherenceRegression.json'
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    assert report['passed'] and report['restored'], report['error']


if __name__ == '__main__':
    run()
