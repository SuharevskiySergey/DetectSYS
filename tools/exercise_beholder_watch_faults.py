"""Synchronous PIE-only watchdog fault injections before any motion Tick.

Inputs/state and the floor's Visibility response are restored. This tests
the guard logic, not physical collision or real-time stopping distance.
"""
import unreal


def check_faults(body, legs, indices, floor_actor):
    rows = []

    def assert_hold(reason):
        assert body.get_editor_property('FourContactWatchState') == 3
        assert body.get_editor_property('FourContactWatchReason') == reason
        for i in indices:
            assert abs(legs[i].get_editor_property('ExtensionAmount')-
                       legs[i].get_editor_property('ExtensionPosition')) < 1e-6

    def restart():
        body.call_method('ReleaseExperimentalFourContact', ())
        assert all(abs(legs[i].get_editor_property('ExtensionPosition')) < 1e-6 for i in indices)
        for i in indices:
            body.call_method('SetBodyLegExtension', (i, 0.0))
        body.set_editor_property('bEnableExperimentalFourContact', True)
        body.call_method('TryExperimentalFourContact', ())
        assert body.get_editor_property('bLastFourContactRequestAccepted')
        assert body.get_editor_property('FourContactWatchState') == 1

    before = [l.get_editor_property('ExtensionAmount') for l in legs]
    body.call_method('TryExperimentalFourContact', ())
    assert not body.get_editor_property('bLastFourContactRequestAccepted')
    body.call_method('UpdateExperimentalContactWatch', (0.0,))
    assert body.get_editor_property('FourContactWatchState') == 1
    assert [l.get_editor_property('ExtensionAmount') for l in legs] == before
    rows.append(dict(case='rejected_repeat_keeps_active_watch', state=1, reason=0))
    preference = body.get_editor_property('FourContactCompletionMinimumMarginCm')
    owned_margin = body.get_editor_property('FourContactWatchRequiredMarginCm')
    try:
        body.set_editor_property('FourContactCompletionMinimumMarginCm', -1.0)
        body.call_method('TryExperimentalFourContact', ())
        assert not body.get_editor_property('bLastFourContactRequestAccepted')
        assert body.get_editor_property('FourContactWatchRequiredMarginCm') == owned_margin
        body.call_method('UpdateExperimentalContactWatch', (0.0,))
        assert body.get_editor_property('FourContactWatchState') == 1
        assert [l.get_editor_property('ExtensionAmount') for l in legs] == before
        rows.append(dict(case='invalid_repeat_keeps_captured_margin', state=1, reason=0))
    finally:
        body.set_editor_property('FourContactCompletionMinimumMarginCm', preference)
    body.call_method('CancelExperimentalFourContact', ())
    assert_hold(5)
    rows.append(dict(case='explicit_cancel', state=3, reason=5))

    component = floor_actor.get_component_by_class(unreal.StaticMeshComponent)
    assert component
    channel = unreal.CollisionChannel.ECC_VISIBILITY
    for case, reason in [('disabled', 1), ('body_moved', 2), ('surface_lost', 3),
                         ('claw_request', 3), ('owned_goal_changed', 3), ('upper_goal', 3),
                         ('timeout', 4), ('invalid_delta', 4), ('invalid_probe_settings', 3)]:
        restart()
        restore = None
        try:
            delta = 0.0
            if case == 'disabled':
                body.set_editor_property('bEnableExperimentalFourContact', False)
                restore = lambda: body.set_editor_property('bEnableExperimentalFourContact', True)
            elif case == 'body_moved':
                p = body.get_actor_location()
                body.set_actor_location(unreal.Vector(p.x+1, p.y, p.z), False, True)
                restore = lambda: body.set_actor_location(p, False, True)
            elif case == 'surface_lost':
                response = component.get_collision_response_to_channel(channel)
                component.set_collision_response_to_channel(channel, unreal.CollisionResponseType.ECR_IGNORE)
                restore = lambda: component.set_collision_response_to_channel(channel, response)
            elif case == 'claw_request':
                request = legs[indices[-1]].get_editor_property('SocketRequestedClaw2')
                legs[indices[-1]].set_editor_property('SocketRequestedClaw2', 0.2)
                restore = lambda: legs[indices[-1]].set_editor_property('SocketRequestedClaw2', request)
            elif case == 'owned_goal_changed':
                # Abort deliberately replaces an incompatible goal on an owned
                # lower leg with its current amount; do not restore that goal.
                body.call_method('SetBodyLegExtension', (indices[0], 0.8))
            elif case == 'upper_goal':
                goal = legs[1].get_editor_property('ExtensionAmount')
                legs[1].set_editor_property('ExtensionAmount', 0.2)
                restore = lambda: legs[1].set_editor_property('ExtensionAmount', goal)
            elif case == 'timeout':
                timeout = body.get_editor_property('FourContactWatchTimeout')
                body.set_editor_property('FourContactWatchTimeout', 0.1)
                delta = 0.2
                restore = lambda: body.set_editor_property('FourContactWatchTimeout', timeout)
            elif case == 'invalid_delta':
                delta = float('nan')
            elif case == 'invalid_probe_settings':
                value = body.get_editor_property('BodySupportMaxGapCm')
                body.set_editor_property('BodySupportMaxGapCm', -1.0)
                restore = lambda: body.set_editor_property('BodySupportMaxGapCm', value)
            body.call_method('UpdateExperimentalContactWatch', (delta,))
            assert_hold(reason)
            if case == 'upper_goal':
                assert abs(legs[1].get_editor_property('ExtensionAmount')-0.2) < 1e-6
            rows.append(dict(case=case, state=3, reason=reason))
        finally:
            if restore:
                restore()
    restart()
    return rows
