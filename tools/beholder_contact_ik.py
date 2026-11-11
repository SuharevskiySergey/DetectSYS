"""Offline position-only IK for isolated rigid sleeves, never actuation.

UE pitch/yaw conventions; each sleeve translates along its rotated local X.
Uses sequential stage packing and the existing exposure/L1 bend envelope.
No contact manifold, head orientation constraint, collision or force proof.
"""
import math

from generate_beholder_telescope import COUNT, STROKE, bend_angles, stage_targets
from beholder_support_polygon import finite_vector


def rotate(v, pitch, yaw):
    p, y = math.radians(pitch), math.radians(yaw)
    cp, sp, cy, sy = math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    # UE positive pitch rotates forward toward +Z: Rz(yaw)*Ry(-pitch).
    x, yy, z = cp*v[0]-sp*v[2], v[1], sp*v[0]+cp*v[2]
    return (cy*x-sy*yy, sy*x+cy*yy, z)


def forward_contact(stages, angles, tip_point, sleeve_index=COUNT-1):
    """Point in a sleeve's coordinates -> leg actor local coordinates."""
    stages, angles = tuple(stages), tuple(tuple(a) for a in angles)
    if len(stages) != COUNT or any(not math.isfinite(s) or not 0 <= s <= 1 for s in stages):
        raise ValueError('Ten finite stages in 0..1 required')
    if len(angles) != COUNT or any(len(a) != 2 or any(not math.isfinite(v) for v in a) for a in angles):
        raise ValueError('Ten finite pitch/yaw pairs required')
    if type(sleeve_index) is not int or not 0 <= sleeve_index < COUNT:
        raise ValueError('Sleeve index in 0..9 required')
    point = finite_vector(tip_point, 3)
    for i in reversed(range(sleeve_index+1)):
        point = rotate((point[0]+STROKE*stages[i], point[1], point[2]), *angles[i])
    return finite_vector(point, 3)


def _pose(parameters):
    extension = max(0, min(1, parameters[0]))
    stages = stage_targets(extension, True)
    limits = bend_angles(stages, 2, 0)
    angles = [(0, 0)]
    projected = [extension]
    for i in range(1, COUNT):
        p, y = parameters[2*i-1:2*i+1]
        cap = limits[i][0]
        scale = min(1, cap/max(abs(p)+abs(y), 1e-30))
        p, y = p*scale, y*scale
        angles.append((p, y))
        projected.extend((p, y))
    return projected, stages, angles


def _solve3(matrix, rhs):
    rows = [list(row)+[value] for row, value in zip(matrix, rhs)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda i: abs(rows[i][column]))
        rows[column], rows[pivot] = rows[pivot], rows[column]
        if abs(rows[column][column]) < 1e-20:
            raise ValueError('Singular damped IK system')
        scale = rows[column][column]
        rows[column] = [v/scale for v in rows[column]]
        for i in range(3):
            if i != column:
                factor = rows[i][column]
                rows[i] = [a-factor*b for a, b in zip(rows[i], rows[column])]
    return [row[3] for row in rows]


def solve_contact_position(extension, tip_point, target_local, tolerance=0.001, iterations=100):
    """Bounded damped least squares, seeded straight at sequential packing.

    Valid input does not guarantee convergence; failure retains final residual.
    This proposes a settled endpoint, NOT a safe path from the current stages.
    """
    if not math.isfinite(extension) or not 0 <= extension <= 1:
        raise ValueError('Finite extension in 0..1 required')
    if not math.isfinite(tolerance) or not 1e-8 <= tolerance <= 1:
        raise ValueError('Finite local-cm tolerance in 1e-8..1 required')
    if type(iterations) is not int or not 1 <= iterations <= 1000:
        raise ValueError('Integer iteration bound in 1..1000 required')
    tip, target = finite_vector(tip_point, 3), finite_vector(target_local, 3)
    if max(abs(v) for v in tip+target) > 1e6:
        raise ValueError('IK coordinates exceed supported range')
    params = [extension]+[0.0]*(2*(COUNT-1))
    evaluations = 0

    def evaluate(values):
        nonlocal evaluations
        projected, stages, angles = _pose(values)
        point = forward_contact(stages, angles, tip)
        error = tuple(t-p for t, p in zip(target, point))
        evaluations += 1
        return projected, stages, angles, point, error, math.hypot(*error)

    state = evaluate(params)
    completed = 0
    for step in range(iterations):
        if state[5] <= tolerance:
            break
        completed = step+1
        params = state[0]
        columns = []
        for j in range(len(params)):
            delta = 1e-5 if j == 0 else 1e-3
            plus, minus = list(params), list(params)
            plus[j] += delta
            minus[j] -= delta
            a, b = evaluate(plus), evaluate(minus)
            columns.append(tuple((x-y)/(2*delta) for x, y in zip(a[3], b[3])))
        # Scale extension steps relative to degree steps for conditioning.
        weights = [0.01]+[1.0]*(len(params)-1)
        matrix = [[sum(col[a]*col[b]*w*w for col, w in zip(columns, weights))
                   +(0.01 if a == b else 0) for b in range(3)] for a in range(3)]
        solution = _solve3(matrix, state[4])
        direction = [w*w*sum(c*v for c, v in zip(col, solution)) for col, w in zip(columns, weights)]
        improved = False
        for factor in (1, 0.5, 0.25, 0.125, 0.0625):
            candidate = evaluate([p+factor*d for p, d in zip(params, direction)])
            if candidate[5] < state[5]-1e-12:
                state, improved = candidate, True
                break
        if not improved:
            break
    return dict(converged=state[5] <= tolerance, reason='position_only' if state[5] <= tolerance else 'not_converged',
                extension=state[0][0], stages=state[1], angles=state[2], pointLocal=state[3],
                targetLocal=target, residualLocal=state[4], residualLocalCm=state[5],
                iterations=completed, evaluations=evaluations, toleranceLocalCm=tolerance,
                headOrientationConstrained=False, motionAuthorized=False)
