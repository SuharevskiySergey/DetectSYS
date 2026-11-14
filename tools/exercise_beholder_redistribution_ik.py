"""Read-only bridge from an actually packed PIE leg to offline position IK.

Called synchronously at passive completion, before explicit monitoring/Release.
No root/joint/stage command, sensor call or native updater is issued here.
An endpoint solution is NOT permission to execute its interpolated trajectory.
"""
import json
import math
from pathlib import Path

import unreal

from beholder_contact_ik import forward_contact, solve_contact_position
from beholder_contact_path import check_contact_path
from generate_beholder_telescope import COUNT, stage_targets
from lapa5_geometry import claw_vertices_world


def xyz(v):
    return (v.x, v.y, v.z)


def transform_signature(transform):
    q = transform.rotation
    return (xyz(transform.translation), (q.x, q.y, q.z, q.w), xyz(transform.scale3d))


def signature(leg):
    fields = ['RedistributionState', 'RedistributionDirection', 'RedistributionReason',
              'RedistributionElapsed', 'RedistributionProgress', 'RedistributionUpdates',
              'RedistributionContactSamples', 'RedistributionMonitoringUpdates',
              'bRedistributionContactOwned', 'bSequentialMotion', 'ExtensionAmount', 'ExtensionPosition']
    return (transform_signature(leg.get_actor_transform()), tuple(leg.get_editor_property(n) for n in fields),
            tuple(leg.get_editor_property(f'Stage{i}Position') for i in range(COUNT)),
            tuple(xyz(leg.get_editor_property(f'Joint{i}Bend')) for i in range(1, COUNT)),
            tuple(sorted((c.get_name(), transform_signature(c.get_relative_transform()))
                         for c in leg.get_components_by_class(unreal.StaticMeshComponent))))


def run(leg):
    extension = leg.get_editor_property('RedistributionExtension')
    path = Path(unreal.Paths.project_dir())/'Saved'/f'BeholderRedistribution_IK_E{extension:.6f}.json'
    report = dict(passed=False, running=True, motionAuthorized=False, runtimeIKExecuted=False,
                  originalExtension=extension, cases=[], error=None)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    before = None
    try:
        before = signature(leg)
        assert leg.get_class().get_name() == 'BP_BeholderStageRedistribution_Test_C'
        assert leg.get_editor_property('RedistributionState') == 2
        assert leg.get_editor_property('RedistributionDirection') == 1
        assert leg.get_editor_property('bSequentialMotion') and leg.get_editor_property('bRedistributionContactOwned')
        stages = [leg.get_editor_property(f'Stage{i}Position') for i in range(COUNT)]
        assert all(abs(a-b) <= 1e-6 for a, b in zip(stages, stage_targets(extension, True)))
        assert all(abs(leg.get_editor_property(f'Joint{i}Magnitude')) <= 1e-6 for i in range(1, COUNT))
        angles = [(0, 0)]*COUNT
        parts = {c.get_name(): c for c in leg.get_components_by_class(unreal.StaticMeshComponent)}
        tip_transform = parts['Sleeve09'].get_world_transform()
        actor_transform = leg.get_actor_transform()
        head = next(c for c in leg.get_components_by_class(unreal.ChildActorComponent)
                    if c.get_name() == 'HeadModule').get_editor_property('child_actor')
        anchor = leg.get_editor_property('RedistributionContactPoint')
        normal = xyz(leg.get_editor_property('RedistributionContactNormal'))
        assert normal[2] > 0.99999
        contact_tip = xyz(tip_transform.inverse_transform_location(anchor))
        vertices_world = [v for claw in claw_vertices_world(head) for v in claw]
        vertices_tip = [xyz(tip_transform.inverse_transform_location(v)) for v in vertices_world]
        center_tip = xyz(tip_transform.inverse_transform_location(head.get_actor_location()))
        radius_world = 27*max(abs(v) for v in xyz(head.get_actor_scale3d()))
        origin = actor_transform.transform_location(unreal.Vector(0, 0, 0))
        basis = [xyz(actor_transform.transform_location(unreal.Vector(*axis))-origin)
                 for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
        checks = [(anchor, contact_tip), (head.get_actor_location(), center_tip)]+list(zip(vertices_world, vertices_tip))
        errors = [math.dist(xyz(actor_transform.transform_location(unreal.Vector(*forward_contact(stages, angles, local)))), xyz(world))
                  for world, local in checks]
        report.update(liveFKPoints=len(errors), maximumLiveFKWorldErrorCm=max(errors),
                      initialStages=stages, contactWorld=xyz(anchor), contactTipLocal=contact_tip)
        assert max(errors) <= 1e-4, ('Actual packed geometry differs from FK', max(errors))
        for translation in ((0, 0, 0), (0.1, 0, 0), (-0.1, 0, 0),
                            (1.1, 0, 0), (-1.1, 0, 0), (0, 1.1, 0), (0, -1.1, 0)):
            target = actor_transform.inverse_transform_location(anchor-unreal.Vector(*translation))
            solution = solve_contact_position(math.fsum(stages)/COUNT, contact_tip, xyz(target))
            reconstructed = actor_transform.transform_location(unreal.Vector(*solution['pointLocal']))+unreal.Vector(*translation)
            transition = check_contact_path(stages, solution['stages'], solution['angles'], contact_tip,
                vertices_tip, center_tip, radius_world, xyz(origin), basis, translation, xyz(anchor), normal)
            report['cases'].append(dict(translationWorldCm=translation, solution=solution,
                endpointResidualWorldCm=math.dist(xyz(reconstructed), xyz(anchor)), transition=transition,
                bodyApertureChecked=False, otherLegsChecked=False, runtimeMotionAuthorized=False))
        assert report['cases'][0]['solution']['converged']
        assert report['cases'][0]['transition']['sampledChecksPass']
        after = signature(leg)
        report.update(liveSnapshotBefore=before, liveSnapshotAfter=after)
        assert before == after, 'Offline inspection changed live state'
        report.update(passed=True, running=False, liveStateUnchanged=True,
            endpointSolutions=sum(c['solution']['converged'] for c in report['cases']),
            sampledPathsPassing=sum(c['transition']['sampledChecksPass'] for c in report['cases']))
    except Exception as exc:
        try:
            unchanged = before is not None and before == signature(leg)
        except Exception:
            unchanged = False
        report.update(passed=False, running=False, error=repr(exc), liveStateUnchanged=unchanged)
        path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        raise
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    return dict(path=str(path), passed=True, liveFKPoints=report['liveFKPoints'],
                maximumLiveFKWorldErrorCm=report['maximumLiveFKWorldErrorCm'],
                endpointSolutions=report['endpointSolutions'], sampledPathsPassing=report['sampledPathsPassing'],
                motionAuthorized=False, liveStateUnchanged=True)
