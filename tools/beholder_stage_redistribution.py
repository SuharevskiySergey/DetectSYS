"""Offline straight-leg stage redistribution; not a runtime trajectory.

For a straight, fixed-axis chain the endpoint depends on the SUM of strokes,
not their distribution. Runtime stage speeds/interlocks are not controlled.
"""
import math

from generate_beholder_telescope import (COUNT, STROKE, MAX_JOINT_BEND_DEGREES,
                                        bend_angles, stage_targets)


def plan_straight_redistribution(stages, joint_angles, samples=21):
    """Interpolate to sequential packing at the same average extension.

    Refuse articulated snapshots; straightening them would move the contact.
    No head orientation, joint limit or nested-sleeve protection is changed.
    Endpoint invariance is an ideal synchronised geometric property ONLY.
    """
    stages = tuple(stages)
    joint_angles = tuple(tuple(a) for a in joint_angles)
    if len(stages) != COUNT or any(not math.isfinite(s) or not 0 <= s <= 1 for s in stages):
        raise ValueError('Ten finite stage positions in 0..1 required')
    if len(joint_angles) != COUNT or any(len(a) != 2 or any(not math.isfinite(v) for v in a) for a in joint_angles):
        raise ValueError('Ten finite pitch/yaw pairs required')
    if type(samples) is not int or not 2 <= samples <= 1001:
        raise ValueError('Integer sample count in 2..1001 required')
    if any(abs(v) > 1e-9 for a in joint_angles for v in a):
        return dict(valid=False, reason='articulated_pose_rejected', samples=[], motionAuthorized=False)
    extension = math.fsum(stages)/COUNT
    target = stage_targets(extension, True)
    original_sum = math.fsum(stages)

    def authority(positions):
        angles = bend_angles(positions, MAX_JOINT_BEND_DEGREES, 0)
        return [dict(index=i, maximumL1Degrees=angles[i][0]) for i in range(1, COUNT)
                if angles[i][0] > 0]

    rows = []
    for k in range(samples):
        f = k/(samples-1)
        positions = tuple((1-f)*a+f*b for a, b in zip(stages, target))
        rows.append(dict(fraction=f, stages=positions,
                         endpointDriftLocalCm=STROKE*(math.fsum(positions)-original_sum),
                         availableJoints=authority(positions)))
    drift = max(abs(r['endpointDriftLocalCm']) for r in rows)
    if drift > 1e-8:
        raise ValueError('Redistribution lost total extension numerically')
    return dict(valid=True, reason='straight_geometry_only', extension=extension,
                initialStages=stages, targetStages=target, initialAvailableJoints=authority(stages),
                targetAvailableJoints=authority(target), maximumEndpointDriftLocalCm=drift,
                samples=rows, motionAuthorized=False)
