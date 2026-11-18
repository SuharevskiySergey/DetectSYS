"""Opt-in editor-only numeric checks of two damage library functions.

No import-time editor access, actors, gameplay, PIE, compilation or asset writes.
Separate user permission is required for every run; the opt-in is not permission.
"""
import json
import math
from pathlib import Path
import traceback
import uuid


BP = '/Game/BeholderPrototype/Damage/BP_BeholderDamageSnapshot'
HELPER = 'EvaluateLegDamageSnapshot'
AGGREGATE = 'EvaluateDamageSnapshot'
HELPER_OUTPUTS = (('NumericInputsAccepted', bool), ('Failed', bool), ('AbortMelee', bool),
                  ('RequestSafeRetraction', bool), ('FinishExistingMelee', bool),
                  ('FailedContribution', int))
AGGREGATE_OUTPUTS = (
    ('NumericInputsAccepted', bool), ('MotionAuthorized', bool), ('FailedLegCount', int),
    ('NeutralizationRequired', bool), ('RejectNewAttacks', bool), ('HasSurvivingMelee', bool),
    ('PreserveCurrentMainEyeState', bool), ('RequestCloseMainEye', bool),
    ('RequestDisableAntimagic', bool), ('GameplayNeutralizedConfirmed', bool),
    ('BeamTransitionUnresolved', bool))+tuple(
    (f'Leg{i}{field}', bool) for i in range(8)
    for field in ('Failed', 'AbortMelee', 'RequestSafeRetraction', 'FinishExistingMelee'))


def helper_reference(hp, active):
    accepted = math.isfinite(hp) and 0 <= hp <= 100
    failed = accepted and hp == 0
    return dict(NumericInputsAccepted=accepted, Failed=failed, AbortMelee=failed and active,
                RequestSafeRetraction=failed, FinishExistingMelee=accepted and hp > 0 and active,
                FailedContribution=int(failed))


def aggregate_reference(health, active, latched, neutralized):
    result = {name: kind() for name, kind in AGGREGATE_OUTPUTS}
    legs = [helper_reference(hp, moving) for hp, moving in zip(health, active)]
    surviving = any(leg['FinishExistingMelee'] for leg in legs)
    if not all(leg['NumericInputsAccepted'] for leg in legs) or neutralized and surviving:
        return result
    count = sum(leg['FailedContribution'] for leg in legs)
    required = count >= 5 or latched or neutralized
    result.update(NumericInputsAccepted=True, FailedLegCount=count,
                  NeutralizationRequired=required, RejectNewAttacks=required,
                  HasSurvivingMelee=surviving, PreserveCurrentMainEyeState=required and surviving,
                  RequestCloseMainEye=required and not surviving,
                  RequestDisableAntimagic=required and not surviving,
                  BeamTransitionUnresolved=required)
    for i, leg in enumerate(legs):
        for field in ('Failed', 'AbortMelee', 'RequestSafeRetraction', 'FinishExistingMelee'):
            result[f'Leg{i}{field}'] = leg[field]
    return result


def _decode(raw, layout):
    if type(raw) is not tuple or len(raw) != len(layout):
        raise ValueError('Unexpected reflected damage output tuple layout')
    result = {}
    for (name, kind), value in zip(layout, raw):
        if type(value) is not kind:
            raise ValueError('Unexpected exact reflected output type: '+name)
        result[name] = value
    return result


def run(*, allow_numeric_calls=False):
    if allow_numeric_calls is not True:
        raise PermissionError('Separate permission and explicit numeric-call opt-in required')
    import unreal

    def require_edit_mode():
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor is None or editor.get_game_world() is not None:
            raise RuntimeError('Edit mode without game world required; no PIE/simulation')

    require_edit_mode()
    cls = unreal.load_class(None, BP+'.BP_BeholderDamageSnapshot_C')
    if cls is None:
        raise RuntimeError('Damage library class not available')
    library = unreal.get_default_object(cls)
    if not isinstance(library, unreal.BlueprintFunctionLibrary):
        raise TypeError('Only the isolated Function Library CDO is allowed')
    path = Path(unreal.Paths.project_dir())/'Saved'/('BeholderDamageNumeric_'+uuid.uuid4().hex+'.json')
    report = dict(passed=False, running=True, blueprintPath=BP, records=[],
                  helperCases=0, aggregateCases=0, pieStarted=False,
                  gameplayConnected=False, actorCommandsIssued=False, motionAuthorized=False,
                  binding='CDO.call_method(name, (None, *inputs)); inspected WorldContext first')
    with path.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2, allow_nan=False)

    def check(case_id, function, arguments, layout, expected, described_inputs):
        record = dict(caseId=case_id, function=function, inputs=described_inputs,
                      expected=expected, passed=False)
        report['records'].append(record)
        require_edit_mode()
        raw = library.call_method(function, (None,)+tuple(arguments))
        require_edit_mode()
        actual = _decode(raw, layout)
        record['actual'] = actual
        if actual != expected:
            raise AssertionError('Damage numeric mismatch: '+case_id)
        record['passed'] = True
        report['helperCases' if function == HELPER else 'aggregateCases'] += 1

    try:
        hp_values = (0.0, 0.5, 50.0, 100.0, -0.5, 100.5, float('nan'), float('inf'), -float('inf'))
        for index, hp in enumerate(hp_values):
            for active in (False, True):
                check(f'helper:{index}:{active}', HELPER, (hp, active), HELPER_OUTPUTS,
                      helper_reference(hp, active), dict(HealthPercent=repr(hp), MeleeActive=active))

        def aggregate_case(case_id, health, active, latched=False, neutralized=False):
            check(case_id, AGGREGATE, tuple(health)+tuple(active)+(latched, neutralized),
                  AGGREGATE_OUTPUTS, aggregate_reference(health, active, latched, neutralized),
                  dict(HealthPercent=[repr(hp) for hp in health], MeleeActive=list(active),
                       NeutralizationLatched=latched, PreviouslyNeutralized=neutralized))

        masks = ((False,)*8, (True,)*8, tuple(i % 2 == 0 for i in range(8)))
        for failed_count in range(9):
            health = tuple(0.0 if i < failed_count else 100.0 for i in range(8))
            for mask_index, active in enumerate(masks):
                for latched in (False, True):
                    for neutralized in (False, True):
                        aggregate_case(f'aggregate:{failed_count}:{mask_index}:{latched}:{neutralized}',
                                       health, active, latched, neutralized)
        for slot in range(8):
            for invalid_index, hp in enumerate(hp_values[4:]):
                health = [100.0]*8
                health[slot] = hp
                aggregate_case(f'invalid_slot:{slot}:{invalid_index}', health, (True,)*8)
            health = tuple(0.0 if i == slot else 100.0 for i in range(8))
            aggregate_case(f'isolated_failed_slot:{slot}', health, (True,)*8)
        require_edit_mode()
        report['editModeConfirmedAfter'] = True
        report['passed'] = True
    except Exception as exc:
        report.update(error=repr(exc), traceback=traceback.format_exc())
        raise
    finally:
        report['running'] = False
        # Only replace this run's own UUID-reserved file, never another archive.
        path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        print('DAMAGE_NUMERIC_REPORT', str(path))
        print('DAMAGE_NUMERIC_SUMMARY', json.dumps({key: report[key] for key in
              ('passed', 'running', 'helperCases', 'aggregateCases', 'motionAuthorized')}))
    return report
