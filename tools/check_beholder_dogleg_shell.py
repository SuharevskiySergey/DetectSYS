"""Offline dogleg checks using archived, restored four-contact PIE geometry.

No live capture or actuation. Checks the head against moving sleeves and each
captured branch against the certified cavity/portal/outboard-octant envelope.
Does not certify arbitrary terrain, all inter-leg pairs or continuous motion.
"""
import math

from beholder_contact_dogleg import plan_cycle
from beholder_transfer_shell import check_branch_pose
from generate_beholder_body import DIRECTIONS
from generate_beholder_housing import INNER_RADIUS, inner_safe_radius
from generate_beholder_telescope import stage_targets

INDICES = {0, 2, 4, 6}


def indexed(rows, key):
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError('Four captured branches required')
    values = [r.get(key) for r in rows]
    if any(type(v) is not int for v in values) or set(values) != INDICES:
        raise ValueError('Distinct branch indices 0/2/4/6 required')
    return {r[key]: r for r in rows}


def captured_branches(source):
    if source.get('passed') is not True or source.get('running') is not False or source.get('restored') is not True:
        raise ValueError('Successful completed restored PIE capture required')
    certificate = source.get('transferShellCertificate', {})
    radius, margin = certificate.get('innerSafeRadius', 0), certificate.get('minimumPortalSupportMargin', 0)
    if not all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in (radius, margin)):
        raise ValueError('Finite positive captured shell certificate required')
    # The shared 144-sided body and isolated 64-sided housing have different
    # tessellations. The shared certificate must CONTAIN the free ball used by
    # check_branch_pose; equal radii are neither expected nor necessary.
    if radius+1e-6 < inner_safe_radius() or radius > INNER_RADIUS+1e-6:
        raise ValueError('Captured shell does not certify the conservative model free ball')
    redistributions = indexed(source.get('stageRedistributionGeometry'), 'index')
    transfers = indexed(source.get('contactPositionIK'), 'removedIndex')
    branches = {}
    for transfer in transfers.values():
        for index, row in indexed(transfer.get('contacts'), 'index').items():
            pose = row['result']
            stages = pose['initialStages']
            fk_error = pose.get('liveFKErrorLocalCm')
            if type(fk_error) not in (int, float) or not math.isfinite(fk_error) or not 0 <= fk_error <= 1e-4:
                raise ValueError('Captured live FK agreement required')
            if len(stages) != 10 or any(type(s) not in (int, float) or not math.isfinite(s) or not 0 <= s <= 1 for s in stages):
                raise ValueError('Ten valid captured stages required')
            extension = math.fsum(stages)/10
            if not 0.4 <= extension <= 0.9:
                raise ValueError('Dogleg requires initial extension in 0.4..0.9')
            plan = redistributions[index]['plan']
            if plan.get('valid') is not True or len(plan['initialStages']) != 10 or any(abs(a-b) > 1e-9 for a,b in zip(stages, plan['initialStages'])):
                raise ValueError('Straight redistribution and geometry captures disagree')
            expected = stage_targets(extension, True)
            if len(plan['targetStages']) != 10 or any(abs(a-b) > 1e-9 for a,b in zip(expected, plan['targetStages'])):
                raise ValueError('Captured sequential target does not match initial extension')
            geometry = pose['shellGeometryInput']
            signs = tuple(1 if v > 0 else -1 for v in DIRECTIONS[index])
            if tuple(geometry['octant_signs']) != signs or any(abs(a-b) > 1e-6 for a,b in zip(geometry['socket_axes_body'][0], DIRECTIONS[index])):
                raise ValueError('Geometry belongs to a different socket/octant')
            value = dict(extension=extension, geometry=geometry)
            if index in branches and branches[index] != value:
                raise ValueError('Repeated branch geometry differs across archived plans')
            branches[index] = value
    return branches


def run(source, samples_per_half=21, angle_degrees=1.0):
    cases = []
    for index, captured in sorted(captured_branches(source).items()):
        geometry = captured['geometry']
        head = {key: geometry[key] for key in ('claw_vertices_tip', 'sphere_center_tip', 'sphere_radius_local')}
        for axis in ('pitch', 'yaw'):
            cycle = plan_cycle(captured['extension'], angle_degrees, axis,
                               samples_per_half=samples_per_half, head_geometry=head)
            shell = [dict(timeSeconds=row['timeSeconds'], **check_branch_pose(row['stages'], row['angles'], **geometry))
                     for row in cycle['samples']]
            cases.append(dict(index=index, axis=axis, dogleg=cycle, shellSamples=shell,
                              passed=cycle['valid'] and all(row['passed'] for row in shell)))
    margins = {}
    for key in ('interior', 'portal', 'outboard'):
        values = [row['marginsLocalCm'][key] for case in cases for row in case['shellSamples']
                  if row['marginsLocalCm'][key] is not None]
        margins[key] = min(values) if values else None
    return dict(passed=all(case['passed'] for case in cases), cases=cases, capturedIndices=sorted(INDICES),
                archivedCapture=True, freshLiveGeometry=False, headGeometryChecked=True, bodyApertureChecked=True,
                outboardOctantChecked=True, terrainChecked=False, allInterLegPairsChecked=False,
                continuousCollisionCertified=False, runtimeIKExecuted=False, motionAuthorized=False,
                nestedPairsChecked=sum(c['dogleg']['nestedPairsChecked'] for c in cases),
                shellPosesChecked=sum(len(c['shellSamples']) for c in cases), minimumShellMarginsLocalCm=margins,
                reasons=sorted({reason for c in cases for reason in c['dogleg']['reasons']}
                               | {reason for c in cases for row in c['shellSamples'] for reason in row['reasons']}))


if __name__ == '__main__':
    import argparse
    import hashlib
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--samples', type=int, default=21)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('Source and output must be different files')
    args.output.write_text(json.dumps(dict(passed=False, running=True)), encoding='utf-8')
    try:
        data = args.source.read_bytes()
        report = run(json.loads(data), samples_per_half=args.samples)
        report.update(running=False, source=str(args.source), sourceSha256=hashlib.sha256(data).hexdigest())
    except Exception as exc:
        args.output.write_text(json.dumps(dict(passed=False, running=False, error=repr(exc))), encoding='utf-8')
        raise
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'cases'}))
    raise SystemExit(0 if report['passed'] else 1)
