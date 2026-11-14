"""Conditional all-fraction hollow-nesting/head bounds for ideal dogleg paths.

At each interval midpoint bound every descendant material point's displacement
in its ancestor frame by V*h/2. Clip the midpoint mesh to an axially expanded
ancestor slab and reserve the same displacement radially. This handles slab
entry/exit and stage-clamp kinks; sampling clearance alone would not.
Never a general collision, runtime timing or force certificate.
"""
import math

from beholder_contact_dogleg import dogleg_pose, finite
from beholder_contact_ik import rotate
from beholder_support_polygon import finite_vector
from check_beholder_dogleg_shell import captured_branches
from generate_beholder_telescope import (COUNT, STROKE, LENGTH, WALL, BEND_WALL_MARGIN,
                                         clip_axial_slab, head_shell_clearance, outer_hull, radius)

HULLS = [outer_hull(i) for i in range(COUNT)]
CUMULATIVE = (0, 1, -1, 0, 0, 0, 0, 0, 0, 0)


def indices(parent, child):
    if type(parent) is not int or type(child) is not int or not 0 <= parent <= child < COUNT:
        raise ValueError('Ancestor/descendant indices in 0..9 required')


class DoglegMotion:
    def __init__(self, extension, angle_degrees, axis):
        self.peak = dogleg_pose(extension, angle_degrees, axis)['stages']
        self.initial = dogleg_pose(extension, 0, axis)['stages']
        self.extension, self.amplitude, self.axis = extension, angle_degrees, axis
        self.angular_rate = abs(math.radians(angle_degrees))
        self.stroke_rate = 2*abs(math.sin(self.angular_rate))*self.angular_rate

    def relative_frame(self, parent, child, fraction):
        indices(parent, child)
        if not finite(fraction) or not 0 <= fraction <= 1:
            raise ValueError('Fraction in 0..1 required')
        angle = self.amplitude*fraction
        stages = dogleg_pose(self.extension, angle, self.axis)['stages']
        def rotated(point, coefficient):
            return rotate(point, coefficient*angle if self.axis == 'pitch' else 0,
                          coefficient*angle if self.axis == 'yaw' else 0)
        origin = [0.0]*3
        for j in range(parent+1, child+1):
            displacement = rotated((STROKE*stages[j], 0, 0), CUMULATIVE[j]-CUMULATIVE[parent])
            origin = [a+b for a,b in zip(origin, displacement)]
        coefficient = CUMULATIVE[child]-CUMULATIVE[parent]
        axes = [rotated(axis, coefficient) for axis in ((1,0,0),(0,1,0),(0,0,1))]
        return origin, axes

    def speed_bound(self, parent, child, points):
        """Maximum ||dp_relative/df||, not seconds; valid across clamp kinks.

        Combine the last stroke with its material point BEFORE bounding norm.
        Sequential compensation is monotonic: all varying strokes together
        consume at most u'(f), not one budget for each descendant stage.
        """
        indices(parent, child)
        points = [finite_vector(p,3) for p in points]
        if not points or max(abs(v) for p in points for v in p) > 1e6:
            raise ValueError('Nonempty bounded material point set required')
        if parent == child:
            return 0.0
        cp = CUMULATIVE[parent]
        angular = math.fsum(STROKE*self.peak[j]*abs(CUMULATIVE[j]-cp)*self.angular_rate
                            for j in range(parent+1,child))
        endpoint_norm = max(math.hypot(p[0]+STROKE*s,p[1],p[2]) for p in points
                            for s in (self.initial[child],self.peak[child]))
        angular += abs(CUMULATIVE[child]-cp)*self.angular_rate*endpoint_norm
        changing = any(self.peak[j] > self.initial[j] for j in range(parent+1,child+1))
        return (angular+(STROKE*self.stroke_rate if changing else 0))*(1+1e-12)


def mapped(frame, point):
    origin, axes = frame
    return tuple(origin[k]+sum(point[j]*axes[j][k] for j in range(3)) for k in range(3))


def settings(intervals, cushion):
    if type(intervals) is not int or not 1 <= intervals <= 200:
        raise ValueError('Integer interval count in 1..200 required')
    if not finite(cushion) or cushion < 1e-7:
        raise ValueError('Finite engineering cushion >=1e-7 local cm required')


def tube_certificate(extension, amplitude, axis, intervals=20, required_margin=BEND_WALL_MARGIN, cushion=1e-7):
    settings(intervals,cushion)
    if not finite(required_margin) or required_margin < BEND_WALL_MARGIN:
        raise ValueError('Existing nested-wall margin cannot be reduced')
    motion = DoglegMotion(extension,amplitude,axis)
    speeds = {(p,c): motion.speed_bound(p,c,HULLS[c][0]) for c in range(1,COUNT) for p in range(c)}
    rows = []
    for k in range(intervals):
        midpoint = (k+0.5)/intervals
        pairs = []
        for child in range(1,COUNT):
            vertices, faces = HULLS[child]
            for parent in range(child):
                displacement = speeds[parent,child]/(2*intervals)+cushion
                frame = motion.relative_frame(parent,child,midpoint)
                points = [mapped(frame,v) for v in vertices]
                row = dict(child=child,ancestor=parent,displacementBoundLocalCm=displacement,
                           axiallySeparatedThroughout=False,clearanceLowerBoundLocalCm=None,passes=True)
                if min(p[0] for p in points) > displacement or max(p[0] for p in points) < -LENGTH-displacement:
                    row['axiallySeparatedThroughout'] = True
                else:
                    maximum = None
                    for face in faces:
                        clipped = clip_axial_slab([points[i] for i in face],-LENGTH-displacement,displacement)
                        for point in clipped:
                            radial = math.hypot(point[1],point[2])
                            maximum = radial if maximum is None else max(maximum,radial)
                    if maximum is not None:
                        lower = (radius(parent)-WALL)*math.cos(math.pi/64)-maximum-displacement
                        row.update(clearanceLowerBoundLocalCm=lower,passes=lower >= required_margin)
                    else:
                        row['axiallySeparatedThroughout'] = True
                pairs.append(row)
        rows.append(dict(fractionStart=k/intervals,fractionEnd=(k+1)/intervals,pairs=pairs))
    margins = [p['clearanceLowerBoundLocalCm'] for r in rows for p in r['pairs'] if p['clearanceLowerBoundLocalCm'] is not None]
    passed = all(p['passes'] for r in rows for p in r['pairs'])
    return dict(passed=passed, allFractionNestingBoundPasses=passed, intervals=rows,
                intervalPairsChecked=45*intervals,requiredMarginLocalCm=required_margin,
                minimumClearanceLowerBoundLocalCm=min(margins) if margins else None,
                numericalCushionLocalCm=cushion,formalIntervalArithmetic=False,
                exactDoglegPathAssumed=True,returnUsesSameGeometricPath=True,
                runtimeTimingCertified=False,continuousCollisionCertified=False,motionAuthorized=False)


def head_certificate(extension, amplitude, axis, geometry, intervals=20, cushion=1e-7):
    settings(intervals,cushion)
    center = finite_vector(geometry['sphere_center_tip'],3)
    vertices = [finite_vector(p,3) for p in geometry['claw_vertices_tip']]
    sphere_radius = geometry['sphere_radius_local']
    if len(vertices) != 12 or not finite(sphere_radius) or not 0 < sphere_radius <= 1e6:
        raise ValueError('Captured bounded sphere and twelve claw vertices required')
    motion = DoglegMotion(extension,amplitude,axis)
    center_speeds = [motion.speed_bound(p,9,[center]) for p in range(COUNT)]
    claw_speeds = [motion.speed_bound(p,9,vertices) for p in range(COUNT)]
    rows = []
    for k in range(intervals):
        sleeves = []
        for parent in range(COUNT):
            frame = motion.relative_frame(parent,9,(k+0.5)/intervals)
            center_displacement = center_speeds[parent]/(2*intervals)+cushion
            claw_displacement = claw_speeds[parent]/(2*intervals)+cushion
            clearance = head_shell_clearance(parent,mapped(frame,center),sphere_radius+center_displacement)
            axial = min(mapped(frame,p)[0] for p in vertices)-claw_displacement
            sleeves.append(dict(ancestor=parent,sphereClearanceLowerBoundLocalCm=clearance,
                clawAxialLowerBoundLocalCm=axial,centerDisplacementBoundLocalCm=center_displacement,
                passes=(clearance is None or clearance > 0) and axial >= -0.001))
        rows.append(dict(fractionStart=k/intervals,fractionEnd=(k+1)/intervals,sleeves=sleeves))
    margins = [s['sphereClearanceLowerBoundLocalCm'] for r in rows for s in r['sleeves'] if s['sphereClearanceLowerBoundLocalCm'] is not None]
    passed = all(s['passes'] for r in rows for s in r['sleeves'])
    return dict(passed=passed,allFractionHeadVsSleevesBoundPasses=passed,intervals=rows,
                intervalSleevesChecked=COUNT*intervals,
                minimumSphereClearanceLowerBoundLocalCm=min(margins) if margins else None,
                minimumClawAxialLowerBoundLocalCm=min(s['clawAxialLowerBoundLocalCm'] for r in rows for s in r['sleeves']),
                numericalCushionLocalCm=cushion,formalIntervalArithmetic=False,
                exactDoglegPathAssumed=True,returnUsesSameGeometricPath=True,
                runtimeTimingCertified=False,continuousCollisionCertified=False,motionAuthorized=False)


def run(source, intervals=20):
    branches = captured_branches(source)
    tubes, cases = {}, []
    for index, branch in sorted(branches.items()):
        for axis in ('pitch','yaw'):
            for amplitude in (-1.0,1.0):
                key = f"E{branch['extension']!r}_{axis}_{amplitude:+g}"
                if key not in tubes:
                    tubes[key] = tube_certificate(branch['extension'],amplitude,axis,intervals)
                head = head_certificate(branch['extension'],amplitude,axis,branch['geometry'],intervals)
                cases.append(dict(index=index,axis=axis,angleDegrees=amplitude,tubeCertificateKey=key,head=head,
                                  passed=tubes[key]['passed'] and head['passed']))
    return dict(passed=all(c['passed'] for c in cases),tubeCertificates=tubes,cases=cases,
                tubeIntervalPairsChecked=sum(t['intervalPairsChecked'] for t in tubes.values()),
                headIntervalSleevesChecked=sum(c['head']['intervalSleevesChecked'] for c in cases),
                archivedCapture=True,freshLiveGeometry=False,bodyShellContinuousChecked=False,
                outboardOctantContinuousChecked=False,terrainChecked=False,otherLegsChecked=False,
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
    print(json.dumps(dict(passed=report['passed'],tubeCertificates=len(report['tubeCertificates']),cases=len(report['cases']),
        tubePairs=report['tubeIntervalPairsChecked'],headSleeves=report['headIntervalSleevesChecked'],
        minimumTubeLower=min(t['minimumClearanceLowerBoundLocalCm'] for t in report['tubeCertificates'].values()),
        minimumHeadLower=min((c['head']['minimumSphereClearanceLowerBoundLocalCm'] for c in report['cases']
                              if c['head']['minimumSphereClearanceLowerBoundLocalCm'] is not None),default=None))))
    raise SystemExit(0 if report['passed'] else 1)
