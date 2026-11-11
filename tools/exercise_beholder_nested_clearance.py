"""Read-only comparison of offline nesting bounds with actual PIE transforms."""
import json
from pathlib import Path

import unreal

from beholder_nested_clearance import check_nested_pose
import validate_beholder_body as geometry
from validate_beholder_telescope import validate_nested_walls, validate_head
from lapa5_geometry import claw_vertices_world


def run():
    path = Path(unreal.Paths.project_dir())/'Saved/BeholderNestedLiveRegression.json'
    report = dict(passed=False, running=True, legs=[], maximumClearanceErrorLocalCm=0, maximumHeadErrorLocalCm=0)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    try:
        body = geometry.find_body()
        geometry.validate(body)
        for i, leg in enumerate(geometry.legs(body)):
            parts = {c.get_name(): c for c in leg.get_components_by_class(unreal.StaticMeshComponent)}
            stages = [leg.get_editor_property(f'Stage{j}Position') for j in range(10)]
            angles = [(0, 0)]+[(leg.get_editor_property(f'Joint{j}Bend').x,
                                leg.get_editor_property(f'Joint{j}Bend').y) for j in range(1, 10)]
            sleeves = [parts[f'Sleeve{j:02d}'] for j in range(10)]
            tip = sleeves[-1].get_world_transform()
            head = next(c for c in leg.get_components_by_class(unreal.ChildActorComponent)
                        if c.get_name() == 'HeadModule').get_editor_property('child_actor')
            def xyz(v):
                return (v.x, v.y, v.z)
            head_geometry = dict(claw_vertices_tip=[xyz(tip.inverse_transform_location(v))
                                                   for claw in claw_vertices_world(head) for v in claw],
                                 sphere_center_tip=xyz(tip.inverse_transform_location(head.get_actor_location())),
                                 sphere_radius_local=27*max(abs(v) for v in xyz(head.get_actor_scale3d()))
                                                     /abs(leg.get_actor_scale3d().x))
            offline = check_nested_pose(stages, angles, head_geometry=head_geometry)
            actual = validate_nested_walls(sleeves)
            actual_head = validate_head(leg, sleeves)
            assert offline['passed']
            assert offline['overlappingPairs'] == actual['overlappingAxialSlabsChecked']
            a, b = offline['minimumClearanceLocalCm'], actual['minimumClearanceLocal']
            assert (a is None) == (b is None)
            error = 0 if a is None else abs(a-b)
            assert error < 1e-6, (i, error)
            head_error = abs(offline['head']['minimumClawAxialLocalCm']-actual_head['minimumClawAxialLocal'])
            a, b = offline['head']['minimumShellClearanceLocalCm'], actual_head['shellClearanceLowerBoundLocal']
            assert (a is None) == (b is None)
            if a is not None:
                head_error = max(head_error, abs(a-b))
            assert head_error < 1e-6, (i, head_error)
            report['maximumClearanceErrorLocalCm'] = max(report['maximumClearanceErrorLocalCm'], error)
            report['maximumHeadErrorLocalCm'] = max(report['maximumHeadErrorLocalCm'], head_error)
            report['legs'].append(dict(index=i, overlappingPairs=offline['overlappingPairs'],
                                       nonadjacentOverlappingPairs=offline['nonadjacentOverlappingPairs'],
                                       minimumClearanceLocalCm=offline['minimumClearanceLocalCm'], errorLocalCm=error,
                                       headErrorLocalCm=head_error))
        report['passed'] = True
    except Exception as exc:
        report['error'] = repr(exc)
        raise
    finally:
        report['running'] = False
        path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(report))
    return report


if __name__ == '__main__':
    run()
