"""PIE regression of the actual callable Blueprint surface sensor."""
import importlib
import json
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
import inspect_beholder_surface as reference
importlib.reload(reference)
from beholder_surface_probe import head_plane_clearance, lowest_head_point
from lapa5_geometry import claw_vertices_world


def xyz(v):
    return (v.x, v.y, v.z)


def run():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world, 'Start PIE first'
    body = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                if a.get_class().get_name() == 'BP_BeholderBody_Test_C')
    legs = {c.get_name(): c.get_editor_property('child_actor')
            for c in body.get_components_by_class(unreal.ChildActorComponent)
            if c.get_name().startswith('Leg')}
    assert len(legs) == 8
    saved = {name: (leg.get_editor_property('ProbeTraceDistance'), leg.get_editor_property('ProbeTraceLift'))
             for name, leg in legs.items()}
    rotation = body.get_actor_rotation()
    report = {'passed': False, 'samples': 0, 'poses': [], 'error': None,
              'maximumPointErrorCm': 0.0, 'maximumGapErrorCm': 0.0,
              'maximumPlaneErrorCm': 0.0, 'syntheticPlaneSamples': 0,
              'negativePlaneClearances': 0}

    def near(actual, expected):
        error = max(abs(a-b) for a, b in zip(actual, expected))
        report['maximumPointErrorCm'] = max(report['maximumPointErrorCm'], error)
        assert error < 0.002, (actual, expected, error)

    def empty(leg):
        assert not leg.get_editor_property('bProbeHit')
        assert leg.get_editor_property('ProbeGap') == 0
        assert xyz(leg.get_editor_property('ProbeImpactPoint')) == (0, 0, 0)
        assert xyz(leg.get_editor_property('ProbeImpactNormal')) == (0, 0, 0)
        empty_plane(leg)

    def empty_plane(leg):
        assert not leg.get_editor_property('bProbePlaneValid')
        assert leg.get_editor_property('ProbePlaneClearance') == 0
        assert xyz(leg.get_editor_property('ProbePlanePoint')) == (0, 0, 0)
        assert xyz(leg.get_editor_property('ProbePlaneNormal')) == (0, 0, 0)

    def compare_plane(leg, expected):
        assert leg.get_editor_property('bProbePlaneValid')
        error = abs(leg.get_editor_property('ProbePlaneClearance')-expected['normalClearance'])
        report['maximumPlaneErrorCm'] = max(error, report['maximumPlaneErrorCm'])
        assert error < 0.002, (error, expected)
        near(xyz(leg.get_editor_property('ProbePlanePoint')), expected['support']['point'])
        near(xyz(leg.get_editor_property('ProbePlaneNormal')), expected['normal'])

    try:
        for pose in (None, unreal.Rotator(pitch=10, yaw=37, roll=-6)):
            if pose:
                body.set_actor_rotation(pose, False)
            for distance in (1000.0, 1.0, 1000.0):
                expected = reference.inspect(distance=distance, verbose=False)
                for row in expected['legs']:
                    leg = legs[row['leg']]
                    leg.set_editor_property('ProbeTraceDistance', distance)
                    leg.set_editor_property('ProbeTraceLift', 1.0)
                    leg.call_method('MeasureSurfaceProbe', ())
                    report['samples'] += 1
                    assert row['valid'] and leg.get_editor_property('bProbeValid'), row
                    assert not leg.get_editor_property('bProbeInitialOverlap')
                    assert leg.get_editor_property('bProbeHit') == row['hit'], row
                    near(xyz(leg.get_editor_property('ProbeLowest')), row['lowest']['point'])
                    ignored = list(leg.get_editor_property('ProbeIgnoreActors'))
                    assert body in ignored and all(a in ignored for a in body.get_all_child_actors(True))
                    if row['hit']:
                        near(xyz(leg.get_editor_property('ProbeImpactPoint')), row['impactPoint'])
                        near(xyz(leg.get_editor_property('ProbeImpactNormal')), row['impactNormal'])
                        error = abs(leg.get_editor_property('ProbeGap')-row['gap'])
                        report['maximumGapErrorCm'] = max(error, report['maximumGapErrorCm'])
                        assert error < 0.002, (error, row)
                        compare_plane(leg, row['planeEstimate'])
                    else:
                        empty(leg)
                report['poses'].append({'rotated': pose is not None, 'distance': distance,
                                        'hits': sum(r['hit'] for r in expected['legs'])})
        for distance, lift in ((0, 1), (-1, 1), (100001, 1), (1000, -1), (1000, 101),
                               (float('nan'), 1), (float('inf'), 1)):
            for leg in legs.values():
                leg.set_editor_property('ProbeTraceDistance', distance)
                leg.set_editor_property('ProbeTraceLift', lift)
                leg.call_method('MeasureSurfaceProbe', ())
                report['samples'] += 1
                assert not leg.get_editor_property('bProbeValid')
                empty(leg)
                assert xyz(leg.get_editor_property('ProbeLowest')) == (0, 0, 0)
        # Synthetic planes test the actual BP plane evaluator, not the trace.
        # Nothing is spawned or moved: only fields on disposable PIE copies.
        body.set_actor_rotation(rotation, False)
        for leg in legs.values():
            head = next(c for c in leg.get_components_by_class(unreal.ChildActorComponent)
                        if c.get_name() == 'HeadModule').get_editor_property('child_actor')
            center = xyz(head.get_actor_location())
            scale = head.get_actor_scale3d()
            radius = 27*max(abs(scale.x), abs(scale.y), abs(scale.z))
            claws = [[xyz(v) for v in claw] for claw in claw_vertices_world(head)]
            bottom = lowest_head_point(center, radius, claws)['point']
            for normal in ((0, 0, 1.5), (1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1)):
                for drop in (1, 50):
                    point = (bottom[0], bottom[1], bottom[2]-drop)
                    expected_plane = head_plane_clearance(center, radius, claws, point, normal)
                    leg.set_editor_property('bProbeValid', True)
                    leg.set_editor_property('bProbeHit', True)
                    leg.set_editor_property('bProbeInitialOverlap', False)
                    leg.set_editor_property('ProbeImpactPoint', unreal.Vector(*point))
                    leg.set_editor_property('ProbeImpactNormal', unreal.Vector(*normal))
                    leg.call_method('EvaluateSurfacePlane', ())
                    report['syntheticPlaneSamples'] += 1
                    compare_plane(leg, expected_plane)
                    if expected_plane['normalClearance'] < 0:
                        report['negativePlaneClearances'] += 1
            for normal in ((0, 0, 0), (0, 0, 3)):
                leg.set_editor_property('ProbeImpactNormal', unreal.Vector(*normal))
                leg.call_method('EvaluateSurfacePlane', ())
                report['syntheticPlaneSamples'] += 1
                empty_plane(leg)
            leg.set_editor_property('ProbeImpactNormal', unreal.Vector(0, 0, 1))
            leg.set_editor_property('bProbeInitialOverlap', True)
            leg.call_method('EvaluateSurfacePlane', ())
            report['syntheticPlaneSamples'] += 1
            empty_plane(leg)
        assert report['negativePlaneClearances'] > 0
        report['passed'] = True
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        body.set_actor_rotation(rotation, False)
        for name, leg in legs.items():
            distance, lift = saved[name]
            leg.set_editor_property('ProbeTraceDistance', distance)
            leg.set_editor_property('ProbeTraceLift', lift)
            leg.call_method('MeasureSurfaceProbe', ())
        path = Path(unreal.Paths.project_dir())/'Saved/BeholderRuntimeProbeRegression.json'
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    assert report['passed'], report['error']


if __name__ == '__main__':
    run()
