import unittest

from build_beholder_contact_request_graph import INDICES, OTHER_INDICES, FOOTPRINT_INDICES, folded, prepare, request, prediction_upgrade
from generate_beholder_telescope import COUNT


class ContactRequestGraphTests(unittest.TestCase):
    def test_batches_fit_and_aliases_are_unique(self):
        for ops in (folded(), prepare(), request()):
            self.assertLessEqual(len(ops), 200)
            ids = [op['id'] for op in ops if 'id' in op]
            self.assertEqual(len(ids), len(set(ids)))

    def test_opt_in_defaults_off_and_result_is_reset(self):
        ops = request()
        flag = next(op for op in ops if op.get('variableName') == 'bEnableExperimentalFourContact')
        self.assertIs(flag['defaultValue'], False)
        self.assertIn({'edit': 'connect_pins', 'from': '$entry.then', 'to': '$reset.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$enabledbranch.then', 'to': '$update.execute'}, ops)

    def test_completion_margin_has_default_and_preflight_numeric_bounds(self):
        ops = request()
        variable = next(o for o in ops if o.get('variableName') == 'FourContactCompletionMinimumMarginCm')
        self.assertEqual(variable['defaultValue'], 1.0)
        body = next(o['expression'] for o in ops if o.get('id') == 'bodyok')
        self.assertIn('FourContactCompletionMinimumMarginCm >= 0.000000', body)
        self.assertIn('FourContactCompletionMinimumMarginCm <= 1000000.000000', body)

    def test_all_four_preflights_finish_before_commit_gate(self):
        ops = request()
        previous = '$folded7.then'
        for i in INDICES:
            self.assertIn({'edit': 'connect_pins', 'from': previous, 'to': f'$prepare{i}.execute'}, ops)
            previous = f'$prepare{i}.then'
        self.assertIn({'edit': 'connect_pins', 'from': previous, 'to': '$commitgate.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$commitgate.then', 'to': '$predictedfootprint.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$predictedgate.then', 'to': '$cache0.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$cache6.then', 'to': '$command0.execute'}, ops)

    def test_predicted_contour_uses_traced_points_correct_order_and_margin(self):
        ops = request()
        self.assertEqual(FOOTPRINT_INDICES, (0, 2, 6, 4))
        for rank, index in enumerate(FOOTPRINT_INDICES):
            self.assertIn({'edit': 'connect_pins', 'from': f'$prepare{index}.Point',
                           'to': f'$predictedfootprint.Point{rank}'}, ops)
        for source, target in [('location.ReturnValue', 'predictedfootprint.ReferenceWorld'),
                               ('predictionmargin.FourContactCompletionMinimumMarginCm', 'predictedfootprint.MinimumMargin'),
                               ('predictedfootprint.Valid', 'predictedflags.A'), ('predictedfootprint.Inside', 'predictedflags.B'),
                               ('predictedflags.ReturnValue', 'predictedready.A'), ('predictedfootprint.PassesMargin', 'predictedready.B')]:
            self.assertIn({'edit': 'connect_pins', 'from': '$'+source, 'to': '$'+target}, ops)
        self.assertNotIn({'edit': 'connect_pins', 'from': '$commitgate.then', 'to': '$cache0.execute'}, ops)

    def test_prediction_delta_has_no_new_members_or_goals(self):
        ids = {name: name+'Guid' for name in ['self', 'location', 'commitgate', 'cache0']+
               [f'prepare{i}' for i in INDICES]}
        ops = prediction_upgrade(ids)
        self.assertLessEqual(len(ops), 200)
        self.assertTrue(all(o['edit'] in ('create_node', 'connect_pins') for o in ops))
        self.assertFalse(any(o.get('memberName') == 'SetBodyLegExtension' for o in ops))
        self.assertIn({'edit': 'connect_pins', 'from': '$predictedgate.then', 'toNodeId': 'cache0Guid',
                       'toPinName': 'execute'}, ops)

    def test_foreign_helpers_and_commands_have_explicit_self(self):
        ops = request()
        for op in ops:
            if op.get('memberName') in ('UpdateBodySurfaceProbes', 'IsExperimentalLegFolded', 'PrepareExperimentalContactLeg', 'SetBodyLegExtension'):
                self.assertIn({'edit': 'connect_pins', 'from': '$self.self', 'to': '$'+op['id']+'.self'}, ops)

    def test_preflight_rejects_future_bends_and_requires_finite_face_trace(self):
        ops = prepare()
        fields = {op.get('memberName') for op in ops}
        for i in range(1, COUNT):
            self.assertIn(f'Joint{i}PitchRequest', fields)
            self.assertIn(f'Joint{i}YawRequest', fields)
        self.assertIn('bAutoDemo', fields)
        self.assertIn('LiveBendPitchDegrees', fields)
        self.assertIn('LiveBendYawDegrees', fields)
        self.assertIn('LineTraceSingle', fields)
        expression = next(op['expression'] for op in ops if op.get('id') == 'conditions')
        self.assertIn('abs(current)', expression)
        self.assertIn('abs(goal)', expression)
        self.assertIn('normalZ > 0.999990', expression)
        self.assertIn('target <= 0.950000', expression)
        reject = next(op for op in ops if op.get('id') == 'reject')
        self.assertIs(reject['pinDefaults']['Ready'], False)

    def test_only_extension_commands_are_added_and_preflight_does_not_actuate(self):
        self.assertNotIn('SetBodyLegExtension', {op.get('memberName') for op in prepare()})
        calls = [op for op in request() if op.get('memberName') == 'SetBodyLegExtension']
        self.assertEqual([op['pinDefaults']['Index'] for op in calls], list(INDICES))
        names = {op.get('memberName') for op in request()+prepare()}
        for forbidden in ('SetActorLocation', 'K2_SetActorLocation', 'SetActorRotation', 'SetJointBend', 'SetHeadOpening'):
            self.assertNotIn(forbidden, names)

    def test_other_four_legs_are_checked_before_preparing_targets(self):
        ops = request()
        previous = '$update.then'
        for i in OTHER_INDICES:
            self.assertIn({'edit': 'connect_pins', 'from': previous, 'to': f'$folded{i}.execute'}, ops)
            previous = f'$folded{i}.then'
        self.assertIn({'edit': 'connect_pins', 'from': previous, 'to': '$prepare0.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$upper3.ReturnValue', 'to': '$groups.B'}, ops)
