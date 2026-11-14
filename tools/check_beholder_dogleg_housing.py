"""Conditional all-fraction body-cavity/portal/outboard-octant dogleg bounds.

Midpoint material points are clipped against axially EXPANDED regions and the
motion reserve is also deducted from radial/norm/halfspace clearance. Merely
subtracting a reserve from the usual sampled clip misses region entry/exit.
Archived geometry only; no actuation, arbitrary-obstacle or timing guarantee.
"""
import math

from beholder_octant_clearance import signed_margin
from beholder_support_polygon import finite_vector
from beholder_contact_dogleg import finite
from check_beholder_dogleg_nesting import DoglegMotion, HULLS, mapped, settings
from check_beholder_dogleg_plane import socket_scale_bound
from check_beholder_dogleg_shell import captured_branches
from generate_beholder_housing import (CENTER_X, OUTER_RADIUS, PORTAL_START_X, PORTAL_RADIUS,
                                       inner_safe_radius, sphere_clearance)
from generate_beholder_telescope import COUNT, STROKE, clip_axial_slab

CLAW_FACES = ((0,1,2),(0,1,3),(0,2,3),(1,2,3))


def body_point(socket_point, geometry):
    return tuple(geometry['socket_origin_body'][k]+sum(socket_point[j]*geometry['socket_axes_body'][j][k]
                                                      for j in range(3)) for k in range(3))


def primitive_bounds(vertices, faces, displacement, geometry):
    """Lower predicates for any triangle material point moving <=displacement.

    Region membership is not held fixed at the midpoint. The caller supplies
    Socket-local material coordinates and an independent displacement bound.
    """
    points = [finite_vector(p,3) for p in vertices]
    if not points or max(abs(v) for p in points for v in p) > 1e7:
        raise ValueError('Bounded midpoint vertices required')
    if not finite(displacement) or not 0 <= displacement <= 1e6:
        raise ValueError('Finite bounded nonnegative displacement required')
    map_scale = socket_scale_bound(geometry)
    signs = tuple(geometry['octant_signs'])
    if len(signs) != 3 or any(type(s) is not int or s not in (-1,1) for s in signs):
        raise ValueError('Three integer octant signs required')
    margins = dict(interior=None,portal=None,outboard=None)
    free = inner_safe_radius()
    triangles = 0
    def record(name, value):
        if not math.isfinite(value):
            raise ValueError('Nonfinite interval shell bound')
        margins[name] = value if margins[name] is None else min(margins[name],value)
    for face in faces:
        if len(face) != 3 or any(type(i) is not int or not 0 <= i < len(points) for i in face):
            raise ValueError('Valid zero-based triangle indices required')
        triangle = [points[i] for i in face]
        triangles += 1
        for p in clip_axial_slab(triangle,-1e8,PORTAL_START_X+displacement):
            record('interior',free-math.hypot(*p)-displacement)
        for p in clip_axial_slab(triangle,PORTAL_START_X-displacement,OUTER_RADIUS+displacement):
            record('portal',PORTAL_RADIUS-math.hypot(p[1],p[2])-displacement)
        outside = clip_axial_slab(triangle,PORTAL_START_X-displacement,1e8)
        if outside:
            record('outboard',signed_margin([body_point(p,geometry) for p in outside],signs)-map_scale*displacement)
    if triangles == 0:
        raise ValueError('Nonempty triangle envelope required')
    return dict(marginsLowerLocalCm=margins,triangleEnvelopesChecked=triangles)


def branch_certificate(extension, amplitude, axis, geometry, intervals=20, cushion=1e-7):
    settings(intervals,cushion)
    map_scale = socket_scale_bound(geometry)
    # The shared-body template is centred on each hidden socket housing.
    if max(abs(v) for v in geometry['socket_origin_body']) > 1e-8:
        raise ValueError('Socket centre must coincide with the certified common-body centre')
    signs = tuple(geometry['octant_signs'])
    if len(signs) != 3 or any(type(s) is not int or s not in (-1,1) for s in signs):
        raise ValueError('Three integer octant signs required')
    center = finite_vector(geometry['sphere_center_tip'],3)
    claws = [finite_vector(p,3) for p in geometry['claw_vertices_tip']]
    radius = geometry['sphere_radius_local']
    if len(claws) != 12 or not finite(radius) or not 0 < radius <= 1e6:
        raise ValueError('Captured head sphere and twelve claw vertices required')
    motion = DoglegMotion(extension,amplitude,axis)
    tube_speeds = [motion.speed_bound(0,i,HULLS[i][0]) for i in range(COUNT)]
    claw_speed = motion.speed_bound(0,9,claws)
    center_speed = motion.speed_bound(0,9,[center])
    rows = []
    for k in range(intervals):
        midpoint = (k+0.5)/intervals
        frames = [motion.relative_frame(0,i,midpoint) for i in range(COUNT)]
        margins = dict(interior=None,portal=None,outboard=None)
        triangles = 0

        def socket_point(index, vertex):
            p = mapped(frames[index],vertex)
            return (p[0]+STROKE*motion.initial[0]-CENTER_X,p[1],p[2])

        def check(vertices, faces, displacement):
            nonlocal triangles
            result = primitive_bounds(vertices,faces,displacement,geometry)
            triangles += result['triangleEnvelopesChecked']
            for name,value in result['marginsLowerLocalCm'].items():
                if value is not None:
                    margins[name] = value if margins[name] is None else min(margins[name],value)

        for i,(vertices,faces) in enumerate(HULLS):
            check([socket_point(i,p) for p in vertices],faces,tube_speeds[i]/(2*intervals)+cushion)
        vertices = [socket_point(9,p) for p in claws]
        for i in range(3):
            check(vertices[4*i:4*i+4],CLAW_FACES,claw_speed/(2*intervals)+cushion)
        center_at_midpoint = socket_point(9,center)
        expanded_radius = radius+center_speed/(2*intervals)+cushion
        sphere = sphere_clearance(center_at_midpoint,expanded_radius)
        sphere_octant = signed_margin([body_point(center_at_midpoint,geometry)],signs)-map_scale*expanded_radius
        cavity_portal = ((margins['interior'] is None or margins['interior'] >= -0.001)
                         and (margins['portal'] is None or margins['portal'] >= -0.001)
                         and (sphere['interior'] is None or sphere['interior'] >= -0.001)
                         and (sphere['portal'] is None or sphere['portal'] >= -0.1))
        octant = (margins['outboard'] is None or margins['outboard'] > 0) and sphere_octant > 0
        rows.append(dict(fractionStart=k/intervals,fractionEnd=(k+1)/intervals,
                         meshMarginsLowerLocalCm=margins,sphereMarginsLowerLocalCm=sphere,
                         sphereOctantLowerLocalCm=sphere_octant,triangleEnvelopesChecked=triangles,
                         cavityAndPortalBoundPasses=cavity_portal,outboardOctantBoundPasses=octant,
                         passed=cavity_portal and octant))
    minimum = {}
    for name in ('interior','portal','outboard'):
        values = [r['meshMarginsLowerLocalCm'][name] for r in rows if r['meshMarginsLowerLocalCm'][name] is not None]
        minimum[name] = min(values) if values else None
    return dict(passed=all(r['passed'] for r in rows),intervals=rows,
                allFractionCavityAndPortalBoundPasses=all(r['cavityAndPortalBoundPasses'] for r in rows),
                allFractionOutboardOctantBoundPasses=all(r['outboardOctantBoundPasses'] for r in rows),
                minimumMeshMarginsLowerLocalCm=minimum,
                minimumSphereOctantLowerLocalCm=min(r['sphereOctantLowerLocalCm'] for r in rows),
                triangleIntervalEnvelopesChecked=sum(r['triangleEnvelopesChecked'] for r in rows),
                numericalCushionLocalCm=cushion,formalIntervalArithmetic=False,
                exactDoglegPathAssumed=True,certifiedSharedBodyModelAssumed=True,returnUsesSameGeometricPath=True,
                allInterLegPairsChecked=False,terrainMeshChecked=False,freshLiveGeometry=False,
                continuousCollisionCertified=False,runtimeTimingCertified=False,runtimeIKExecuted=False,motionAuthorized=False)


def run(source, intervals=20):
    cases = []
    for index, branch in sorted(captured_branches(source).items()):
        for axis in ('pitch','yaw'):
            for amplitude in (-1.0,1.0):
                result = branch_certificate(branch['extension'],amplitude,axis,branch['geometry'],intervals)
                cases.append(dict(index=index,axis=axis,angleDegrees=amplitude,result=result))
    minima = {}
    for name in ('interior','portal','outboard'):
        values = [c['result']['minimumMeshMarginsLowerLocalCm'][name] for c in cases
                  if c['result']['minimumMeshMarginsLowerLocalCm'][name] is not None]
        minima[name] = min(values) if values else None
    return dict(passed=all(c['result']['passed'] for c in cases),cases=cases,
                minimumMeshMarginsLowerLocalCm=minima,
                triangleIntervalEnvelopesChecked=sum(c['result']['triangleIntervalEnvelopesChecked'] for c in cases),
                archivedCapture=True,freshLiveGeometry=False,allInterLegPairsChecked=False,terrainMeshChecked=False,
                continuousCollisionCertified=False,runtimeTimingCertified=False,runtimeIKExecuted=False,motionAuthorized=False)


if __name__ == '__main__':
    import argparse
    import hashlib
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--intervals',type=int,default=20)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('Source and output must be different files')
    args.output.write_text(json.dumps(dict(passed=False,running=True,source=str(args.source))),encoding='utf-8')
    try:
        data = args.source.read_bytes()
        report = run(json.loads(data),args.intervals)
        report.update(running=False,source=str(args.source),sourceSha256=hashlib.sha256(data).hexdigest())
    except Exception as exc:
        args.output.write_text(json.dumps(dict(passed=False,running=False,source=str(args.source),error=repr(exc))),encoding='utf-8')
        raise
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'cases'}))
    raise SystemExit(0 if report['passed'] else 1)
