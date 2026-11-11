import unittest

import build_beholder_retraction_graph as graph
import build_beholder_contact_watch_graph as watch
from build_beholder_contact_request_graph import INDICES


class RetractionGraphTests(unittest.TestCase):
    def test_batches_fit_and_aliases_are_unique(self):
        for build in (graph.members, graph.leg, graph.inspect, graph.check, graph.request, graph.update):
            ops = build()
            self.assertLessEqual(len(ops), 200)
            ids = [o['id'] for o in ops if 'id' in o]
            self.assertEqual(len(ids), len(set(ids)))

    def test_only_reached_or_monitoring_can_start_and_preflight_has_no_partial_goals(self):
        ops = graph.request()
        eligible = next(o['expression'] for o in ops if o.get('id') == 'eligible')
        self.assertIn('FourContactWatchState == 2', eligible)
        self.assertIn('FourContactWatchState == 4', eligible)
        self.assertNotIn('== 3', eligible)
        self.assertIn({'edit': 'connect_pins', 'from': '$commit.then', 'to': '$elapsed.execute'}, ops)
        calls = [o for o in ops if o.get('memberName') == 'SetBodyLegExtension']
        self.assertEqual([o['pinDefaults'] for o in calls], [{'Index': i, 'Amount': 0} for i in INDICES])
        self.assertIn({'edit': 'connect_pins', 'from': '$goal6.then', 'to': '$state.execute'}, ops)
        self.assertEqual(next(o for o in ops if o.get('id') == 'state')['pinDefaults']['FourContactWatchState'], 5)

    def test_preflight_uses_fresh_real_contact_and_captured_margin(self):
        ops = graph.request()
        for name in ('UpdateBodySurfaceProbes', 'CheckExperimentalApproach', 'EvaluateExperimentalFourFootprint'):
            self.assertTrue(any(o.get('memberName') == name for o in ops))
        self.assertIn({'edit': 'connect_pins', 'from': '$margin.FourContactWatchRequiredMarginCm',
                       'to': '$footprint.MinimumMargin'}, ops)
        for flag, target in [('Valid', 'flags.A'), ('Inside', 'flags.B'), ('PassesMargin', 'all.B')]:
            self.assertIn({'edit': 'connect_pins', 'from': '$footprint.'+flag, 'to': '$'+target}, ops)

    def test_retraction_checks_all_stages_and_does_not_require_contact_at_zero(self):
        ops = graph.leg()
        conditions = next(o['expression'] for o in ops if o.get('id') == 'conditions')
        folded = next(o['expression'] for o in ops if o.get('id') == 'folded')
        for i in range(10):
            self.assertIn(f'Stage{i}Position >= 0.000000', conditions)
            self.assertIn(f'Stage{i}Position <= 1.000000', conditions)
            self.assertIn(f'abs(Stage{i}Position) <= 0.000001', folded)
        self.assertIn('abs(ExtensionAmount) <= 0.000001', conditions)
        self.assertNotIn('abs(ProbePlaneClearance)', folded)
        self.assertIn({'edit': 'connect_pins', 'from': '$safe.Safe', 'to': '$valid.A'}, ops)

    def test_stage_snapshot_numeric_guards(self):
        expression = next(o['expression'] for o in graph.leg() if o.get('id') == 'conditions')
        expression = expression.replace('&&', ' and ')
        values = dict(bProbeValid=True, bProbeHit=True, bProbePlaneValid=True, ExtensionAmount=0,
                      ExtensionPosition=0.3, upperLimit=0.5, ProbePlaneClearance=20, nz=1, qz=0, expectedZ=0)
        values.update((f'Stage{i}Position', 1 if i < 3 else 0) for i in range(10))

        def valid(**changes):
            return eval(expression, {'__builtins__': {}, 'abs': abs}, {**values, **changes})

        self.assertTrue(valid())
        for changes in (dict(ExtensionAmount=0.2), dict(ExtensionPosition=0.6), dict(Stage2Position=-0.1),
                        dict(Stage2Position=1.1), dict(Stage2Position=float('nan')), dict(nz=float('nan')),
                        dict(qz=1), dict(bProbeValid=False)):
            self.assertFalse(valid(**changes))

    def test_time_and_abort_apply_to_retraction(self):
        expression = graph.TIME.replace('&&', ' and ')
        values = dict(dt=0.1, FourContactRetractionElapsed=0, FourContactWatchTimeout=10)
        self.assertTrue(eval(expression, {'__builtins__': {}}, values))
        for changes in (dict(dt=-1), dict(dt=11), dict(dt=float('nan')), dict(FourContactWatchTimeout=0),
                        dict(FourContactRetractionElapsed=10), dict(FourContactRetractionElapsed=float('inf'))):
            self.assertFalse(eval(expression, {'__builtins__': {}}, {**values, **changes}))
        self.assertIn('FourContactWatchState == 5', watch.ABORT_EXPRESSION)

    def test_dispatch_reuses_existing_tick_and_terminal_six_does_not_sample(self):
        ops = graph.integration({'entry': 'entryGuid', 'self': 'selfGuid', 'activebranch': 'oldGuid'})
        self.assertFalse(any(o['edit'] in ('add_function', 'add_variable') for o in ops))
        self.assertIn({'edit': 'connect_pins', 'fromNodeId': 'entryGuid', 'fromPinName': 'DeltaSeconds',
                       'to': '$retractiontick.DeltaSeconds'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$retractiondispatch.else', 'toNodeId': 'oldGuid',
                       'toPinName': 'execute'}, ops)
        update = graph.update()
        self.assertEqual(next(o['expression'] for o in update if o.get('id') == 'active'), 'FourContactWatchState == 5')
        self.assertEqual(next(o for o in update if o.get('id') == 'done')['pinDefaults']['FourContactWatchState'], 6)
        self.assertFalse(any(o.get('memberName') == 'EvaluateExperimentalFourFootprint' for o in update))

    def test_every_retraction_update_requires_all_eight_fresh_rows(self):
        ops = graph.update()
        self.assertIn({'edit': 'connect_pins', 'from': '$freshbranch.then', 'to': '$check.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$freshbranch.else', 'to': '$invalid.execute'}, ops)
        self.assertEqual(next(o['expression'] for o in ops if o.get('id') == 'freshsnapshot'),
                         'bBodyProbeSettingsValid && (BodyProbeMeasuredCount == 8)')

    def test_only_owned_legs_and_no_body_motion(self):
        check = graph.check()
        self.assertFalse(any(str(o.get('memberName', '')).startswith('LastFourContactTarget') for o in check))
        for i in INDICES:
            self.assertTrue(any(o.get('memberName') == f'FourContactWatchTarget{i}' for o in check))
        for build in (graph.request, graph.update, graph.check):
            self.assertFalse(any(o.get('memberName') in ('SetActorLocation', 'K2_SetActorLocation', 'SetActorTransform') for o in build()))
