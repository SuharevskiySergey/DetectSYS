"""Prepared, NOT RUN: damage graph source structure, not UE compilation."""
import copy
import unittest

from build_beholder_damage_snapshot_graph import (
    BP, FUNCTION, HELPER, INPUT_LAYOUT, OUTPUT_LAYOUT, plans)
from beholder_damage_graph_batches import prepare_complete_function, prepare_next_batch


ENTRY = '1'*32
RETURN = '2'*32


class DamageBlueprintPlanTests(unittest.TestCase):
    def test_function_dependencies_and_public_snapshot_layout(self):
        plan = plans()
        self.assertEqual(plan['blueprintPath'], BP)
        self.assertEqual(plan['installationOrder'], (HELPER, FUNCTION))
        self.assertEqual([function['graphName'] for function in plan['functions']], [HELPER, FUNCTION])
        helper, aggregate = plan['functions']
        self.assertEqual(helper['dependencies'], ())
        self.assertEqual(aggregate['dependencies'], (HELPER,))
        declaration = aggregate['functionDeclaration']
        self.assertEqual([(p['name'], p['type']) for p in declaration['inputs']], list(INPUT_LAYOUT))
        self.assertEqual([(p['name'], p['type']) for p in declaration['outputs']], list(OUTPUT_LAYOUT))
        self.assertEqual(len(INPUT_LAYOUT), 18)
        self.assertEqual(len(OUTPUT_LAYOUT), 43)
        self.assertTrue(plan['installed'])
        self.assertTrue(plan['compilationPerformed'])
        self.assertTrue(plan['numericVerificationPerformed'])
        self.assertEqual(plan['numericVerificationCases'], 174)
        self.assertFalse(plan['motionAuthorized'])

    def test_complete_bodies_fit_batch_limit_and_bind_without_mutating_plan(self):
        for function in plans()['functions']:
            with self.subTest(graph=function['graphName']):
                before = copy.deepcopy(function)
                self.assertLessEqual(len(function['operations']), 200)
                batch = prepare_complete_function(function, entry_guid=ENTRY, return_guid=RETURN)
                self.assertEqual(function, before)
                self.assertEqual(batch['startIndex'], 0)
                self.assertEqual(batch['nextIndexAfterConfirmedSuccess'], len(function['operations']))
                self.assertTrue(batch['completeAfterConfirmedSuccess'])
                self.assertFalse(batch['editorExecutionPerformed'])
                local = set()
                for operation in batch['operations']:
                    self.assertEqual(operation['graphName'], function['graphName'])
                    if operation['edit'] == 'create_node':
                        local.add(operation['id'])
                    for key in ('nodeId', 'fromNodeId', 'toNodeId'):
                        if key in operation:
                            reference = operation[key]
                            if reference.startswith('$'):
                                self.assertIn(reference[1:], local)
                            else:
                                self.assertIn(reference, (ENTRY, RETURN))
                    self.assertNotIn('from', operation)
                    self.assertNotIn('to', operation)

    def test_aggregate_has_eight_helper_calls_and_forwards_world_context(self):
        aggregate = plans()['functions'][1]
        operations = aggregate['operations']
        calls = [operation for operation in operations if operation.get('nodeType') == 'CallFunction'
                 and operation.get('memberName') == HELPER]
        self.assertEqual({call['id'] for call in calls}, {f'leg{i}' for i in range(8)})
        self.assertTrue(all(call['memberClass'] == BP for call in calls))
        links = {(operation.get('from'), operation.get('to')) for operation in operations
                 if operation['edit'] == 'connect_pins'}
        for i in range(8):
            self.assertIn(('$entry.__WorldContext', f'$leg{i}.__WorldContext'), links)
            if i == 0:
                self.assertIn(('$leg0.NumericInputsAccepted', '$accepted1.A'), links)
            else:
                self.assertIn((f'$leg{i}.NumericInputsAccepted', f'$accepted{i}.B'), links)
        self.assertIn(('$accepted7.ReturnValue', '$health_branch.Condition'), links)

    def test_plan_has_no_actor_writers_and_literal_denial_flags(self):
        for function in plans()['functions']:
            operations = function['operations']
            self.assertTrue(all(operation['edit'] in
                                ('create_node', 'connect_pins', 'set_pin_default_value')
                                for operation in operations))
            allowed_nodes = {'FunctionResult', 'MathExpression', 'Branch', 'CallFunction'}
            for operation in operations:
                if operation['edit'] == 'create_node':
                    self.assertIn(operation['nodeType'], allowed_nodes)
                    if operation['nodeType'] == 'CallFunction':
                        self.assertIn(operation['memberName'], (
                            HELPER, 'SelectInt', 'Add_IntInt', 'BooleanAND', 'BooleanOR', 'Not_PreBool'))
            reject = next(operation for operation in operations if operation.get('id') == 'reject')
            self.assertTrue(all(value is False or type(value) is int and value == 0
                                for value in reject['pinDefaults'].values()))
        aggregate = plans()['functions'][1]['operations']
        for flag in ('MotionAuthorized', 'GameplayNeutralizedConfirmed'):
            default = next(operation for operation in aggregate
                           if operation['edit'] == 'set_pin_default_value' and operation['pinName'] == flag)
            self.assertIs(default['propertyValue'], False)
            self.assertFalse(any(operation.get('to') == '$entry_return.'+flag for operation in aggregate))

    def test_preparer_refuses_missing_guid_wrong_graph_and_oversized_body(self):
        helper = plans()['functions'][0]
        with self.assertRaises(ValueError):
            prepare_complete_function(helper, entry_guid='unknown', return_guid=RETURN)
        with self.assertRaisesRegex(ValueError, 'distinct actual GUIDs'):
            prepare_complete_function(helper, entry_guid='a'*32, return_guid='A'*32)
        synthetic = [dict(edit='create_node', graphName=HELPER, id='prior', nodeType='Branch'),
                     dict(edit='connect_pins', graphName=HELPER,
                          **{'from': '$prior.then', 'to': '$entry_return.execute'})]
        with self.assertRaisesRegex(ValueError, 'distinct actual GUIDs'):
            prepare_next_batch(synthetic, start_index=1, graph_name=HELPER,
                               entry_guid=ENTRY, return_guid=RETURN, node_guids={'prior': ENTRY})
        with self.assertRaises(ValueError):
            prepare_next_batch(helper['operations'], graph_name='OtherGraph', entry_guid=ENTRY, return_guid=RETURN)
        oversized = dict(helper, operations=helper['operations']*201)
        with self.assertRaisesRegex(ValueError, 'partial-body'):
            prepare_complete_function(oversized, entry_guid=ENTRY, return_guid=RETURN)
        missing_binding = [dict(edit='connect_pins', graphName=HELPER,
                                **{'from': '$missing.then', 'to': '$entry_return.execute'})]
        with self.assertRaisesRegex(ValueError, 'Missing confirmed GUID'):
            prepare_next_batch(missing_binding, graph_name=HELPER, entry_guid=ENTRY, return_guid=RETURN)
