"""Sampled stage-motion audit, not a collision or per-frame certification.

Uses controller elapsed (clamped on the last update), normalised stage positions
and the public motion profile. Never writes an Unreal object or drives Tick.
"""
import math


class StageObservation:
    def __init__(self, initial, target, duration, extension_seconds, retraction_seconds, tolerance=1e-6):
        self.initial = tuple(initial)
        self.target = tuple(target)
        if len(self.initial) != 10 or len(self.target) != 10:
            raise ValueError('Ten stages required')
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in self.initial+self.target):
            raise ValueError('Finite stage positions in 0..1 required')
        if any(not math.isfinite(v) or v <= 0 for v in (duration, extension_seconds, retraction_seconds, tolerance)):
            raise ValueError('Positive finite duration, profile and tolerance required')
        if abs(math.fsum(self.initial)-math.fsum(self.target)) > 10*tolerance:
            raise ValueError('Redistribution must conserve extension')
        self.duration = duration
        self.extension_seconds = extension_seconds
        self.retraction_seconds = retraction_seconds
        self.tolerance = tolerance
        self.previous = self.initial
        self.elapsed = 0.0
        self.report = dict(sampledWindows=0, maximumNormalisedSpeedPerSecond=0.0,
                           maximumStageDelta=0.0, maximumSumError=0.0,
                           maximumAffineError=0.0, continuousCertified=False)

    def observe(self, stages, elapsed):
        stages = tuple(stages)
        if len(stages) != 10 or any(not math.isfinite(v) or not -self.tolerance <= v <= 1+self.tolerance for v in stages):
            raise ValueError('Invalid observed stages')
        if not math.isfinite(elapsed) or not self.elapsed <= elapsed <= self.duration:
            raise ValueError('Elapsed must be monotonic within the motion')
        dt = elapsed-self.elapsed
        delta = [b-a for a, b in zip(self.previous, stages)]
        affine_error = max(abs(s-(a+(b-a)*elapsed/self.duration))
                           for s, a, b in zip(stages, self.initial, self.target))
        sum_error = abs(math.fsum(stages)-math.fsum(self.initial))
        if affine_error > self.tolerance or sum_error > 10*self.tolerance:
            raise ValueError('Affine trajectory or conservation violated')
        for d, a, b in zip(delta, self.initial, self.target):
            if d*(1 if b >= a else -1) < -2*self.tolerance:
                raise ValueError('Stage reversed its commanded direction')
            seconds = self.extension_seconds if d >= 0 else self.retraction_seconds
            if abs(d) > dt/seconds+2*self.tolerance:
                raise ValueError('Observed displacement exceeds profile budget')
        if dt:
            self.report['sampledWindows'] += 1
            self.report['maximumNormalisedSpeedPerSecond'] = max(
                self.report['maximumNormalisedSpeedPerSecond'], max(abs(d) for d in delta)/dt)
        self.report['maximumStageDelta'] = max(self.report['maximumStageDelta'], max(abs(d) for d in delta))
        self.report['maximumSumError'] = max(self.report['maximumSumError'], sum_error)
        self.report['maximumAffineError'] = max(self.report['maximumAffineError'], affine_error)
        self.previous, self.elapsed = stages, elapsed
