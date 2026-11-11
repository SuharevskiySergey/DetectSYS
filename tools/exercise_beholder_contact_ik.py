"""Read-only Unreal cross-checks and offline IK at captured live contacts."""
import math

import unreal

from beholder_contact_ik import forward_contact, solve_contact_position
from generate_beholder_telescope import COUNT, STROKE, bend_angles, stage_targets
from lapa5_geometry import claw_vertices_world
from beholder_contact_path import check_contact_path


def xyz(v):
    return (v.x, v.y, v.z)


def engine_fk_checks():
    maximum = 0.0
    cases = 0
    for extension in (0, 0.5, 0.999, 1):
        stages = stage_targets(extension, True)
        for pitch, yaw in ((0, 0), (1.2, 0.8), (-1.5, 0.5), (0.3, -1.7)):
            angles = bend_angles(stages, pitch, yaw)
            tip = (56, 12, -17)
            point = unreal.Vector(*tip)
            for i in reversed(range(COUNT)):
                point = unreal.Rotator(pitch=angles[i][0], yaw=angles[i][1], roll=0).quaternion().rotate_vector(
                    point+unreal.Vector(STROKE*stages[i], 0, 0))
            error = math.dist(xyz(point), forward_contact(stages, angles, tip))
            # Unreal Python Rotator/Vector conversion introduces float rounding.
            assert error < 1e-4, (extension, pitch, yaw, error)
            maximum = max(maximum, error)
            cases += 1
    return dict(cases=cases, maximumLocalErrorCm=maximum)


def inspect_leg(leg, contact_world, translation_world, plane_point, plane_normal, body_transform, octant_signs):
    """Never set transforms, joint requests, stage positions or extension goals."""
    sleeves = {c.get_name(): c for c in leg.get_components_by_class(unreal.StaticMeshComponent)}
    actor_transform = leg.get_actor_transform()
    contact = unreal.Vector(*contact_world)
    tip = sleeves['Sleeve09'].get_world_transform().inverse_transform_location(contact)
    local_contact = actor_transform.inverse_transform_location(contact)
    stages = [leg.get_editor_property(f'Stage{i}Position') for i in range(COUNT)]
    angles = [(0, 0)]+[xyz(leg.get_editor_property(f'Joint{i}Bend'))[:2] for i in range(1, COUNT)]
    model = forward_contact(stages, angles, xyz(tip))
    error = math.dist(model, xyz(local_contact))
    assert error < 1e-4, ('Live FK mismatch', error)
    translated_target_world = contact-unreal.Vector(*translation_world)
    target = actor_transform.inverse_transform_location(translated_target_world)
    result = solve_contact_position(sum(stages)/COUNT, xyz(tip), xyz(target))
    reconstructed_world = actor_transform.transform_location(unreal.Vector(*result['pointLocal']))+unreal.Vector(*translation_world)
    result.update(liveFKErrorLocalCm=error, tipPointLocal=xyz(tip),
                  residualWorldCm=math.dist(xyz(reconstructed_world), contact_world),
                  initialStages=stages, translationWorld=translation_world)
    head = next(c for c in leg.get_components_by_class(unreal.ChildActorComponent)
                if c.get_name() == 'HeadModule').get_editor_property('child_actor')
    tip_transform = sleeves['Sleeve09'].get_world_transform()

    def predicted_world(world_point):
        local = tip_transform.inverse_transform_location(world_point)
        predicted = forward_contact(result['stages'], result['angles'], xyz(local))
        return xyz(actor_transform.transform_location(unreal.Vector(*predicted))+unreal.Vector(*translation_world))

    def clearance(p):
        return sum((v-q)*n for v, q, n in zip(p, plane_point, plane_normal))

    vertices = [predicted_world(v) for claw in claw_vertices_world(head) for v in claw]
    center = predicted_world(head.get_actor_location())
    radius = 27*max(abs(v) for v in xyz(head.get_actor_scale3d()))
    minimum = min([clearance(v) for v in vertices]+[clearance(center)-radius])
    result.update(predictedHeadPlaneMinimumCm=minimum, predictedClawVertices=len(vertices),
                  predictedHeadPlanePasses=minimum >= -0.05,
                  headPlaneCheckIsEndpointOnly=True)
    origin = xyz(actor_transform.transform_location(unreal.Vector(0, 0, 0)))
    basis = []
    for j in range(3):
        axis = xyz(actor_transform.transform_location(unreal.Vector(*(1 if k == j else 0 for k in range(3)))))
        basis.append(tuple(v-o for v, o in zip(axis, origin)))
    result['sampledTransition'] = check_contact_path(
        initial_stages=stage_targets(sum(stages)/COUNT, True), final_stages=result['stages'],
        final_angles=result['angles'], contact_tip=xyz(tip),
        claw_vertices_tip=[xyz(tip_transform.inverse_transform_location(v))
                           for claw in claw_vertices_world(head) for v in claw],
        sphere_center_tip=xyz(tip_transform.inverse_transform_location(head.get_actor_location())),
        sphere_radius_world=radius, origin_world=origin, basis_world=basis,
        translation_world=translation_world, plane_point=plane_point, plane_normal=plane_normal)
    # Capture rigid geometry for slower offline shell checks outside PIE ticks.
    socket = sleeves['SocketHousing'].get_world_transform()
    socket_origin = body_transform.inverse_transform_location(socket.translation)
    socket_axes = [xyz(body_transform.inverse_transform_location(socket.transform_location(unreal.Vector(*v)))-socket_origin)
                   for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    result['shellGeometryInput'] = dict(
        claw_vertices_tip=[xyz(tip_transform.inverse_transform_location(v))
                           for claw in claw_vertices_world(head) for v in claw],
        sphere_center_tip=xyz(tip_transform.inverse_transform_location(head.get_actor_location())),
        sphere_radius_local=radius/abs(actor_transform.scale3d.x),
        socket_origin_body=xyz(socket_origin), socket_axes_body=socket_axes, octant_signs=octant_signs)
    return result
