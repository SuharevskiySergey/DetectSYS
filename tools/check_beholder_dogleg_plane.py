"""Offline contact/reference-plane bounds for the NONLINEAR dogleg path.

Reconstructs a rigid world map from four archived anchors and their recorded
actor-origin reference. The horizontal plane is reconstructed from world-down
signed gaps, not from a terrain mesh. Never actuates or claims general terrain
or runtime collision safety. Return traces the same geometric path backwards.
"""
import math

from beholder_contact_dogleg import dogleg_pose, finite
from beholder_contact_ik import _solve3, forward_contact
from beholder_support_polygon import finite_vector
from check_beholder_dogleg_shell import captured_branches, indexed
from generate_beholder_housing import CENTER_X
from generate_beholder_telescope import COUNT, STROKE, outer_hull

HULLS = [outer_hull(i)[0] for i in range(COUNT)]


def to_body(local, geometry):
    point = (local[0]-CENTER_X, local[1], local[2])
    return tuple(geometry['socket_origin_body'][k]+sum(point[j]*geometry['socket_axes_body'][j][k]
                                                     for j in range(3)) for k in range(3))


def mapped(point, origin, basis):
    return tuple(origin[k]+sum(point[j]*basis[j][k] for j in range(3)) for k in range(3))


def socket_scale_bound(geometry):
    axes = tuple(finite_vector(v, 3) for v in geometry['socket_axes_body'])
    finite_vector(geometry['socket_origin_body'], 3)
    if len(axes) != 3 or any(abs(math.hypot(*v)-1) > 1e-6 for v in axes):
        raise ValueError('Rigid unit-scale socket axes required')
    if any(abs(sum(a*b for a, b in zip(axes[i], axes[j]))) > 1e-6 for i in range(3) for j in range(i)):
        raise ValueError('Orthogonal socket axes required')
    a, b, c = axes
    determinant = a[0]*(b[1]*c[2]-b[2]*c[1])-b[0]*(a[1]*c[2]-a[2]*c[1])+c[0]*(a[1]*b[2]-a[2]*b[1])
    if determinant <= 0:
        raise ValueError('Reflected socket map rejected')
    return max(math.hypot(*v) for v in axes)*math.sqrt(1+2e-6)*(1+1e-12)


def archived_world_frame(source):
    branches = captured_branches(source)
    contacts = indexed(source.get('contacts'), 'index')
    poses = indexed(indexed(source['contactPositionIK'], 'removedIndex')[0]['contacts'], 'index')
    origin = finite_vector(source['singleContactReleaseGeometry']['referenceWorld'], 3)
    local, world, heights, fk_errors = [], [], [], []
    for index in sorted(branches):
        pose, contact = poses[index]['result'], contacts[index]
        socket_scale_bound(branches[index]['geometry'])
        tip = finite_vector(pose['tipPointLocal'], 3)
        p = forward_contact(pose['initialStages'], [(0, 0)]*COUNT, tip)
        local.append(to_body(p, branches[index]['geometry']))
        world.append(finite_vector(contact['point'], 3))
        gap, clearance = contact['verticalGapCm'], contact['clearanceCm']
        if any(not finite(v) or abs(v) > 0.05 for v in (gap, clearance)) or abs(gap-clearance) > 1e-5:
            raise ValueError('Coherent near-contact world-down gap/clearance required')
        heights.append(world[-1][2]-gap)
        fk_errors.append(pose['liveFKErrorLocalCm'])
    if max(heights)-min(heights) > 1e-5:
        raise ValueError('Captured vertical gaps do not describe one horizontal reference plane')
    if max(abs(v) for p in local+world+[origin] for v in p) > 1e8:
        raise ValueError('Captured coordinates exceed supported numerical range')
    # Least-squares fit uses all four anchors relative to the recorded root.
    # Their vectors span 3D even though their endpoints lie on one ground plane.
    gram = [[math.fsum(p[i]*p[j] for p in local) for j in range(3)] for i in range(3)]
    rows = [_solve3(gram, [math.fsum(p[i]*(q[k]-origin[k]) for p,q in zip(local, world))
                           for i in range(3)]) for k in range(3)]
    basis = tuple(tuple(rows[k][j] for k in range(3)) for j in range(3))
    lengths = [math.hypot(*axis) for axis in basis]
    if any(not math.isfinite(s) or not 1e-6 <= s <= 1000 for s in lengths):
        raise ValueError('Finite nondegenerate world scale required')
    if max(lengths)-min(lengths) > 1e-6*max(lengths):
        raise ValueError('Captured anchors do not reconstruct uniform body scale')
    if any(abs(sum(a*b for a,b in zip(basis[i], basis[j]))) > 1e-6*lengths[i]*lengths[j]
           for i in range(3) for j in range(i)):
        raise ValueError('Captured anchors do not reconstruct an orthogonal world map')
    a, b, c = basis
    determinant = a[0]*(b[1]*c[2]-b[2]*c[1])-b[0]*(a[1]*c[2]-a[2]*c[1])+c[0]*(a[1]*b[2]-a[2]*b[1])
    if determinant <= 0:
        raise ValueError('Reflected or degenerate world map rejected')
    residual = max(math.dist(mapped(p, origin, basis), q) for p,q in zip(local, world))
    if residual > 1e-4:
        raise ValueError('Archived anchor/world reconstruction residual too large')
    scale_bound = max(lengths)*math.sqrt(1+2e-6)*(1+1e-12)
    cushion = max(1e-5, 10*residual+10*max(fk_errors)*scale_bound)
    return dict(bodyOriginWorld=origin, bodyBasisWorld=basis, bodyScaleBound=scale_bound,
                maximumAnchorResidualWorldCm=residual, planeZ=max(heights),
                planeHeightSpreadCm=max(heights)-min(heights), numericalCushionWorldCm=cushion)


def split_fractions(extension, angle_degrees, samples=21):
    dogleg_pose(extension, angle_degrees)
    if type(samples) is not int or not 2 <= samples <= 1001:
        raise ValueError('Integer sample count in 2..1001 required')
    a = abs(math.radians(angle_degrees))
    maximum = 4*math.sin(a/2)**2
    critical = []
    for i in range(4, COUNT):
        threshold = i+1-COUNT*extension
        if 0 < threshold < maximum:
            critical.append(2*math.asin(math.sqrt(threshold)/2)/a)
    return sorted(set([k/(samples-1) for k in range(samples)]+critical)), critical


def sleeve_curvature_bound(index, local_point, angle_degrees):
    """Bound d²p/df² within one smooth clamp region, in local cm.

    Q1=R(a*f), Q2=R(-a*f), Q3..9=I. For i>=4 the origin is
    STROKE*min(10E,i+1-u(f)), u=2*(1-cos(a*f)); split its clamp kink.
    The old linear-stage interpolation bound does NOT apply to this path.
    """
    if type(index) is not int or not 0 <= index < COUNT:
        raise ValueError('Sleeve index in 0..9 required')
    if not finite(angle_degrees) or abs(angle_degrees) > 1:
        raise ValueError('Finite supported dogleg amplitude required')
    point = finite_vector(local_point, 3)
    if max(abs(v) for v in point) > 1e6:
        raise ValueError('Local point exceeds supported range')
    a2 = math.radians(angle_degrees)**2
    if index == 0:
        return 0.0
    if index == 1:
        return a2*math.hypot(point[0]+STROKE, point[1], point[2])*(1+1e-12)
    if index == 2:
        return a2*(2*STROKE+math.hypot(*point))*(1+1e-12)
    return a2*2*STROKE*(1+1e-12)


def certificate(extension, angle_degrees, rows, world_scale_bound, cushion, contact_tolerance=0.01, plane_tolerance=0.05):
    if not finite(world_scale_bound) or not 0 < world_scale_bound <= 1e8 or not finite(cushion) or cushion < 1e-5:
        raise ValueError('Positive scale and finite numerical cushion >=1e-5 required')
    if any(not finite(v) or not 0 <= v <= 1 for v in (contact_tolerance, plane_tolerance)):
        raise ValueError('Finite contact/plane tolerances in 0..1 required')
    _, critical = split_fractions(extension, angle_degrees, 2)
    if len(rows) < 2 or rows[0]['fraction'] != 0 or rows[-1]['fraction'] != 1:
        raise ValueError('Endpoint-inclusive samples required')
    if any(any(not finite(r[k]) for k in ('fraction','contactDriftCm','headPlaneMinimumCm','sleevePlaneMinimumCm'))
           or r['contactDriftCm'] < 0 for r in rows):
        raise ValueError('Finite sample metrics required')
    gaps = [b['fraction']-a['fraction'] for a,b in zip(rows, rows[1:])]
    if any(h <= 0 for h in gaps):
        raise ValueError('Strictly ordered sample fractions required')
    if any(not any(abs(r['fraction']-f) <= 1e-14 for r in rows) for f in critical):
        raise ValueError('Stage-boundary kink must be split before using curvature bound')
    h = max(gaps)
    curvature = world_scale_bound*max(sleeve_curvature_bound(i,p,angle_degrees)
                                      for i in range(COUNT) for p in HULLS[i])
    sleeve_error = curvature*h*h/8+cushion
    contact_upper = max(r['contactDriftCm'] for r in rows)+cushion
    head_lower = min(r['headPlaneMinimumCm'] for r in rows)-cushion
    sleeve_lower = min(r['sleevePlaneMinimumCm'] for r in rows)-sleeve_error
    return dict(contactAndReferencePlaneBoundPasses=contact_upper <= contact_tolerance and head_lower >= -plane_tolerance and sleeve_lower >= -plane_tolerance,
                contactDriftUpperBoundCm=contact_upper, headPlaneLowerBoundCm=head_lower, sleevePlaneLowerBoundCm=sleeve_lower,
                maximumFractionGap=h, criticalFractions=critical, sleeveCurvatureBoundWorldCm=curvature,
                sleeveBetweenSampleErrorWorldCm=sleeve_error, numericalCushionWorldCm=cushion,
                exactDoglegPathAssumed=True, fixedRootAssumed=True, returnUsesSameGeometricPath=True,
                linearStageInterpolationAssumed=False, formalIntervalArithmetic=False,
                runtimeTimingCertified=False, continuousCollisionCertified=False, motionAuthorized=False)


def run(source, samples=21):
    branches = captured_branches(source)
    frame = archived_world_frame(source)
    contacts = indexed(source['contacts'], 'index')
    poses = indexed(indexed(source['contactPositionIK'], 'removedIndex')[0]['contacts'], 'index')
    cases = []
    for index, branch in sorted(branches.items()):
        geometry = branch['geometry']
        vertices = [finite_vector(p, 3) for p in geometry['claw_vertices_tip']]
        center = finite_vector(geometry['sphere_center_tip'], 3)
        radius = geometry['sphere_radius_local']
        if len(vertices) != 12 or not finite(radius) or not 0 < radius <= 1e6:
            raise ValueError('Twelve claw vertices and positive bounded head radius required')
        if max(abs(v) for p in vertices+[center] for v in p) > 1e6:
            raise ValueError('Captured head points exceed supported local range')
        tip = poses[index]['result']['tipPointLocal']
        socket_scale = socket_scale_bound(geometry)
        world_scale = frame['bodyScaleBound']*socket_scale
        for axis in ('pitch', 'yaw'):
            for amplitude in (-1.0, 1.0):
                fractions, _ = split_fractions(branch['extension'], amplitude, samples)
                rows = []
                for f in fractions:
                    pose = dogleg_pose(branch['extension'], amplitude*f, axis)
                    def world(point, sleeve=COUNT-1):
                        local = forward_contact(pose['stages'], pose['angles'], point, sleeve)
                        return mapped(to_body(local, geometry), frame['bodyOriginWorld'], frame['bodyBasisWorld'])
                    head = [world(p)[2]-frame['planeZ'] for p in vertices]
                    head.append(world(center)[2]-frame['planeZ']-radius*world_scale)
                    rows.append(dict(fraction=f, contactDriftCm=math.dist(world(tip), contacts[index]['point']),
                        headPlaneMinimumCm=min(head),
                        sleevePlaneMinimumCm=min(world(p,i)[2]-frame['planeZ'] for i in range(COUNT) for p in HULLS[i])))
                bound = certificate(branch['extension'], amplitude, rows, world_scale, frame['numericalCushionWorldCm'])
                cases.append(dict(index=index, axis=axis, angleDegrees=amplitude, samples=rows, bound=bound))
    return dict(passed=all(c['bound']['contactAndReferencePlaneBoundPasses'] for c in cases), cases=cases, worldFrame=frame,
                archivedCapture=True, freshLiveGeometry=False, horizontalReferencePlaneOnly=True,
                terrainMeshChecked=False, bodyAndNestedBoundsRechecked=False, otherLegsChecked=False,
                continuousCollisionCertified=False, runtimeIKExecuted=False, motionAuthorized=False)


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
    args.output.write_text(json.dumps(dict(passed=False, running=True, source=str(args.source))), encoding='utf-8')
    try:
        data = args.source.read_bytes()
        report = run(json.loads(data), args.samples)
        report.update(running=False, source=str(args.source), sourceSha256=hashlib.sha256(data).hexdigest())
    except Exception as exc:
        args.output.write_text(json.dumps(dict(passed=False, running=False, source=str(args.source), error=repr(exc))), encoding='utf-8')
        raise
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(passed=report['passed'], cases=len(report['cases']), worldFrame=report['worldFrame'],
        contactUpper=max(c['bound']['contactDriftUpperBoundCm'] for c in report['cases']),
        headLower=min(c['bound']['headPlaneLowerBoundCm'] for c in report['cases']),
        sleeveLower=min(c['bound']['sleevePlaneLowerBoundCm'] for c in report['cases']))))
    raise SystemExit(0 if report['passed'] else 1)
