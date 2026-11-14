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
        self.assertTrue(all(n in ('bEnableStageRedistribution', 'ProbeTraceDistance', 'RedistributionMaxStageStep', 'RedistributionGameTimeout') for n in names))

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

    def test_monitor_observation_never_drives_update_or_probes(self):
        block = next(n for n in ast.walk(self.tree) if isinstance(n, ast.If)
                     and ast.unparse(n.test) == "state['phase'] in (4, 5)")
        source = ast.unparse(block)
        self.assertNotIn('UpdateRedistributionContactMonitoring', source)
        self.assertNotIn('MeasureSurfaceProbe', source)
        self.assertNotIn('set_editor_property', source)
        self.assertIn('monitor_updates - 2', source)
        self.assertIn('game_elapsed >= 1.25', source)

    def test_monitor_begin_is_explicit_and_repeated_without_counter_reset(self):
        function = next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == 'begin_monitor')
        source = ast.unparse(function)
        self.assertEqual(source.count("call_method('BeginRedistributionContactMonitoring'"), 2)
        self.assertNotIn('set_editor_property', source)
        self.assertIn("get_editor_property('RedistributionMonitoringUpdates') == 1", source)
        self.assertIn("get_editor_property('RedistributionMonitoringUpdates') == 2", source)

    def test_monitor_reports_are_separate_from_passive_contact_regression(self):
        self.assertIn('BeholderRedistribution_monitor_', self.source)
        self.assertIn('if monitor_contacts:', self.source)
        self.assertIn("== report['contactSamplesAtComplete']", self.source)

    def test_stale_begin_is_rejected_by_public_api_without_state_forcing(self):
        function = next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == 'reject_stale_begin')
        source = ast.unparse(function)
        self.assertIn("inject_fault('surface_lost')", source)
        self.assertIn("assert not boolean(actor.call_method('BeginRedistributionContactMonitoring', ()))", source)
        self.assertNotIn('set_editor_property', source)
        self.assertNotIn('MeasureSurfaceProbe', source)

    def test_mode_fault_changes_both_uniform_and_sequential_modes(self):
        function = next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == 'inject_fault')
        source = ast.unparse(function)
        self.assertIn("actor.call_method('SetMotionMode', (not actor.get_editor_property('bSequentialMotion'),))", source)

    def test_uniform_return_starts_only_through_atomic_public_request(self):
        function = next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == 'begin_uniform_return')
        source = ast.unparse(function)
        self.assertIn("assert boolean(actor.call_method('TryExperimentalUniformRedistribution', (1.0,)))", source)
        setters = [n for n in ast.walk(function) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute) and n.func.attr == 'set_editor_property']
        self.assertTrue(all(n.args[0].value in ('RedistributionMaxStageStep', 'RedistributionGameTimeout') for n in setters))
        self.assertNotIn('set_actor_location', source)
        self.assertIn("get_editor_property('RedistributionUpdates') == 0", source)

    def test_return_observer_does_not_drive_the_native_controller(self):
        block = next(n for n in ast.walk(self.tree) if isinstance(n, ast.If)
                     and ast.unparse(n.test) == "state['phase'] in (6, 7)")
        source = ast.unparse(block)
        self.assertNotIn('UpdateStageRedistribution', source)
        self.assertNotIn('MeasureSurfaceProbe', source)
        self.assertNotIn('set_editor_property', source)
        self.assertIn("ret['contactSamplesAtStart'] + 2 * updates", source)

    def test_repeat_cycles_do_not_teleport_fixture_or_force_state(self):
        self.assertIn('cyclesCompleted', self.source)
        self.assertIn("state['cycle'] < cycles", self.source)
        self.assertIn('cycleResults', self.source)

    def test_extension_parameter_keeps_default_and_separates_reports(self):
        start = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef) and n.name == 'start')
        defaults = dict(zip([a.arg for a in start.args.args][-len(start.args.defaults):], start.args.defaults))
        self.assertEqual(ast.literal_eval(defaults['extension']), 0.5)
        self.assertEqual(ast.literal_eval(defaults['max_stage_step']), 1.0)
        self.assertIn("f'_E{extension:.6f}.json'", self.source)
        self.assertIn("report['requestedExtension'] = extension", self.source)

    def test_fractional_patterns_and_goal_injection_are_not_half_extension_constants(self):
        self.assertIn('COUNT*extension-i', self.source)
        self.assertIn('math.fsum(stages)-COUNT*extension', self.source)
        self.assertIn('extension+(packed[i]-extension)*blend', self.source)
        self.assertNotIn('[1]*5+[0]*5', self.source)
        calls = [n for n in ast.walk(self.tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == 'call_method'
                 and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 'SetLegExtension']
        self.assertTrue(calls)
        for call in calls:
            self.assertIn(ast.unparse(call.args[1]), ('(extension,)', '(changed_goal,)'))

    def test_pause_observer_does_not_force_motion_or_private_state(self):
        function = next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == 'observe_pause')
        source = ast.unparse(function)
        self.assertNotIn('call_method', source)
        self.assertNotIn('set_editor_property', source)
        self.assertNotIn('set_actor_location', source)
        self.assertIn('set_game_paused(world, True)', source)
        self.assertIn('set_game_paused(world, False)', source)
        self.assertIn("pause['heldSamples'] >= 3", source)
        self.assertIn("abs(now - pause['gameTime']) <= 1e-06", source)

    def test_pause_cleanup_is_owned_and_reports_are_separate(self):
        finish = next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == 'finish')
        source = ast.unparse(finish)
        self.assertIn("state.get('pause_owned')", source)
        self.assertIn('set_game_paused(world, False)', source)
        self.assertIn("f'_Pause{pause_motion}.json'", self.source)
        self.assertIn('Start in an unpaused fresh PIE', self.source)

    def test_time_dilation_is_temporary_and_has_separate_reports(self):
        self.assertIn("f'_Dilation{time_dilation:.6f}.json'", self.source)
        self.assertIn('timeDilationRestoredOnSetupFailure', self.source)
        self.assertIn('timeDilationRestoreError', self.source)
        finish = next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == 'finish')
        source = ast.unparse(finish)
        self.assertIn('if dilation_owned:', source)
        self.assertIn('set_global_time_dilation(world, dilation_before)', source)
        self.assertIn("report['timeDilationRestored'] = True", source)

    def test_time_dilation_default_is_one_and_does_not_force_actor_time(self):
        start = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef) and n.name == 'start')
        defaults = dict(zip([a.arg for a in start.args.args][-len(start.args.defaults):], start.args.defaults))
        self.assertEqual(ast.literal_eval(defaults['time_dilation']), 1.0)
        self.assertNotIn('CustomTimeDilation', self.source)
        self.assertIn("report['timeDilationDuring']-time_dilation", self.source)

    def test_offline_ik_inspection_is_opt_in_and_only_on_packed_completion(self):
        start = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef) and n.name == 'start')
        defaults = dict(zip([a.arg for a in start.args.args][-len(start.args.defaults):], start.args.defaults))
        self.assertIs(ast.literal_eval(defaults['inspect_packed_ik']), False)
        blocks = [n for n in ast.walk(self.tree) if isinstance(n, ast.If) and ast.unparse(n.test) == 'phase == 2']
        self.assertTrue(any('inspect_ik(actor)' in ast.unparse(n) and "get_editor_property('bSequentialMotion')" in ast.unparse(n)
                            for n in blocks))
        self.assertIn("filename[:-5]+'_IK.json'", self.source)

    def test_failures_keep_bounded_history_and_exact_failed_sample(self):
        self.assertIn('deque(maxlen=8)', self.source)
        self.assertIn("report['recentSamplesAtFailure'] = list(state['recent_samples'])", self.source)
        self.assertIn("report['traceback'] = traceback.format_exc()", self.source)
        self.assertIn("sample['readStampBefore'] == sample['readStampAfter']", self.source)
        self.assertIn("'mixed_native_snapshot'", self.source)
        self.assertIn("sample['nativeUpdatesSincePreviousObservation']", self.source)
        self.assertIn("sample['stageDisplacementSincePreviousObservation']", self.source)
        self.assertIn("state['native_step_audit'].observe(audit_input, stages, updates)", self.source)
        self.assertIn("sample['nativeStageAudit'] = native_step_audit()", self.source)
        self.assertIn("report['nativeStageAuditLatest']", self.source)

    def test_named_stage_checks_do_not_relax_existing_tolerances(self):
        self.assertIn("abs(stage-expected) < 1e-6, ('stage_pattern'", self.source)
        self.assertIn("sample['meshErrorsCm'][i] < 1e-4, ('stage_mesh_transform'", self.source)
        self.assertIn("max(head_drift, claw_drift) < 0.01, ('head_or_claw_drift'", self.source)
        self.assertIn('if phase in (1, 2):', self.source)
        self.assertEqual(self.source.count('NativeStageObservation(native_step_audit(),'), 3)

    def test_injected_observer_failures_are_opt_in_and_separate_from_real_faults(self):
        self.assertIn("f'_ObserverFailure{observer_failure}.json'", self.source)
        self.assertIn("raise RuntimeError('Injected observer failure during return')", self.source)
        self.assertIn("raise RuntimeError('Injected observer failure while paused')", self.source)
        self.assertIn("observer_failure != 'return' or uniform_return", self.source)
        self.assertIn("observer_failure != 'native_coverage' or uniform_return", self.source)
        block = next(n for n in ast.walk(self.tree) if isinstance(n, ast.If)
                     and "observer_failure == 'native_coverage'" in ast.unparse(n.test))
        code = ast.unparse(block)
        self.assertIn('dict(audit_input)', code)
        self.assertNotIn('set_editor_property', code)
        self.assertIn("f'_SkipReturn{skip_return_observations}.json'", self.source)
        start = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef) and n.name == 'start')
        defaults = dict(zip([a.arg for a in start.args.args][-len(start.args.defaults):], start.args.defaults))
        self.assertEqual(ast.literal_eval(defaults['skip_return_observations']), 0)
        block = next(n for n in ast.walk(self.tree) if isinstance(n, ast.If)
                     and 'last_intentionally_skipped_update' in ast.unparse(n.test))
        code = ast.unparse(block)
        for forbidden in ('call_method', 'set_editor_property', 'set_actor_location'):
            self.assertNotIn(forbidden, code)
