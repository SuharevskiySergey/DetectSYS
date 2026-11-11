"""One-socket hollow body for the isolated telescopic seating test (cm).

The socket axis is +X; the shell has a real opening, not an opacity mask.
The outer lip plane bisects the folded head sphere at its equator.
"""

from functools import lru_cache
import math
from pathlib import Path

from generate_beholder_telescope import HEAD_OFFSET

OUTER_RADIUS = 200.0
INNER_RADIUS = 192.0
APERTURE_RADIUS = 60.0
SIDES = 64
LATITUDES = 32
APERTURE_ANGLE = math.asin(APERTURE_RADIUS/OUTER_RADIUS)
INNER_APERTURE_ANGLE = math.asin(APERTURE_RADIUS/INNER_RADIUS)
OUTER_LIP_X = OUTER_RADIUS*math.cos(APERTURE_ANGLE)
CENTER_X = HEAD_OFFSET-OUTER_LIP_X
INNER_LIP_X = INNER_RADIUS*math.cos(INNER_APERTURE_ANGLE)
# Begin the certified cylinder behind the inner lip, where the cavity still
# contains it. This avoids forcing a tangent seated sphere into a smaller ball.
PORTAL_START_X = 181.0
PORTAL_RADIUS = APERTURE_RADIUS*math.cos(math.pi/SIDES)


def build_shell(sides=SIDES, latitudes=LATITUDES):
    if sides < 3 or latitudes < 2:
        raise ValueError("At least three sides and two latitude rows required")
    vertices, normals, uvs, faces = [], [], [], []

    def vertex(radius, theta, phi, surface, v):
        radial = (math.cos(theta), math.sin(theta)*math.cos(phi), math.sin(theta)*math.sin(phi))
        vertices.append(tuple(radius*x for x in radial))
        if surface == 2:
            normals.append((0.0, -math.cos(phi), -math.sin(phi)))
        else:
            normals.append(tuple((1 if surface == 0 else -1)*x for x in radial))
        uvs.append((surface*2+phi/math.tau, v))
        return len(vertices)

    for surface, radius in ((0, OUTER_RADIUS), (1, INNER_RADIUS)):
        opening_angle = APERTURE_ANGLE if surface == 0 else INNER_APERTURE_ANGLE
        rows = []
        for i in range(latitudes+1):
            t = i/latitudes
            theta = opening_angle+t*(math.pi-opening_angle)
            rows.append([vertex(radius, theta, math.tau*j/sides, surface, t) for j in range(sides+1)])
        for i in range(latitudes):
            for j in range(sides):
                a, b, c, d = rows[i][j], rows[i+1][j], rows[i+1][j+1], rows[i][j+1]
                triangles = [(a, b, c), (a, c, d)]
                faces.extend(triangles if surface == 0 else [tuple(reversed(f)) for f in triangles])
    rim = [[vertex(r, math.asin(APERTURE_RADIUS/r), math.tau*j/sides, 2, v) for j in range(sides+1)]
           for r, v in ((OUTER_RADIUS, 0), (INNER_RADIUS, 1))]
    for j in range(sides):
        a, b, c, d = rim[0][j], rim[0][j+1], rim[1][j+1], rim[1][j]
        faces.extend(((a, b, c), (a, c, d)))

    def area(face):
        a, b, c = [vertices[i-1] for i in face]
        u, v = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
        cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        return sum(x*x for x in cross)

    faces = [f for f in faces if area(f) > 1e-14]
    return vertices, normals, uvs, faces


@lru_cache(maxsize=1)
def inner_safe_radius():
    """Conservative free ball inside the actual triangulated inner surface."""
    vertices, _, _, faces = build_shell()
    minimum = INNER_RADIUS
    for face in faces:
        points = [vertices[i-1] for i in face]
        if not all(abs(math.sqrt(sum(x*x for x in p))-INNER_RADIUS) < 1e-6 for p in points):
            continue
        a, b, c = points
        u, v = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
        n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        minimum = min(minimum, abs(sum(n[i]*a[i] for i in range(3)))/math.sqrt(sum(x*x for x in n)))
    return minimum


def sphere_clearance(center, radius):
    """Sufficient free-ball / cylindrical-portal bounds on axial pieces.

    Behind PORTAL_START_X require containment in the free inner ball; ahead
    require the inscribed aperture cylinder until the frontmost body point.
    """
    x, y, z = center
    rho = math.hypot(y, z)
    norm = math.sqrt(x*x+rho*rho)
    interior = portal = None
    if x-radius <= PORTAL_START_X:
        upper = min(x+radius, PORTAL_START_X)
        farthest_x = x+radius*x/norm if norm else x
        at = min(upper, max(x-radius, farthest_x))
        cross = math.sqrt(max(0.0, radius*radius-(at-x)**2))
        interior = inner_safe_radius()-math.hypot(at, rho+cross)
    lower, upper = max(x-radius, PORTAL_START_X), min(x+radius, OUTER_RADIUS)
    if lower <= upper:
        at = min(upper, max(lower, x))
        cross = math.sqrt(max(0.0, radius*radius-(at-x)**2))
        portal = PORTAL_RADIUS-rho-cross
    return {"interior": interior, "portal": portal}


def write_obj(path):
    vertices, normals, uvs, faces = build_shell()
    lines = ["# One-socket Beholder housing; cm; opening toward +X", "o BeholderHousing", "s 1"]
    lines += ["v "+" ".join(f"{x:.10f}" for x in row) for row in vertices]
    lines += ["vt "+" ".join(f"{x:.10f}" for x in row) for row in uvs]
    lines += ["vn "+" ".join(f"{x:.10f}" for x in row) for row in normals]
    lines += ["f "+" ".join(f"{i}/{i}/{i}" for i in face) for face in faces]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines)+"\n", encoding="utf-8")
    return path
