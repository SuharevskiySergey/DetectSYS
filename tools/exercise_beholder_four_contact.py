"""PIE-only four-point geometric contact experiment; no support physics.

The test computes a temporary fixture height, verifies finite surface hits,
uses existing limb commands and restores the elevated stand. No asset edits.
"""
import importlib
import json
from pathlib import Path
import sys
import time

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
import validate_beholder_body as geometry
importlib.reload(geometry)
import beholder_straight_reach
importlib.reload(beholder_straight_reach)
from beholder_straight_reach import shared_vertical_offset
from beholder_support_polygon import evaluate_body_candidates
from beholder_surface_probe import head_plane_clearance
from generate_beholder_telescope import COUNT, STROKE, outer_hull
from generate_beholder_body import OUTER_RADIUS
from lapa5_geometry import claw_vertices_world
from build_beholder_footprint_graph import FOOTPRINT_INDICES


def xyz(v):
    return (v.x, v.y, v.z)


ABORT_REASONS = {'disabled': 1, 'body_moved': 2, 'surface_lost': 3}
MONITOR_REASONS = {**ABORT_REASONS, 'goal_changed': 3, 'cancel': 5, 'footprint_rejected': 6,
                   'incoherent_pose': 3}
RETRACTION_REASONS = {**ABORT_REASONS, 'goal_changed': 3, 'timeout': 4, 'cancel': 5,
                      'invalid_probe_settings': 3}


def report_path(blueprint_request, abort_mid_approach, abort_fault, reject_final_footprint,
                monitor_contacts, monitor_fault, blueprint_retraction=False, retraction_fault='none'):
    suffix = '' if abort_fault == 'disabled' else '_'+abort_fault
    origin = 'monitored' if monitor_contacts else 'reached'
    filename = (f'BeholderFourContact_retraction_{origin}_{retraction_fault}.json' if blueprint_retraction else
                'BeholderFourContact_monitor_'+monitor_fault+'.json' if monitor_contacts else
                'BeholderFourContact_completion_rejected.json' if reject_final_footprint else
                'BeholderFourContact_watch_abort'+suffix+'.json' if abort_mid_approach else
                'BeholderFourContact_blueprint.json' if blueprint_request else 'BeholderFourContact.json')
    return Path(unreal.Paths.project_dir())/'Saved'/filename


def start(blueprint_request=False, abort_mid_approach=False, abort_fault='disabled', reject_final_footprint=False,
          monitor_contacts=False, monitor_fault='none', blueprint_retraction=False, retraction_fault='none'):
    assert type(blueprint_request) is bool
    assert type(abort_mid_approach) is bool and (not abort_mid_approach or blueprint_request)
    assert abort_fault in ABORT_REASONS
    assert type(reject_final_footprint) is bool
    assert not reject_final_footprint or (blueprint_request and not abort_mid_approach)
    assert type(monitor_contacts) is bool
    assert not monitor_contacts or (blueprint_request and not abort_mid_approach and not reject_final_footprint)
    assert monitor_fault in ('none', *MONITOR_REASONS)
    assert monitor_fault == 'none' or monitor_contacts
    assert type(blueprint_retraction) is bool
    assert not blueprint_retraction or (blueprint_request and not abort_mid_approach and not reject_final_footprint and monitor_fault == 'none')
    assert retraction_fault in ('none', *RETRACTION_REASONS)
    assert retraction_fault == 'none' or blueprint_retraction
    body = geometry.find_body()
    original = body.get_actor_location()
    original_enabled = body.get_editor_property('bEnableExperimentalFourContact') if blueprint_request else None
    original_margin = body.get_editor_property('FourContactCompletionMinimumMarginCm') if blueprint_request else None
    original_timeout = body.get_editor_property('FourContactWatchTimeout') if blueprint_request else None
    if blueprint_request:
        assert body.get_editor_property('FourContactWatchState') == 0, 'Release the previous test before starting another'
    assert all(abs(l.get_editor_property('ExtensionPosition')) < 1e-6 and
               abs(l.get_editor_property('ExtensionAmount')) < 1e-6 for l in geometry.legs(body))
    # A broad, flat part of this test level avoids the narrow ramp's edges.
    # This is a known test fixture, not runtime navigation or body control.
    path = report_path(blueprint_request, abort_mid_approach, abort_fault, reject_final_footprint,
                       monitor_contacts, monitor_fault, blueprint_retraction, retraction_fault)
    pending = dict(passed=False, running=True, setupPending=True, startedAtUnix=time.time(), error=None)
    path.write_text(json.dumps(pending, indent=2), encoding='utf-8')
    gate = dict(ticks=0, handle=None, game_time=unreal.SystemLibrary.get_game_time_in_seconds(body),
                since=time.monotonic())

    def restore_setup_failure(exc):
        cleanup_error = None
        try:
            if blueprint_request:
                body.call_method('ReleaseExperimentalFourContact', ())
            body.set_actor_location(original, False, True)
            if blueprint_request:
                body.set_editor_property('bEnableExperimentalFourContact', original_enabled)
                body.set_editor_property('FourContactCompletionMinimumMarginCm', original_margin)
                body.set_editor_property('FourContactWatchTimeout', original_timeout)
            body.call_method('UpdateBodySurfaceProbes', ())
        except Exception as cleanup:
            cleanup_error = repr(cleanup)
        current = json.loads(path.read_text(encoding='utf-8'))
        if current.get('setupPending'):
            current.update(passed=False, running=False, setupPending=False, error=repr(exc))
        if cleanup_error:
            current['cleanupError'] = cleanup_error
        if current.get('setupPending') is False or cleanup_error:
            path.write_text(json.dumps(current, indent=2), encoding='utf-8')

    def setup_tick(_dt):
        try:
            assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'PIE stopped during setup'
            gate['ticks'] += 1
            if gate['ticks'] < 2 or unreal.SystemLibrary.get_game_time_in_seconds(body) <= gate['game_time']:
                assert time.monotonic()-gate['since'] < 5, 'PIE did not tick during fixture setup'
                return
            unreal.unregister_slate_post_tick_callback(gate['handle'])
            gate['handle'] = None
            _start(body, original, blueprint_request, abort_mid_approach, abort_fault, reject_final_footprint,
                   monitor_contacts, monitor_fault, gate['ticks'], blueprint_retraction, retraction_fault)
        except Exception as exc:
            if gate['handle'] is not None:
                unreal.unregister_slate_post_tick_callback(gate['handle'])
                gate['handle'] = None
            restore_setup_failure(exc)

    try:
        # Poseable head socket transforms may still describe the previous
        # frame after a root teleport. Never sample that stale fixture pose.
        body.set_actor_location(unreal.Vector(original.x, -1000.0, original.z), False, True)
        gate['handle'] = unreal.register_slate_post_tick_callback(setup_tick)
    except Exception as exc:
        restore_setup_failure(exc)
        raise
    print('Four-contact PIE setup deferred:', path)


def _start(body, original_location, blueprint_request, abort_mid_approach, abort_fault, reject_final_footprint,
           monitor_contacts, monitor_fault, setup_ticks, blueprint_retraction, retraction_fault):
    legs = geometry.legs(body)
    location = body.get_actor_location()
    saved = [(tuple(l.get_editor_property(n) for n in ('ExtensionSeconds', 'RetractionSeconds', 'EmergencyRetractionSeconds')),
              l.get_editor_property('bSequentialMotion')) for l in legs]
    saved_enabled = body.get_editor_property('bEnableExperimentalFourContact') if blueprint_request else None
    saved_margin = body.get_editor_property('FourContactCompletionMinimumMarginCm') if blueprint_request else None
    saved_timeout = body.get_editor_property('FourContactWatchTimeout') if blueprint_request else None
    request_rejections = []
    heads = [next(c for c in l.get_components_by_class(unreal.ChildActorComponent)
                  if c.get_name() == 'HeadModule').get_editor_property('child_actor') for l in legs]
    for leg, head in zip(legs, heads):
        assert not leg.get_editor_property('bAutoDemo')
        assert abs(leg.get_editor_property('ExtensionAmount')) < 1e-6
        assert abs(leg.get_editor_property('ExtensionPosition')) < 1e-6
        assert leg.get_editor_property('SocketRequestedOpening') == 0
        assert all(leg.get_editor_property(f'SocketRequestedClaw{i}') <= 0 for i in range(3))
        assert all(abs(head.get_editor_property(f'Claw{i}Position')) < 1e-6 for i in range(3))
        assert all(abs(leg.get_editor_property(n)) < 1e-6 for n in
                   ('BendPitchDegrees', 'BendYawDegrees', 'LiveBendPitchDegrees', 'LiveBendYawDegrees'))
        for i in range(1, COUNT):
            assert abs(leg.get_editor_property(f'Joint{i}Magnitude')) < 1e-6
            if leg.get_editor_property(f'bJoint{i}Override'):
                assert abs(leg.get_editor_property(f'Joint{i}PitchRequest')) < 1e-6
                assert abs(leg.get_editor_property(f'Joint{i}YawRequest')) < 1e-6
    if blueprint_request:
        for enabled, reason in [(False, 'disabled'), (True, 'unreachable_at_elevated_height')]:
            body.set_editor_property('bEnableExperimentalFourContact', enabled)
            body.call_method('TryExperimentalFourContact', ())
            assert not body.get_editor_property('bLastFourContactRequestAccepted')
            assert all(abs(l.get_editor_property('ExtensionAmount')) < 1e-6 for l in legs)
            request_rejections.append(reason)
    body.call_method('UpdateBodySurfaceProbes', ())
    normal = xyz(legs[0].get_editor_property('ProbePlaneNormal'))
    point = xyz(legs[0].get_editor_property('ProbeImpactPoint'))
    assert normal[2] > 0.99999, ('The four-contact experiment requires the broad flat fixture',
                               normal, point, xyz(body.get_actor_location()),
                               legs[0].get_editor_property('bProbeValid'), legs[0].get_editor_property('bProbeHit'))
    ignored = [body]+list(body.get_all_child_actors(True))
    initial_hit = unreal.SystemLibrary.line_trace_single(body, unreal.Vector(point[0], point[1], point[2]+2),
                                                         unreal.Vector(point[0], point[1], point[2]-2),
                                                         unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignored,
                                                         unreal.DrawDebugTrace.NONE, True)
    assert initial_hit is not None
    surface_actor = initial_hit.to_tuple()[9]
    assert surface_actor is not None
    floor_component = surface_actor.get_component_by_class(unreal.StaticMeshComponent)
    visibility = unreal.CollisionChannel.ECC_VISIBILITY
    floor_response = floor_component.get_collision_response_to_channel(visibility) if floor_component else None
    dy = 0.0
    horizontal_bias = normal[1]*dy
    base_location = (location.x, location.y+dy, location.z)

    def signed(p):
        return sum((x-y)*n for x, y, n in zip(p, point, normal))

    for leg in legs:
        assert leg.get_editor_property('bStraightPlanValid')
        assert sum(a*b for a, b in zip(xyz(leg.get_editor_property('ProbePlaneNormal')), normal)) > 0.99999
        assert abs(signed(xyz(leg.get_editor_property('ProbeImpactPoint')))) < 0.05
    indices = [i for i, leg in enumerate(legs) if leg.get_actor_forward_vector().z < -0.1
               and leg.get_editor_property('StraightProjectedStroke') < -1]
    assert len(indices) == 4
    interval = shared_vertical_offset([legs[i].get_editor_property('ProbePlaneClearance')+horizontal_bias for i in indices],
                                      [legs[i].get_editor_property('StraightProjectedStroke') for i in indices], normal[2])
    assert interval['feasible'], interval
    scale = body.get_actor_scale3d()
    assert min(xyz(scale)) > 0 and max(xyz(scale))-min(xyz(scale)) < 1e-6
    # Bound the temporary height by every folded head and the whole body sphere.
    lower = max(interval['lower'], (1-min(l.get_editor_property('ProbePlaneClearance')+horizontal_bias for l in legs))/normal[2],
                (OUTER_RADIUS*scale.x+1-signed(base_location))/normal[2])
    assert lower < interval['upper']
    dz = (lower+interval['upper'])/2
    assert -600 < dz < -1
    lowered = unreal.Vector(base_location[0], base_location[1], location.z+dz)
    report = dict(passed=False, running=True, startedAtUnix=time.time(), error=None, indices=indices,
                  bodyVerticalOffsetCm=dz, bodyYOffsetCm=location.y-original_location.y,
                  originalBodyLocation=xyz(original_location), targetExtensions={}, samples=0, geometryChecks=0,
                  minimumHeadPlaneClearanceCm=None, minimumSleevePlaneClearanceCm=None,
                  contacts=None, footprint=None, restored=False)
    path = report_path(blueprint_request, abort_mid_approach, abort_fault, reject_final_footprint,
                       monitor_contacts, monitor_fault, blueprint_retraction, retraction_fault)
    report.update(blueprintRequest=blueprint_request, requestRejections=request_rejections,
                  abortMidApproach=abort_mid_approach, abortFault=abort_fault if abort_mid_approach else None,
                  rejectFinalFootprint=reject_final_footprint, monitorContacts=monitor_contacts,
                  monitorFault=monitor_fault if monitor_contacts else None,
                  setupPending=False, setupDeferredTicks=setup_ticks,
                  blueprintRetraction=blueprint_retraction, retractionFault=retraction_fault if blueprint_retraction else None)
    state = dict(phase=0, since=time.monotonic(), handle=None, restore_fault=None)
    targets = {}

    def begin_monitor():
        result = body.call_method('BeginExperimentalContactMonitoring', ())
        if isinstance(result, tuple):
            assert len(result) == 1
            result = result[0]
        assert type(result) is bool
        return result

    def try_retraction():
        result = body.call_method('TryExperimentalFourRetraction', ())
        if isinstance(result, tuple):
            assert len(result) == 1
            result = result[0]
        assert type(result) is bool
        return result

    def start_retraction():
        origin = body.get_editor_property('FourContactWatchState')
        assert origin in (2, 4)
        body.set_editor_property('FourContactWatchTimeout', saved_timeout)
        old_goal = legs[indices[0]].get_editor_property('ExtensionAmount')
        try:
            body.call_method('SetBodyLegExtension', (indices[0], 0.2))
            before = [l.get_editor_property('ExtensionAmount') for l in legs]
            assert not try_retraction()
            assert body.get_editor_property('FourContactWatchState') == origin
            assert before == [l.get_editor_property('ExtensionAmount') for l in legs]
            report['retractionStartRejections'].append('incompatible_owned_goal')
        finally:
            body.call_method('SetBodyLegExtension', (indices[0], old_goal))
        assert try_retraction()
        assert body.get_editor_property('FourContactWatchState') == 5
        assert all(legs[i].get_editor_property('ExtensionAmount') == 0 for i in indices)
        assert body.get_editor_property('FourContactRetractionUpdates') == 0
        assert not try_retraction()
        report['retractionStartRejections'].append('already_retracting')
        assert not begin_monitor()
        body.call_method('TryExperimentalFourContact', ())
        assert not body.get_editor_property('bLastFourContactRequestAccepted')
        assert body.get_editor_property('FourContactWatchState') == 5
        assert all(legs[i].get_editor_property('ExtensionAmount') == 0 for i in indices)
        assert all(abs(body.get_editor_property(f'FourContactWatchTarget{i}')-targets[i]) < 1e-6 for i in indices)
        report['retraction'] = dict(originState=origin, samples=0, faultInjected=False,
                                    previousAmounts=[legs[i].get_editor_property('ExtensionPosition') for i in indices])
        state.update(phase=9, since=time.monotonic())

    def restore_fault():
        if state['restore_fault'] is not None:
            state['restore_fault']()
            state['restore_fault'] = None
        report['faultRestored'] = True

    def inject_strict_candidates():
        names = ('BodySupportMaxGapCm', 'BodySupportPenetrationToleranceCm')
        settings = [body.get_editor_property(name) for name in names]

        def restore_candidates():
            for name, value in zip(names, settings):
                body.set_editor_property(name, value)

        state['restore_fault'] = restore_candidates
        for name in names:
            body.set_editor_property(name, 0.0)

    def inject_fault(fault=abort_fault):
        report['injection'] = dict(amounts=[legs[i].get_editor_property('ExtensionPosition') for i in indices],
                                   updates=body.get_editor_property('FourContactWatchUpdates'))
        if fault == 'disabled':
            old = body.get_editor_property('bEnableExperimentalFourContact')
            state['restore_fault'] = lambda: body.set_editor_property('bEnableExperimentalFourContact', old)
            body.set_editor_property('bEnableExperimentalFourContact', False)
        elif fault == 'body_moved':
            old = body.get_actor_location()
            state['restore_fault'] = lambda: body.set_actor_location(old, False, True)
            body.set_actor_location(unreal.Vector(old.x+1, old.y, old.z), False, True)
        else:
            component = surface_actor.get_component_by_class(unreal.StaticMeshComponent)
            assert component
            channel = unreal.CollisionChannel.ECC_VISIBILITY
            old = component.get_collision_response_to_channel(channel)
            state['restore_fault'] = lambda: component.set_collision_response_to_channel(channel, old)
            component.set_collision_response_to_channel(channel, unreal.CollisionResponseType.ECR_IGNORE)

    def surface_point(p):
        hit = unreal.SystemLibrary.line_trace_single(body, unreal.Vector(p[0], p[1], p[2]+2),
                                                     unreal.Vector(p[0], p[1], p[2]-2),
                                                     unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignored,
                                                     unreal.DrawDebugTrace.NONE, True)
        assert hit is not None, f'No finite surface under predicted contact {p}'
        fields = hit.to_tuple()
        assert fields[0] and not fields[1]
        assert max(abs(a-b) for a, b in zip(xyz(fields[5]), p)) < 0.05
        assert sum(a*b for a, b in zip(xyz(fields[7]), normal)) > 0.99999

    def check_geometry():
        geometry.validate(body)
        report['geometryChecks'] += 1
        minimum = float('inf')
        identity = unreal.Transform()
        for leg in legs:
            parts = {c.get_name(): c for c in leg.get_components_by_class(unreal.StaticMeshComponent)}
            for i in range(COUNT):
                transform = geometry.coordinate_map(parts[f'Sleeve{i:02d}'].get_world_transform(), identity)
                vertices, _ = outer_hull(i)
                minimum = min(minimum, min(signed(transform(v)) for v in vertices))
        assert minimum > 0, f'Sleeve crosses plane: {minimum}'
        old = report['minimumSleevePlaneClearanceCm']
        report['minimumSleevePlaneClearanceCm'] = minimum if old is None else min(old, minimum)

    def runtime_footprint(reference, minimum=1.0):
        goals = [leg.get_editor_property('ExtensionAmount') for leg in legs]
        value = body.call_method('EvaluateExperimentalFourFootprint', (reference, minimum))
        assert isinstance(value, tuple) and len(value) == 5
        assert goals == [leg.get_editor_property('ExtensionAmount') for leg in legs], 'Footprint must not command motion'
        if not value[0] and body.get_editor_property('BodySupportCandidateCount') == 4:
            components = {c.get_name(): c for c in body.get_components_by_class(unreal.ChildActorComponent)}
            rows = []
            for i in indices:
                ready, point = body.call_method('ReadExperimentalFootprintPoint', (components[f'Leg{i}'],))
                rows.append(dict(index=i, ready=ready, point=xyz(point),
                                 supportPoint=xyz(legs[i].get_editor_property('ProbePlanePoint'))))
            args = tuple(legs[i].get_editor_property('ProbePlanePoint') for i in FOOTPRINT_INDICES)+(reference, minimum)
            report['runtimeFootprintDiagnostic'] = dict(points=rows, directKernel=body.call_method('CalculateOrderedFourFootprint', args))
        return value

    def finish(error=None):
        try:
            restore_fault()
            if ((abort_mid_approach and abort_fault == 'surface_lost') or
                    (monitor_contacts and monitor_fault == 'surface_lost') or
                    (blueprint_retraction and retraction_fault == 'surface_lost')):
                assert floor_component.get_collision_response_to_channel(visibility) == floor_response
                report['floorVisibilityRestored'] = True
            if blueprint_request:
                body.call_method('ReleaseExperimentalFourContact', ())
            if error:
                for i in indices:
                    body.call_method('RetractBodyLeg', (i, True))
            body.set_actor_location(original_location, False, True)
            for i in indices:
                legs[i].call_method('SetMotionDurations', saved[i][0])
                legs[i].call_method('SetMotionMode', (saved[i][1],))
            if blueprint_request:
                body.set_editor_property('bEnableExperimentalFourContact', saved_enabled)
                body.set_editor_property('FourContactCompletionMinimumMarginCm', saved_margin)
                body.set_editor_property('FourContactWatchTimeout', saved_timeout)
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
        if blueprint_retraction:
            goals = [l.get_editor_property('ExtensionAmount') for l in legs]
            assert not try_retraction()
            assert goals == [l.get_editor_property('ExtensionAmount') for l in legs]
            assert body.get_editor_property('FourContactWatchState') == 0
            report['retractionStartRejections'] = ['idle']
        if monitor_contacts:
            before = [l.get_editor_property('ExtensionAmount') for l in legs]
            updates = body.get_editor_property('FourContactWatchUpdates')
            assert not begin_monitor()
            assert body.get_editor_property('FourContactWatchState') == 0
            assert updates == body.get_editor_property('FourContactWatchUpdates')
            assert before == [l.get_editor_property('ExtensionAmount') for l in legs]
            report['monitorStartRejections'] = ['idle']
        body.set_actor_location(lowered, False, True)
        assert max(abs(a-b) for a, b in zip(xyz(body.get_actor_location()), xyz(lowered))) < 0.001
        body.call_method('UpdateBodySurfaceProbes', ())
        assert all(l.get_editor_property('bProbePlaneValid') and l.get_editor_property('ProbePlaneClearance') > 1 for l in legs)
        predicted = [None]*8
        for i in indices:
            leg = legs[i]
            assert leg.get_editor_property('bStraightPlanValid') and leg.get_editor_property('bStraightPlaneReachable')
            target = leg.get_editor_property('StraightTargetExtension')
            assert 0.04999 <= target <= 0.95001
            targets[i] = target
            report['targetExtensions'][str(i)] = target
            forward = xyz(leg.get_actor_forward_vector())
            distance = COUNT*STROKE*leg.get_actor_scale3d().x*target
            predicted[i] = tuple(p+d*distance for p, d in zip(xyz(leg.get_editor_property('ProbePlanePoint')), forward))
            surface_point(predicted[i])
        planned = evaluate_body_candidates(predicted, [i in indices for i in range(8)], xyz(lowered), minimum_margin=1)
        assert planned['valid'] and planned['passesMargin'], planned
        report['predictedFootprint'] = planned
        if blueprint_request:
            assert runtime_footprint(body.get_actor_location()) == (False, False, False, 0, 0)
            report['runtimeFootprintBeforeContactRejected'] = True
        check_geometry()
        for rank, i in enumerate(indices):
            legs[i].call_method('SetMotionDurations', (3.0, 3.0, 1.0))
            legs[i].call_method('SetMotionMode', (rank % 2 == 0,))
        if blueprint_request:
            body.set_editor_property('bEnableExperimentalFourContact', True)
            component = next(c for c in body.get_components_by_class(unreal.ChildActorComponent)
                             if c.get_name() == f'Leg{indices[-1]}')
            good = body.call_method('PrepareExperimentalContactLeg', (component,))
            assert isinstance(good, tuple) and len(good) == 3 and good[0] is True
            # Synthetic diagnostic snapshot: the predicted point is moved far
            # outside the level, without moving any actor or changing terrain.
            saved_point = xyz(legs[indices[-1]].get_editor_property('ProbePlanePoint'))
            try:
                legs[indices[-1]].set_editor_property('ProbePlanePoint', unreal.Vector(100000, 100000, 0))
                missed = body.call_method('PrepareExperimentalContactLeg', (component,))
                assert isinstance(missed, tuple) and len(missed) == 3
                assert missed[0] is False and missed[1] == 0 and xyz(missed[2]) == (0, 0, 0)
                assert all(abs(l.get_editor_property('ExtensionAmount')) < 1e-6 for l in legs)
                report['helperSnapshotChecks'] = 2
            finally:
                legs[indices[-1]].set_editor_property('ProbePlanePoint', unreal.Vector(*saved_point))
            # The last of four legs fails preflight: none of the first three
            # may receive a goal. No frame ticks before restoring this request.
            bad = legs[indices[-1]]
            for name, value, reason in [('SocketRequestedClaw2', 0.2, 'one_leg_requested_open_claw'),
                                         ('BendPitchDegrees', 0.2, 'pending_global_bend'),
                                         ('Joint9PitchRequest', 0.2, 'pending_joint_request'),
                                         ('bAutoDemo', True, 'automatic_demo_enabled')]:
                old_request = bad.get_editor_property(name)
                changed = False
                try:
                    bad.set_editor_property(name, value)
                    changed = True
                    body.call_method('TryExperimentalFourContact', ())
                    assert not body.get_editor_property('bLastFourContactRequestAccepted')
                    assert all(abs(l.get_editor_property('ExtensionAmount')) < 1e-6 for l in legs)
                    report['requestRejections'].append(reason)
                finally:
                    if changed:
                        bad.set_editor_property(name, old_request)
            upper = legs[1]
            for name, value, reason in [('ExtensionAmount', 0.2, 'upper_leg_has_pending_motion'),
                                         ('bAutoDemo', True, 'upper_leg_automatic_demo_enabled')]:
                old_value = upper.get_editor_property(name)
                changed = False
                try:
                    upper.set_editor_property(name, value)
                    changed = True
                    before_goals = [l.get_editor_property('ExtensionAmount') for l in legs]
                    body.call_method('TryExperimentalFourContact', ())
                    assert not body.get_editor_property('bLastFourContactRequestAccepted')
                    assert [l.get_editor_property('ExtensionAmount') for l in legs] == before_goals
                    report['requestRejections'].append(reason)
                finally:
                    if changed:
                        upper.set_editor_property(name, old_value)
            for margin, reason in [(-1.0, 'negative_completion_margin'),
                                   (float('nan'), 'nan_completion_margin'),
                                   (float('inf'), 'infinite_completion_margin'),
                                   (1000001.0, 'oversized_completion_margin'),
                                   (200.0, 'insufficient_predicted_margin')]:
                try:
                    body.set_editor_property('FourContactCompletionMinimumMarginCm', margin)
                    before_goals = [l.get_editor_property('ExtensionAmount') for l in legs]
                    body.call_method('TryExperimentalFourContact', ())
                    assert not body.get_editor_property('bLastFourContactRequestAccepted')
                    assert before_goals == [l.get_editor_property('ExtensionAmount') for l in legs]
                    if margin == 200.0:
                        assert body.get_editor_property('FourContactWatchState') == 0
                        assert all(abs(l.get_editor_property('ExtensionPosition')) < 1e-6 for l in legs)
                        assert all(body.get_editor_property(f'LastFourContactTarget{i}') == 0 for i in indices)
                        report['predictedFootprintEarlyRejection'] = dict(requiredMarginCm=200.0,
                            predictedMarginCm=planned['marginCm'], watchState=0, goalsUnchanged=True)
                    report['requestRejections'].append(reason)
                finally:
                    body.set_editor_property('FourContactCompletionMinimumMarginCm', saved_margin)
            required_margin = 1.0
            body.set_editor_property('FourContactCompletionMinimumMarginCm', required_margin)
            body.call_method('TryExperimentalFourContact', ())
            assert body.get_editor_property('bLastFourContactRequestAccepted')
            assert body.get_editor_property('FourContactWatchState') == 1
            assert body.get_editor_property('FourContactWatchRequiredMarginCm') == required_margin
            report['completionRequiredMarginCm'] = required_margin
            for i in indices:
                assert abs(body.get_editor_property(f'LastFourContactTarget{i}')-targets[i]) < 1e-6
                assert abs(legs[i].get_editor_property('ExtensionAmount')-targets[i]) < 1e-6
            report['requestAccepted'] = True
            if not abort_mid_approach and not reject_final_footprint:
                import exercise_beholder_watch_faults as faults
                importlib.reload(faults)
                report['watchFaultChecks'] = faults.check_faults(body, legs, indices, surface_actor)
                assert body.get_editor_property('FourContactWatchState') == 1
                if blueprint_retraction:
                    goals = [l.get_editor_property('ExtensionAmount') for l in legs]
                    assert not try_retraction()
                    assert goals == [l.get_editor_property('ExtensionAmount') for l in legs]
                    assert body.get_editor_property('FourContactWatchState') == 1
                    report['retractionStartRejections'].append('approaching')
                if monitor_contacts:
                    before = [l.get_editor_property('ExtensionAmount') for l in legs]
                    assert not begin_monitor()
                    assert body.get_editor_property('FourContactWatchState') == 1
                    assert before == [l.get_editor_property('ExtensionAmount') for l in legs]
                    report['monitorStartRejections'].append('approaching')
            else:
                # Activate after the expensive setup has returned to the
                # editor loop, so a single long setup frame cannot skip the
                # whole mid-approach injection window.
                body.call_method('CancelExperimentalFourContact', ())
                body.call_method('ReleaseExperimentalFourContact', ())
                state['phase'] = -1
                report['deferredWatchStart'] = True
        else:
            for i in indices:
                body.call_method('SetBodyLegExtension', (i, targets[i]))
        state['since'] = time.monotonic()
    except Exception as exc:
        finish(repr(exc))
        raise

    def tick(_dt):
        try:
            assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(), 'PIE stopped'
            age = time.monotonic()-state['since']
            assert age < 45
            report['samples'] += 1
            if state['phase'] == -1:
                body.call_method('TryExperimentalFourContact', ())
                assert body.get_editor_property('bLastFourContactRequestAccepted')
                assert body.get_editor_property('FourContactWatchState') == 1
                if reject_final_footprint:
                    assert body.get_editor_property('FourContactWatchRequiredMarginCm') == 1.0
                    # A changed next-request preference must not rewrite the
                    # accepted margin. Tighten only the live candidate filter
                    # to make the final fresh-snapshot gate refuse contact.
                    body.set_editor_property('FourContactCompletionMinimumMarginCm', 200.0)
                    report['completionPreferenceChangedAfterStart'] = True
                    inject_strict_candidates()
                    report['completionRejectionMode'] = 'strict_zero_candidate_tolerances'
                state.update(phase=0, since=time.monotonic())
                return
            if state['phase'] in (9, 10):
                # No Python motion/probe/update calls in a nominal return.
                ret = report['retraction']
                ret['samples'] += 1
                phase = body.get_editor_property('FourContactWatchState')
                updates = body.get_editor_property('FourContactRetractionUpdates')
                amounts = [legs[i].get_editor_property('ExtensionPosition') for i in indices]
                goals = [legs[i].get_editor_property('ExtensionAmount') for i in indices]
                assert all(abs(l.get_editor_property('ExtensionPosition')) < 1e-6 for i, l in enumerate(legs) if i not in indices)
                if state['phase'] == 10:
                    assert phase == 6 and updates == ret['nativeUpdatesAtFolded']
                    assert max(amounts+goals) < 1e-6
                    ret['terminalSamples'] += 1
                    if age >= 0.25 and ret['terminalSamples'] >= 3:
                        body.call_method('ReleaseExperimentalFourContact', ())
                        finish()
                    return
                if phase == 3:
                    assert retraction_fault != 'none' and ret['faultInjected']
                    assert body.get_editor_property('FourContactWatchReason') == RETRACTION_REASONS[retraction_fault]
                    if retraction_fault != 'cancel':
                        assert updates > ret['updatesAtFault']
                    if retraction_fault == 'invalid_probe_settings':
                        assert not body.get_editor_property('bBodyProbeSettingsValid')
                        assert body.get_editor_property('BodyProbeMeasuredCount') == 0
                        ret['invalidSnapshotRejected'] = True
                    assert any(a > 0.01 for a in amounts)
                    assert all(a < targets[i]-0.001 for i, a in zip(indices, amounts))
                    assert max(abs(a-b) for a, b in zip(amounts, goals)) < 1e-5
                    assert not try_retraction()
                    report['watchAbort'] = dict(state=3, reason=RETRACTION_REASONS[retraction_fault],
                        amounts=amounts, goals=goals, updates=updates, holdSamples=0,
                        counterName='FourContactRetractionUpdates')
                    state.update(phase=3, since=time.monotonic())
                    return
                assert phase in (5, 6), phase
                assert all(goal == 0 for goal in goals)
                assert all(-1e-6 <= a <= previous+1e-6 for a, previous in zip(amounts, ret['previousAmounts']))
                ret['previousAmounts'] = amounts
                if phase == 6:
                    assert retraction_fault == 'none', 'Need an intermediate return frame for the fault injection'
                    assert updates > 0 and max(amounts) < 1e-6
                    assert all(abs(legs[i].get_editor_property(f'Stage{j}Position')) < 1e-6 for i in indices for j in range(10))
                    check_geometry()
                    ret.update(nativeUpdatesAtFolded=updates, elapsed=body.get_editor_property('FourContactRetractionElapsed'), terminalSamples=0)
                    assert not try_retraction() and not begin_monitor()
                    report['retractionStartRejections'].append('retracted')
                    assert runtime_footprint(body.get_actor_location()) == (False, False, False, 0, 0)
                    state.update(phase=10, since=time.monotonic())
                    return
                if retraction_fault != 'none' and not ret['faultInjected'] and any(0.1 < a < targets[i]-0.005 for i, a in zip(indices, amounts)):
                    ret.update(faultInjected=True, updatesAtFault=updates, amountsAtFault=amounts)
                    if retraction_fault in ABORT_REASONS:
                        inject_fault(retraction_fault)
                    elif retraction_fault == 'goal_changed':
                        body.call_method('SetBodyLegExtension', (indices[0], 0.05))
                    elif retraction_fault == 'timeout':
                        old = body.get_editor_property('FourContactWatchTimeout')
                        state['restore_fault'] = lambda: body.set_editor_property('FourContactWatchTimeout', old)
                        body.set_editor_property('FourContactWatchTimeout', 0.1)
                    elif retraction_fault == 'invalid_probe_settings':
                        old = body.get_editor_property('BodySupportMaxGapCm')
                        state['restore_fault'] = lambda: body.set_editor_property('BodySupportMaxGapCm', old)
                        body.set_editor_property('BodySupportMaxGapCm', -1.0)
                    else:
                        body.call_method('CancelExperimentalFourContact', ())
                return
            if state['phase'] == 8:
                monitor = report['monitor']
                monitor['passiveSamples'] += 1
                assert body.get_editor_property('FourContactWatchState') == 2, 'Monitoring must not start automatically'
                assert body.get_editor_property('FourContactWatchUpdates') == monitor['passiveUpdates']
                assert monitor['passiveGoals'] == [l.get_editor_property('ExtensionAmount') for l in legs]
                if age < 0.25 or monitor['passiveSamples'] < 3:
                    return
                body.set_editor_property('FourContactWatchTimeout', 0.1)
                assert begin_monitor()
                assert body.get_editor_property('FourContactWatchState') == 4
                assert begin_monitor(), 'A healthy repeated Begin must revalidate without resetting goals'
                assert monitor['passiveGoals'] == [l.get_editor_property('ExtensionAmount') for l in legs]
                assert body.get_editor_property('FourContactWatchElapsed') == monitor['approachElapsed']
                monitor.update(approachTimeoutDuringMonitor=0.1,
                               updatesAtStart=body.get_editor_property('FourContactWatchUpdates'), samples=0)
                state.update(phase=5, since=time.monotonic())
                return
            if state['phase'] in (5, 6, 7):
                # Only native Blueprint Tick samples/validates contacts here.
                # Python observes state/goals and changes a single fault input.
                monitor = report['monitor']
                monitor['samples'] += 1
                current_state = body.get_editor_property('FourContactWatchState')
                updates = body.get_editor_property('FourContactWatchUpdates')
                if state['phase'] == 5:
                    assert current_state == 4, 'Contact monitor aborted during its healthy dwell'
                    assert abs(body.get_editor_property('FourContactWatchElapsed')-monitor['approachElapsed']) < 1e-6
                    assert all(abs(legs[i].get_editor_property('ExtensionAmount')-targets[i]) < 1e-6 and
                               abs(legs[i].get_editor_property('ExtensionPosition')-targets[i]) < 1e-6 for i in indices)
                    if age < 1.0 or updates < monitor['updatesAtStart']+3 or monitor['samples'] < 3:
                        return
                    monitor['healthyNativeUpdates'] = updates-monitor['updatesAtStart']
                    monitor['healthyDwellSeconds'] = age
                    monitor['updatesBeforeFault'] = updates
                    if blueprint_retraction:
                        start_retraction()
                        return
                    if monitor_fault == 'none':
                        goals = [l.get_editor_property('ExtensionAmount') for l in legs]
                        body.call_method('ReleaseExperimentalFourContact', ())
                        assert body.get_editor_property('FourContactWatchState') == 0
                        assert goals == [l.get_editor_property('ExtensionAmount') for l in legs]
                        monitor['releasedGoals'] = goals
                        monitor['releasedSamples'] = 0
                        state.update(phase=7, since=time.monotonic())
                        return
                    if monitor_fault in ABORT_REASONS:
                        # Reuse only the fault-input mutation, not its approach
                        # phase or its abort assertions.
                        inject_fault(monitor_fault)
                    elif monitor_fault == 'goal_changed':
                        body.call_method('SetBodyLegExtension', (indices[0], 0.2))
                    elif monitor_fault == 'footprint_rejected':
                        inject_strict_candidates()
                    elif monitor_fault == 'incoherent_pose':
                        mesh = heads[indices[0]].get_editor_property('HeadMesh')
                        old = xyz(mesh.get_editor_property('relative_location'))
                        state['restore_fault'] = lambda: mesh.set_relative_location(unreal.Vector(*old), False, True)
                        mesh.set_relative_location(unreal.Vector(old[0]+10000, old[1], old[2]), False, True)
                    else:
                        body.call_method('CancelExperimentalFourContact', ())
                    state.update(phase=6, since=time.monotonic())
                    return
                if state['phase'] == 6:
                    if current_state != 3:
                        assert age < 2.0, 'Native contact monitor did not abort'
                        return
                    reason = MONITOR_REASONS[monitor_fault]
                    assert body.get_editor_property('FourContactWatchReason') == reason
                    if reason == 6:
                        monitor['rejectedCandidateCount'] = body.get_editor_property('BodySupportCandidateCount')
                        assert monitor['rejectedCandidateCount'] == 0
                    if monitor_fault == 'incoherent_pose':
                        poisoned = legs[indices[0]]
                        assert not poisoned.get_editor_property('bProbeValid')
                        assert not poisoned.get_editor_property('bProbeHit')
                        assert not poisoned.get_editor_property('bProbePlaneValid')
                        assert not poisoned.get_editor_property('bStraightPlanValid')
                        monitor['incoherentPoseSnapshotCleared'] = True
                    if monitor_fault != 'cancel':
                        assert updates > monitor['updatesBeforeFault']
                    amounts = [legs[i].get_editor_property('ExtensionPosition') for i in indices]
                    goals = [legs[i].get_editor_property('ExtensionAmount') for i in indices]
                    assert all(0 <= amount <= targets[i]+1e-6 for i, amount in zip(indices, amounts))
                    assert max(abs(a-b) for a, b in zip(amounts, goals)) < 1e-5
                    assert not begin_monitor()
                    assert body.get_editor_property('FourContactWatchState') == 3
                    report['monitorStartRejections'].append('aborted')
                    report['watchAbort'] = dict(state=3, reason=reason, amounts=amounts, goals=goals,
                                                updates=updates, holdSamples=0)
                    state.update(phase=3, since=time.monotonic())
                    return
                assert current_state == 0
                assert updates == monitor['updatesBeforeFault'], 'Released monitor still updates'
                assert monitor['releasedGoals'] == [l.get_editor_property('ExtensionAmount') for l in legs]
                monitor['releasedSamples'] += 1
                if age >= 0.25 and monitor['releasedSamples'] >= 3:
                    assert not begin_monitor()
                    report['monitorStartRejections'].append('released')
                    for i in indices:
                        body.call_method('RetractBodyLeg', (i, False))
                    state.update(phase=1, since=time.monotonic())
                return
            # Do not refresh probes from Python while waiting: only native
            # Blueprint Tick may observe the injected fault and abort.
            if state['phase'] in (2, 3):
                if state['phase'] == 2:
                    if body.get_editor_property('FourContactWatchState') != 3:
                        assert age < 2, 'Native watchdog did not abort within two seconds'
                        return
                    reason = ABORT_REASONS[abort_fault]
                    assert body.get_editor_property('FourContactWatchReason') == reason
                    amounts = [legs[i].get_editor_property('ExtensionPosition') for i in indices]
                    goals = [legs[i].get_editor_property('ExtensionAmount') for i in indices]
                    assert any(e > 0.05 for e in amounts)
                    assert all(e < targets[i]-0.001 for i, e in zip(indices, amounts))
                    assert max(abs(a-b) for a, b in zip(amounts, goals)) < 1e-5
                    updates = body.get_editor_property('FourContactWatchUpdates')
                    assert updates > report['injection']['updates']
                    report['watchAbort'] = dict(state=3, reason=reason, amounts=amounts, goals=goals,
                                                updates=updates, observedLatencySeconds=age, holdSamples=0)
                    state.update(phase=3, since=time.monotonic())
                    return
                abort = report['watchAbort']
                assert body.get_editor_property('FourContactWatchState') == 3
                assert body.get_editor_property(abort.get('counterName', 'FourContactWatchUpdates')) == abort['updates']
                for i, goal in zip(indices, abort['goals']):
                    assert abs(legs[i].get_editor_property('ExtensionPosition')-goal) < 1e-5
                    assert abs(legs[i].get_editor_property('ExtensionAmount')-goal) < 1e-5
                abort['holdSamples'] += 1
                if age >= 0.25 and abort['holdSamples'] >= 3:
                    restore_fault()
                    body.call_method('ReleaseExperimentalFourContact', ())
                    for i in indices:
                        body.call_method('RetractBodyLeg', (i, False))
                    state.update(phase=1, since=time.monotonic())
                return
            assert max(abs(a-b) for a, b in zip(xyz(body.get_actor_location()), xyz(lowered))) < 0.001
            for i in indices:
                leg = legs[i]
                leg.call_method('MeasureSurfaceProbe', ())
                assert leg.get_editor_property('bProbePlaneValid')
                assert sum(a*b for a, b in zip(xyz(leg.get_editor_property('ProbePlaneNormal')), normal)) > 0.99999
                assert abs(signed(xyz(leg.get_editor_property('ProbeImpactPoint')))) < 0.05
                gap = leg.get_editor_property('ProbePlaneClearance')
                old = report['minimumHeadPlaneClearanceCm']
                report['minimumHeadPlaneClearanceCm'] = gap if old is None else min(old, gap)
                assert gap >= -0.05, (i, gap)
                assert all(abs(leg.get_editor_property(f'Joint{j}Magnitude')) < 1e-6 for j in range(1, COUNT))
                assert all(abs(heads[i].get_editor_property(f'Claw{j}Position')) < 1e-6 for j in range(3))
            assert all(abs(l.get_editor_property('ExtensionPosition')) < 1e-6 for i, l in enumerate(legs) if i not in indices)
            if blueprint_request and state['phase'] == 0:
                allowed = (1, 3) if reject_final_footprint else (1, 2)
                assert body.get_editor_property('FourContactWatchState') in allowed, 'Unexpected native watchdog state'
            if reject_final_footprint and state['phase'] == 0 and body.get_editor_property('FourContactWatchState') == 3:
                assert body.get_editor_property('FourContactWatchReason') == 6
                assert body.get_editor_property('FourContactWatchRequiredMarginCm') == 1.0
                amounts = [legs[i].get_editor_property('ExtensionPosition') for i in indices]
                goals = [legs[i].get_editor_property('ExtensionAmount') for i in indices]
                assert all(abs(a-targets[i]) < 1e-6 for i, a in zip(indices, amounts))
                assert max(abs(a-b) for a, b in zip(amounts, goals)) < 1e-5
                runtime = runtime_footprint(body.get_actor_location(), 1.0)
                assert runtime == (False, False, False, 0, 0), runtime
                report['completionRejectedFootprint'] = dict(zip(
                    ('valid', 'inside', 'passesMargin', 'marginCm', 'areaCm2'), runtime))
                report['completionRejectedCandidateCount'] = body.get_editor_property('BodySupportCandidateCount')
                restore_fault()
                recovered = runtime_footprint(body.get_actor_location(), 1.0)
                assert recovered[:3] == (True, True, True), recovered
                report['completionRestoredFootprint'] = dict(zip(
                    ('valid', 'inside', 'passesMargin', 'marginCm', 'areaCm2'), recovered))
                report['watchAbort'] = dict(state=3, reason=6, amounts=amounts, goals=goals,
                                            updates=body.get_editor_property('FourContactWatchUpdates'), holdSamples=0)
                assert report['watchAbort']['updates'] > 0
                check_geometry()
                state.update(phase=3, since=time.monotonic())
                return
            if abort_mid_approach and state['phase'] == 0:
                amounts = [legs[i].get_editor_property('ExtensionPosition') for i in indices]
                if any(0.1 < e < targets[i]-0.005 for i, e in zip(indices, amounts)):
                    inject_fault()
                    state.update(phase=2, since=time.monotonic())
                elif body.get_editor_property('FourContactWatchState') == 2:
                    raise AssertionError('Need enough game ticks to inject a mid-approach fault')
            if state['phase'] == 2:
                return
            if not abort_mid_approach and not reject_final_footprint and state['phase'] == 0 and age > 3.2 and all(abs(legs[i].get_editor_property('ExtensionPosition')-targets[i]) < 1e-6 for i in indices):
                if blueprint_request:
                    assert body.get_editor_property('FourContactWatchState') == 2
                    assert body.get_editor_property('FourContactWatchUpdates') > 0
                    report['watchStateAtContact'] = 2
                    report['watchUpdatesAtContact'] = body.get_editor_property('FourContactWatchUpdates')
                points, contacts = [None]*8, []
                for i in indices:
                    leg, head = legs[i], heads[i]
                    assert abs(leg.get_editor_property('ProbePlaneClearance')) < 0.05
                    radius = 27*max(abs(v) for v in xyz(head.get_actor_scale3d()))
                    support = head_plane_clearance(xyz(head.get_actor_location()), radius,
                                                   [[xyz(v) for v in claw] for claw in claw_vertices_world(head)], point, normal)
                    points[i] = support['support']['point']
                    surface_point(points[i])
                    assert max(abs(a-b) for a, b in zip(points[i], predicted[i])) < 0.002
                    assert max(abs(a-b) for a, b in zip(points[i], xyz(leg.get_editor_property('ProbePlanePoint')))) < 0.002
                    contacts.append(dict(index=i, supportSource=support['support']['source'],
                                         point=points[i], clearanceCm=support['normalClearance'],
                                         verticalGapCm=leg.get_editor_property('ProbeGap')))
                footprint = evaluate_body_candidates(points, [i in indices for i in range(8)], xyz(body.get_actor_location()), minimum_margin=1)
                assert footprint['valid'] and footprint['passesMargin'], footprint
                report.update(contacts=contacts, footprint=footprint)
                # Offline diagnostic only: no single-leg command is issued.
                from beholder_contact_release import evaluate_four_releases
                goals_before_release_check = [leg.get_editor_property('ExtensionAmount') for leg in legs]
                report['singleContactReleaseGeometry'] = evaluate_four_releases(
                    {i: points[i] for i in indices}, xyz(body.get_actor_location()), 1.0)
                assert not report['singleContactReleaseGeometry']['geometricallyEligibleIndices'], (
                    'This symmetric fixture must not admit a single release at a 1 cm margin')
                assert goals_before_release_check == [leg.get_editor_property('ExtensionAmount') for leg in legs]
                from beholder_reference_transfer import plan_reference_transfers
                report['referenceTransferGeometry'] = plan_reference_transfers(
                    {i: points[i] for i in indices}, xyz(body.get_actor_location()),
                    minimum_margin=1.0, reserve_margin=0.1, maximum_shift=10.0)
                assert report['referenceTransferGeometry']['geometricallyFeasibleIndices'] == list(indices)
                assert not report['referenceTransferGeometry']['motionAuthorized']
                assert goals_before_release_check == [leg.get_editor_property('ExtensionAmount') for leg in legs]
                from beholder_fixed_contact_transfer import evaluate_fixed_contact_translation
                strokes = {i: tuple(v*COUNT*STROKE*legs[i].get_actor_scale3d().x
                                    for v in xyz(legs[i].get_actor_forward_vector())) for i in indices}
                extensions = {i: legs[i].get_editor_property('ExtensionPosition') for i in indices}
                origin = xyz(body.get_actor_location())
                transfer_checks = []
                for plan in report['referenceTransferGeometry']['transfers']:
                    assert plan['feasibleGeometry']
                    translation = tuple(a-b for a, b in zip(plan['proposedReferenceWorld'], origin))
                    all_four = evaluate_fixed_contact_translation(strokes, extensions, translation)
                    remaining = plan['remainingIndices']
                    after_release = evaluate_fixed_contact_translation(
                        {i: strokes[i] for i in remaining}, {i: extensions[i] for i in remaining}, translation)
                    assert not all_four['compatibleGeometry'] and not after_release['compatibleGeometry'], (
                        'Straight extension alone must not be reported as a fixed-contact body transfer')
                    transfer_checks.append(dict(removedIndex=plan['removedIndex'],
                                                fourContacts=all_four, remainingThree=after_release))
                report['fixedContactTransferGeometry'] = transfer_checks
                assert goals_before_release_check == [leg.get_editor_property('ExtensionAmount') for leg in legs]
                from beholder_stage_redistribution import plan_straight_redistribution
                redistribution = []
                for i in indices:
                    stages = [legs[i].get_editor_property(f'Stage{j}Position') for j in range(COUNT)]
                    angles = [(0, 0)]+[(legs[i].get_editor_property(f'Joint{j}Bend').x,
                                        legs[i].get_editor_property(f'Joint{j}Bend').y)
                                       for j in range(1, COUNT)]
                    plan = plan_straight_redistribution(stages, angles)
                    assert plan['valid'] and abs(plan['extension']-targets[i]) < 1e-6
                    assert len(plan['targetAvailableJoints']) == 4
                    expected_initial = 4 if legs[i].get_editor_property('bSequentialMotion') else 0
                    assert len(plan['initialAvailableJoints']) == expected_initial
                    redistribution.append(dict(index=i, sequential=legs[i].get_editor_property('bSequentialMotion'),
                                               plan=plan))
                report['stageRedistributionGeometry'] = redistribution
                assert goals_before_release_check == [leg.get_editor_property('ExtensionAmount') for leg in legs]
                from exercise_beholder_contact_ik import engine_fk_checks, inspect_leg
                report['contactIKEngineFK'] = engine_fk_checks()
                report['transferShellCertificate'] = geometry.shell_certificate()
                from generate_beholder_body import DIRECTIONS
                ik_checks = []
                for plan in report['referenceTransferGeometry']['transfers']:
                    translation = tuple(a-b for a, b in zip(plan['proposedReferenceWorld'], origin))
                    results = [dict(index=i, result=inspect_leg(legs[i], points[i], translation, point, normal,
                                    body.get_actor_transform(), tuple(1 if v > 0 else -1 for v in DIRECTIONS[i])))
                               for i in indices]
                    assert all(r['result']['converged'] and r['result']['residualWorldCm'] <= 0.01
                               and r['result']['predictedHeadPlanePasses']
                               and r['result']['predictedClawVertices'] == 12
                               and r['result']['sampledTransition']['sampledChecksPass']
                               and r['result']['sampledTransition']['continuousContactPlane']['contactAndPlaneBoundPasses']
                               for r in results)
                    ik_checks.append(dict(removedIndex=plan['removedIndex'], contacts=results))
                report['contactPositionIK'] = ik_checks
                assert goals_before_release_check == [leg.get_editor_property('ExtensionAmount') for leg in legs]
                if blueprint_request:
                    runtime = runtime_footprint(body.get_actor_location())
                    assert runtime[:3] == (True, True, True), runtime
                    assert abs(runtime[3]-footprint['marginCm']) < 0.002
                    assert abs(runtime[4]-footprint['areaCm2']) < 0.2
                    report['runtimeFootprintAtContact'] = dict(zip(
                        ('valid', 'inside', 'passesMargin', 'marginCm', 'areaCm2'), runtime))
                    p = body.get_actor_location()
                    outside = runtime_footprint(unreal.Vector(p.x+1000, p.y, p.z))
                    assert outside[:3] == (True, False, False) and outside[3] < 0
                    report['runtimeFootprintOutsideReferenceRejected'] = True
                    # A synthetic support point must not pass on a previous
                    # centre-ray hit when the actual short endpoint ray misses.
                    leg = legs[indices[-1]]
                    support_point = leg.get_editor_property('ProbePlanePoint')
                    component = next(c for c in body.get_components_by_class(unreal.ChildActorComponent)
                                     if c.get_name() == f'Leg{indices[-1]}')
                    try:
                        leg.set_editor_property('ProbePlanePoint', unreal.Vector(100000, 100000, 0))
                        ready, sampled = body.call_method('ReadExperimentalFootprintPoint', (component,))
                        assert not ready and xyz(sampled) == (0, 0, 0), 'Endpoint miss reused a point'
                    finally:
                        leg.set_editor_property('ProbePlanePoint', support_point)
                    report['runtimeFootprintSyntheticEndpointMissRejected'] = True
                    # Invalidate a previously successful live snapshot, then
                    # restore it before the next motion Tick. No goals change.
                    distance = legs[indices[0]].get_editor_property('ProbeTraceDistance')
                    try:
                        legs[indices[0]].set_editor_property('ProbeTraceDistance', 0.0)
                        assert runtime_footprint(p) == (False, False, False, 0, 0), 'Invalid probe settings reused a contour'
                    finally:
                        legs[indices[0]].set_editor_property('ProbeTraceDistance', distance)
                    assert runtime_footprint(p)[:3] == (True, True, True)
                    response = floor_component.get_collision_response_to_channel(visibility)
                    try:
                        floor_component.set_collision_response_to_channel(visibility, unreal.CollisionResponseType.ECR_IGNORE)
                        assert runtime_footprint(p) == (False, False, False, 0, 0), 'Lost floor reused a contour'
                    finally:
                        floor_component.set_collision_response_to_channel(visibility, response)
                    assert runtime_footprint(p)[:3] == (True, True, True)
                    report['runtimeFootprintLiveInvalidations'] = ['one_probe_invalid_settings', 'floor_visibility_lost']
                body.call_method('UpdateBodySurfaceProbes', ())
                report['bodyCandidateCountAtContact'] = body.get_editor_property('BodySupportCandidateCount')
                report['bodyCandidateFlagsAtContact'] = list(body.get_editor_property('BodySupportCandidates'))
                assert report['bodyCandidateCountAtContact'] == 4
                assert report['bodyCandidateFlagsAtContact'] == [i in indices for i in range(8)]
                check_geometry()
                if monitor_contacts:
                    elapsed = body.get_editor_property('FourContactWatchElapsed')
                    before_goals = [l.get_editor_property('ExtensionAmount') for l in legs]
                    report['monitor'] = dict(approachElapsed=elapsed, passiveGoals=before_goals,
                                             passiveUpdates=body.get_editor_property('FourContactWatchUpdates'), passiveSamples=0)
                    state.update(phase=8, since=time.monotonic())
                    return
                if blueprint_retraction:
                    start_retraction()
                    return
                if blueprint_request:
                    body.call_method('ReleaseExperimentalFourContact', ())
                for i in indices:
                    body.call_method('RetractBodyLeg', (i, False))
                state.update(phase=1, since=time.monotonic())
            elif state['phase'] == 1 and age > 3.2 and all(abs(legs[i].get_editor_property('ExtensionPosition')) < 1e-6 for i in indices):
                check_geometry()
                if blueprint_request:
                    assert runtime_footprint(body.get_actor_location()) == (False, False, False, 0, 0)
                    report['runtimeFootprintAfterRetractionRejected'] = True
                finish()
        except Exception as exc:
            finish(repr(exc))

    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Four-contact PIE experiment registered:', path)


if __name__ == '__main__':
    start()
