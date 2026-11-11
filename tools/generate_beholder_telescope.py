"""Rigid hollow sleeves for the isolated straight telescopic test, in cm.

Each mesh spans X=-112..0. Only its translation changes during deployment.
Ten equal-length sleeves have decreasing radii, 0.75 cm radial clearance and
8 cm axial overlap at full stroke. This is not the final organic leg model.
"""

import math
from pathlib import Path

COUNT = 10
LENGTH = 112.0
STROKE = 104.0
WALL = 1.25
RADIUS_STEP = 2.0
HEAD_OFFSET = 56.0
HEAD_SCALE = 60.0/27.0
MAX_JOINT_BEND_DEGREES = 2.0
BEND_EXPOSURE_START = 0.98
BEND_WALL_MARGIN = 0.25


def head_shell_clearance(index, center, shell_radius):
    """Conservative sphere clearance inside the sleeve's axial slab only."""
    x, y, z = center
    nearest = min(0.0, max(-LENGTH, x))
    axial_distance = abs(x-nearest)
    if axial_distance > shell_radius:
        return None
    section_radius = math.sqrt(max(0.0, shell_radius**2-axial_distance**2))
    return (radius(index)-WALL)*math.cos(math.pi/64) - math.hypot(y, z) - section_radius


def bend_angles(stages, pitch, yaw, overrides=None):
    """Conservative per-joint angles, matching the Blueprint's authoring math."""
    if len(stages) != COUNT or any(not 0 <= s <= 1 for s in stages):
        raise ValueError("Ten stage positions in 0..1 required")
    overrides = overrides or {}
    if any(i not in range(1, COUNT) for i in overrides):
        raise ValueError('Only joints 1..9 can override the global bend')
    result = [(0.0, 0.0)]  # Root stays on the socket axis.
    for i in range(1, COUNT):
        local_pitch, local_yaw = overrides.get(i, (pitch, yaw))
        scale = min(1.0, MAX_JOINT_BEND_DEGREES / max(abs(local_pitch) + abs(local_yaw), 0.0001))
        t = min(1.0, max(0.0, (min(stages[i-1], stages[i])-BEND_EXPOSURE_START)
                         / (1-BEND_EXPOSURE_START)))
        exposure = t*t*(3-2*t)
        result.append((local_pitch*scale*exposure, local_yaw*scale*exposure))
    return result


def joint_targets(stages, pitch, yaw, extension_target, sequential, overrides=None):
    """Straighten either side of a sleeve before that sleeve retracts."""
    result = bend_angles(stages, pitch, yaw, overrides)
    goals = stage_targets(extension_target, sequential)
    for i in range(1, COUNT):
        if stages[i] > goals[i] or stages[i-1] > goals[i-1]:
            result[i] = (0.0, 0.0)
    return result


def step_joint(current, target, delta_seconds, speed_degrees):
    """Vector constant interpolation; L1 Euler change is bounded by speed*dt."""
    delta = [target[i]-current[i] for i in range(2)]
    length = math.hypot(*delta)
    step = max(delta_seconds, 0)*max(speed_degrees, 0.01)/math.sqrt(2)
    scale = min(1.0, step/length) if length else 0.0
    return tuple(current[i]+scale*delta[i] for i in range(2))


def retraction_allowed(index, stages, target, sequential, joints):
    if stages[index] <= stage_targets(target, sequential)[index]:
        return True
    involved = ([index] if index else []) + ([index+1] if index+1 < COUNT else [])
    return sum(math.hypot(*joints[j]) for j in involved) < 0.00001


def joint_clearance(index, extension, pitch, yaw):
    """Lower bound for radial wall clearance in the direct parent's axial slab.

    L1 Euler angle bounds the total rotation. Behind the parent's front plane,
    the child's radial excursion is <= R + max(overlap,R*tan(angle))*sin(angle).
    Parent inner apothem accounts for the generated 64-sided cross-section.
    """
    if not 1 <= index < COUNT:
        raise ValueError("Joint index must be 1..9")
    angle = math.radians(abs(pitch) + abs(yaw))
    outer = radius(index)
    overlap = LENGTH - STROKE*extension
    excursion = max(overlap, outer*math.tan(angle))*math.sin(angle)
    return (radius(index-1)-WALL)*math.cos(math.pi/64) - outer - excursion


def outer_hull(index, sides=64):
    """Solid outer envelope, for conservative sleeve-wall checks."""
    r = radius(index)
    vertices = [(x, r*math.cos(math.tau*j/sides), r*math.sin(math.tau*j/sides))
                for x in (-LENGTH, 0) for j in range(sides)]
    vertices += [(-LENGTH, 0, 0), (0, 0, 0)]
    faces = []
    for j in range(sides):
        k = (j+1) % sides
        faces += [(j, k, sides+k), (j, sides+k, sides+j),
                  (2*sides, k, j), (2*sides+1, sides+j, sides+k)]
    return vertices, faces


def clip_axial_slab(polygon, lower=-LENGTH, upper=0.0):
    """Clip a convex triangle/polygon to the closed X slab; standard Python."""
    for boundary, lower_side in ((lower, True), (upper, False)):
        if not polygon:
            break
        output = []
        a = polygon[-1]
        a_inside = a[0] >= boundary if lower_side else a[0] <= boundary
        for b in polygon:
            b_inside = b[0] >= boundary if lower_side else b[0] <= boundary
            if a_inside != b_inside:
                t = (boundary-a[0])/(b[0]-a[0])
                output.append(tuple(a[i]+t*(b[i]-a[i]) for i in range(3)))
            if b_inside:
                output.append(b)
            a, a_inside = b, b_inside
        polygon = output
    return polygon


def radius(index):
    if not 0 <= index < COUNT:
        raise ValueError("Sleeve index must be 0..9")
    return 50.0 - RADIUS_STEP * index


def fronts(extension):
    extension = min(1.0, max(0.0, extension))
    return [(i + 1) * STROKE * extension for i in range(COUNT)]


def stage_targets(extension, sequential):
    extension = min(1.0, max(0.0, extension))
    return [min(1.0, max(0.0, extension * COUNT - i)) if sequential else extension
            for i in range(COUNT)]


def fronts_from_stages(stages):
    if len(stages) != COUNT or any(not 0 <= s <= 1 for s in stages):
        raise ValueError("Ten stage positions in 0..1 required")
    result, total = [], 0.0
    for stage in stages:
        total += STROKE * stage
        result.append(total)
    return result


def build_sleeve(index, sides=64):
    outer = radius(index)
    if sides < 3:
        raise ValueError("At least three sides required")
    vertices, normals, uvs, faces = [], [], [], []

    def ring(x, r, normal_kind):
        row = []
        for j in range(sides + 1):
            phi = math.tau * j / sides
            row.append(len(vertices) + 1)
            vertices.append((x, r * math.cos(phi), r * math.sin(phi)))
            if normal_kind in (-1, 1):
                normals.append((0, normal_kind * math.cos(phi), normal_kind * math.sin(phi)))
            else:
                normals.append((1 if x == 0 else -1, 0, 0))
            v = (r - (outer - WALL)) / WALL if normal_kind == 0 else (x + LENGTH) / LENGTH
            uvs.append((j / sides, v))
        return row

    for r, sign in ((outer, 1), (outer - WALL, -1)):
        back, front = ring(-LENGTH, r, sign), ring(0, r, sign)
        for j in range(sides):
            a, b, c, d = back[j], front[j], front[j + 1], back[j + 1]
            triangles = [(a, c, b), (a, d, c)]
            faces.extend(triangles if sign == 1 else [tuple(reversed(f)) for f in triangles])
    for x in (-LENGTH, 0):
        outside, inside = ring(x, outer, 0), ring(x, outer - WALL, 0)
        for j in range(sides):
            a, b, c, d = outside[j], outside[j + 1], inside[j + 1], inside[j]
            triangles = [(a, b, c), (a, c, d)]
            faces.extend(triangles if x == 0 else [tuple(reversed(f)) for f in triangles])
    return vertices, normals, uvs, faces


def write_obj(path, index):
    vertices, normals, uvs, faces = build_sleeve(index)
    lines = [f"# Beholder telescopic sleeve {index}; cm; X=-112..0", f"o Sleeve{index:02d}"]
    lines += ["v " + " ".join(f"{x:.10f}" for x in row) for row in vertices]
    lines += ["vt " + " ".join(f"{x:.10f}" for x in row) for row in uvs]
    lines += ["vn " + " ".join(f"{x:.10f}" for x in row) for row in normals]
    lines += ["f " + " ".join(f"{i}/{i}/{i}" for i in face) for face in faces]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
