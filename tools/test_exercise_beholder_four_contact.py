"""Structural guards for the editor-only asynchronous test harness.

Actual motion and restoration are verified in PIE, not mocked here.
"""
import ast
from pathlib import Path
import unittest


class FourContactHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(Path(__file__).with_name('exercise_beholder_four_contact.py').read_text(encoding='utf-8'))

    def function(self, name):
        return next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == name)

    def test_faults_have_separate_expected_reasons(self):
        assignment = next(n for n in self.tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'ABORT_REASONS' for t in n.targets))
        self.assertEqual(ast.literal_eval(assignment.value), {'disabled': 1, 'body_moved': 2, 'surface_lost': 3})

    def test_fault_injection_does_not_call_watchdog(self):
        source = ast.unparse(self.function('inject_fault'))
        self.assertNotIn('UpdateExperimentalContactWatch', source)
        self.assertNotIn('AbortExperimentalFourContact', source)
        self.assertNotIn('CancelExperimentalFourContact', source)
        self.assertIn('ECR_IGNORE', source)

    def test_wait_branch_precedes_python_probe_refresh(self):
        source = ast.unparse(self.function('tick'))
        self.assertLess(source.index("state['phase'] in (2, 3)"), source.index('MeasureSurfaceProbe'))
        self.assertIn("updates > report['injection']['updates']", source)
        self.assertIn("abort['holdSamples'] >= 3", source)

    def test_failure_cleanup_restores_fault_before_body(self):
        source = ast.unparse(self.function('finish'))
        self.assertLess(source.index('restore_fault()'), source.index('body.set_actor_location'))
        self.assertIn('floorVisibilityRestored', source)
        self.assertIn('unregister_slate_post_tick_callback', source)

    def test_fault_harness_does_not_write_private_watch_state_or_requirements(self):
        protected = {'FourContactWatchRequiredMarginCm', 'FourContactWatchState',
                     'FourContactWatchReason', 'ExtensionPosition', 'FourContactRetractionElapsed',
                     'FourContactRetractionUpdates'} | {f'Stage{i}Position' for i in range(10)}
        writes = [n.args[0].value for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr == 'set_editor_property' and n.args
                  and isinstance(n.args[0], ast.Constant)]
        self.assertTrue(protected.isdisjoint(writes))

    def test_early_refusal_is_asserted_before_accepted_request(self):
        source = ast.unparse(self.function('_start'))
        self.assertLess(source.index('insufficient_predicted_margin'), source.index('required_margin = 1.0'))
        self.assertIn('predictedFootprintEarlyRejection', source)
        self.assertIn("body.get_editor_property('FourContactWatchState') == 0", source)

    def test_contact_monitor_dwell_does_not_refresh_or_tick_from_python(self):
        block = next(n for n in ast.walk(self.function('tick')) if isinstance(n, ast.If)
                     and ast.unparse(n.test) == "state['phase'] in (5, 6, 7)")
        source = ast.unparse(block)
        for name in ('MeasureSurfaceProbe', 'UpdateExperimentalContactWatch', 'runtime_footprint'):
            self.assertNotIn(name, source)
        self.assertIn("monitor['updatesAtStart'] + 3", source)
        self.assertIn("updates > monitor['updatesBeforeFault']", source)

    def test_monitor_release_is_checked_before_retraction(self):
        block = next(n for n in ast.walk(self.function('tick')) if isinstance(n, ast.If)
                     and ast.unparse(n.test) == "state['phase'] in (5, 6, 7)")
        source = ast.unparse(block)
        self.assertLess(source.index('ReleaseExperimentalFourContact'), source.index('RetractBodyLeg'))
        self.assertIn("updates == monitor['updatesBeforeFault']", source)
        self.assertIn('Released monitor still updates', source)

    def test_reached_remains_passive_until_explicit_begin(self):
        block = next(n for n in ast.walk(self.function('tick')) if isinstance(n, ast.If)
                     and ast.unparse(n.test) == "state['phase'] == 8")
        source = ast.unparse(block)
        self.assertIn("body.get_editor_property('FourContactWatchState') == 2", source)
        self.assertIn("body.get_editor_property('FourContactWatchUpdates') == monitor['passiveUpdates']", source)
        self.assertIn("monitor['passiveSamples'] < 3", source)
        self.assertIn('assert begin_monitor()', source)
        self.assertNotIn('MeasureSurfaceProbe', source)

    def test_fixture_setup_waits_for_a_real_game_tick(self):
        source = ast.unparse(self.function('setup_tick'))
        self.assertIn("gate['ticks'] < 2", source)
        self.assertIn("get_game_time_in_seconds(body) <= gate['game_time']", source)
        self.assertLess(source.index('unregister_slate_post_tick_callback'), source.index('_start('))

    def test_setup_report_cannot_reuse_a_previous_success(self):
        source = ast.unparse(self.function('start'))
        self.assertIn('setupPending=True', source)
        self.assertLess(source.index('path.write_text'), source.index('body.set_actor_location'))
        failed = ast.unparse(self.function('restore_setup_failure'))
        self.assertIn('running=False', failed)
        self.assertIn('setupPending=False', failed)

    def test_return_observation_does_not_drive_the_controller_from_python(self):
        block = next(n for n in ast.walk(self.function('tick')) if isinstance(n, ast.If)
                     and ast.unparse(n.test) == "state['phase'] in (9, 10)")
        source = ast.unparse(block)
        self.assertNotIn('UpdateExperimentalRetractionWatch', source)
        self.assertNotIn('MeasureSurfaceProbe', source)
        self.assertNotIn('RetractBodyLeg', source)
        self.assertIn('nativeUpdatesAtFolded', source)
        self.assertIn('Stage{j}Position', source)

    def test_return_start_uses_one_batch_api_and_keeps_captured_limits(self):
        source = ast.unparse(self.function('start_retraction'))
        self.assertIn('assert try_retraction()', source)
        self.assertNotIn('RetractBodyLeg', source)
        self.assertIn('incompatible_owned_goal', source)
        self.assertIn('already_retracting', source)
        self.assertIn('FourContactWatchTarget{i}', source)
