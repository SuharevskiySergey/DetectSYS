"""Transient PIE execution of one straight plane-contact target.

The body is repositioned only as a test fixture and restored. It is never
physically supported. Discrete plane/geometry checks are not terrain sweeps.
"""
import importlib
import json
import math
from pathlib import Path
import sys
import time

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
import validate_beholder_body as geometry
importlib.reload(geometry)
from generate_beholder_telescope import COUNT, outer_hull
from generate_beholder_body import OUTER_RADIUS
from beholder_surface_probe import head_plane_clearance
from lapa5_geometry import claw_vertices_world


def xyz(v):
    return (v.x, v.y, v.z)


def start(sequential=None):
    body = geometry.find_body()
    legs = geometry.legs(body)
    leg = legs[0]
    original_location = body.get_actor_location()
    original_durations = tuple(leg.get_editor_property(name) for name in
                               ('ExtensionSeconds', 'RetractionSeconds', 'EmergencyRetractionSeconds'))
    original_mode = leg.get_editor_property('bSequentialMotion')
    assert sequential is None or type(sequential) is bool
    test_mode = original_mode if sequential is None else sequential
    for branch in legs:
        assert not branch.get_editor_property('bAutoDemo')
        assert abs(branch.get_editor_property('ExtensionAmount')) < 1e-6
        assert abs(branch.get_editor_property('ExtensionPosition')) < 1e-6, 'Wait for folded stand'
        assert all(abs(branch.get_editor_property(f'Joint{i}Magnitude')) < 1e-6 for i in range(1, COUNT))
        head = next(c for c in branch.get_components_by_class(unreal.ChildActorComponent)
                    if c.get_name() == 'HeadModule').get_editor_property('child_actor')
        assert all(abs(head.get_editor_property(f'Claw{i}Position')) < 1e-6 for i in range(3))
        assert branch.get_editor_property('SocketRequestedOpening') == 0
        assert all(branch.get_editor_property(f'SocketRequestedClaw{i}') <= 0 for i in range(3))
    assert all(abs(leg.get_editor_property(name)) < 1e-6 for name in
               ('BendPitchDegrees', 'BendYawDegrees', 'LiveBendPitchDegrees', 'LiveBendYawDegrees'))
    for i in range(1, COUNT):
        if leg.get_editor_property(f'bJoint{i}Override'):
            assert abs(leg.get_editor_property(f'Joint{i}PitchRequest')) < 1e-6
            assert abs(leg.get_editor_property(f'Joint{i}YawRequest')) < 1e-6
    scale = body.get_actor_scale3d()
    assert min(xyz(scale)) > 0 and max(xyz(scale))-min(xyz(scale)) < 1e-6
    geometry.validate(body)
    leg.call_method('MeasureSurfaceProbe', ())
    assert leg.get_editor_property('bStraightPlanValid')
    normal = xyz(leg.get_editor_property('ProbePlaneNormal'))
    point = xyz(leg.get_editor_property('ProbeImpactPoint'))
    projected = leg.get_editor_property('StraightProjectedStroke')
    clearance = leg.get_editor_property('ProbePlaneClearance')
    assert normal[2] > 0.5 and projected < -1
    test_amount = 0.2
    dz = (-test_amount*projected-clearance)/normal[2]
    assert math.isfinite(dz) and -400 < dz < -1, 'Unexpected stand calibration'
    lowered = unreal.Vector(original_location.x, original_location.y, original_location.z+dz)

    def signed(p):
        return sum((x-y)*n for x, y, n in zip(p, point, normal))

    assert signed(xyz(lowered))-OUTER_RADIUS*scale.x > 1, 'Body sphere would approach the plane'
    mode_name = 'sequential' if test_mode else 'simultaneous'
    path = Path(unreal.Paths.project_dir())/f'Saved/BeholderSingleContact_{mode_name}.json'
    report = dict(passed=False, running=True, startedAtUnix=time.time(), error=None, samples=0, geometryChecks=0, sleevePlaneChecks=0,
                  bodyVerticalOffsetCm=dz, targetExtension=None, contact=None,
                  sequential=test_mode,
                  minimumMeasuredHeadClearanceCm=None, minimumSleevePlaneClearanceCm=None,
                  originalBodyLocation=xyz(original_location), restored=False)
    state = dict(phase=0, since=time.monotonic(), handle=None)

    def check_sleeves():
        minimum = float('inf')
        identity = unreal.Transform()
        for branch in legs:
            parts = {c.get_name(): c for c in branch.get_components_by_class(unreal.StaticMeshComponent)}
            for i in range(COUNT):
                transform = geometry.coordinate_map(parts[f'Sleeve{i:02d}'].get_world_transform(), identity)
                vertices, _ = outer_hull(i)
                minimum = min(minimum, min(signed(transform(v)) for v in vertices))
        assert minimum > 0, f'Sleeve envelope intersects sampled plane: {minimum}'
        report['sleevePlaneChecks'] += 1
        previous = report['minimumSleevePlaneClearanceCm']
        report['minimumSleevePlaneClearanceCm'] = minimum if previous is None else min(previous, minimum)

    def check_geometry():
        geometry.validate(body)
        report['geometryChecks'] += 1
        check_sleeves()

    def finish(error=None):
        try:
            # Restore the elevated fixture even on failure. On success the leg
            # has already fully retracted; on failure request a safe retraction.
            if error:
                body.call_method('RetractBodyLeg', (0, True))
            body.set_actor_location(original_location, False, True)
            leg.call_method('SetMotionDurations', original_durations)
            leg.call_method('SetMotionMode', (original_mode,))
            body.call_method('UpdateBodySurfaceProbes', ())
            report['restored'] = max(abs(a-b) for a, b in zip(xyz(body.get_actor_location()), xyz(original_location))) < 0.001
            assert report['restored']
        except Exception as exc:
            error = error or str(exc)
        report.update(passed=error is None, running=False, error=error)
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        if state['handle'] is not None:
            unreal.unregister_slate_post_tick_callback(state['handle'])

    try:
        body.set_actor_location(lowered, False, True)
        assert max(abs(a-b) for a, b in zip(xyz(body.get_actor_location()), xyz(lowered))) < 0.001
        body.call_method('UpdateBodySurfaceProbes', ())
        assert all(branch.get_editor_property('bProbePlaneValid') and branch.get_editor_property('ProbePlaneClearance') > 1 for branch in legs)
        assert leg.get_editor_property('bStraightPlanValid') and leg.get_editor_property('bStraightPlaneReachable')
        target = leg.get_editor_property('StraightTargetExtension')
        assert abs(target-test_amount) < 0.00001
        report['targetExtension'] = target
        check_geometry()
        leg.call_method('SetMotionDurations', (3.0, 3.0, 1.0))
        leg.call_method('SetMotionMode', (test_mode,))
        body.call_method('SetBodyLegExtension', (0, target))
    except Exception as exc:
        finish(str(exc))
        raise

    def tick(_dt):
        try:
            assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'PIE stopped'
            age = time.monotonic()-state['since']
            assert age < 45, 'Contact execution phase timed out'
            report['samples'] += 1
            leg.call_method('MeasureSurfaceProbe', ())
            assert leg.get_editor_property('bProbePlaneValid'), 'Lost sampled surface'
            n = xyz(leg.get_editor_property('ProbePlaneNormal'))
            assert sum(a*b for a, b in zip(n, normal)) > 0.99999, 'Surface normal changed'
            assert abs(signed(xyz(leg.get_editor_property('ProbeImpactPoint')))) < 0.05, 'Surface left original plane'
            gap = leg.get_editor_property('ProbePlaneClearance')
            old = report['minimumMeasuredHeadClearanceCm']
            report['minimumMeasuredHeadClearanceCm'] = gap if old is None else min(old, gap)
            assert gap >= -0.05, f'Head envelope crossed sampled plane: {gap}'
            assert all(abs(leg.get_editor_property(f'Joint{i}Magnitude')) < 1e-6 for i in range(1, COUNT)), 'Limb stopped being straight'
            assert all(abs(branch.get_editor_property('ExtensionPosition')) < 1e-6 for branch in legs[1:])
            amount = leg.get_editor_property('ExtensionPosition')
            if state['phase'] == 0 and abs(amount-target) < 1e-6 and age > 0.8:
                assert abs(gap) < 0.05, f'Target did not reach sampled plane: {gap}'
                check_geometry()
                head = next(c for c in leg.get_components_by_class(unreal.ChildActorComponent)
                            if c.get_name() == 'HeadModule').get_editor_property('child_actor')
                radius = 27*max(abs(value) for value in xyz(head.get_actor_scale3d()))
                support = head_plane_clearance(xyz(head.get_actor_location()), radius,
                                               [[xyz(v) for v in claw] for claw in claw_vertices_world(head)],
                                               point, normal)
                assert abs(support['normalClearance']-gap) < 0.002
                assert max(abs(a-b) for a, b in zip(support['support']['point'], xyz(leg.get_editor_property('ProbePlanePoint')))) < 0.002
                report['contact'] = dict(extension=amount, planeClearanceCm=gap,
                                         verticalGapCm=leg.get_editor_property('ProbeGap'),
                                         supportSource=support['support']['source'],
                                         headSupportPoint=xyz(leg.get_editor_property('ProbePlanePoint')))
                body.call_method('RetractBodyLeg', (0, False))
                state.update(phase=1, since=time.monotonic())
            elif state['phase'] == 1 and amount < 1e-6 and age > 0.8:
                check_geometry()
                finish()
        except Exception as exc:
            finish(str(exc))

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Single-contact PIE execution registered:', path)


if __name__ == '__main__':
    start()
