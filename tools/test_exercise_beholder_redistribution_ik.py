import ast
from pathlib import Path
import unittest
from types import SimpleNamespace


class RedistributionIKBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).with_name('exercise_beholder_redistribution_ik.py').read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source)

    def test_read_only_no_actuation_or_sensor_refresh(self):
        forbidden = {'set_editor_property', 'call_method', 'set_actor_location', 'set_actor_transform',
                     'set_relative_location', 'set_global_time_dilation'}
        calls = {n.func.attr for n in ast.walk(self.tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertFalse(calls & forbidden)
        self.assertNotIn('UpdateStageRedistribution', self.source)

    def test_actual_completed_owned_packed_pose_and_unchanged_state_required(self):
        self.assertIn("get_editor_property('RedistributionState') == 2", self.source)
        self.assertIn("get_editor_property('RedistributionDirection') == 1", self.source)
        self.assertIn("get_editor_property('bRedistributionContactOwned')", self.source)
        self.assertIn('assert before == after', self.source)
        self.assertNotIn('str(leg.get_actor_transform())', self.source)
        self.assertIn('transform_signature(c.get_relative_transform())', self.source)
        self.assertIn('maximumLiveFKWorldErrorCm', self.source)

    def test_endpoint_and_path_diagnostics_never_authorize_runtime(self):
        self.assertIn('runtimeMotionAuthorized=False', self.source)
        self.assertIn('bodyApertureChecked=False, otherLegsChecked=False', self.source)
        self.assertIn('check_contact_path(', self.source)
        self.assertIn('sampledPathsPassing', self.source)
        self.assertIn('passed=False, running=True', self.source)

    def test_equivalent_transform_copies_have_identical_numeric_signatures(self):
        functions = [n for n in self.tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in ('xyz', 'transform_signature')]
        namespace = {}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<numeric signature>', 'exec'), namespace)

        def transform():
            return SimpleNamespace(translation=SimpleNamespace(x=1, y=2, z=3),
                rotation=SimpleNamespace(x=0, y=0, z=0, w=1), scale3d=SimpleNamespace(x=0.25, y=0.25, z=0.25))

        a, b = transform(), transform()
        self.assertIsNot(a, b)
        self.assertEqual(namespace['transform_signature'](a), namespace['transform_signature'](b))
        b.translation.x += 1
        self.assertNotEqual(namespace['transform_signature'](a), namespace['transform_signature'](b))
