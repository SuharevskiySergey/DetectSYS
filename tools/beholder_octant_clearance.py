"""Separating-octant checks for outboard convex geometry (standard Python)."""
import math

from generate_beholder_telescope import clip_axial_slab
from generate_beholder_housing import PORTAL_START_X


def signed_margin(points, signs):
    if len(signs) != 3 or any(s not in (-1, 1) for s in signs):
        raise ValueError('Three octant signs required')
    values = []
    for p in points:
        if len(p) != 3 or not all(math.isfinite(x) for x in p):
            raise ValueError('Finite 3D coordinates required')
        values.extend(x*s for x, s in zip(p, signs))
    return min(values) if values else None


def outboard_margin(triangle, to_body, signs, portal_start=PORTAL_START_X):
    """Clip in the socket frame, then test linear body-octant halfspaces.

    Parts behind this plane are certified inside the body cavity by the
    housing validator; their overlap with other hidden branches is permitted.
    """
    polygon = clip_axial_slab(triangle, portal_start, 1e9)
    return signed_margin([to_body(p) for p in polygon], signs)
