"""Offline all-ancestor wall checks for a completed captured PIE report."""
import argparse
import hashlib
import json
from pathlib import Path

from beholder_nested_clearance import check_nested_transfer
from generate_beholder_telescope import COUNT, stage_targets


def run(source):
    if source.get('passed') is not True or source.get('running') is not False or source.get('restored') is not True:
        raise ValueError('Completed successful restored PIE capture required')
    plans = source.get('contactPositionIK', [])
    if len(plans) != 4 or {p['removedIndex'] for p in plans} != {0, 2, 4, 6}:
        raise ValueError('Four distinct transfer plans required')
    checks, redistributions, initial_snapshots = [], [], {}
    for plan in plans:
        contacts = plan['contacts']
        if len(contacts) != 4 or {c['index'] for c in contacts} != {0, 2, 4, 6}:
            raise ValueError('Four distinct contact snapshots required')
        for contact in contacts:
            i, pose = contact['index'], contact['result']
            if not pose['converged'] or not pose['sampledTransition']['sampledChecksPass']:
                raise ValueError('IK and sampled contact transition must pass')
            initial = pose['initialStages']
            if len(initial) != COUNT:
                raise ValueError('Ten initial stage positions required')
            packed = stage_targets(sum(initial)/COUNT, True)
            shell = pose['shellGeometryInput']
            head = {key: shell[key] for key in ('claw_vertices_tip', 'sphere_center_tip', 'sphere_radius_local')}
            if i not in initial_snapshots:
                initial_snapshots[i] = initial
                redistributions.append(dict(index=i, result=check_nested_transfer(initial, packed, [(0, 0)]*COUNT,
                                                                                 head_geometry=head)))
            elif initial != initial_snapshots[i]:
                raise ValueError('Inconsistent initial stage snapshots')
            checks.append(dict(index=i, removedIndex=plan['removedIndex'],
                               result=check_nested_transfer(packed, pose['stages'], pose['angles'], head_geometry=head)))
    return dict(passed=all(c['result']['passed'] for c in checks+redistributions), checks=checks,
                redistributions=redistributions, motionAuthorized=False, continuousCollisionCertified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('Source and output must be different files')
    args.output.write_text(json.dumps(dict(passed=False, running=True, source=str(args.source))), encoding='utf-8')
    try:
        captured = args.source.read_bytes()
        result = run(json.loads(captured.decode('utf-8')))
        result.update(running=False, source=str(args.source), sourceSha256=hashlib.sha256(captured).hexdigest())
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    except Exception as exc:
        args.output.write_text(json.dumps(dict(passed=False, running=False, error=repr(exc))), encoding='utf-8')
        raise
    rows = [s for c in result['checks']+result['redistributions'] for s in c['result']['samples']]
    print(json.dumps(dict(passed=result['passed'], poses=len(rows),
                         pairs=sum(len(s['pairs']) for s in rows),
                         minimumClearanceLocalCm=min(s['minimumClearanceLocalCm'] for s in rows
                                                     if s['minimumClearanceLocalCm'] is not None))))
    raise SystemExit(0 if result['passed'] else 1)
