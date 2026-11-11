"""Offline nearest XY reference transfer into an inset contact triangle.

Fixed contact points only. This is NOT a body trajectory, COM calculation,
kinematic feasibility check, physical stability check or motion permission.
"""
import math

from beholder_contact_release import LOWER_INDICES, evaluate_four_releases
from beholder_support_polygon import evaluate_footprint, finite_vector


def _nearest_segment(point, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    length2 = dx*dx+dy*dy
    if not math.isfinite(length2):
        raise ValueError('Transfer coordinates exceed numeric range')
    t = 0 if length2 == 0 else max(0, min(1, ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length2))
    return (a[0]+t*dx, a[1]+t*dy)


def plan_reference_transfers(points_world, reference_world, minimum_margin=1.0,
                             reserve_margin=0.1, maximum_shift=100.0):
    """Closest reference to each triangle inset by minimum+positive reserve.

    Z stays unchanged, contacts stay fixed. The reference segment is contained
    in the original four-contact hull when both endpoint checks pass, by
    convexity; this says nothing about any actual sleeve/head swept path.
    The returned target is a proposed reference, never an actor transform.
    """
    if not math.isfinite(reserve_margin) or reserve_margin <= 0:
        raise ValueError('Positive finite reserve margin required')
    if not math.isfinite(maximum_shift) or maximum_shift < 0:
        raise ValueError('Nonnegative finite maximum shift required')
    required = minimum_margin+reserve_margin
    if not math.isfinite(required):
        raise ValueError('Transfer margin exceeds numeric range')
    base = evaluate_four_releases(points_world, reference_world, minimum_margin)
    reference = base['referenceWorld']
    # Local coordinates reduce cancellation of large world translations.
    points = {i: finite_vector((points_world[i][0]-reference[0],
                               points_world[i][1]-reference[1]), 2) for i in LOWER_INDICES}
    rows = []
    for release in base['releases']:
        row = dict(removedIndex=release['removedIndex'], remainingIndices=release['remainingIndices'],
                   feasibleGeometry=False, reason='current_footprint_rejected',
                   proposedReferenceWorld=None, shiftCm=None, triangleInradiusCm=None,
                   targetTriangleFootprint=None, targetFourFootprint=None)
        rows.append(row)
        if not base['currentFootprint']['passesMargin']:
            continue
        triangle = evaluate_footprint([points[i] for i in release['remainingIndices']], (0, 0))
        if not triangle['valid']:
            row['reason'] = 'degenerate_triangle'
            continue
        a, b, c = triangle['hullXY']
        lengths = (math.dist(b, c), math.dist(c, a), math.dist(a, b))
        perimeter = math.fsum(lengths)
        radius = 2*triangle['areaCm2']/perimeter
        if not math.isfinite(radius) or radius <= 0:
            raise ValueError('Triangle inradius exceeds numeric range')
        row['triangleInradiusCm'] = radius
        if required > radius:
            row['reason'] = 'insufficient_triangle_inradius'
            continue
        center = tuple(math.fsum(p[j]*(w/perimeter) for p, w in zip((a, b, c), lengths)) for j in (0, 1))
        factor = max(0, 1-required/radius)
        inset = [tuple(center[j]+factor*(p[j]-center[j]) for j in (0, 1)) for p in (a, b, c)]
        if triangle['marginCm'] >= required:
            target = (0, 0)
        else:
            candidates = [_nearest_segment((0, 0), p, q) for p, q in zip(inset, inset[1:]+inset[:1])]
            target = min(candidates, key=lambda p: math.hypot(*p))
        world = finite_vector((reference[0]+target[0], reference[1]+target[1], reference[2]), 3)
        # Verify the representable world target, not only local calculations.
        check = evaluate_four_releases(points_world, world, minimum_margin)
        final = next(r['footprint'] for r in check['releases'] if r['removedIndex'] == release['removedIndex'])
        shift = math.hypot(world[0]-reference[0], world[1]-reference[1])
        row.update(proposedReferenceWorld=world, shiftCm=shift, targetTriangleFootprint=final,
                   targetFourFootprint=check['currentFootprint'])
        # Preserve at least half the explicit reserve after floating-point rounding.
        if not (final['passesMargin'] and final['marginCm'] >= minimum_margin+reserve_margin/2
                and check['currentFootprint']['passesMargin']):
            row['reason'] = 'target_verification_failed'
        elif shift > maximum_shift:
            row['reason'] = 'maximum_shift_exceeded'
        else:
            row.update(feasibleGeometry=True, reason='geometric_reference_only')
    return dict(referenceWorld=reference, minimumMarginCm=minimum_margin, reserveMarginCm=reserve_margin,
                maximumShiftCm=maximum_shift, currentFootprint=base['currentFootprint'], transfers=rows,
                geometricallyFeasibleIndices=[r['removedIndex'] for r in rows if r['feasibleGeometry']],
                motionAuthorized=False)
