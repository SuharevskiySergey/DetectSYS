"""Read-only checks of the actual rigid-sleeve test in PIE (Unreal Python).

Verifies transforms, dimensions, bounded joint bends and conservative clearance
of generated rigid sleeves in the current PIE pose. Not a swept collision test
against the level, arbitrary replacement meshes or an organic body.
"""

import json
import importlib
import math
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / "tools"))
import generate_beholder_telescope
importlib.reload(generate_beholder_telescope)
from generate_beholder_telescope import (COUNT, LENGTH, STROKE, WALL, HEAD_OFFSET, HEAD_SCALE,
                                        fronts_from_stages, radius, stage_targets,
                                        bend_angles, joint_clearance, BEND_WALL_MARGIN,
                                        outer_hull, clip_axial_slab, head_shell_clearance,
                                        joint_targets)
from lapa5_geometry import claw_vertices_world


def close(a, b):
    return math.isclose(a, b, abs_tol=0.001)


def distance(a, b):
    return math.sqrt(sum((getattr(a, c) - getattr(b, c))**2 for c in ("x", "y", "z")))


def validate_head(actor, sleeves):
    tip = sleeves[-1]
    module = next(c for c in actor.get_components_by_class(unreal.ChildActorComponent)
                  if c.get_name() == "HeadModule")
    assert module.get_attach_parent() == tip, "HeadModule is not attached to Sleeve09"
    head = module.get_editor_property("child_actor")
    assert head is not None and head.get_class().get_name() == "BP_Lapa5_Head_C"
    expected_center = tip.get_world_transform().transform_location(unreal.Vector(HEAD_OFFSET, 0, 0))
    center_error = distance(head.get_actor_location(), expected_center)
    assert center_error < 0.001, "Head no longer follows sleeve front"
    forward = head.get_actor_up_vector()
    axis = tip.get_world_transform().rotation.rotate_vector(unreal.Vector(1, 0, 0))
    dot = sum(getattr(forward, c)*getattr(axis, c) for c in ("x", "y", "z"))
    assert dot > 0.9999, "Eye is not facing the end sleeve's +X"
    head_scale = head.get_actor_transform().scale3d
    actor_scale = actor.get_actor_transform().scale3d
    assert distance(head_scale, actor_scale*HEAD_SCALE) < 0.0001, "Unexpected head scale"
    parts = {c.get_name(): c for c in head.get_components_by_class(unreal.SceneComponent)}
    axial = []
    for vertices in claw_vertices_world(head):
        for world_point in vertices:
            axial.extend(s.get_world_transform().inverse_transform_location(world_point).x
                         for s in sleeves)
    claws = [head.get_editor_property(f"Claw{i}Position") for i in range(3)]
    assert all(0 <= c <= 1 for c in claws)
    # All vertices ahead of every sleeve lip implies their convex faces
    # cannot enter the tube walls behind any of the lips in this pose.
    assert min(axial) >= -0.001, "Claw reaches behind telescope front"
    lid = parts["Eyelid"]
    assert lid.get_editor_property("static_mesh").get_name() == "SM_Lapa5_EyelidShell"
    assert distance(lid.get_relative_transform().scale3d, unreal.Vector(1, 1, 1)) < 0.0001
    assert distance(lid.get_world_transform().translation, head.get_actor_location()) < 0.001
    assert distance(lid.get_world_transform().scale3d, head_scale) < 0.0001
    # Radius is invariant under the shell material's angular deformation.
    from generate_lapa5_lid import OUTER_RADIUS
    shell_clearance = None
    for i, sleeve in enumerate(sleeves):
        center = sleeve.get_world_transform().inverse_transform_location(head.get_actor_location())
        clearance = head_shell_clearance(i, (center.x, center.y, center.z), OUTER_RADIUS*HEAD_SCALE)
        if clearance is None:
            continue
        assert clearance > 0, f"Head shell cannot fit inside Sleeve{i:02d}"
        shell_clearance = clearance if shell_clearance is None else min(shell_clearance, clearance)
    return {"centerErrorWorldCm": center_error, "axisDot": dot,
            "claws": claws, "clawAxialClearanceChecked": True,
            "minimumClawAxialLocal": min(axial),
            "shellClearanceLowerBoundLocal": shell_clearance,
            "eyelidOpening": head.get_editor_property("EyelidPosition")}


def validate_nested_walls(sleeves):
    """Clip every descendant's solid envelope against every ancestor's slab.

    Radial norm is convex: its maximum on each clipped triangle is at a vertex.
    Staying within the ancestor's inner apothem is a conservative sufficient
    condition for no wall intersection, including the annular end faces.
    """
    minimum, checked = None, 0
    for i in range(1, COUNT):
        vertices, faces = outer_hull(i)
        world = sleeves[i].get_world_transform()
        world_vertices = [world.transform_location(unreal.Vector(*v)) for v in vertices]
        for j in range(i):
            ancestor = sleeves[j].get_world_transform()
            points = [ancestor.inverse_transform_location(v) for v in world_vertices]
            if min(p.x for p in points) > 0 or max(p.x for p in points) < -LENGTH:
                continue
            points = [(p.x, p.y, p.z) for p in points]
            maximum_radius = 0.0
            found = False
            for face in faces:
                clipped = clip_axial_slab([points[k] for k in face])
                for p in clipped:
                    found = True
                    maximum_radius = max(maximum_radius, math.hypot(p[1], p[2]))
            if found:
                checked += 1
                clearance = (radius(j)-WALL)*math.cos(math.pi/64) - maximum_radius
                assert clearance >= BEND_WALL_MARGIN-0.001, f"Sleeve{i:02d} enters Sleeve{j:02d} wall: {clearance}"
                minimum = clearance if minimum is None else min(minimum, clearance)
    return {"overlappingAxialSlabsChecked": checked, "minimumClearanceLocal": minimum}


def validate(actor=None):
    if actor is None:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        assert world is not None, "Start PIE first"
        actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                     if a.get_actor_label() == "BeholderTelescopic_Demo")
    amount = actor.get_editor_property("ExtensionPosition")
    assert 0 <= amount <= 1
    parts = {c.get_name(): c for c in actor.get_components_by_class(unreal.StaticMeshComponent)
             if c.get_name().startswith("Sleeve")}
    assert len(parts) == COUNT, "Expected ten sleeves"
    stages = [actor.get_editor_property(f"Stage{i}Position") for i in range(COUNT)]
    positions = fronts_from_stages(stages)
    assert close(amount, sum(stages)/COUNT), "Overall position is not the stage average"
    sequential = actor.get_editor_property("bSequentialMotion")
    target = actor.get_editor_property("ExtensionAmount")
    targets = stage_targets(target, sequential)
    settled = all(close(s, t) for s, t in zip(stages, targets))
    pitch = actor.get_editor_property("LiveBendPitchDegrees")
    yaw = actor.get_editor_property("LiveBendYawDegrees")
    overrides = {i: (actor.get_editor_property(f'Joint{i}PitchRequest'),
                     actor.get_editor_property(f'Joint{i}YawRequest')) for i in range(1, COUNT)
                 if actor.get_editor_property(f'bJoint{i}Override')}
    desired = joint_targets(stages, pitch, yaw, target, sequential, overrides)
    maximum_angles = bend_angles(stages, 2, 0)
    angles = [(0.0, 0.0)]
    dt = actor.get_editor_property("LastJointDeltaSeconds")
    assert math.isfinite(dt) and dt >= 0, "Invalid joint delta time"
    angular_speed = max(actor.get_editor_property("JointAngularSpeedDegrees"), 0.01)
    maximum_step = 0.0
    for i in range(1, COUNT):
        current = actor.get_editor_property(f"Joint{i}Bend")
        previous = actor.get_editor_property(f"PreviousJoint{i}Bend")
        assert abs(current.z) < 0.0001 and abs(previous.z) < 0.0001
        angle = (current.x, current.y)
        assert abs(current.x)+abs(current.y) <= maximum_angles[i][0]+0.0001, "Joint bends while nested"
        step = abs(current.x-previous.x)+abs(current.y-previous.y)
        assert step <= angular_speed*dt+0.0001, f"Joint{i}: angular speed limit exceeded"
        maximum_step = max(maximum_step, step)
        magnitude = actor.get_editor_property(f"Joint{i}Magnitude")
        assert close(magnitude, math.hypot(current.x, current.y)), "Stale retraction guard magnitude"
        angles.append(angle)
    sleeves = [parts[f"Sleeve{i:02d}"] for i in range(COUNT)]
    rows = []
    for i, part in enumerate(sleeves):
        transform = part.get_relative_transform()
        position, scale = transform.translation, transform.scale3d
        expected_rotation = unreal.Rotator(pitch=angles[i][0], yaw=angles[i][1], roll=0).quaternion()
        expected_position = expected_rotation.rotate_vector(unreal.Vector(STROKE*stages[i], 0, 0))
        assert distance(position, expected_position) < 0.001, f"Wrong relative translation: Sleeve{i:02d}"
        if i:
            assert part.get_attach_parent() == sleeves[i-1], "Broken sleeve hierarchy"
        assert all(close(getattr(scale, c), 1) for c in ("x", "y", "z")), "Sleeve is scaled"
        rotation = transform.rotation
        dot = sum(getattr(rotation, c)*getattr(expected_rotation, c) for c in ("x", "y", "z", "w"))
        assert abs(dot) > 1-1e-10, f"Wrong joint rotation: Sleeve{i:02d}"
        mesh = part.get_editor_property("static_mesh")
        box = mesh.get_bounding_box()
        assert close(box.min.x, -LENGTH) and close(box.max.x, 0), "Mesh length changed"
        assert close(box.max.y, radius(i)) and close(box.max.z, radius(i)), "Wrong mesh radius"
        assert part.get_material(0).get_name() == "M_Claw_Prototype", "Unexpected material"
        overlap = None if i == 0 else LENGTH-STROKE*stages[i]
        assert overlap is None or overlap >= 8 - 0.001, "Sleeves separated axially"
        clearance = None if i == 0 else radius(i - 1) - WALL - radius(i)
        assert clearance is None or clearance > 0, "Sleeves cannot nest"
        analytic_clearance = None if i == 0 else joint_clearance(i, stages[i], *angles[i])
        assert analytic_clearance is None or analytic_clearance >= BEND_WALL_MARGIN-0.001
        rows.append({"sleeve": i, "lengthLocal": LENGTH, "jointPitchYaw": angles[i],
                     "overlapWithParent": overlap, "nominalRadialClearance": clearance,
                     "analyticClearanceLowerBound": analytic_clearance})
    walls = validate_nested_walls(sleeves)
    head_result = validate_head(actor, sleeves)
    import validate_beholder_housing
    importlib.reload(validate_beholder_housing)
    housing_result = validate_beholder_housing.validate(actor, sleeves)
    from beholder_socket_safety import locked
    socket_locked = actor.get_editor_property("bSocketClawsLocked")
    socket_target = actor.get_editor_property("SocketTarget")
    # Lock can remain true for the arrival frame: safety runs before stages.
    if not socket_locked:
        assert not locked(stages, socket_target, sequential,
                          outside=housing_result['headOutsideConservativePlane']), "Claws unlocked away from a safe settled pose"
    socket_result = {"locked": socket_locked,
                     "headOutside": actor.get_editor_property("bSocketHeadOutside"),
                     "headCenterXBodyLocal": actor.get_editor_property("SocketHeadCenterX"),
                     "motionReady": actor.get_editor_property("bSocketMotionReady"),
                     "sampledTarget": socket_target,
                     "requestedOpening": actor.get_editor_property("SocketRequestedOpening"),
                     "requestedClaws": [actor.get_editor_property(f"SocketRequestedClaw{i}") for i in range(3)]}
    from beholder_stage_timing import step as stage_step
    previous_stages = [actor.get_editor_property(f"PreviousStage{i}Position") for i in range(COUNT)]
    stage_dt = actor.get_editor_property("LastStageDeltaSeconds")
    stage_target = actor.get_editor_property("LastStageTarget")
    stage_ready = [actor.get_editor_property(f"FrameStage{i}RetractReady") for i in range(COUNT)]
    predicted = stage_step(previous_stages, stage_target,
                           actor.get_editor_property("LastStageSequential"), stage_dt,
                           actor.get_editor_property("LastStageTransitionSeconds"), stage_ready,
                           actor.get_editor_property("LastStageMotionReady"))
    timing_error = max(abs(a-b) for a, b in zip(stages, predicted))
    assert timing_error < 0.0001, f"Stage time allocation differs from reference: {timing_error}"
    tip = actor.get_actor_transform().inverse_transform_location(sleeves[-1].get_world_transform().translation)
    return {"extension": amount, "stages": stages, "sequential": sequential,
            "head": head_result, "walls": walls, "housing": housing_result,
            "socketSafety": socket_result, "liveBendPitchYaw": [pitch, yaw],
            "stageTiming": {"deltaSeconds": stage_dt, "maximumPredictionError": timing_error},
            "motionDurations": {name: actor.get_editor_property(name) for name in
                                ('ExtensionSeconds', 'RetractionSeconds', 'EmergencyRetractionSeconds', 'TransitionSeconds')},
            "jointOverrides": overrides,
            "jointDeltaSeconds": dt, "jointAngularSpeedLimit": angular_speed,
            "maximumJointStepDegrees": maximum_step,
            "maximumJointRateDegrees": maximum_step/dt if dt else 0,
            "jointsSettledForManualTarget": all(math.hypot(a[0]-b[0], a[1]-b[1]) < 0.001
                                                for a, b in zip(angles, desired)),
            "settledManualTarget": settled, "deployedStrokeLocal": positions[-1],
            "tipPositionLocal": {c: getattr(tip, c) for c in ("x", "y", "z")}, "rigidScales": True,
            "rows": rows, "passed": True}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
