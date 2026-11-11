"""Engine-independent geometry for a world-down diagnostic surface probe.

The sphere is a conservative eye/eyelid envelope, not the rendered lid shape.
A single ray cannot certify whole-head clearance on uneven ground.
"""
import math


def vector(value):
    value = tuple(value)
    if len(value) != 3 or not all(math.isfinite(x) for x in value):
        raise ValueError('Finite 3D coordinates required')
    return value


def lowest_head_point(center, sphere_radius, claws):
    return head_plane_clearance(center, sphere_radius, claws, (0, 0, 0), (0, 0, 1))['support']


def head_plane_clearance(center, sphere_radius, claws, plane_point, plane_normal):
    """Minimum signed normal clearance of the head envelope to an infinite plane.

    Positive means above the plane in its normal direction. This is not a
    clearance certificate for a nonplanar surface sampled by a single ray.
    """
    center = vector(center)
    plane_point, normal = vector(plane_point), vector(plane_normal)
    length = math.hypot(*normal)
    if length < 1e-12 or not math.isfinite(length):
        raise ValueError('Nonzero finite plane normal required')
    normal = tuple(x/length for x in normal)
    if not math.isfinite(sphere_radius) or sphere_radius <= 0:
        raise ValueError('Positive finite world sphere radius required')
    claws = [list(claw) for claw in claws]
    if len(claws) != 3 or any(len(claw) != 4 for claw in claws):
        raise ValueError('Three calibrated tetrahedral claws required')
    lowest = tuple(c-sphere_radius*n for c, n in zip(center, normal))
    def signed(point):
        return sum((x-p)*n for x, p, n in zip(point, plane_point, normal))
    minimum = signed(lowest)
    source = 'sphereEnvelope'
    for i, claw in enumerate(claws):
        for j, point in enumerate(claw):
            point = vector(point)
            clearance = signed(point)
            if clearance < minimum:
                lowest, source = point, f'claw{i}.vertex{j}'
                minimum = clearance
    return {'normalClearance': minimum, 'normal': normal,
            'support': {'point': lowest, 'source': source}}


def downward_segment(point, distance=1000.0, lift=1.0):
    point = vector(point)
    if not math.isfinite(distance) or distance <= 0:
        raise ValueError('Positive finite trace distance required')
    if not math.isfinite(lift) or lift < 0:
        raise ValueError('Nonnegative finite trace lift required')
    return ((point[0], point[1], point[2]+lift),
            (point[0], point[1], point[2]-distance))
