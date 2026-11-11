"""Necessary near-surface conditions only, not physical support/stability.

Defaults are prototype tuning, not approved Beholder movement parameters.
"""
import math

MIN_NORMAL_Z = 2**-0.5
MAX_GAP_CM = 2.0
PENETRATION_TOLERANCE_CM = 0.1


def settings_valid(min_normal_z, max_gap, penetration_tolerance):
    return (all(math.isfinite(v) for v in (min_normal_z, max_gap, penetration_tolerance))
            and 0 <= min_normal_z <= 1 and 0 <= max_gap <= 100
            and 0 <= penetration_tolerance <= 1)


def candidate(valid, hit, plane_valid, normal_z, plane_clearance, vertical_gap,
              min_normal_z=MIN_NORMAL_Z, max_gap=MAX_GAP_CM,
              penetration_tolerance=PENETRATION_TOLERANCE_CM):
    return (settings_valid(min_normal_z, max_gap, penetration_tolerance)
            and bool(valid and hit and plane_valid)
            and all(math.isfinite(v) for v in (normal_z, plane_clearance, vertical_gap))
            and min_normal_z <= normal_z <= 1.00001
            and -penetration_tolerance <= plane_clearance <= max_gap
            and -penetration_tolerance <= vertical_gap <= max_gap)
