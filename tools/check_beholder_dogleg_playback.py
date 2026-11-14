"""Sampled offline chord-playback error, not an Unreal executor certificate.

Even proportional joint angles do not make linearly interpolated stage lengths
follow the nonlinear compensated dogleg. All coordinates are local cm.
"""
import math

from beholder_contact_ik import forward_contact
from beholder_dogleg_timing import DoglegTiming
from generate_beholder_telescope import STROKE


def chord_tip_bound(angle_start, angle_end, cushion=1e-9):
    """Conditional all-fraction tip translation bound for exact dogleg endpoints.

    Full strokes 1/2 and proportional joint interpolation cancel lateral
    displacement and tip rotation. Interpolated distal stroke leaves axial
    error 2*STROKE*(cos((1-u)*a+u*b)-(1-u)*cos(a)-u*cos(b)).
    The secant remainder has magnitude <= (b-a)^2/8 since |cos''|<=1.
    No statement about sleeves/collisions or independent engine interpolators.
    """
    for angle in (angle_start,angle_end):
        if type(angle) not in (int,float) or not math.isfinite(angle) or abs(angle) > 1:
            raise ValueError('Finite dogleg endpoint angle within +/-1 degree required')
    if type(cushion) not in (int,float) or not math.isfinite(cushion) or cushion < 1e-9:
        raise ValueError('Numerical cushion >=1e-9 local cm required')
    return STROKE*math.radians(angle_end-angle_start)**2/4+cushion


def audit(schedule, frame_times, subdivisions=8):
    if type(subdivisions) is not int or not 2 <= subdivisions <= 100:
        raise ValueError('Integer subdivisions in 2..100 required')
    times = list(frame_times)
    end = 2*schedule.half_duration
    if len(times) < 2 or len(times) > 10001 or times[0] != 0 or times[-1] != end:
        raise ValueError('Frame times must cover the exact full cycle')
    if any(type(t) not in (int,float) or not math.isfinite(t) for t in times):
        raise ValueError('Finite numeric frame times required')
    if any(a >= b for a,b in zip(times,times[1:])):
        raise ValueError('Strictly increasing frame times required')
    # Multiple non-collinear tip points detect orientation as well as translation.
    points = ((0,0,0),(56,0,0),(56,12,-17))
    initial = schedule.evaluate(0)
    anchors = [forward_contact(initial['stages'],initial['angles'],p) for p in points]
    maximum_chord = maximum_exact = 0.0
    maximum_bound = 0.0
    bound_passes = True
    worst = None
    samples = 0
    for left,right in zip(times,times[1:]):
        a,b = schedule.evaluate(left),schedule.evaluate(right)
        bound = chord_tip_bound(a['angleDegrees'],b['angleDegrees'])
        maximum_bound = max(maximum_bound,bound)
        for k in range(subdivisions+1):
            u = k/subdivisions
            t = left if k == 0 else right if k == subdivisions else left+(right-left)*u
            exact = schedule.evaluate(t)
            stages = [(1-u)*x+u*y for x,y in zip(a['stages'],b['stages'])]
            angles = [tuple((1-u)*x+u*y for x,y in zip(aa,bb)) for aa,bb in zip(a['angles'],b['angles'])]
            chord_error = max(math.dist(forward_contact(stages,angles,p),anchor) for p,anchor in zip(points,anchors))
            exact_error = max(math.dist(forward_contact(exact['stages'],exact['angles'],p),anchor) for p,anchor in zip(points,anchors))
            if chord_error > maximum_chord:
                maximum_chord = chord_error
                worst = dict(timeSeconds=t,frameStartSeconds=left,frameEndSeconds=right,fraction=u)
            maximum_exact = max(maximum_exact,exact_error)
            bound_passes = bound_passes and chord_error <= bound
            samples += 1
    return dict(passed=maximum_exact <= 1e-9 and bound_passes,frames=len(times)-1,samples=samples,
                maximumSampledChordTipErrorLocalCm=maximum_chord,
                maximumSampledExactPhaseTipErrorLocalCm=maximum_exact,worstChordSample=worst,
                conditionalAllFractionChordTipBoundLocalCm=maximum_bound,
                sampledErrorsWithinConditionalBound=bound_passes,
                exactDoglegEndpointsAndCommonLinearInterpolationAssumed=True,
                formalIntervalArithmetic=False,numericalCushionLocalCm=1e-9,
                sampledOnly=True,linearJointAndStageInterpolationAssumed=True,
                engineInterpolationReproduced=False,continuousErrorBoundCertified=False,
                runtimeTimingCertified=False,runtimeIKExecuted=False,motionAuthorized=False)


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(dict(passed=False,running=True)),encoding='utf-8')
    try:
        cases = []
        for e in (0.5,0.49999):
            for axis in ('pitch','yaw'):
                for sign in (-1,1):
                    schedule = DoglegTiming.fit_duration(e,sign,axis,joint_acceleration_limit=12)
                    end = 2*schedule.half_duration
                    for fps in (15,30,60):
                        count = math.ceil(end*fps)
                        times = [end*(k/count) for k in range(count+1)]
                        cases.append(dict(extension=e,axis=axis,angleDegrees=sign,
                                          nominalFramesPerSecond=fps,result=audit(schedule,times)))
        report = dict(passed=all(c['result']['passed'] for c in cases),running=False,cases=cases,
                      runtimeTimingCertified=False,runtimeIKExecuted=False,motionAuthorized=False)
    except Exception as exc:
        args.output.write_text(json.dumps(dict(passed=False,running=False,error=repr(exc))),encoding='utf-8')
        raise
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(passed=report['passed'],cases=len(cases),maximumChordErrorLocalCm=max(
        c['result']['maximumSampledChordTipErrorLocalCm'] for c in cases))))
    raise SystemExit(0 if report['passed'] else 1)
