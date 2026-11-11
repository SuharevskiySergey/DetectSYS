"""Sampled offline interpolation checks, not a continuous collision proof.

Starts AFTER ideal straight stage redistribution. Body translation, stages and
bends interpolate together. Never overrides retraction guards or actuates.
"""
import math

from beholder_contact_ik import forward_contact
from beholder_support_polygon import finite_vector
from beholder_continuous_bounds import contact_plane_certificate
from generate_beholder_telescope import (COUNT, STROKE, LENGTH, BEND_WALL_MARGIN, bend_angles,
                                        joint_clearance, outer_hull, radius, retraction_allowed)

HULLS = [outer_hull(i)[0] for i in range(COUNT)]


def check_contact_path(initial_stages, final_stages, final_angles, contact_tip,
                       claw_vertices_tip, sphere_center_tip, sphere_radius_world,
                       origin_world, basis_world, translation_world, plane_point, plane_normal,
                       samples=21, contact_tolerance=0.01, plane_tolerance=0.05):
    """Check a proposed straight-to-IK interpolation at discrete fractions.

    basis_world contains three transformed local unit axes INCLUDING scale.
    Only direct-parent sleeve wall bounds and one infinite plane are tested.
    No other legs, body aperture, finite terrain, velocity or force certificate.
    """
    if type(samples) is not int or not 2 <= samples <= 1001:
        raise ValueError('Integer sample count in 2..1001 required')
    initial_stages, final_stages = tuple(initial_stages), tuple(final_stages)
    final_angles = tuple(tuple(a) for a in final_angles)
    contact_tip = finite_vector(contact_tip, 3)
    # FK validates full chain arrays and finite/bounded stages and angles.
    forward_contact(initial_stages, [(0, 0)]*COUNT, contact_tip)
    forward_contact(final_stages, final_angles, contact_tip)
    vertices = [finite_vector(v, 3) for v in claw_vertices_tip]
    if len(vertices) != 12:
        raise ValueError('Twelve calibrated claw vertices required')
    center = finite_vector(sphere_center_tip, 3)
    origin, translation = finite_vector(origin_world, 3), finite_vector(translation_world, 3)
    plane, normal = finite_vector(plane_point, 3), finite_vector(plane_normal, 3)
    basis = tuple(finite_vector(v, 3) for v in basis_world)
    if len(basis) != 3 or any(math.hypot(*v) <= 1e-9 for v in basis):
        raise ValueError('Three nonzero world basis axes required')
    # Engine actor transforms are orthogonal; reject shear/degenerate input.
    for i in range(3):
        for j in range(i):
            if abs(sum(a*b for a, b in zip(basis[i], basis[j]))) > 1e-7*math.hypot(*basis[i])*math.hypot(*basis[j]):
                raise ValueError('Orthogonal actor basis required')
    if abs(math.hypot(*normal)-1) > 1e-6:
        raise ValueError('Unit plane normal required')
    if not math.isfinite(sphere_radius_world) or sphere_radius_world <= 0:
        raise ValueError('Positive finite world sphere radius required')
    if any(not math.isfinite(t) or not 0 <= t <= 1 for t in (contact_tolerance, plane_tolerance)):
        raise ValueError('Finite tolerances in 0..1 cm required')

    def world(local, fraction):
        return tuple(origin[k]+translation[k]*fraction+sum(local[j]*basis[j][k] for j in range(3)) for k in range(3))

    def clearance(p):
        return sum((v-q)*n for v, q, n in zip(p, plane, normal))

    anchor = world(forward_contact(initial_stages, [(0, 0)]*COUNT, contact_tip), 0)
    rows = []
    target_extension = math.fsum(final_stages)/COUNT
    # The retraction guard assumes a sequential target. Verify that contract.
    from generate_beholder_telescope import stage_targets
    if any(abs(a-b) > 1e-9 for a, b in zip(final_stages, stage_targets(target_extension, True))):
        raise ValueError('Final sequential stage packing required')
    for step in range(samples):
        fraction = step/(samples-1)
        stages = [(1-fraction)*a+fraction*b for a, b in zip(initial_stages, final_stages)]
        angles = [(fraction*p, fraction*y) for p, y in final_angles]
        caps = bend_angles(stages, 2, 0)
        frames = []
        for i in range(COUNT):
            local_origin = forward_contact(stages, angles, (0, 0, 0), i)
            world_origin = world(local_origin, fraction)
            axes = []
            for j in range(3):
                point = forward_contact(stages, angles, tuple(1 if k == j else 0 for k in range(3)), i)
                axes.append(tuple(sum((point[n]-local_origin[n])*basis[n][k] for n in range(3)) for k in range(3)))
            frames.append((world_origin, axes))

        def mapped(index, point):
            position, axes = frames[index]
            return tuple(position[k]+sum(point[j]*axes[j][k] for j in range(3)) for k in range(3))

        envelope = all(abs(p)+abs(y) <= caps[i][0]+1e-9 for i, (p, y) in enumerate(angles))
        root_fixed = abs(angles[0][0])+abs(angles[0][1]) <= 1e-9
        wall = min(joint_clearance(i, stages[i], *angles[i]) for i in range(1, COUNT))
        blocked = [i for i in range(COUNT) if stages[i] > final_stages[i]+1e-9
                   and not retraction_allowed(i, stages, target_extension, True, angles)]
        error = math.dist(mapped(COUNT-1, contact_tip), anchor)
        head = min([clearance(mapped(COUNT-1, v)) for v in vertices]
                   +[clearance(mapped(COUNT-1, center))-sphere_radius_world])
        sleeve = min(clearance(mapped(i, v))
                     for i in range(COUNT) for v in HULLS[i])
        reasons = []
        for condition, reason in ((envelope and root_fixed, 'bend_envelope'),
                                  (wall >= BEND_WALL_MARGIN, 'direct_parent_wall'),
                                  (not blocked, 'retraction_interlock'),
                                  (error <= contact_tolerance, 'contact_drift'),
                                  (head >= -plane_tolerance, 'head_plane'),
                                  (sleeve >= -plane_tolerance, 'sleeve_plane')):
            if not condition:
                reasons.append(reason)
        rows.append(dict(fraction=fraction, contactDriftCm=error, headPlaneMinimumCm=head,
                         sleevePlaneMinimumCm=sleeve, directParentWallMinimumLocalCm=wall,
                         blockedRetractingStages=blocked, reasons=reasons))
    return dict(samples=rows, sampledChecksPass=all(not r['reasons'] for r in rows),
                continuousContactPlane=contact_plane_certificate(
                    initial_stages, final_stages, final_angles, contact_tip, vertices, center,
                    max(math.hypot(*v) for v in basis)*math.sqrt(1+2e-7), rows, contact_tolerance, plane_tolerance,
                    numerical_cushion=max(1e-8, 1e-12*(1+math.hypot(*origin)+math.hypot(*translation)
                        +max(math.hypot(*v) for v in basis)*(COUNT*STROKE+LENGTH+radius(0)
                            +max(math.hypot(*p) for p in vertices+[center, contact_tip]))))),
                reasons=sorted({reason for row in rows for reason in row['reasons']}),
                maximumContactDriftCm=max(r['contactDriftCm'] for r in rows),
                minimumHeadPlaneCm=min(r['headPlaneMinimumCm'] for r in rows),
                minimumSleevePlaneCm=min(r['sleevePlaneMinimumCm'] for r in rows),
                continuousCollisionCertified=False, motionAuthorized=False)
