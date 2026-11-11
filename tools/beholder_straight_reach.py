"""Snapshot-only rigid, straight telescope versus an infinite plane.

No actuation, IK, swept collision, changing claw pose or terrain certificate.
Projected stroke is the normal component of the entire world-space travel.
"""
import math


def straight_plane_target(extension, clearance, projected_stroke):
    result = dict(valid=False, reachable=False, target=0.0, projectedStroke=0.0,
                  foldedClearance=0.0, extendedClearance=0.0)
    if not (all(math.isfinite(v) for v in (extension, clearance, projected_stroke))
            and 0 <= extension <= 1 and 0 <= clearance <= 1e7
            and 1e-6 < abs(projected_stroke) <= 1e8):
        return result
    target = extension-clearance/projected_stroke
    reachable = 0 <= target <= 1
    result.update(valid=True, reachable=reachable, target=target if reachable else 0.0,
                  projectedStroke=projected_stroke,
                  foldedClearance=clearance-extension*projected_stroke,
                  extendedClearance=clearance+(1-extension)*projected_stroke)
    return result


def shared_vertical_offset(clearances, projected_strokes, normal_z,
                           minimum_extension=0.05, maximum_extension=0.95):
    """Test-fixture height interval for folded, straight, downward branches.

    A common plane and unchanged body orientation are assumed. This does not
    check body clearance, finite terrain, a footprint, or physical equilibrium.
    """
    clearances, projected_strokes = list(clearances), list(projected_strokes)
    if not clearances or len(clearances) != len(projected_strokes):
        raise ValueError('Matching nonempty branch inputs required')
    if not (math.isfinite(normal_z) and 1e-6 < normal_z <= 1
            and math.isfinite(minimum_extension) and math.isfinite(maximum_extension)
            and 0 <= minimum_extension < maximum_extension <= 1):
        raise ValueError('Upward normal and bounded extension interval required')
    if not (all(math.isfinite(c) and 0 <= c <= 1e7 for c in clearances)
            and all(math.isfinite(p) and -1e8 <= p < -1e-6 for p in projected_strokes)):
        raise ValueError('Free snapshots and downward projected strokes required')
    lower = max((-minimum_extension*p-c)/normal_z for c, p in zip(clearances, projected_strokes))
    upper = min((-maximum_extension*p-c)/normal_z for c, p in zip(clearances, projected_strokes))
    feasible = lower <= upper
    return dict(feasible=feasible, lower=lower, upper=upper,
                offset=(lower+upper)/2 if feasible else None)
