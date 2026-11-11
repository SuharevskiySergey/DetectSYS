"""Offline sufficient hollow-sleeve nesting check, including nonadjacent pairs.

Descendant outer envelopes clipped to an ancestor axial slab must fit inside
its inner apothem. A failed bound is NOT proof of an actual mesh collision.
Uses the same geometric bound as validate_beholder_telescope, no actuation.
"""
import math

from beholder_contact_ik import forward_contact
from beholder_support_polygon import finite_vector
from generate_beholder_telescope import (COUNT, LENGTH, WALL, BEND_WALL_MARGIN,
                                        clip_axial_slab, outer_hull, radius, head_shell_clearance)

HULLS = [outer_hull(i) for i in range(COUNT)]


def check_nested_pose(stages, angles, required_margin=BEND_WALL_MARGIN, head_geometry=None):
    if not math.isfinite(required_margin) or required_margin < BEND_WALL_MARGIN:
        raise ValueError('Finite margin at least the existing wall margin required')
    frames = []
    for i in range(COUNT):
        origin = forward_contact(stages, angles, (0, 0, 0), i)
        axes = []
        for j in range(3):
            point = forward_contact(stages, angles, tuple(1 if k == j else 0 for k in range(3)), i)
            axes.append(tuple(a-b for a, b in zip(point, origin)))
        frames.append((origin, axes))

    def to_actor(index, point):
        origin, axes = frames[index]
        return tuple(origin[k]+sum(point[j]*axes[j][k] for j in range(3)) for k in range(3))

    rows = []
    for child in range(1, COUNT):
        vertices, faces = HULLS[child]
        actor_points = [to_actor(child, v) for v in vertices]
        for parent in range(child):
            origin, axes = frames[parent]
            points = [tuple(sum((p[k]-origin[k])*axis[k] for k in range(3)) for axis in axes)
                      for p in actor_points]
            row = dict(child=child, ancestor=parent, adjacent=child == parent+1,
                       overlappingSlab=False, clearanceLocalCm=None, boundPasses=True)
            rows.append(row)
            if min(p[0] for p in points) > 0 or max(p[0] for p in points) < -LENGTH:
                continue
            maximum = None
            for face in faces:
                clipped = clip_axial_slab([points[i] for i in face])
                for p in clipped:
                    distance = math.hypot(p[1], p[2])
                    maximum = distance if maximum is None else max(maximum, distance)
            if maximum is None:
                continue
            clearance = (radius(parent)-WALL)*math.cos(math.pi/64)-maximum
            if not math.isfinite(clearance):
                raise ValueError('Nonfinite nested clearance')
            row.update(overlappingSlab=True, clearanceLocalCm=clearance,
                       boundPasses=clearance >= required_margin)
    margins = [row['clearanceLocalCm'] for row in rows if row['overlappingSlab']]
    head = None
    if head_geometry is not None:
        vertices = [finite_vector(v, 3) for v in head_geometry['claw_vertices_tip']]
        if len(vertices) != 12:
            raise ValueError('Twelve claw vertices required')
        center = finite_vector(head_geometry['sphere_center_tip'], 3)
        sphere_radius = head_geometry['sphere_radius_local']
        if not math.isfinite(sphere_radius) or not 0 < sphere_radius <= 1e6:
            raise ValueError('Positive finite bounded head radius required')
        head_vertices = [to_actor(COUNT-1, v) for v in vertices]
        head_center = to_actor(COUNT-1, center)
        axial, shell_margins = [], []
        for i, (origin, axes) in enumerate(frames):
            def to_sleeve(p):
                return tuple(sum((p[k]-origin[k])*axis[k] for k in range(3)) for axis in axes)
            axial.extend(to_sleeve(p)[0] for p in head_vertices)
            clearance = head_shell_clearance(i, to_sleeve(head_center), sphere_radius)
            if clearance is not None:
                shell_margins.append(clearance)
        head = dict(minimumClawAxialLocalCm=min(axial),
                    minimumShellClearanceLocalCm=min(shell_margins) if shell_margins else None,
                    passed=min(axial) >= -0.001 and all(c > 0 for c in shell_margins))
    return dict(passed=all(row['boundPasses'] for row in rows) and (head is None or head['passed']), pairs=rows,
                head=head, headChecked=head is not None,
                overlappingPairs=sum(row['overlappingSlab'] for row in rows),
                nonadjacentOverlappingPairs=sum(row['overlappingSlab'] and not row['adjacent'] for row in rows),
                minimumClearanceLocalCm=min(margins) if margins else None,
                requiredMarginLocalCm=required_margin, motionAuthorized=False,
                continuousCollisionCertified=False)


def check_nested_transfer(initial_stages, final_stages, final_angles, samples=21, head_geometry=None):
    if type(samples) is not int or not 2 <= samples <= 1001:
        raise ValueError('Integer sample count in 2..1001 required')
    forward_contact(initial_stages, [(0, 0)]*COUNT, (0, 0, 0))
    forward_contact(final_stages, final_angles, (0, 0, 0))
    rows = []
    for k in range(samples):
        f = k/(samples-1)
        stages = [(1-f)*a+f*b for a, b in zip(initial_stages, final_stages)]
        angles = [(f*p, f*y) for p, y in final_angles]
        rows.append(dict(fraction=f, **check_nested_pose(stages, angles, head_geometry=head_geometry)))
    margins = [row['minimumClearanceLocalCm'] for row in rows if row['minimumClearanceLocalCm'] is not None]
    return dict(passed=all(row['passed'] for row in rows), samples=rows,
                minimumClearanceLocalCm=min(margins) if margins else None,
                motionAuthorized=False, continuousCollisionCertified=False)
