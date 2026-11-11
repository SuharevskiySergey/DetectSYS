"""Reference policy; the live controller is authored in the leg Blueprint."""
from generate_beholder_telescope import stage_targets

SEATED_CLAW_OPENING_MAX = 0.6
# All claw vertices preserve their distance to the head centre. Measured max
# was 96.95646 cm at scale 1.3; the enlarged head is below 166 cm. The
# conservative 180 cm envelope also encloses the 60 cm eye/eyelid.
HEAD_FREE_ENVELOPE_RADIUS = 180.0
HEAD_OUTSIDE_MARGIN = 1.0


def head_outside(center_x, body_radius=200.0):
    """Body-local +X separating plane, valid for every claw orbit angle."""
    return center_x >= body_radius+HEAD_FREE_ENVELOPE_RADIUS+HEAD_OUTSIDE_MARGIN


def locked(stages, target, sequential, outside=False):
    settled = sum(abs(a-b) for a, b in zip(stages, stage_targets(target, sequential))) < 1e-6
    amount = sum(stages)/10
    return not (settled and (amount < 1e-6 or outside))


def requested_claw(general, override, is_locked, seated=False):
    maximum = SEATED_CLAW_OPENING_MAX if seated else 1.0
    return 0.0 if is_locked else max(0.0, min(maximum, override if override >= 0 else general))
