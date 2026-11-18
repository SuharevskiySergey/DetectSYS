"""Standalone-tested pure supplied planning-data cases, not editor tests."""
import copy
import json
from pathlib import Path
import unittest

from beholder_guard_isolation_review import review_isolation_manifest


def manifest():
    path = Path(__file__).resolve().parents[1] / 'docs' / 'BeholderGuardIsolationManifest.json'
    return json.loads(path.read_text(encoding='utf-8'))


class IsolationReviewTests(unittest.TestCase):
    def test_nonempty_reference_list_cannot_replace_required_parent_or_component(self):
        for role in ('body_leg', 'redistribution_leg', 'head_controller', 'telescope_base'):
            value = manifest()
            asset = next(x for x in value['assets'] if x['role'] == role)
            asset['referenceReview'].pop(0)
            with self.subTest(role=role):
                self.assertTrue(asset['referenceReview'])
                codes = {x['code'] for x in review_isolation_manifest(value)['issues']}
                self.assertIn('required_reference_missing', codes)

    def test_guard_boundary_and_rig_preservation_cannot_be_replaced_by_labels(self):
        value = manifest()
        value['assets'][0]['guardBoundaries'] = ['some_guard']
        rig = next(x for x in value['assets'] if x['role'] == 'head_rig')
        rig['preserve'] = ['some_preservation']
        codes = {x['code'] for x in review_isolation_manifest(value)['issues']}
        self.assertIn('required_guard_boundary_missing', codes)
        self.assertIn('rig_preservation_requirement_missing', codes)

    def test_duplicate_slots_and_malformed_reference_targets(self):
        value = manifest()
        body = value['assets'][-1]
        body['referenceReview'].append(copy.deepcopy(body['referenceReview'][0]))
        value['assets'][0]['referenceReview'].append({'kind': [], 'targetRole': []})
        codes = {x['code'] for x in review_isolation_manifest(value)['issues']}
        self.assertIn('duplicate_body_slot_selection', codes)
        self.assertIn('reference_kind_invalid', codes)
        self.assertIn('reference_target_unresolved', codes)

    def test_current_draft_remains_blocked_and_input_unchanged(self):
        value = manifest()
        before = copy.deepcopy(value)
        result = review_isolation_manifest(value)
        codes = [item['code'] for item in result['issues']]
        self.assertEqual(codes.count('destination_unresolved'), 6)
        self.assertIn('slot_class_selection_unresolved', codes)
        self.assertEqual(codes.count('installation_gate_unresolved'), 7)
        self.assertFalse(result['installationReady'])
        self.assertFalse(result['motionAuthorized'])
        self.assertEqual(value, before)

    def test_protected_and_duplicate_destinations_case_insensitive(self):
        value = manifest()
        source = value['assets'][0]['source']
        value['assets'][0]['destination'] = source.upper().replace('/GAME/', '/Game/')
        value['assets'][1]['destination'] = value['assets'][0]['destination']
        codes = {x['code'] for x in review_isolation_manifest(value)['issues']}
        self.assertIn('destination_is_protected_source', codes)
        self.assertIn('duplicate_destination', codes)

    def test_boolean_readiness_cannot_be_forged_with_integer_zero(self):
        for flag in ('motionAuthorized', 'installationAuthorized', 'dependencyClosureComplete'):
            value = manifest()
            value[flag] = 0
            result = review_isolation_manifest(value)
            with self.subTest(flag=flag):
                self.assertIn({'code': 'unsubstantiated_readiness_or_authorization',
                               'pointer': '/'+flag}, result['issues'])
                self.assertFalse(result['installationAuthorized'])

    def test_malformed_data_and_missing_or_duplicate_roles(self):
        for value in (None, [], {'assets': [None, {'role': []}]}):
            with self.subTest(value=value):
                self.assertTrue(review_isolation_manifest(value)['issues'])
        value = manifest()
        value['assets'][1] = copy.deepcopy(value['assets'][0])
        codes = {x['code'] for x in review_isolation_manifest(value)['issues']}
        self.assertIn('duplicate_role', codes)
        self.assertIn('required_role_missing', codes)

    def test_unknown_fields_and_missing_slot_selection(self):
        value = manifest()
        value['execute'] = True
        body = value['assets'][-1]
        body['referenceReview'][0]['members'].pop()
        codes = {x['code'] for x in review_isolation_manifest(value)['issues']}
        self.assertIn('top_level_fields_mismatch', codes)
        self.assertIn('eight_ordered_slots_required', codes)
