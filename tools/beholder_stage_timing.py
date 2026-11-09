"""Reference for snapshot-based sequential time allocation in the Blueprint.

Each directional queue consumes one frame's travel budget, not one frame per
stage boundary. Safety waits deliberately do not accumulate unused time.
"""
import math

from generate_beholder_telescope import COUNT, stage_targets


def step(stages, target, sequential, dt, transition=0.6, retract_ready=None,
         motion_ready=True):
    if len(stages) != COUNT or any(not math.isfinite(v) or not 0 <= v <= 1 for v in stages):
        raise ValueError('Ten finite stage values in 0..1 required')
    if not all(math.isfinite(v) for v in (target, dt, transition)):
        raise ValueError('Finite target, time and duration required')
    goals = stage_targets(target, sequential)
    ready = [True]*COUNT if retract_ready is None else retract_ready
    if len(ready) != COUNT:
        raise ValueError('Ten retraction readiness flags required')
    budget = max(0, dt)*(COUNT if sequential else 1)/max(transition, 0.01)
    if not motion_ready:
        budget = 0
    output = []
    for i, (current, goal) in enumerate(zip(stages, goals)):
        retracting = current > goal
        predecessors = range(i+1, COUNT) if retracting else range(i)
        distance = lambda j: max(stages[j]-goals[j], 0) if retracting else max(goals[j]-stages[j], 0)
        blocked = retracting and (not ready[i] or
                                 (sequential and any(distance(j) > 0 and not ready[j] for j in predecessors)))
        remaining = max(0, budget-sum(distance(j) for j in predecessors)) if sequential else budget
        travel = 0 if blocked else min(abs(goal-current), remaining)
        output.append(current+(-travel if retracting else travel))
    return output
