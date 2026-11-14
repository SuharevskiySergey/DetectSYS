"""Offline fixed-root, fixed-tip-frame articulation; never Unreal actuation.

Three same-axis relative bends (a, -2a, a) at joints 1/2/3 cancel
orientation and lateral displacement. The two intervening full strokes lose
2*STROKE*(1-cos(a)) axially; distal sequential extension compensates exactly.
This is NOT constant-total-extension redistribution or a runtime trajectory.
"""
import math

from beholder_contact_ik import forward_contact
from beholder_nested_clearance import check_nested_pose
from generate_beholder_telescope import (COUNT, MAX_JOINT_BEND_DEGREES, BEND_WALL_MARGIN,
                                         bend_angles, joint_clearance, retraction_allowed, stage_targets)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def dogleg_pose(extension, angle_degrees, axis='yaw'):
    if not finite(extension) or not 0.4 <= extension <= 0.9:
        raise ValueError('Initial sequential extension in 0.4..0.9 required')
    if not finite(angle_degrees) or abs(angle_degrees) > MAX_JOINT_BEND_DEGREES/2:
        raise ValueError('Finite angle within half the existing joint limit required')
    if axis not in ('pitch', 'yaw'):
        raise ValueError('Single pitch or yaw axis required; no mixed Euler proof')
    # Stable for small angles, algebraically equal to 2*(1-cos(a)).
    added_stroke = 4*math.sin(math.radians(angle_degrees)/2)**2
    result_extension = extension+added_stroke/COUNT
    stages = stage_targets(result_extension, True)
    angles = [(0.0, 0.0)]*COUNT
    component = 0 if axis == 'pitch' else 1
    for index, scale in ((1, 1), (2, -2), (3, 1)):
        values = [0.0, 0.0]
        values[component] = scale*angle_degrees
        angles[index] = tuple(values)
    return dict(stages=stages, angles=angles, extension=result_extension,
                addedNormalisedStroke=added_stroke, motionAuthorized=False)


def plan_cycle(extension=0.5, angle_degrees=1.0, axis='yaw', half_duration=1.0,
               samples_per_half=21, transition_seconds=0.6, joint_speed_degrees=6.0,
               check_nested=True, head_geometry=None):
    peak = dogleg_pose(extension, angle_degrees, axis)
    if not finite(half_duration) or not 0.1 <= half_duration <= 60:
        raise ValueError('Half-cycle duration in 0.1..60 seconds required')
    if type(samples_per_half) is not int or not 2 <= samples_per_half <= 101:
        raise ValueError('Integer sample count in 2..101 required')
    if type(check_nested) is not bool:
        raise ValueError('Boolean nested-check flag required')
    if any(not finite(v) or v <= 0 for v in (transition_seconds, joint_speed_degrees)):
        raise ValueError('Positive finite profile times and joint speed required')
    angular_rate = 2*abs(angle_degrees)/half_duration
    stroke_rate = 2*abs(math.sin(math.radians(angle_degrees))*math.radians(angle_degrees))/half_duration
    if angular_rate > joint_speed_degrees+1e-12 or stroke_rate > 1/transition_seconds+1e-12:
        raise ValueError('Requested cycle exceeds joint/stage speed profile')
    initial = stage_targets(extension, True)
    probes = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    reference = [forward_contact(initial, [(0, 0)]*COUNT, p) for p in probes]
    rows = []
    for k in range(2*(samples_per_half-1)+1):
        phase = k/(samples_per_half-1)
        fraction = phase if phase <= 1 else 2-phase
        pose = dogleg_pose(extension, fraction*angle_degrees, axis)
        stages, angles = pose['stages'], pose['angles']
        caps = bend_angles(stages, MAX_JOINT_BEND_DEGREES, 0)
        envelope = all(abs(p)+abs(y) <= caps[i][0]+1e-12 for i, (p, y) in enumerate(angles))
        blocked = [i for i in range(COUNT)
                   if not retraction_allowed(i, stages, extension, True, angles)]
        frame_error = max(math.dist(forward_contact(stages, angles, p), ref) for p, ref in zip(probes, reference))
        wall = min(joint_clearance(i, stages[i], *angles[i]) for i in range(1, COUNT))
        nested = check_nested_pose(stages, angles, head_geometry=head_geometry) if check_nested else None
        reasons = []
        for passes, reason in ((envelope, 'bend_envelope'), (not blocked, 'return_interlock'),
                               (frame_error <= 1e-8, 'tip_frame_drift'),
                               (wall >= BEND_WALL_MARGIN, 'direct_parent_wall'),
                               (nested is None or nested['passed'], 'nested_walls')):
            if not passes:
                reasons.append(reason)
        rows.append(dict(timeSeconds=phase*half_duration, angleDegrees=fraction*angle_degrees,
                         stages=stages, angles=angles, extension=pose['extension'],
                         tipFrameErrorLocalCm=frame_error, blockedReturnStages=blocked,
                         directParentWallMinimumLocalCm=wall,
                         nestedPassed=nested['passed'] if nested else None,
                         nestedPairsChecked=len(nested['pairs']) if nested else 0,
                         nestedMinimumClearanceLocalCm=nested['minimumClearanceLocalCm'] if nested else None,
                         headGeometryPassed=nested['head']['passed'] if nested and nested['head'] else None,
                         minimumHeadShellClearanceLocalCm=nested['head']['minimumShellClearanceLocalCm'] if nested and nested['head'] else None,
                         minimumClawAxialLocalCm=nested['head']['minimumClawAxialLocalCm'] if nested and nested['head'] else None,
                         reasons=reasons))
    nested_margins = [r['nestedMinimumClearanceLocalCm'] for r in rows if r['nestedMinimumClearanceLocalCm'] is not None]
    return dict(valid=all(not r['reasons'] for r in rows), initialExtension=extension,
                peakExtension=peak['extension'], peakAddedNormalisedStroke=peak['addedNormalisedStroke'],
                axis=axis, requestedAngleDegrees=angle_degrees, halfDurationSeconds=half_duration,
                maximumJointL1SpeedDegrees=angular_rate, maximumStageSpeedPerSecond=stroke_rate,
                maximumTipFrameErrorLocalCm=max(r['tipFrameErrorLocalCm'] for r in rows),
                minimumNestedClearanceLocalCm=min(nested_margins) if nested_margins else None,
                nestedPairsChecked=sum(r['nestedPairsChecked'] for r in rows),
                nestedWallsChecked=check_nested, headGeometryChecked=check_nested and head_geometry is not None,
                headGeometryPassed=all(r['headGeometryPassed'] for r in rows) if check_nested and head_geometry is not None else None,
                bodyApertureChecked=False, terrainChecked=False, otherLegsChecked=False,
                continuousCollisionCertified=False, runtimeIKExecuted=False, motionAuthorized=False,
                reasons=sorted({reason for r in rows for reason in r['reasons']}), samples=rows)


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extension', type=float, default=0.5)
    parser.add_argument('--angle', type=float, default=1)
    parser.add_argument('--axis', choices=('pitch', 'yaw'), default='yaw')
    parser.add_argument('--samples', type=int, default=21)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = plan_cycle(args.extension, args.angle, args.axis, samples_per_half=args.samples)
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(text, encoding='utf-8')
        print(json.dumps({k: v for k, v in report.items() if k != 'samples'}))
    else:
        print(text)
    raise SystemExit(0 if report['valid'] else 1)
