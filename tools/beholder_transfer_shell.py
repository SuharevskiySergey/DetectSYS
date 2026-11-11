"""Sampled branch-vs-housing and separating-octant diagnostics, offline only.

Reuses the existing conservative free ball/cylinder and clipped octant tests.
Does NOT test nonadjacent sleeves against each other or continuous trajectories.
"""
import math

from beholder_contact_ik import forward_contact
from beholder_octant_clearance import signed_margin
from beholder_support_polygon import finite_vector
from generate_beholder_housing import (CENTER_X, PORTAL_START_X, OUTER_RADIUS,
                                      PORTAL_RADIUS, inner_safe_radius, sphere_clearance)
from generate_beholder_telescope import COUNT, clip_axial_slab, outer_hull

HULLS = [outer_hull(i) for i in range(COUNT)]
CLAW_FACES = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))


def check_branch_pose(stages, angles, claw_vertices_tip, sphere_center_tip, sphere_radius_local,
                      socket_origin_body, socket_axes_body, octant_signs):
    """All dimensions are unscaled actor/socket/body local cm.

    Requires the project's certified shell and a rigid unit-scale socket/body
    map. Same geometry/assumptions as validate_beholder_body, not a mesh query.
    """
    claws = [finite_vector(v, 3) for v in claw_vertices_tip]
    if len(claws) != 12:
        raise ValueError('Twelve claw vertices required')
    center = finite_vector(sphere_center_tip, 3)
    origin = finite_vector(socket_origin_body, 3)
    axes = tuple(finite_vector(v, 3) for v in socket_axes_body)
    signs = tuple(octant_signs)
    if len(signs) != 3 or any(type(s) is not int or s not in (-1, 1) for s in signs):
        raise ValueError('Three integer octant signs required')
    if len(axes) != 3 or any(abs(math.hypot(*v)-1) > 1e-6 for v in axes):
        raise ValueError('Rigid unit-scale socket/body map required')
    if any(abs(sum(a*b for a, b in zip(axes[i], axes[j]))) > 1e-6 for i in range(3) for j in range(i)):
        raise ValueError('Orthogonal socket/body map required')
    if not math.isfinite(sphere_radius_local) or not 0 < sphere_radius_local <= 1e6:
        raise ValueError('Positive bounded sphere radius required')
    # Validate arrays and build sleeve affine frames once per pose.
    frames = []
    for i in range(COUNT):
        point = forward_contact(stages, angles, (0, 0, 0), i)
        basis = []
        for j in range(3):
            p = forward_contact(stages, angles, tuple(1 if k == j else 0 for k in range(3)), i)
            basis.append(tuple(a-b for a, b in zip(p, point)))
        frames.append((point, basis))

    def to_socket(index, vertex):
        p, basis = frames[index]
        result = [p[k]+sum(vertex[j]*basis[j][k] for j in range(3)) for k in range(3)]
        result[0] -= CENTER_X
        return tuple(result)

    def to_body(p):
        return tuple(origin[k]+sum(p[j]*axes[j][k] for j in range(3)) for k in range(3))

    margins = dict(interior=None, portal=None, outboard=None)
    checked = 0

    def record(name, value):
        if not math.isfinite(value):
            raise ValueError('Nonfinite shell clearance')
        margins[name] = value if margins[name] is None else min(margins[name], value)

    free = inner_safe_radius()

    def check(vertices, faces):
        nonlocal checked
        for face in faces:
            triangle = [vertices[i] for i in face]
            checked += 1
            for p in clip_axial_slab(triangle, -1e8, PORTAL_START_X):
                record('interior', free-math.hypot(*p))
            for p in clip_axial_slab(triangle, PORTAL_START_X, OUTER_RADIUS):
                record('portal', PORTAL_RADIUS-math.hypot(p[1], p[2]))
            outside = clip_axial_slab(triangle, PORTAL_START_X, 1e9)
            if outside:
                record('outboard', signed_margin([to_body(p) for p in outside], signs))

    for i, (vertices, faces) in enumerate(HULLS):
        check([to_socket(i, v) for v in vertices], faces)
    vertices = [to_socket(COUNT-1, v) for v in claws]
    for i in range(3):
        check(vertices[4*i:4*i+4], CLAW_FACES)
    sphere_center = to_socket(COUNT-1, center)
    sphere = sphere_clearance(sphere_center, sphere_radius_local)
    sphere_octant = signed_margin([to_body(sphere_center)], signs)-sphere_radius_local
    reasons = []
    for condition, reason in ((margins['interior'] is None or margins['interior'] >= -0.001, 'inner_cavity'),
                              (margins['portal'] is None or margins['portal'] >= -0.001, 'portal'),
                              (margins['outboard'] is None or margins['outboard'] > 0, 'outboard_octant'),
                              (sphere['interior'] is None or sphere['interior'] >= -0.001, 'sphere_cavity'),
                              (sphere['portal'] is None or sphere['portal'] >= -0.1, 'sphere_portal'),
                              (sphere_octant > 0, 'sphere_octant')):
        if not condition:
            reasons.append(reason)
    return dict(passed=not reasons, reasons=reasons, marginsLocalCm=margins,
                sphereClearanceLocalCm=sphere, sphereOctantMarginLocalCm=sphere_octant,
                trianglesChecked=checked, motionAuthorized=False, continuousCollisionCertified=False)


def check_transfer(initial_stages, final_stages, final_angles, geometry, samples=21):
    if type(samples) is not int or not 2 <= samples <= 1001:
        raise ValueError('Integer sample count in 2..1001 required')
    # Validate both endpoints before zip interpolation could truncate inputs.
    forward_contact(initial_stages, [(0, 0)]*COUNT, (0, 0, 0))
    forward_contact(final_stages, final_angles, (0, 0, 0))
    rows = []
    for k in range(samples):
        f = k/(samples-1)
        stages = [(1-f)*a+f*b for a, b in zip(initial_stages, final_stages)]
        angles = [(f*p, f*y) for p, y in final_angles]
        rows.append(dict(fraction=f, **check_branch_pose(stages, angles, **geometry)))
    return dict(passed=all(r['passed'] for r in rows), samples=rows,
                reasons=sorted({reason for row in rows for reason in row['reasons']}),
                motionAuthorized=False, continuousCollisionCertified=False)
