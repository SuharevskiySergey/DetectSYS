import ast
from pathlib import Path
import unittest


class RedistributionHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).with_name('exercise_beholder_redistribution.py').read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source)

    def test_never_forces_stage_or_controller_telemetry(self):
        names = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'set_editor_property':
                self.assertIsInstance(node.args[0], ast.Constant)
                names.append(node.args[0].value)
        self.assertTrue(all(n in ('bEnableStageRedistribution', 'ProbeTraceDistance') for n in names))

    def test_observer_does_not_update_controller_or_move_components(self):
        for forbidden in ('UpdateStageRedistribution', 'set_relative_location', 'Stage0Position\',',
                          'set_actor_transform'):
            self.assertNotIn(forbidden, self.source)
        self.assertIn('nativeUpdates', self.source)
        self.assertIn('unregister_slate_post_tick_callback', self.source)

    def test_failed_setup_cannot_reuse_old_success(self):
        pending = self.source.index('path.write_text')
        begin = self.source.index("actor.call_method('SetMotionMode'")
        self.assertLess(pending, begin)
        self.assertLess(pending, self.source.index('get_game_world'))
        self.assertIn('passed=False, running=True', self.source)
        self.assertIn('running=False', self.source)
