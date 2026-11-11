"""Read-only PIE checks for the eight-branch body assembly.

Certifies each branch against the stricter single-socket free region. The new
body's inner ball and eight free cylindrical portals are independently checked
from generated triangles. Outboard convex geometry must stay in disjoint body
octants. This does not certify swept collision or physical support.
"""
from functools import lru_cache
import importlib
import json
import math
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
import generate_beholder_body
importlib.reload(generate_beholder_body)
import validate_beholder_telescope
importlib.reload(validate_beholder_telescope)
from generate_beholder_housing import CENTER_X, inner_safe_radius as single_safe
from generate_beholder_telescope import HEAD_SCALE, outer_hull
from lapa5_geometry import claw_vertices_world
from beholder_octant_clearance import outboard_margin, signed_margin


@lru_cache(maxsize=1)
def shell_certificate():
    vertices, _, _, faces = generate_beholder_body.build_body()
    inner = generate_beholder_body.inner_safe_radius(vertices, faces)
    portal = generate_beholder_body.portal_free_margin(vertices, faces)
    assert inner >= single_safe() and portal > 0
    return {'innerSafeRadius': inner, 'minimumPortalSupportMargin': portal,
            'triangles': len(faces)}


def find_body():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world, 'Start PIE first'
    return next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                if a.get_actor_label() == 'BeholderBody_Demo')


def legs(body):
    parts = {c.get_name(): c for c in body.get_components_by_class(unreal.ChildActorComponent)}
    assert set(parts) == {f'Leg{i}' for i in range(8)}
    result = [parts[f'Leg{i}'].get_editor_property('child_actor') for i in range(8)]
    assert all(result), 'Missing child leg'
    assert len({a.get_path_name() for a in result}) == 8
    return result


def distance(a, b):
    return math.sqrt((a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2)


def coordinate_map(source, target):
    origin = target.inverse_transform_location(source.translation)
    axes = [target.inverse_transform_location(source.transform_location(unreal.Vector(*a)))-origin
            for a in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    return lambda p: tuple(getattr(origin, a)+sum(p[j]*getattr(axes[j], a) for j in range(3))
                           for a in ('x', 'y', 'z'))


def validate_outboard_sector(leg, head, housing, body_transform, direction):
    signs = tuple(1 if x > 0 else -1 for x in direction)
    socket = housing.get_world_transform()
    to_body = coordinate_map(socket, body_transform)
    checked, minimum = 0, float('inf')

    def check(vertices, faces):
        nonlocal checked, minimum
        for face in faces:
            margin = outboard_margin([vertices[i] for i in face], to_body, signs)
            if margin is not None:
                checked += 1
                minimum = min(minimum, margin)
                assert margin > 0, f'{leg.get_name()}: outboard geometry leaves its separating octant'

    parts = {c.get_name(): c for c in leg.get_components_by_class(unreal.StaticMeshComponent)}
    for i in range(10):
        vertices, faces = outer_hull(i)
        transform = coordinate_map(parts[f'Sleeve{i:02d}'].get_world_transform(), socket)
        check([transform(v) for v in vertices], faces)
    for vertices in claw_vertices_world(head):
        local = [socket.inverse_transform_location(v) for v in vertices]
        check([(v.x, v.y, v.z) for v in local], ((0,1,2), (0,1,3), (0,2,3), (1,2,3)))
    center = body_transform.inverse_transform_location(head.get_actor_location())
    sphere_margin = signed_margin([(center.x, center.y, center.z)], signs)-27*HEAD_SCALE
    assert sphere_margin > 0, 'Eye/eyelid sphere leaves its separating octant'
    return {'minimumOctantMarginLocal': min(minimum, sphere_margin),
            'outboardPolygonsChecked': checked, 'sphereMarginLocal': sphere_margin}


def validate(body=None):
    body = body or find_body()
    shell = next(c for c in body.get_components_by_class(unreal.StaticMeshComponent)
                 if c.get_name() == 'BodyShell')
    mesh = shell.get_editor_property('static_mesh')
    assert mesh.get_name() == 'SM_BeholderEightSocketBody'
    assert shell.is_visible()
    assert shell.get_material(0).get_name() == 'M_Claw_Prototype'
    box = mesh.get_bounding_box()
    for axis in ('x', 'y', 'z'):
        assert abs(getattr(box.min, axis)+200) < 0.001
        assert abs(getattr(box.max, axis)-200) < 0.001
    world = body.get_actor_transform()
    scale = world.scale3d
    assert min(scale.x, scale.y, scale.z) > 0 and max(scale.x, scale.y, scale.z)-min(scale.x, scale.y, scale.z) < 1e-6, 'Sector certificate requires positive uniform body scale'
    assert distance(shell.get_world_transform().translation, world.translation) < 0.001
    rows, heads, lids = [], set(), set()
    for i, leg in enumerate(legs(body)):
        direction = generate_beholder_body.DIRECTIONS[i]
        transform = leg.get_actor_transform()
        location = world.inverse_transform_location(transform.translation)
        expected = unreal.Vector(*(-CENTER_X*x for x in direction))
        assert distance(location, expected) < 0.001, f'Leg{i}: wrong cube-diagonal root'
        point = world.inverse_transform_location(transform.transform_location(unreal.Vector(1, 0, 0)))
        axis = point-location
        assert abs(axis.x*direction[0]+axis.y*direction[1]+axis.z*direction[2]-1) < 0.00001
        housing = next(c for c in leg.get_components_by_class(unreal.StaticMeshComponent)
                       if c.get_name() == 'SocketHousing')
        assert not housing.is_visible(), f'Leg{i}: duplicate single-socket body is still visible'
        assert distance(housing.get_world_transform().translation, world.translation) < 0.001
        head = next(c for c in leg.get_components_by_class(unreal.ChildActorComponent)
                    if c.get_name() == 'HeadModule').get_editor_property('child_actor')
        assert head and head.get_path_name() not in heads, 'Heads are not independent instances'
        heads.add(head.get_path_name())
        lid = next(c for c in head.get_components_by_class(unreal.StaticMeshComponent)
                   if c.get_name() == 'Eyelid').get_material(0)
        assert lid and lid.get_class().get_name() == 'MaterialInstanceDynamic'
        assert lid.get_path_name() not in lids, 'Eyelid materials are shared between heads'
        lids.add(lid.get_path_name())
        result = validate_beholder_telescope.validate(leg)
        sector = validate_outboard_sector(leg, head, housing, world, direction)
        octant_margin = None
        if result['extension'] < 1e-6:
            center = world.inverse_transform_location(head.get_actor_location())
            signs = [1 if x > 0 else -1 for x in direction]
            octant_margin = min(getattr(center, a)*s-27*HEAD_SCALE for a, s in zip(('x','y','z'), signs))
            for claw in claw_vertices_world(head):
                for vertex in claw:
                    p = world.inverse_transform_location(vertex)
                    octant_margin = min(octant_margin, *(getattr(p, a)*s for a, s in zip(('x','y','z'), signs)))
            assert octant_margin > 0, 'Folded head geometry leaves its own octant and may meet a neighbour'
        rows.append({'index': i, 'extension': result['extension'], 'claws': result['head']['claws'],
                     'eyelid': result['head']['eyelidOpening'], 'housing': result['housing'],
                     'foldedHeadOctantMargin': octant_margin,
                     'outboardSector': sector,
                     'passed': result['passed']})
    return {'certificate': shell_certificate(), 'legs': rows, 'passed': True}


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
