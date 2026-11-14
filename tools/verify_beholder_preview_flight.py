"""Editor Python: short native PIE spectator-input probe, restoring its pose.

Run run() in an idle, unpaused preview PIE. Does not emulate keyboard events,
edit assets, drive the Beholder, or change pause/time-dilation settings.
"""
import json
from pathlib import Path
import time

import unreal

_active = None


def run():
    global _active
    if _active is not None:
        raise RuntimeError('Preview flight verification is already running')
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if not world or unreal.GameplayStatics.is_game_paused(world):
        raise RuntimeError('Start an unpaused preview PIE first')
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    if not isinstance(pawn, unreal.SpectatorPawn):
        raise RuntimeError('Player 0 must possess the preview SpectatorPawn')
    if controller.is_move_input_ignored() or controller.is_look_input_ignored():
        raise RuntimeError('Preview input is blocked')
    movement = pawn.get_movement_component()
    if not movement.is_active() or pawn.get_velocity().length() > 0.001:
        raise RuntimeError('Preview camera must be idle with active movement')
    if pawn.get_pending_movement_input_vector().length() > 0.001:
        raise RuntimeError('Release movement controls before verification')
    location, rotation = pawn.get_actor_location(), pawn.get_actor_rotation()
    control_rotation = controller.get_control_rotation()
    axes = [('x', unreal.Vector(1, 0, 0)), ('y', unreal.Vector(0, 1, 0)),
            ('z', unreal.Vector(0, 0, 1)), ('-x', unreal.Vector(-1, 0, 0)),
            ('-y', unreal.Vector(0, -1, 0)), ('-z', unreal.Vector(0, 0, -1))]
    path = Path(unreal.Paths.project_saved_dir())/'BeholderPreviewFlight.json'
    report = dict(passed=False, running=True, samples=[], keyboardEventsTested=False,
                  nativePawnMovementInput=True, assetsModified=False,
                  startLocation=dict(x=location.x, y=location.y, z=location.z))
    state = dict(index=0, start=time.monotonic(), handle=None)

    def write():
        path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')

    def restore():
        pawn.consume_movement_input_vector()
        movement.stop_movement_immediately()
        pawn.set_actor_location_and_rotation(location, rotation, False, True)
        controller.set_control_rotation(control_rotation)
        if (pawn.get_actor_location()-location).length() > 1e-6:
            raise RuntimeError('Camera position was not restored')
        if pawn.get_velocity().length() > 1e-6:
            raise RuntimeError('Camera velocity was not cleared')

    def finish(error=None):
        global _active
        report.update(passed=False, running=False)
        if error is not None:
            report['error'] = repr(error)
        try:
            restore()
            report['poseRestored'] = True
        except Exception as exc:
            report['restoreError'] = repr(exc)
        finally:
            unreal.unregister_slate_post_tick_callback(state['handle'])
            _active = None
        report['passed'] = error is None and report.get('poseRestored', False)
        write()

    def tick(_delta):
        try:
            if unreal.GameplayStatics.get_player_pawn(world, 0) != pawn:
                raise RuntimeError('Player pawn changed during verification')
            if unreal.GameplayStatics.is_game_paused(world):
                raise RuntimeError('PIE paused during verification')
            name, direction = axes[state['index']]
            if time.monotonic()-state['start'] >= 0.2:
                displacement = pawn.get_actor_location()-location
                projection = displacement.dot(direction)
                sideways = (displacement-direction*projection).length()
                report['samples'].append(dict(axis=name, travelCm=projection, offAxisCm=sideways))
                if not 0.01 < projection < 500 or sideways > 0.1:
                    raise RuntimeError('Unexpected camera travel: '+str(report['samples'][-1]))
                restore()
                state['index'] += 1
                if state['index'] == len(axes):
                    finish()
                    return
                state['start'] = time.monotonic()
                direction = axes[state['index']][1]
            pawn.add_movement_input(direction, 1.0, False)
        except Exception as exc:
            finish(exc)

    write()
    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    _active = state
    print('Preview flight probe scheduled; keep movement controls released')
    return str(path)
