"""Read-only distance-limit check in a running PIE world (Unreal Python).

Call SetTargetLocal, let the rig update, then run this file. It verifies the
actual Blueprint diagnostics and mesh endpoint, not a standalone copy of its
math. This is NOT collision, spline-length or joint-reachability validation.
"""

import json
import math

import unreal


def length(vector):
    return math.sqrt(vector.x ** 2 + vector.y ** 2 + vector.z ** 2)


def xyz(vector):
    return {axis: getattr(vector, axis) for axis in ("x", "y", "z")}


def validate():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world is not None, "Start PIE before running this check"
    actors = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
              if a.get_actor_label() == "BeholderLeg_Demo"]
    assert len(actors) == 1, "Expected one BeholderLeg_Demo in PIE"
    actor = actors[0]
    raw = actor.get_editor_property("RequestedTargetLocal")
    live = actor.get_editor_property("LiveTargetLocal")
    maximum = max(actor.get_editor_property("MaxTargetDistance"), 1.0)
    raw_length = length(raw)
    assert math.isfinite(raw_length), "Non-finite requested target"
    extension = actor.get_editor_property("ExtensionPosition")
    assert 0 <= extension <= 1, "Extension out of range"
    expected = raw * (min(1.0, maximum / raw_length) * extension) if raw_length > 0 else raw
    assert length(live - expected) < 0.001, "Live target is not the radial clamp"
    assert length(live) <= maximum + 0.001, "Distance limit exceeded"
    reported_distance = actor.get_editor_property("RequestedTargetDistance")
    assert math.isclose(reported_distance, raw_length, rel_tol=1e-6, abs_tol=0.001)
    clamped = actor.get_editor_property("bTargetDistanceClamped")
    assert clamped == (raw_length > maximum), "Wrong distance-clamped flag"
    solver = actor.get_editor_property("SolverTargetLocal")
    near_base = actor.get_editor_property("bNearBaseFallback")
    assert near_base == (length(live) < 1.0), "Wrong near-base flag"
    direction = raw / raw_length if raw_length >= 0.0001 else unreal.Vector(1, 0, 0)
    alignment_start = min(1.0, max(0.01, actor.get_editor_property("SocketAlignmentStart")))
    t = min(1.0, max(0.0, 1 - extension / alignment_start))
    enabled = actor.get_editor_property("bAlignRetractionToSocket")
    weight = t * t * (3 - 2 * t) if enabled else 0.0
    reported_weight = actor.get_editor_property("SocketAlignmentWeight")
    assert math.isclose(weight, reported_weight, abs_tol=1e-5), "Wrong socket blend weight"
    axis = actor.get_editor_property("SocketAxisLocal")
    origin = unreal.Vector(0, 0, 0)
    target_rotation = unreal.MathLibrary.find_look_at_rotation(origin, direction)
    socket_rotation = unreal.MathLibrary.find_look_at_rotation(origin, axis)
    rotation = unreal.MathLibrary.r_lerp(target_rotation, socket_rotation, weight, True)
    direction = unreal.MathLibrary.get_forward_vector(rotation)
    reported_direction = actor.get_editor_property("SolverDirectionLocal")
    assert length(reported_direction - direction) < 0.0001, "Wrong aligned direction"
    expected_solver = direction * max(length(live), 1.0)
    assert length(solver - expected_solver) < 0.001, "Wrong non-degenerate solver target"
    bend = actor.get_editor_property("BendOffset")
    live_bend = actor.get_editor_property("LiveBendOffset")
    fade_distance = max(actor.get_editor_property("BendFadeDistance"), 1.0)
    bend_scale = extension * min(1.0, max(0.0, (length(live) - 1) / fade_distance)) * (1 - weight)
    assert length(live_bend - bend * bend_scale) < 0.001, "Wrong bend attenuation"
    rig = next(c for c in actor.get_components_by_class(unreal.ControlRigComponent)
               if c.get_name() == "ControlRig")
    mesh = next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                if c.get_name() == "SKM_Tenticle")
    world_target = rig.get_world_transform().transform_location(live)
    endpoint = mesh.get_socket_location("EyeTip")
    endpoint_error = length(endpoint - world_target)
    solver_error = length(endpoint - rig.get_world_transform().transform_location(solver))
    module = next(c for c in actor.get_components_by_class(unreal.ChildActorComponent)
                  if c.get_name() == "HeadModule")
    head = module.get_editor_property("child_actor")
    assert head is not None, "HeadModule has no child actor"
    assert length(head.get_actor_location() - endpoint) < 0.001, "Head detached from EyeTip"
    world_axis = rig.get_world_transform().rotation.rotate_vector(
        unreal.MathLibrary.get_forward_vector(socket_rotation))
    head_forward = head.get_actor_up_vector()  # Local +Z is the eye's facing axis.
    facing_dot = sum(getattr(world_axis, c) * getattr(head_forward, c) for c in ("x", "y", "z"))
    if weight >= 0.99999:
        assert facing_dot > 0.9999, "Retracted head is not aligned with socket axis"
    # Report endpoint quality separately: a radial limit is not an IK solver.
    # In particular the existing spline fit cannot reliably reach the origin.
    return {"requested": xyz(raw), "live": xyz(live), "maximum": maximum,
            "extension": extension, "solver": xyz(solver), "nearBase": near_base,
            "alignmentWeight": reported_weight, "solverDirection": xyz(reported_direction),
            "headSocketAxisDot": facing_dot,
            "liveBend": xyz(live_bend), "solverEndpointErrorCm": solver_error,
            "solverEndpointWithinOneCm": solver_error < 1.0,
            "clamped": clamped, "eyeTipWorld": xyz(endpoint),
            "endpointErrorCm": endpoint_error,
            "endpointWithinOneCm": endpoint_error < 1.0,
            "distanceLimitPassed": True}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
