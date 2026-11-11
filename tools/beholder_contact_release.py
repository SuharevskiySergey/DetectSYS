"""Offline one-contact-removal diagnostics, never a motion authorization.

Uses supplied, already validated contact points. No freshness, reach, forces,
friction, body motion or remaining-contact preservation is certified here.
"""
from beholder_support_polygon import evaluate_footprint, finite_vector

LOWER_INDICES = (0, 2, 4, 6)


def evaluate_four_releases(points_world, reference_world, minimum_margin=1.0):
    """Evaluate each remaining triangle; reference is explicit, not a COM.

    Require exactly the four lower contact slots. Even a passing triangle is
    only geometric evidence; callers must not turn it into a retract command.
    All cases are returned rather than choosing an arbitrary stepping order.
    """
    if set(points_world) != set(LOWER_INDICES) or any(type(i) is not int for i in points_world):
        raise ValueError('Exactly contact slots 0/2/4/6 required')
    reference = finite_vector(reference_world, 3)
    points = {i: finite_vector(points_world[i], 3) for i in LOWER_INDICES}
    current = evaluate_footprint([points[i][:2] for i in LOWER_INDICES], reference[:2], minimum_margin)
    rows = []
    for removed in LOWER_INDICES:
        remaining = [i for i in LOWER_INDICES if i != removed]
        footprint = evaluate_footprint([points[i][:2] for i in remaining], reference[:2], minimum_margin)
        rows.append(dict(removedIndex=removed, remainingIndices=remaining, footprint=footprint,
                         passesGeometry=current['passesMargin'] and footprint['passesMargin']))
    return dict(referenceWorld=reference, minimumMarginCm=minimum_margin,
                currentFootprint=current, releases=rows,
                geometricallyEligibleIndices=[r['removedIndex'] for r in rows if r['passesGeometry']],
                motionAuthorized=False)
