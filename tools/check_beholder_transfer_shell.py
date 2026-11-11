"""Check captured PIE IK plans offline; never loads Unreal or applies poses."""
import argparse
import hashlib
import json
from pathlib import Path

from beholder_transfer_shell import check_transfer
from generate_beholder_telescope import stage_targets


def run(source):
    if not source.get('passed') or source.get('running') or not source.get('restored'):
        raise ValueError('Completed successful restored PIE report required')
    certificate = source.get('transferShellCertificate', {})
    if not (certificate.get('minimumPortalSupportMargin', 0) > 0 and certificate.get('innerSafeRadius', 0) > 0):
        raise ValueError('Captured body shell certificate required')
    rows = []
    redistributions = []
    stage_plans = source.get('stageRedistributionGeometry', [])
    if len(stage_plans) != 4 or {p['index'] for p in stage_plans} != {0, 2, 4, 6}:
        raise ValueError('Four distinct straight redistribution snapshots required')
    stage_plans = {p['index']: p['plan'] for p in stage_plans}
    if any(not p['valid'] for p in stage_plans.values()):
        raise ValueError('Straight redistribution preflight must pass')
    transfers = source.get('contactPositionIK', [])
    if len(transfers) != 4 or {t['removedIndex'] for t in transfers} != {0, 2, 4, 6}:
        raise ValueError('Four distinct captured transfer plans required')
    for transfer in transfers:
        contacts = transfer['contacts']
        if len(contacts) != 4 or {c['index'] for c in contacts} != {0, 2, 4, 6}:
            raise ValueError('Four distinct contact snapshots required')
        for contact in contacts:
            pose = contact['result']
            if not pose['converged'] or not pose['sampledTransition']['sampledChecksPass']:
                raise ValueError('Converged IK with passing sampled transition required')
            stage_plan = stage_plans[contact['index']]
            if len(pose['initialStages']) != 10 or len(stage_plan['initialStages']) != 10 or any(
                    abs(a-b) > 1e-9 for a, b in zip(pose['initialStages'], stage_plan['initialStages'])):
                raise ValueError('Redistribution and IK snapshots disagree')
            packed = stage_targets(sum(pose['initialStages'])/10, True)
            if not any(r['index'] == contact['index'] for r in redistributions):
                result = check_transfer(pose['initialStages'], packed, [(0, 0)]*10, pose['shellGeometryInput'])
                redistributions.append(dict(index=contact['index'], result=result))
            result = check_transfer(packed,
                                    pose['stages'], pose['angles'], pose['shellGeometryInput'])
            rows.append(dict(removedIndex=transfer['removedIndex'], index=contact['index'], result=result))
    return dict(passed=all(r['result']['passed'] for r in rows+redistributions), checks=rows,
                redistributions=redistributions,
                motionAuthorized=False, continuousCollisionCertified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('Source capture and output report must be different files')
    result = dict(passed=False, running=True, source=str(args.source))
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    try:
        captured = args.source.read_bytes()
        digest = hashlib.sha256(captured).hexdigest()
        result = run(json.loads(captured.decode('utf-8')))
        result.update(source=str(args.source), sourceSha256=digest, running=False)
    except Exception as exc:
        args.output.write_text(json.dumps(dict(passed=False, running=False, source=str(args.source),
                                              error=repr(exc)), indent=2), encoding='utf-8')
        raise
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'], paths=len(result['checks']),
                         redistributions=len(result['redistributions']),
                         samples=sum(len(r['result']['samples']) for r in result['checks']+result['redistributions']),
                         reasons=sorted({s for r in result['checks']+result['redistributions'] for s in r['result']['reasons']}))))
    raise SystemExit(0 if result['passed'] else 1)
