"""Offline XY footprint checks under world-down gravity, not support physics.

Input points must already be selected geometric candidates. The reference is
explicit: passing the body origin does not make it a physical centre of mass.
Height, friction, forces, dynamics and reachability are not certified here.
"""
import math


def finite_vector(value, dimensions):
    value = tuple(value)
    if len(value) != dimensions or not all(math.isfinite(x) for x in value):
        raise ValueError(f'Finite {dimensions}D coordinates required')
    return value


def cross(a, b, c):
    value = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    if not math.isfinite(value):
        raise ValueError('Footprint coordinates exceed numeric range')
    return value


def convex_hull(points):
    points = sorted(set(points))
    if len(points) < 3:
        return points
    lower, upper = [], []
    for sequence, chain in ((points, lower), (reversed(points), upper)):
        for point in sequence:
            while len(chain) >= 2 and cross(chain[-2], chain[-1], point) <= 0:
                chain.pop()
            chain.append(point)
    return lower[:-1]+upper[:-1]


def evaluate_footprint(points_xy, reference_xy, minimum_margin=0.0, area_epsilon=1e-6):
    """Test convex-hull halfspaces and a strict inward edge margin in cm.

    Collinear/too-small hulls are invalid. A boundary reference is inside but
    never passes the strict margin test. A negative margin is a violated edge
    halfspace, not the Euclidean distance to a polygon corner outside it.
    """
    reference = finite_vector(reference_xy, 2)
    if not math.isfinite(minimum_margin) or minimum_margin < 0:
        raise ValueError('Nonnegative finite minimum margin required')
    if not math.isfinite(area_epsilon) or area_epsilon < 0:
        raise ValueError('Nonnegative finite area tolerance required')
    points = [finite_vector(point, 2) for point in points_xy]
    # Work around the supplied reference to reduce world-translation error.
    local = [finite_vector((p[0]-reference[0], p[1]-reference[1]), 2) for p in points]
    hull = convex_hull(local)
    result = {'valid': False, 'inside': False, 'passesMargin': False,
              'marginCm': None, 'areaCm2': 0.0,
              'hullXY': [(p[0]+reference[0], p[1]+reference[1]) for p in hull],
              'reason': 'too_few_distinct_points'}
    if len(set(local)) < 3:
        return result
    if len(hull) < 3:
        result['reason'] = 'degenerate_polygon'
        return result
    edges = list(zip(hull, hull[1:]+hull[:1]))
    area = math.fsum(cross(hull[0], a, b) for a, b in edges)/2
    if not math.isfinite(area):
        raise ValueError('Footprint area exceeds numeric range')
    result['areaCm2'] = area
    if area <= area_epsilon:
        result['reason'] = 'degenerate_polygon'
        return result
    margins = [cross(a, b, (0, 0))/math.hypot(b[0]-a[0], b[1]-a[1]) for a, b in edges]
    if not all(math.isfinite(value) for value in margins):
        raise ValueError('Footprint margin exceeds numeric range')
    margin = min(margins)
    result.update(valid=True, inside=margin >= 0, passesMargin=margin > minimum_margin, marginCm=margin,
                  reason='encloses_reference' if margin > minimum_margin else
                         'outside_polygon' if margin < 0 else 'insufficient_margin')
    return result


def evaluate_body_candidates(points_world, candidate_flags, reference_world, minimum_margin=0.0):
    """Eight candidate slots. Inactive placeholders are ignored, not contacts."""
    points_world, candidate_flags = list(points_world), list(candidate_flags)
    if len(points_world) != 8 or len(candidate_flags) != 8:
        raise ValueError('Exactly eight body slots required')
    if any(type(flag) is not bool for flag in candidate_flags):
        raise ValueError('Candidate flags must be booleans')
    reference = finite_vector(reference_world, 3)
    indices = [i for i, flag in enumerate(candidate_flags) if flag]
    points = [finite_vector(points_world[i], 3)[:2] for i in indices]
    result = evaluate_footprint(points, reference[:2], minimum_margin)
    result['candidateIndices'] = indices
    return result
