"""On-demand editor/PIE diagnostic; does not implement a gameplay sensor."""
import importlib
import json
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
import beholder_surface_probe
importlib.reload(beholder_surface_probe)
from beholder_surface_probe import downward_segment, lowest_head_point, head_plane_clearance
from lapa5_geometry import claw_vertices_world


def xyz(v):
    return (v.x, v.y, v.z)


def inspect(distance=1000.0, lift=1.0, verbose=True):
    # Reject configuration errors before reporting eight misleading failures.
    downward_segment((0, 0, 0), distance, lift)
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = subsystem.get_game_world() or subsystem.get_editor_world()
    bodies = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
              if a.get_class().get_name() == 'BP_BeholderBody_Test_C']
    assert len(bodies) == 1, 'Expected one eight-leg prototype'
    body = bodies[0]
    ignored = [body] + list(body.get_all_child_actors(True))
    rows = []
    for component in sorted(body.get_components_by_class(unreal.ChildActorComponent), key=lambda c: c.get_name()):
        leg = component.get_editor_property('child_actor')
        if not component.get_name().startswith('Leg'):
            continue
        row = {'leg': component.get_name(), 'valid': False, 'hit': False,
               'impactPoint': None, 'impactNormal': None, 'gap': None,
               'hitActor': None, 'planeEstimate': None}
        try:
            head = next(c for c in leg.get_components_by_class(unreal.ChildActorComponent)
                        if c.get_name() == 'HeadModule').get_editor_property('child_actor')
            scale = head.get_actor_scale3d()
            radius = 27*max(abs(scale.x), abs(scale.y), abs(scale.z))
            center = xyz(head.get_actor_location())
            claws = [[xyz(v) for v in claw] for claw in claw_vertices_world(head)]
            point = lowest_head_point(center, radius, claws)
            start, end = downward_segment(point['point'], distance, lift)
            hit = unreal.SystemLibrary.line_trace_single(
                leg, unreal.Vector(*start), unreal.Vector(*end),
                unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignored,
                unreal.DrawDebugTrace.NONE, True)
            row.update(valid=True, lowest=point, start=start, end=end)
            if hit is not None:
                # Python's HitResult fields follow BreakHitResult tuple order.
                fields = hit.to_tuple()
                assert not fields[1], 'Initial overlap is not a valid surface sample'
                if fields[0]:
                    impact, normal, actor = fields[5], fields[7], fields[9]
                    assert actor not in ignored, 'Probe hit its own assembly'
                    row.update(hit=True, impactPoint=xyz(impact), impactNormal=xyz(normal),
                               hitActor=actor.get_path_name() if actor else None,
                               gap=point['point'][2]-impact.z,
                               planeEstimate=head_plane_clearance(center, radius, claws, xyz(impact), xyz(normal)))
        except Exception as exc:
            row.update(valid=False, hit=False, error=str(exc),
                       impactPoint=None, impactNormal=None, gap=None, hitActor=None, planeEstimate=None)
        rows.append(row)
    assert len(rows) == 8
    report = {'mode': 'PIE' if subsystem.get_game_world() else 'editor',
              'diagnosticOnly': True, 'legs': rows}
    if verbose:
        print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    inspect()
