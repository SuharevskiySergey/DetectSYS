import unittest

import build_beholder_contact_watch_graph as graph
from build_beholder_contact_request_graph import INDICES


class ContactWatchGraphTests(unittest.TestCase):
    def test_batches_fit_and_aliases_are_unique(self):
        for build in (graph.pose, graph.start, graph.inspect_leg, graph.check_all, graph.hold_leg,
                      graph.abort, graph.controls, graph.update, graph.begin_monitor):
            ops = build()
            self.assertLessEqual(len(ops), 200)
            ids = [o['id'] for o in ops if 'id' in o]
            self.assertEqual(len(ids), len(set(ids)))

    def test_inactive_state_does_not_sample_and_completion_is_terminal(self):
        ops = graph.update()
        expr = next(o['expression'] for o in ops if o.get('id') == 'active')
        self.assertEqual(expr, graph.ACTIVE_EXPRESSION)
        self.assertNotIn('== 2', expr)
        self.assertIn({'edit': 'connect_pins', 'from': '$activebranch.then', 'to': '$setcount.execute'}, ops)
        done = next(o for o in ops if o.get('id') == 'done')
        self.assertEqual(done['pinDefaults']['FourContactWatchState'], 2)
        self.assertNotIn({'edit': 'connect_pins', 'from': '$donebranch.then', 'to': '$done.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$finalbranch.then', 'to': '$monitorcomplete.execute'}, ops)
        writes = [o for o in ops if o.get('to') == '$done.execute']
        self.assertEqual(writes[-1]['from'], '$monitorcomplete.then')

    def test_completion_requires_fresh_valid_inside_strict_margin(self):
        ops = graph.update()
        self.assertIn({'edit': 'connect_pins', 'from': '$donebranch.then', 'to': '$finalfootprint.execute'}, ops)
        for source, target in [('finalfootprint.Valid', 'finalflags.A'), ('finalfootprint.Inside', 'finalflags.B'),
                               ('finalflags.ReturnValue', 'finalready.A'), ('finalfootprint.PassesMargin', 'finalready.B')]:
            self.assertIn({'edit': 'connect_pins', 'from': '$'+source, 'to': '$'+target}, ops)
        call = next(o for o in ops if o.get('id') == 'badfootprint')
        self.assertEqual(call['pinDefaults']['Reason'], 6)
        self.assertIn({'edit': 'connect_pins', 'from': '$finalbranch.else', 'to': '$badfootprint.execute'}, ops)

    def test_completion_uses_captured_margin_and_explicit_body_origin(self):
        ops = graph.update()
        self.assertIn({'edit': 'connect_pins', 'from': '$finalrequired.FourContactWatchRequiredMarginCm',
                       'to': '$finalfootprint.MinimumMargin'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$finalreference.ReturnValue',
                       'to': '$finalfootprint.ReferenceWorld'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$requiredmargin.FourContactCompletionMinimumMarginCm',
                       'to': '$cachemargin.FourContactWatchRequiredMarginCm'}, graph.start())
        self.assertFalse(any(o.get('memberName') == 'FourContactCompletionMinimumMarginCm' for o in ops))

    def test_upgrade_resolves_existing_nodes_without_recreating_functions(self):
        ids = {name: name+'Guid' for name in ('bodyok', 'cache6', 'cachepose', 'self', 'donebranch', 'done')}
        ops = graph.completion_upgrade(ids)
        self.assertLessEqual(len(ops), 200)
        self.assertEqual(sum(o['edit'] == 'add_variable' for o in ops), 2)
        self.assertFalse(any(o['edit'] == 'add_function' for o in ops))
        self.assertIn({'edit': 'connect_pins', 'fromNodeId': 'donebranchGuid', 'fromPinName': 'then',
                       'to': '$finalfootprint.execute'}, ops)

    def test_watch_targets_are_separate_from_last_request_metadata(self):
        start, check = graph.start(), graph.check_all()
        for i in INDICES:
            self.assertIn({'edit': 'connect_pins', 'from': f'$target{i}.LastFourContactTarget{i}',
                           'to': f'$cache{i}.FourContactWatchTarget{i}'}, start)
            self.assertTrue(any(o.get('memberName') == f'FourContactWatchTarget{i}' for o in check))
        self.assertFalse(any(str(o.get('memberName', '')).startswith('LastFourContactTarget') for o in check))

    def test_abort_holds_current_amount_not_original_goal(self):
        ops = graph.hold_leg()
        self.assertIn({'edit': 'connect_pins', 'from': '$amount.ExtensionPosition', 'to': '$hold.Amount'}, ops)
        abort = graph.abort()
        self.assertEqual(next(o for o in abort if o.get('id') == 'state')['pinDefaults']['FourContactWatchState'], 3)
        self.assertEqual(sum(o.get('memberName') == 'HoldExperimentalContactLeg' for o in abort), 4)

    def test_pose_guard_includes_live_angles_requests_and_closed_actual_claws(self):
        expression = next(o['expression'] for o in graph.pose() if o.get('id') == 'conditions')
        for name in ('bAutoDemo', 'LiveBendPitchDegrees', 'LiveBendYawDegrees', 'SocketRequestedOpening'):
            self.assertIn(name, expression)
        for i in range(1, 10):
            for suffix in ('Magnitude', 'PitchRequest', 'YawRequest'):
                self.assertIn(f'Joint{i}{suffix}', expression)
        for i in range(3):
            self.assertIn(f'abs(c{i})', expression)

    def test_time_and_pose_checks_precede_world_sampling(self):
        ops = graph.update()
        self.assertIn({'edit': 'connect_pins', 'from': '$timebranch.else', 'to': '$badtime.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$posebranch.else', 'to': '$moved.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$posebranch.then', 'to': '$sample.execute'}, ops)
        self.assertFalse(any(o.get('memberName') in ('SetActorLocation', 'K2_SetActorLocation', 'SpawnActorFromClass') for o in ops))

    def test_invalid_body_probe_settings_do_not_reuse_stale_leg_rows(self):
        ops = graph.update()
        self.assertEqual(next(o['expression'] for o in ops if o.get('id') == 'freshsnapshot'),
                         'bBodyProbeSettingsValid && (BodyProbeMeasuredCount == 8)')
        self.assertIn({'edit': 'connect_pins', 'from': '$sample.then', 'to': '$freshbranch.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$freshbranch.then', 'to': '$inspect.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$freshbranch.else', 'to': '$invalid.execute'}, ops)

    def test_integration_has_real_tick_and_explicit_self(self):
        ops = graph.integration('accepted', 'tick')
        self.assertIn({'edit': 'connect_pins', 'fromNodeId': 'tick', 'fromPinName': 'DeltaSeconds',
                       'to': '$watchtick.DeltaSeconds'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$tickself.self', 'to': '$watchtick.self'}, ops)
        self.assertIn({'edit': 'connect_pins', 'fromNodeId': 'accepted', 'fromPinName': 'then',
                       'to': '$startwatch.execute'}, ops)

    def test_monitor_can_only_be_explicitly_started_from_reached_or_monitoring(self):
        ops = graph.begin_monitor()
        eligible = next(o['expression'] for o in ops if o.get('id') == 'eligible')
        self.assertEqual(eligible, '(FourContactWatchState == 2) || (FourContactWatchState == 4)')
        self.assertIn({'edit': 'connect_pins', 'from': '$branch.else', 'to': '$reject.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$monitorstate.then', 'to': '$validate.execute'}, ops)
        self.assertEqual(next(o for o in ops if o.get('id') == 'validate')['pinDefaults']['DeltaSeconds'], 0)
        for build in (graph.start, graph.update, graph.controls):
            self.assertFalse(any(o.get('memberName') == 'BeginExperimentalContactMonitoring' for o in build()))

    def test_monitor_keeps_approach_clock_and_checks_delta_without_approach_deadline(self):
        formula = graph.TIME_EXPRESSION.replace('&&', ' and ').replace('||', ' or ')

        def allowed(state, dt, elapsed=3, timeout=0.1):
            return eval(formula, {'__builtins__': {}}, dict(FourContactWatchState=state, dt=dt,
                        FourContactWatchElapsed=elapsed, FourContactWatchTimeout=timeout))

        self.assertFalse(allowed(1, 1))
        self.assertTrue(allowed(1, 1, timeout=10))
        self.assertTrue(allowed(4, 1))
        for delta in (-1, 11, float('nan'), float('inf')):
            self.assertFalse(allowed(4, delta))
        for elapsed in (-1, 61, float('nan')):
            self.assertFalse(allowed(4, 0, elapsed=elapsed))
        ops = graph.update()
        self.assertIn({'edit': 'connect_pins', 'from': '$monitoroldelapsed.FourContactWatchElapsed',
                       'to': '$monitorclock.B'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$monitorclock.ReturnValue',
                       'to': '$setelapsed.FourContactWatchElapsed'}, ops)

    def test_monitor_lost_target_aborts_instead_of_resuming_approach(self):
        ops = graph.update()
        self.assertIn({'edit': 'connect_pins', 'from': '$donebranch.else', 'to': '$monitordrift.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$monitordrift.then', 'to': '$invalid.execute'}, ops)
        self.assertIn('FourContactWatchState == 4', graph.ABORT_EXPRESSION)

    def test_monitor_upgrade_adds_no_tick_members_or_goals(self):
        ids = {name: name+'Guid' for name in ('active', 'timeok', 'abortactive', 'elapsed', 'setelapsed',
                                               'donebranch', 'finalbranch', 'done', 'invalid')}
        ops = graph.monitor_upgrade(ids)
        self.assertLessEqual(len(ops), 200)
        self.assertFalse(any(o['edit'] in ('add_variable', 'add_function') for o in ops))
        self.assertFalse(any(o.get('memberName') in ('SetBodyLegExtension', 'RetractBodyLeg') for o in ops))
        self.assertIn({'edit': 'connect_pins', 'fromNodeId': 'donebranchGuid', 'fromPinName': 'else',
                       'to': '$monitordrift.execute'}, ops)
