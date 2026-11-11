"""PIE regression of the body-wide probe and geometric candidate classifier.

Run only after the four plans have been applied and compiled in the editor.
This script never installs graphs or moves the creature. Parameter changes
are confined to PIE copies and restored in finally.
"""
import json
from pathlib import Path
import sys

import unreal

sys.path.insert(0, str(Path(unreal.Paths.project_dir()).resolve() / 'tools'))
from beholder_support_candidate import candidate
from build_beholder_body_probe_graph import ARRAYS


def xyz(v):
    return (v.x, v.y, v.z)


def run():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    assert world, 'Start PIE after applying and compiling the body probe graphs'
    body = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                if a.get_class().get_name() == 'BP_BeholderBody_Test_C')
    components = {c.get_name(): c for c in body.get_components_by_class(unreal.ChildActorComponent)
                  if c.get_name().startswith('Leg')}
    legs = [components[f'Leg{i}'].get_editor_property('child_actor') for i in range(8)]
    setting_names = ('BodySupportMinNormalZ', 'BodySupportMaxGapCm', 'BodySupportPenetrationToleranceCm')
    # Fail before changing anything if the new Blueprint members are absent.
    saved_settings = tuple(body.get_editor_property(name) for name in setting_names)
    saved_distance = [leg.get_editor_property('ProbeTraceDistance') for leg in legs]
    report = {'passed': False, 'bodyUpdates': 0, 'legRowsChecked': 0,
              'classifierChecks': 0, 'error': None}

    def update():
        body.call_method('UpdateBodySurfaceProbes', ())
        report['bodyUpdates'] += 1

    def arrays():
        result = {}
        for name, type, _ in ARRAYS:
            values = list(body.get_editor_property(name))
            assert len(values) == 8, (name, len(values))
            result[name] = [xyz(v) for v in values] if type == 'Vector' else values
        return result

    def verify():
        state = arrays()
        assert body.get_editor_property('bBodyProbeSettingsValid')
        assert body.get_editor_property('BodyProbeMeasuredCount') == 8
        flags = []
        for i, leg in enumerate(legs):
            for name, type, source in ARRAYS:
                if source:
                    expected = leg.get_editor_property(source)
                    if type == 'Vector':
                        expected = xyz(expected)
                    assert state[name][i] == expected, (name, i, state[name][i], expected)
            expected_candidate = candidate(
                state['BodyProbeValid'][i], state['BodyProbeHit'][i], state['BodyProbePlaneValid'][i],
                state['BodyProbeNormals'][i][2], state['BodyProbePlaneClearances'][i], state['BodyProbeGaps'][i],
                *(body.get_editor_property(name) for name in setting_names))
            assert state['BodySupportCandidates'][i] == expected_candidate
            flags.append(expected_candidate)
            report['legRowsChecked'] += 1
        assert body.get_editor_property('BodySurfaceHitCount') == sum(state['BodyProbeHit'])
        assert body.get_editor_property('BodySupportCandidateCount') == sum(flags)
        return state

    try:
        update()
        verify()
        for leg in legs:
            leg.set_editor_property('ProbeTraceDistance', 0.0001)
        update()
        state = verify()
        assert not any(state['BodyProbeHit']), 'Use the elevated technical stand for the short-ray miss test'
        assert not any(state['BodySupportCandidates'])
        for leg, distance in zip(legs, saved_distance):
            leg.set_editor_property('ProbeTraceDistance', distance)
        update()
        verify()
        before = arrays()
        for index, component in ((-1, components['Leg0']), (8, components['Leg0']), (0, None)):
            body.call_method('SampleBodySurfaceLeg', (component, index))
            assert arrays() == before
            assert body.get_editor_property('BodyProbeMeasuredCount') == 8
        for settings in ((-1, 2, 0.1), (1.1, 2, 0.1), (0.8, -1, 0.1), (0.8, 101, 0.1),
                         (0.8, 2, -1), (0.8, 2, 2), (float('nan'), 2, 0.1)):
            for name, value in zip(setting_names, settings):
                body.set_editor_property(name, value)
            update()
            assert not body.get_editor_property('bBodyProbeSettingsValid')
            state = arrays()
            for name, type, _ in ARRAYS:
                assert all(v == ((0, 0, 0) if type == 'Vector' else 0) for v in state[name]), name
            for name in ('BodyProbeMeasuredCount', 'BodySurfaceHitCount', 'BodySupportCandidateCount'):
                assert body.get_editor_property(name) == 0
        for name, value in zip(setting_names, saved_settings):
            body.set_editor_property(name, value)
        readings = [(True, True, True, 1.0, 1.0, 1.0), (True, True, True, 0.5, 0.0, 0.0),
                    (True, True, True, 1.0, -1.0, 1.0), (True, True, True, 1.0, 333.0, 373.0),
                    (False, True, True, 1.0, 0.0, 0.0), (True, False, True, 1.0, 0.0, 0.0),
                    (True, True, False, 1.0, 0.0, 0.0), (True, True, True, 1.0, float('nan'), 0.0)]
        for reading in readings:
            actual = body.call_method('ClassifyBodySurfaceCandidate', reading)
            if isinstance(actual, tuple):
                assert len(actual) == 1
                actual = actual[0]
            assert isinstance(actual, bool)
            assert actual == candidate(*reading, *saved_settings), reading
            report['classifierChecks'] += 1
        report['passed'] = True
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        for name, value in zip(setting_names, saved_settings):
            body.set_editor_property(name, value)
        for leg, distance in zip(legs, saved_distance):
            leg.set_editor_property('ProbeTraceDistance', distance)
        try:
            update()
        except Exception as exc:
            report.update(passed=False, error=report['error'] or str(exc))
        path = Path(unreal.Paths.project_dir())/'Saved/BeholderBodyProbeRegression.json'
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    assert report['passed'], report['error']


if __name__ == '__main__':
    run()
