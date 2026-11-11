"""PIE-only read-only-in-motion regression of the straight contact planner.

No extension command is issued. Guard tests temporarily change cached state
fields on PIE copies, not actual joint/claw transforms, and restore them.
"""
import json
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
from beholder_straight_reach import straight_plane_target
from generate_beholder_telescope import COUNT, STROKE


def run():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world, 'Start PIE first and allow the technical stand to fold'
    body = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                if a.get_class().get_name() == 'BP_BeholderBody_Test_C')
    legs = [next(c for c in body.get_components_by_class(unreal.ChildActorComponent)
                 if c.get_name() == f'Leg{i}').get_editor_property('child_actor') for i in range(8)]
    report = dict(passed=False, solverChecks=0, liveChecks=0, guardChecks=0,
                  maximumError=0.0, liveReachable=0, error=None)

    def snapshot(leg):
        return tuple(leg.get_editor_property(name) for name in
                     ['ExtensionAmount', 'ExtensionPosition']+[f'Stage{i}Position' for i in range(COUNT)])

    def compare(leg, expected):
        assert leg.get_editor_property('bStraightPlanValid') == expected['valid']
        assert leg.get_editor_property('bStraightPlaneReachable') == expected['reachable']
        for name, key in [('StraightTargetExtension', 'target'), ('StraightProjectedStroke', 'projectedStroke'),
                          ('StraightFoldedClearance', 'foldedClearance'), ('StraightExtendedClearance', 'extendedClearance')]:
            error = abs(leg.get_editor_property(name)-expected[key])
            report['maximumError'] = max(error, report['maximumError'])
            assert error < 0.002, (name, error, expected)

    try:
        values = [(0, 100, -100), (1, 100, 100), (0.25, 25, -100), (0.75, 25, 100),
                  (0, 400, -150), (0, 10, 100), (0.5, 0, -100), (0, 1, 0),
                  (-1, 1, -100), (0, -1, -100), (0, float('nan'), -100), (0, 1, float('inf'))]
        for leg in legs:
            before = snapshot(leg)
            for args in values:
                leg.call_method('SolveStraightPlaneTarget', args)
                compare(leg, straight_plane_target(*args))
                assert snapshot(leg) == before, 'Planner changed limb motion state'
                report['solverChecks'] += 1
            leg.call_method('MeasureSurfaceProbe', ())
            assert leg.get_editor_property('bProbePlaneValid')
            forward = leg.get_actor_forward_vector()
            normal = leg.get_editor_property('ProbePlaneNormal')
            scale = leg.get_actor_scale3d()
            projected = COUNT*STROKE*scale.x*(forward.x*normal.x+forward.y*normal.y+forward.z*normal.z)
            expected = straight_plane_target(leg.get_editor_property('ExtensionPosition'),
                                             leg.get_editor_property('ProbePlaneClearance'), projected)
            compare(leg, expected)
            assert snapshot(leg) == before
            report['liveChecks'] += 1
            report['liveReachable'] += int(expected['reachable'])
            head = next(c for c in leg.get_components_by_class(unreal.ChildActorComponent)
                        if c.get_name() == 'HeadModule').get_editor_property('child_actor')
            for actor, name, value in [(leg, 'Joint1Magnitude', 1.0), (head, 'Claw0Position', 0.2),
                                        (leg, 'ExtensionAmount', 0.5), (leg, 'bProbePlaneValid', False)]:
                saved = actor.get_editor_property(name)
                try:
                    actor.set_editor_property(name, value)
                    leg.call_method('PlanStraightSurfaceContact', ())
                    compare(leg, straight_plane_target(0, 0, 0))
                    report['guardChecks'] += 1
                finally:
                    actor.set_editor_property(name, saved)
            distance = leg.get_editor_property('ProbeTraceDistance')
            try:
                leg.set_editor_property('ProbeTraceDistance', 0.0001)
                leg.call_method('MeasureSurfaceProbe', ())
                assert not leg.get_editor_property('bProbeHit')
                compare(leg, straight_plane_target(0, 0, 0))
                report['guardChecks'] += 1
            finally:
                leg.set_editor_property('ProbeTraceDistance', distance)
                leg.call_method('MeasureSurfaceProbe', ())
        report['passed'] = True
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        path = Path(unreal.Paths.project_dir())/'Saved/BeholderStraightReachRegression.json'
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    assert report['passed'], report['error']


if __name__ == '__main__':
    run()
