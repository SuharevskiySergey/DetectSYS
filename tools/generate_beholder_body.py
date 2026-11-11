"""Eight-socket shell from matching octant patches; no external dependencies.

Each cube-diagonal socket retains the single-leg aperture and equator seating.
Reflected patches share exactly matching coordinate-plane boundaries.
"""
import itertools
import math
from pathlib import Path

from generate_beholder_housing import (OUTER_RADIUS, INNER_RADIUS, APERTURE_ANGLE,
                                      INNER_APERTURE_ANGLE, PORTAL_START_X, PORTAL_RADIUS)
from generate_beholder_telescope import clip_axial_slab

SIDES = 144
ROWS = 16
DIRECTIONS = tuple(tuple(s/math.sqrt(3) for s in signs)
                   for signs in itertools.product((-1, 1), repeat=3))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def build_body(sides=SIDES, rows=ROWS):
    if sides < 6 or sides % 6 or rows < 2:
        raise ValueError('Sides must be a multiple of six; at least two rows')
    n = (1/math.sqrt(3),)*3
    u, v = (1/math.sqrt(2), -1/math.sqrt(2), 0), (1/math.sqrt(6), 1/math.sqrt(6), -2/math.sqrt(6))
    vertices, normals, uvs, faces = [], [], [], []

    def vertex(radius, theta, phi, signs, island, surface):
        tangent = tuple(math.cos(phi)*a+math.sin(phi)*b for a, b in zip(u, v))
        radial = tuple(math.cos(theta)*a+math.sin(theta)*b for a, b in zip(n, tangent))
        vertices.append(tuple(0.0 if abs(radius*x) < 1e-9 else radius*x*s for x, s in zip(radial, signs)))
        normal = tuple(-x for x in tangent) if surface == 2 else tuple(x*(1 if surface == 0 else -1) for x in radial)
        normals.append(tuple(x*s for x, s in zip(normal, signs)))
        uvs.append((island*6+surface*2+(phi-math.pi/6)/math.tau, theta if surface != 2 else radius/OUTER_RADIUS))
        return len(vertices)

    for island, signs in enumerate(itertools.product((-1, 1), repeat=3)):
        reverse = math.prod(signs) < 0

        def face(a, b, c, inward=False):
            faces.append((c, b, a) if reverse != inward else (a, b, c))

        for surface, radius in ((0, OUTER_RADIUS), (1, INNER_RADIUS)):
            opening_angle = APERTURE_ANGLE if surface == 0 else INNER_APERTURE_ANGLE
            grid = []
            for i in range(rows+1):
                ring = []
                for j in range(sides+1):
                    phi = math.pi/6+math.tau*j/sides
                    tangent = tuple(math.cos(phi)*a+math.sin(phi)*b for a, b in zip(u, v))
                    boundary = min(math.atan2(n[k], -tangent[k]) for k in range(3) if tangent[k] < -1e-10)
                    theta = opening_angle+(boundary-opening_angle)*i/rows
                    ring.append(vertex(radius, theta, phi, signs, island, surface))
                grid.append(ring)
            for i in range(rows):
                for j in range(sides):
                    a, b, c, d = grid[i][j], grid[i+1][j], grid[i+1][j+1], grid[i][j+1]
                    face(a, b, c, surface == 1)
                    face(a, c, d, surface == 1)
        rim = [[vertex(radius, math.asin(60.0/radius), math.pi/6+math.tau*j/sides, signs, island, 2)
                for j in range(sides+1)] for radius in (OUTER_RADIUS, INNER_RADIUS)]
        for j in range(sides):
            a, b, c, d = rim[0][j], rim[0][j+1], rim[1][j+1], rim[1][j]
            face(a, b, c)
            face(a, c, d)
    return vertices, normals, uvs, faces


def inner_safe_radius(vertices, faces):
    minimum = INNER_RADIUS
    for face in faces:
        a, b, c = [vertices[i-1] for i in face]
        if not all(abs(math.sqrt(dot(p, p))-INNER_RADIUS) < 1e-6 for p in (a, b, c)):
            continue
        x, y = tuple(b[i]-a[i] for i in range(3)), tuple(c[i]-a[i] for i in range(3))
        cross = (x[1]*y[2]-x[2]*y[1], x[2]*y[0]-x[0]*y[2], x[0]*y[1]-x[1]*y[0])
        minimum = min(minimum, abs(dot(a, cross))/math.sqrt(dot(cross, cross)))
    return minimum


def portal_free_margin(vertices, faces):
    """Prove each clipped body facet stays outside the certified cylinder.

    A supporting radial plane bounds the cylinder from outside. Checking every
    clipped polygon vertex against that linear plane certifies the whole facet,
    unlike just checking vertex distance to the axis (a convex function).
    """
    minimum = math.inf
    for n in DIRECTIONS:
        signs = tuple(1 if x > 0 else -1 for x in n)
        u = (signs[0]/math.sqrt(2), -signs[1]/math.sqrt(2), 0)
        v = (signs[0]/math.sqrt(6), signs[1]/math.sqrt(6), -2*signs[2]/math.sqrt(6))
        projected = [(dot(p, n), dot(p, u), dot(p, v)) for p in vertices]
        for face in faces:
            triangle = [projected[i-1] for i in face]
            if max(p[0] for p in triangle) < PORTAL_START_X:
                continue
            polygon = clip_axial_slab(triangle, PORTAL_START_X, OUTER_RADIUS)
            if not polygon:
                continue
            y, z = sum(p[1] for p in polygon), sum(p[2] for p in polygon)
            rho = math.hypot(y, z)
            assert rho > 1e-6, 'Body facet spans a socket axis'
            minimum = min(minimum, min((p[1]*y+p[2]*z)/rho-PORTAL_RADIUS for p in polygon))
    return minimum


def write_obj(path):
    vertices, normals, uvs, faces = build_body()
    lines = ['# Eight-socket Beholder body; cm', 'o BeholderEightSocketBody', 's 1']
    lines += ['v '+' '.join(f'{x:.10f}' for x in p) for p in vertices]
    lines += ['vt '+' '.join(f'{x:.10f}' for x in p) for p in uvs]
    lines += ['vn '+' '.join(f'{x:.10f}' for x in p) for p in normals]
    lines += ['f '+' '.join(f'{i}/{i}/{i}' for i in f) for f in faces]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return path
