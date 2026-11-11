"""Offline translation-only compatibility of straight telescopic contacts.

Fixed body rotation, fixed leg axes and unchanged rigid head/claw pose.
No joint IK, terrain trace, swept collision, actuation or physical support.
"""
import math

from beholder_support_polygon import finite_vector


def evaluate_fixed_contact_translation(strokes_world, extensions, translation_world,
                                       contact_tolerance=0.01):
    """Fit extension changes to cancel a body translation at fixed contacts.

    A stroke is the WORLD displacement for extension 0->1. Under the stated
    rigid assumptions a contact moves by translation + stroke*deltaExtension.
    The bounded least-squares fit is diagnostic, not a command or a certificate
    for an articulated pose. Initial world contact locations cancel out.
    """
    if not strokes_world or set(strokes_world) != set(extensions):
        raise ValueError('Matching nonempty contact slots required')
    if any(type(i) is not int or not 0 <= i < 8 for i in strokes_world):
        raise ValueError('Body contact indices must be integers in 0..7')
    translation = finite_vector(translation_world, 3)
    if not math.isfinite(contact_tolerance) or not 0 <= contact_tolerance <= 1:
        raise ValueError('Finite contact tolerance in 0..1 cm required')
    rows = []
    for i in sorted(strokes_world):
        stroke = finite_vector(strokes_world[i], 3)
        extension = extensions[i]
        if not math.isfinite(extension) or not 0 <= extension <= 1:
            raise ValueError('Finite current extension in 0..1 required')
        length = math.hypot(*stroke)
        if not 1e-6 < length <= 1e8:
            raise ValueError('Nonzero bounded world stroke required')
        axis = tuple(v/length for v in stroke)
        along = math.fsum(t*a for t, a in zip(translation, axis))
        raw_target = extension-along/length
        target = max(0, min(1, raw_target))
        residual = finite_vector(tuple(t+s*(target-extension) for t, s in zip(translation, stroke)), 3)
        error = math.hypot(*residual)
        if not math.isfinite(error):
            raise ValueError('Contact residual exceeds numeric range')
        reachable = 0 <= raw_target <= 1
        compatible = error <= contact_tolerance
        rows.append(dict(index=i, currentExtension=extension, unconstrainedTarget=raw_target,
                         boundedTarget=target, extensionInRange=reachable,
                         residualWorld=residual, residualCm=error, compatibleGeometry=compatible))
    return dict(translationWorld=translation, contactToleranceCm=contact_tolerance, contacts=rows,
                compatibleGeometry=all(r['compatibleGeometry'] for r in rows),
                maximumResidualCm=max(r['residualCm'] for r in rows), motionAuthorized=False)
