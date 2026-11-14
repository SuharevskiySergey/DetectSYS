import math
import unittest

from beholder_contact_ik import forward_contact
from beholder_dogleg_timing import DoglegTiming, QUINTIC_ACCELERATION, QUINTIC_SPEED, quintic
from beholder_stage_timing import step
from generate_beholder_telescope import retraction_allowed, stage_targets, step_joint


class DoglegTimingTests(unittest.TestCase):
    def test_fitted_duration_saturates_velocity_bound(self):
        schedule=DoglegTiming.fit_duration(0.5)
        self.assertAlmostEqual(schedule.half_duration,3.75/(6/math.sqrt(2)))
        self.assertAlmostEqual(schedule.bounds['maximumJointSpeedDegreesPerSecond'],6/math.sqrt(2))
        with self.assertRaises(ValueError):
            DoglegTiming(0.5,half_duration=schedule.half_duration*0.999)

    def test_report_samples_stay_inside_strict_cycle_endpoints(self):
        schedules=[DoglegTiming.fit_duration(0.5),DoglegTiming.fit_duration(0.49999,joint_acceleration_limit=12)]
        for schedule in schedules:
            for n in (2,21,37,1001):
                report=schedule.report(n)
                self.assertEqual(report['samples'][0]['timeSeconds'],0)
                self.assertEqual(report['samples'][-1]['timeSeconds'],2*schedule.half_duration)
                self.assertEqual(report['samples'][-1]['phase'],0)
            with self.assertRaises(ValueError):
                schedule.evaluate(math.nextafter(2*schedule.half_duration,math.inf))

    def test_fitted_acceleration_duration_and_time_scaling(self):
        for axis in ('pitch','yaw'):
            for sign in (-1,1):
                schedule=DoglegTiming.fit_duration(0.49999,sign,axis,joint_acceleration_limit=12)
                self.assertAlmostEqual(schedule.half_duration,math.sqrt(22.9704155406547/12))
                self.assertLessEqual(schedule.bounds['maximumJointAccelerationDegreesPerSecond2'],12+1e-12)
                slower=DoglegTiming(0.49999,sign,axis,2*schedule.half_duration)
                for k in range(21):
                    t=2*schedule.half_duration*k/20
                    a,b=schedule.evaluate(t),slower.evaluate(2*t)
                    self.assertAlmostEqual(a['phase'],b['phase'])
                    self.assertAlmostEqual(a['angleVelocityDegreesPerSecond'],2*b['angleVelocityDegreesPerSecond'])
                    self.assertAlmostEqual(a['angleAccelerationDegreesPerSecond2'],4*b['angleAccelerationDegreesPerSecond2'])

    def test_fitting_handles_slow_controllers_and_rejects_impossible_budget(self):
        schedule=DoglegTiming.fit_duration(joint_speed_degrees=0.1)
        self.assertGreater(schedule.half_duration,50)
        with self.assertRaises(ValueError):
            DoglegTiming.fit_duration(joint_speed_degrees=0.01)
        for kwargs in (dict(joint_speed_degrees=True),dict(transition_seconds=0),
                       dict(joint_acceleration_limit=math.nan),dict(joint_acceleration_limit=1e-12)):
            with self.assertRaises(ValueError):
                DoglegTiming.fit_duration(**kwargs)

    def test_quintic_endpoints_and_analytic_derivative_maxima(self):
        self.assertEqual(quintic(0),(0,0,0))
        self.assertEqual(quintic(1),(1,0,0))
        for k in range(10001):
            q,dq,ddq=quintic(k/10000)
            self.assertTrue(0<=q<=1)
            self.assertLessEqual(dq,QUINTIC_SPEED+1e-12)
            self.assertLessEqual(abs(ddq),QUINTIC_ACCELERATION+1e-12)

    def test_velocity_and_acceleration_stop_at_turnaround_and_stage_boundaries(self):
        schedule=DoglegTiming(0.49999)
        self.assertEqual(len(schedule.segments),2)
        for t in schedule.report()['stopTimesSeconds']:
            row=schedule.evaluate(t)
            for key in ('angleVelocityDegreesPerSecond','angleAccelerationDegreesPerSecond2',
                        'compensationSpeedPerSecond','compensationAccelerationPerSecond2'):
                self.assertAlmostEqual(row[key],0,places=8)
        boundary=schedule.evaluate(schedule.segments[0]['endSeconds'])
        self.assertAlmostEqual(sum(boundary['stages']),5,places=12)

    def test_dense_derivatives_respect_reported_reference_budgets(self):
        for e in (0.4,0.49999,0.5,0.9):
            schedule=DoglegTiming(e)
            b=schedule.bounds
            for k in range(2001):
                row=schedule.evaluate(2*k/2000)
                self.assertLessEqual(2*abs(row['angleVelocityDegreesPerSecond']),b['maximumJointSpeedDegreesPerSecond']+1e-10)
                self.assertLessEqual(2*abs(row['angleAccelerationDegreesPerSecond2']),b['maximumJointAccelerationDegreesPerSecond2']+1e-10)
                self.assertLessEqual(abs(row['compensationSpeedPerSecond']),b['maximumStageSpeedPerSecond']+1e-10)
                self.assertLessEqual(abs(row['compensationAccelerationPerSecond2']),b['maximumStageAccelerationPerSecond2']+1e-10)
            self.assertLessEqual(b['maximumJointSpeedDegreesPerSecond'],6/math.sqrt(2))

    def test_same_fixed_tip_geometry_and_exact_round_trip(self):
        for axis in ('pitch','yaw'):
            schedule=DoglegTiming(0.49999,amplitude=-1,axis=axis)
            initial=stage_targets(0.49999,True)
            reference=forward_contact(initial,[(0,0)]*10,(56,12,-17))
            for k in range(101):
                row=schedule.evaluate(2*k/100)
                self.assertLess(math.dist(forward_contact(row['stages'],row['angles'],(56,12,-17)),reference),1e-9)
            self.assertEqual(schedule.evaluate(0)['stages'],schedule.evaluate(2)['stages'])
            self.assertFalse(schedule.report()['motionAuthorized'])

    def test_native_reference_steps_can_track_targets_at_irregular_intervals(self):
        schedule=DoglegTiming(0.49999)
        stages=stage_targets(0.49999,True)
        joints=[(0,0)]*10
        t=0
        for dt in (0.017,0.13,0.03,0.05,0.2,0.08,0.31,0.04,0.16,0.11,0.27,0.25,0.353):
            target=schedule.evaluate(min(2,t+dt))
            dt=min(2-t,dt)
            ready=[retraction_allowed(i,stages,target['extension'],True,joints) for i in range(10)]
            stages=step(stages,target['extension'],True,dt,transition=0.6,retract_ready=ready)
            joints=[step_joint(a,b,dt,6) for a,b in zip(joints,target['angles'])]
            for a,b in zip(stages,target['stages']):
                self.assertAlmostEqual(a,b,places=12)
            for a,b in zip(joints,target['angles']):
                self.assertLess(math.dist(a,b),1e-12)
            t=min(2,t+dt)
        self.assertEqual(t,2)

    def test_profiles_and_optional_acceleration_budget_reject_infeasible_time(self):
        with self.assertRaises(ValueError):
            DoglegTiming(half_duration=0.2)
        with self.assertRaises(ValueError):
            DoglegTiming(0.49999,joint_acceleration_limit=12)
        accepted=DoglegTiming(0.49999,half_duration=1.5,joint_acceleration_limit=12)
        self.assertLessEqual(accepted.bounds['maximumJointAccelerationDegreesPerSecond2'],12)
        for kwargs in (dict(half_duration=math.nan),dict(transition_seconds=0),dict(joint_speed_degrees=True)):
            with self.assertRaises(ValueError):
                DoglegTiming(**kwargs)
