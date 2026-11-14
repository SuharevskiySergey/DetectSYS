"""Offline C2 time parameterisation of the exact dogleg curve; no actuation.

Quintic phase stops at stage-clamp boundaries and the turn-around. Segment
times proportional to sqrt(phase span) avoid exploding acceleration for a
small span. Jerk continuity and physical acceleration safety are not claimed.
"""
import math

from beholder_contact_dogleg import dogleg_pose, finite
from check_beholder_dogleg_plane import split_fractions

QUINTIC_SPEED = 15/8
QUINTIC_ACCELERATION = 10/math.sqrt(3)


def quintic(s):
    if not finite(s) or not 0 <= s <= 1:
        raise ValueError('Unit phase required')
    tail = min(s,1-s)
    value = tail**3*(10-15*tail+6*tail*tail)
    if s > 0.5:
        value = 1-value
    return (value, 30*s*s*(1-s)**2, 60*s*(1-s)*(1-2*s))


class DoglegTiming:
    def __init__(self, extension=0.5, amplitude=1.0, axis='yaw', half_duration=1.0,
                 joint_speed_degrees=6.0, transition_seconds=0.6, joint_acceleration_limit=None):
        dogleg_pose(extension,amplitude,axis)
        if not finite(half_duration) or not 0.1 <= half_duration <= 60:
            raise ValueError('Half duration in 0.1..60 required')
        if not finite(joint_speed_degrees) or not 0.01 <= joint_speed_degrees <= 1e6:
            raise ValueError('Finite reference joint speed >=0.01 required')
        if not finite(transition_seconds) or not 0.01 <= transition_seconds <= 60:
            raise ValueError('Reference transition time in 0.01..60 required')
        if joint_acceleration_limit is not None and (not finite(joint_acceleration_limit) or joint_acceleration_limit <= 0):
            raise ValueError('Positive finite optional acceleration budget required')
        self.extension,self.amplitude,self.axis = extension,amplitude,axis
        self.half_duration = half_duration
        fractions,_ = split_fractions(extension,amplitude,samples=2)
        spans = [b-a for a,b in zip(fractions,fractions[1:])]
        weight = math.fsum(math.sqrt(d) for d in spans)
        self.segments = []
        start = 0.0
        for i,span in enumerate(spans):
            end = half_duration if i == len(spans)-1 else start+half_duration*math.sqrt(span)/weight
            if end <= start:
                raise ValueError('Unresolvable segment duration')
            self.segments.append(dict(startSeconds=start,endSeconds=end,
                                      phaseStart=fractions[i],phaseEnd=fractions[i+1]))
            start = end
        phase_speed = max(QUINTIC_SPEED*(s['phaseEnd']-s['phaseStart'])/(s['endSeconds']-s['startSeconds']) for s in self.segments)
        phase_accel = max(QUINTIC_ACCELERATION*(s['phaseEnd']-s['phaseStart'])/(s['endSeconds']-s['startSeconds'])**2 for s in self.segments)
        angular_speed = abs(amplitude)*phase_speed
        angular_accel = abs(amplitude)*phase_accel
        a = abs(math.radians(amplitude))
        stage_speed = 2*math.sin(a)*a*phase_speed
        stage_accel = 2*((a*phase_speed)**2+math.sin(a)*a*phase_accel)
        # step_joint uses speed/sqrt(2) for Euclidean travel. For ONE axis this
        # is stricter than the advertised L1 budget, and must not be ignored.
        axis_budget = joint_speed_degrees/math.sqrt(2)
        if 2*angular_speed > axis_budget+1e-12 or stage_speed > 1/transition_seconds+1e-12:
            raise ValueError('Schedule exceeds reference single-axis joint/stage velocity budget')
        if joint_acceleration_limit is not None and 2*angular_accel > joint_acceleration_limit+1e-12:
            raise ValueError('Schedule exceeds supplied reference acceleration budget')
        self.bounds = dict(maximumJointSpeedDegreesPerSecond=2*angular_speed,
            maximumJointAccelerationDegreesPerSecond2=2*angular_accel,
            maximumStageSpeedPerSecond=stage_speed,maximumStageAccelerationPerSecond2=stage_accel,
            jointSpeedParameterDegrees=joint_speed_degrees,singleAxisJointSpeedBudgetDegreesPerSecond=axis_budget,
            stageSpeedBudgetPerSecond=1/transition_seconds,jointAccelerationLimit=joint_acceleration_limit)

    @classmethod
    def fit_duration(cls, extension=0.5, amplitude=1.0, axis='yaw',
                     joint_speed_degrees=6.0, transition_seconds=0.6,
                     joint_acceleration_limit=None):
        """Shortest allowed half-duration under our conservative reference bounds.

        Not an optimal-control result: the segment weighting remains fixed.
        Reconstruct through the ordinary validator; never relax any budget.
        """
        if not finite(joint_speed_degrees) or not 0.01 <= joint_speed_degrees <= 1e6:
            raise ValueError('Finite reference joint speed >=0.01 required')
        if not finite(transition_seconds) or not 0.01 <= transition_seconds <= 60:
            raise ValueError('Reference transition time in 0.01..60 required')
        if joint_acceleration_limit is not None and (not finite(joint_acceleration_limit) or joint_acceleration_limit <= 0):
            raise ValueError('Positive finite optional acceleration budget required')
        # Permissive reference budgets let us extract unit-time constants even
        # when the requested slow controller cannot track a one-second half.
        reference = cls(extension,amplitude,axis,joint_speed_degrees=1e6,transition_seconds=0.01)
        b = reference.bounds
        duration = max(0.1,
            b['maximumJointSpeedDegreesPerSecond']/(joint_speed_degrees/math.sqrt(2)),
            b['maximumStageSpeedPerSecond']*transition_seconds)
        if joint_acceleration_limit is not None:
            duration = max(duration,math.sqrt(b['maximumJointAccelerationDegreesPerSecond2']/joint_acceleration_limit))
        if not math.isfinite(duration) or duration > 60:
            raise ValueError('Required half duration exceeds the supported 60 seconds')
        # One ULP avoids boundary round-off without hiding an infeasible bound.
        duration = min(60.0,math.nextafter(duration,math.inf))
        return cls(extension,amplitude,axis,duration,joint_speed_degrees,
                   transition_seconds,joint_acceleration_limit)

    def evaluate(self, seconds):
        if not finite(seconds) or not 0 <= seconds <= 2*self.half_duration:
            raise ValueError('Time must lie within the full cycle')
        forward = seconds <= self.half_duration
        local = seconds if forward else 2*self.half_duration-seconds
        segment = next((s for s in self.segments if local <= s['endSeconds']),self.segments[-1])
        duration = segment['endSeconds']-segment['startSeconds']
        q,dq,ddq = quintic(max(0.0,min(1.0,(local-segment['startSeconds'])/duration)))
        span = segment['phaseEnd']-segment['phaseStart']
        phase = max(segment['phaseStart'],min(segment['phaseEnd'],segment['phaseStart']+span*q))
        velocity = (1 if forward else -1)*span*dq/duration
        acceleration = span*ddq/(duration*duration)
        angle = self.amplitude*phase
        angle_velocity = self.amplitude*velocity
        angle_acceleration = self.amplitude*acceleration
        pose = dogleg_pose(self.extension,angle,self.axis)
        theta,dtheta,ddtheta = map(math.radians,(angle,angle_velocity,angle_acceleration))
        return dict(timeSeconds=seconds,phase=phase,angleDegrees=angle,
            angleVelocityDegreesPerSecond=angle_velocity,angleAccelerationDegreesPerSecond2=angle_acceleration,
            compensationSpeedPerSecond=2*math.sin(theta)*dtheta,
            compensationAccelerationPerSecond2=2*(math.cos(theta)*dtheta*dtheta+math.sin(theta)*ddtheta),
            **pose)

    def report(self, samples_per_half=21):
        if type(samples_per_half) is not int or not 2 <= samples_per_half <= 1001:
            raise ValueError('Integer sample count in 2..1001 required')
        count = 2*(samples_per_half-1)
        # Form the unit fraction first: multiplying time by k before dividing
        # can round the final sample beyond the strict cycle endpoint.
        times = {2*self.half_duration*(k/count) for k in range(count+1)}
        stops = {0.0,self.half_duration,2*self.half_duration}
        for segment in self.segments:
            for t in (segment['startSeconds'],segment['endSeconds']):
                stops.add(t);stops.add(2*self.half_duration-t)
        times.update(stops)
        return dict(passed=True,initialExtension=self.extension,amplitudeDegrees=self.amplitude,axis=self.axis,
            halfDurationSeconds=self.half_duration,segments=self.segments,stopTimesSeconds=sorted(stops),
            bounds=self.bounds,samples=[self.evaluate(t) for t in sorted(times)],
            exactSynchronousDoglegTrackingAssumed=True,velocityAndAccelerationContinuous=True,
            jerkContinuityGuaranteed=False,physicalAccelerationValidated=False,spatialProofsRecomputed=False,
            runtimeTimingCertified=False,runtimeIKExecuted=False,motionAuthorized=False)


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extension',type=float,default=0.5)
    parser.add_argument('--angle',type=float,default=1)
    parser.add_argument('--axis',choices=('pitch','yaw'),default='yaw')
    duration_group = parser.add_mutually_exclusive_group()
    duration_group.add_argument('--half-duration',type=float,default=1)
    parser.add_argument('--joint-accel-limit',type=float)
    duration_group.add_argument('--fit-duration',action='store_true',help='Choose half-duration from conservative reference bounds')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(dict(passed=False,running=True)),encoding='utf-8')
    try:
        if args.fit_duration:
            schedule = DoglegTiming.fit_duration(args.extension,args.angle,args.axis,
                                                joint_acceleration_limit=args.joint_accel_limit)
        else:
            schedule = DoglegTiming(args.extension,args.angle,args.axis,args.half_duration,
                                    joint_acceleration_limit=args.joint_accel_limit)
        result = schedule.report()
        result['durationFittedFromReferenceBounds'] = args.fit_duration
        result['running'] = False
    except Exception as exc:
        args.output.write_text(json.dumps(dict(passed=False,running=False,error=repr(exc))),encoding='utf-8')
        raise
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('samples','segments')}))
