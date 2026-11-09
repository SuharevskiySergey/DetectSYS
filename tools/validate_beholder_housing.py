"""Read-only one-socket body seating checks in PIE (Unreal editor Python).

Conservative bounds for the generated shell and rigid sleeve envelopes. This
does not implement a physical collider, a motion interlock or a swept test.
"""

import importlib
import json
import math
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / "tools"))
import generate_beholder_housing
importlib.reload(generate_beholder_housing)
from generate_beholder_housing import (CENTER_X, OUTER_RADIUS, OUTER_LIP_X, INNER_LIP_X,
                                      PORTAL_SLOPE, APERTURE_ANGLE, inner_safe_radius,
                                      sphere_clearance)
from generate_beholder_telescope import outer_hull, clip_axial_slab, HEAD_SCALE
from lapa5_geometry import claw_vertices_world


def length(p):
    return math.sqrt(sum(x*x for x in p))


def validate(actor=None, sleeves=None):
    if actor is None:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        assert world is not None, "Start PIE first"
        actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                     if a.get_actor_label() == "BeholderTelescopic_Demo")
    components = {c.get_name(): c for c in actor.get_components_by_class(unreal.StaticMeshComponent)}
    housing = components["SocketHousing"]
    assert housing.get_editor_property("static_mesh").get_name() == "SM_BeholderSocketBody"
    assert housing.get_material(0).get_name() == "M_Claw_Prototype"
    relative = housing.get_relative_transform()
    assert abs(relative.translation.x-CENTER_X) < 0.001
    assert abs(relative.translation.y)+abs(relative.translation.z) < 0.001
    assert all(abs(getattr(relative.scale3d, c)-1) < 0.0001 for c in ("x", "y", "z"))
    assert all(abs(getattr(relative.rotation, c)) < 1e-6 for c in ("x", "y", "z"))
    box = housing.get_editor_property("static_mesh").get_bounding_box()
    assert abs(box.min.x+OUTER_RADIUS) < 0.001
    assert abs(box.max.x-OUTER_RADIUS*math.cos(APERTURE_ANGLE)) < 0.001
    sleeves = sleeves or [components[f"Sleeve{i:02d}"] for i in range(10)]
    body = housing.get_world_transform()
    free = inner_safe_radius()
    interior_min = portal_min = None
    max_radius = 0.0
    sleeve_max_radius = 0.0
    triangle_count = 0

    def check(vertices, faces, label):
        nonlocal interior_min, portal_min, max_radius, triangle_count
        points = [body.inverse_transform_location(v) for v in vertices]
        points = [(p.x, p.y, p.z) for p in points]
        max_radius = max(max_radius, max(length(p) for p in points))
        for face in faces:
            triangle_count += 1
            triangle = [points[i] for i in face]
            for p in clip_axial_slab(triangle, -1e8, INNER_LIP_X):
                clearance = free-length(p)
                assert clearance >= -0.001, f"{label}: outside the safe inner cavity ({clearance} cm)"
                interior_min = clearance if interior_min is None else min(interior_min, clearance)
            for p in clip_axial_slab(triangle, INNER_LIP_X, OUTER_RADIUS):
                clearance = PORTAL_SLOPE*p[0]-math.hypot(p[1], p[2])
                assert clearance >= -0.001, f"{label}: does not fit the body aperture ({clearance} cm)"
                portal_min = clearance if portal_min is None else min(portal_min, clearance)

    for i, sleeve in enumerate(sleeves):
        vertices, faces = outer_hull(i)
        world = sleeve.get_world_transform()
        check([world.transform_location(unreal.Vector(*v)) for v in vertices], faces, f"Sleeve{i:02d}")
    sleeve_max_radius = max_radius
    module = next(c for c in actor.get_components_by_class(unreal.ChildActorComponent)
                  if c.get_name() == "HeadModule")
    head = module.get_editor_property("child_actor")
    assert head is not None
    center = body.inverse_transform_location(head.get_actor_location())
    import beholder_socket_safety
    importlib.reload(beholder_socket_safety)
    max_claw_radius = 0.0
    for i, vertices in enumerate(claw_vertices_world(head)):
        check(vertices, [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)], f"Claw{i}")
        for vertex in vertices:
            point = body.inverse_transform_location(vertex)
            max_claw_radius = max(max_claw_radius, length((point.x-center.x, point.y-center.y, point.z-center.z)))
    assert max_claw_radius <= beholder_socket_safety.HEAD_FREE_ENVELOPE_RADIUS, 'Claw exceeds the certified free envelope'
    sphere = sphere_clearance((center.x, center.y, center.z), 27*HEAD_SCALE)
    assert all(v is None or v >= -0.001 for v in sphere.values()), f"Eye shell intersects housing: {sphere}"
    amount = actor.get_editor_property("ExtensionPosition")
    folded_inside = folded_margin = equator_error = exposed_fraction = None
    if amount < 0.00001:
        folded_margin = free-sleeve_max_radius
        folded_inside = folded_margin > 0
        assert folded_inside, "Folded sleeve pack is not fully inside the inner body envelope"
        equator_error = abs(center.x-OUTER_LIP_X)
        assert equator_error < 0.001, "Head sphere is not seated at the outer lip equator"
        assert math.hypot(center.y, center.z) < 0.001, "Folded head is off the socket axis"
        # Spherical cap surface-area fraction ahead of the planar outer lip.
        exposed_fraction = (1+(center.x-OUTER_LIP_X)/(27*HEAD_SCALE))/2
        assert abs(exposed_fraction-0.5) < 0.0001
        assert all(head.get_editor_property(f'Claw{i}Position') <= beholder_socket_safety.SEATED_CLAW_OPENING_MAX+0.00001
                   for i in range(3)), 'Seated claw exceeds the certified opening limit'
    return {"extension": amount, "innerSafeRadiusLocal": free,
            "minimumInteriorClearanceLocal": interior_min,
            "minimumPortalClearanceLocal": portal_min,
            "shellBounds": sphere, "trianglesChecked": triangle_count,
            "foldedSleevesFullyInside": folded_inside, "foldedSleeveMarginLocal": folded_margin,
            "foldedEquatorErrorLocal": equator_error,
            "foldedSphereExposedAreaFraction": exposed_fraction,
            "headCenterXBodyLocal": center.x,
            "headOutsideConservativePlane": beholder_socket_safety.head_outside(center.x),
            "maximumClawRadiusLocal": max_claw_radius,
            "passed": True}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
