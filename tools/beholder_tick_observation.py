"""Read-only sampled native-update telemetry; never drives the controller.

Elapsed deltas are controller game-time windows, not CPU or render durations.
The controller clamps its final elapsed to the requested motion duration, so
the final window may understate that frame's actual game delta.
A window spanning several native updates cannot certify each frame's delta.
"""
import math


def observe(timing, updates, elapsed):
    if type(updates) is not int or updates < 0 or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('Nonnegative update count and finite elapsed required')
    old_count = timing.get('nativeUpdates', 0)
    old_elapsed = timing.get('gameElapsedSeconds', 0.0)
    if updates < old_count or elapsed < old_elapsed:
        raise ValueError('Use a fresh timing record for each motion')
    if updates == old_count:
        if elapsed != old_elapsed:
            raise ValueError('Elapsed changed without a native update')
        return
    count = updates-old_count
    delta = elapsed-old_elapsed
    timing.update(nativeUpdates=updates, gameElapsedSeconds=elapsed,
                  meanGameSecondsPerUpdate=elapsed/updates,
                  observedWindows=timing.get('observedWindows', 0)+1,
                  skippedNativeUpdates=timing.get('skippedNativeUpdates', 0)+count-1,
                  maximumObservedWindowSeconds=max(timing.get('maximumObservedWindowSeconds', 0.0), delta))
    if count == 1:
        timing['singleUpdateWindows'] = timing.get('singleUpdateWindows', 0)+1
        timing['maximumSingleUpdateElapsedSeconds'] = max(timing.get('maximumSingleUpdateElapsedSeconds', 0.0), delta)
