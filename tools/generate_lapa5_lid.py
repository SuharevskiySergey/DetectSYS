"""Generate the prototype eyelid's thick spherical shell (standard Python 3).

Packed UV U: 0..1 outer, 2..3 inner, 4..5 aperture rim. Material deformation
uses local positions, so OBJ import's UV V flip does not change the aperture.
"""

import math
from pathlib import Path

REST_APERTURE = 0.05
OUTER_RADIUS = 27.0
INNER_RADIUS = 26.0


def build_lid(longitudes=64, latitudes=24):
    if longitudes < 3 or latitudes < 2:
        raise ValueError("At least 3 longitudes and 2 latitudes are required")
    vertices, normals, uvs, triangles = [], [], [], []

    def vertex(radius, theta, phi, surface, v):
        radial = (math.sin(theta) * math.cos(phi), math.sin(theta) * math.sin(phi),
                  math.cos(theta))
        vertices.append(tuple(radius * c for c in radial))
        if surface == 2:
            normals.append((-math.cos(theta) * math.cos(phi),
                            -math.cos(theta) * math.sin(phi), math.sin(theta)))
        else:
            sign = 1 if surface == 0 else -1
            normals.append(tuple(sign * c for c in radial))
        uvs.append((2 * surface + phi / math.tau, 1 - v))
        return len(vertices)

    for surface, radius in ((0, OUTER_RADIUS), (1, INNER_RADIUS)):
        rows = []
        for latitude in range(latitudes + 1):
            v = latitude / latitudes
            theta = REST_APERTURE + v * (math.pi - REST_APERTURE)
            rows.append([vertex(radius, theta, math.tau * j / longitudes, surface, v)
                         for j in range(longitudes + 1)])
        for latitude in range(latitudes):
            for j in range(longitudes):
                a, b = rows[latitude][j], rows[latitude + 1][j]
                c, d = rows[latitude + 1][j + 1], rows[latitude][j + 1]
                faces = [(a, b, c), (a, c, d)]
                if surface == 1:
                    faces = [tuple(reversed(face)) for face in faces]
                triangles.extend(faces)

    rim = [[vertex(radius, REST_APERTURE, math.tau * j / longitudes, 2, 0)
            for j in range(longitudes + 1)] for radius in (OUTER_RADIUS, INNER_RADIUS)]
    for j in range(longitudes):
        a, b = rim[0][j], rim[0][j + 1]
        c, d = rim[1][j + 1], rim[1][j]
        triangles.extend(((a, b, c), (a, c, d)))
    # Pole quads contain one zero-area triangle each. Keep the valid fan only.
    def area_squared(face):
        a, b, c = [vertices[i - 1] for i in face]
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        return sum(x * x for x in (u[1] * v[2] - u[2] * v[1],
                                   u[2] * v[0] - u[0] * v[2],
                                   u[0] * v[1] - u[1] * v[0]))
    triangles = [face for face in triangles if area_squared(face) > 1e-14]
    return vertices, normals, uvs, triangles


def write_obj(path):
    vertices, normals, uvs, triangles = build_lid()
    lines = ["# Lapa5 geometric eyelid; units are centimetres", "o Lapa5Lid"]
    lines += ["v " + " ".join(f"{x:.10f}" for x in row) for row in vertices]
    lines += ["vt " + " ".join(f"{x:.10f}" for x in row) for row in uvs]
    lines += ["vn " + " ".join(f"{x:.10f}" for x in row) for row in normals]
    lines += ["f " + " ".join(f"{i}/{i}/{i}" for i in face) for face in triangles]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write_obj(Path(__file__).resolve().parents[1] / "Saved/Generated/Lapa5Lid.obj"))
