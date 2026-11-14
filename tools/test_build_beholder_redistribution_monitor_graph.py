import math
import unittest

import build_beholder_redistribution_monitor_graph as graph


class RedistributionMonitorTests(unittest.TestCase):
    def test_plans_fit_and_aliases_unique(self):
        for build in (graph.members, graph.update, graph.begin):
            ops = build()
            self.assertLessEqual(len(ops), 200)
            ids = [o['id'] for o in ops if 'id' in o]
            self.assertEqual(len(ids), len(set(ids)))

    def test_only_contact_owned_complete_or_already_monitoring_can_begin(self):
        expression = graph.ELIGIBLE.replace('&&', ' and ').replace('||', ' or ')
        for state in range(5):
            for owned in (False, True):
                self.assertEqual(eval(expression, {'__builtins__': {}},
                                      dict(RedistributionState=state, bRedistributionContactOwned=owned)),
                                 owned and state in (2, 4))

    def test_begin_rechecks_without_recapturing_contact_or_resetting_motion(self):
        ops = graph.begin()
        self.assertIn(dict(edit='connect_pins', **{'from': '$firstbranch.else', 'to': '$state.execute'}), ops)
        self.assertIn(dict(edit='connect_pins', **{'from': '$state.then', 'to': '$check.execute'}), ops)
        setters = {o.get('memberName') for o in ops if o.get('nodeType') == 'VariableSet'}
        self.assertEqual(setters, {'RedistributionState', 'RedistributionMonitoringUpdates'})
        self.assertEqual(next(o for o in ops if o.get('id') == 'check')['pinDefaults'], {'DeltaSeconds': 0})

    def test_snapshot_fails_closed_on_lost_ownership_goals_mode_or_stage(self):
        expression = graph.SNAPSHOT.replace('&&', ' and ')
        base = dict(bRedistributionContactOwned=True, bSequentialMotion=True, RedistributionExtension=0.5,
                    ExtensionAmount=0.5, ExtensionPosition=0.5, RedistributionProgress=1)
        base.update({f'Stage{i}Position': 1 if i < 5 else 0 for i in range(10)})
        def valid(**changes):
            return eval(expression, {'__builtins__': {}, 'abs': abs, 'clamp': lambda x, a, b: max(a, min(b, x))},
                        {**base, **changes})
        self.assertTrue(valid())
        for changes in (dict(bRedistributionContactOwned=False), dict(bSequentialMotion=False),
                        dict(ExtensionAmount=0.2), dict(ExtensionPosition=math.nan),
                        dict(RedistributionProgress=0.9), dict(Stage9Position=math.nan),
                        dict(Stage0Position=0.9)):
            self.assertFalse(valid(**changes))

    def test_monitor_does_not_move_or_use_redistribution_duration(self):
        ops = graph.update()
        self.assertEqual(next(o['expression'] for o in ops if o.get('id') == 'active'), 'RedistributionState == 4')
        setters = {o.get('memberName') for o in ops if o.get('nodeType') == 'VariableSet'}
        self.assertEqual(setters, {'RedistributionMonitoringUpdates'})
        self.assertFalse(any(o.get('memberName') in ('ApplyRedistribution0', 'ApplyRedistribution5') for o in ops))
        self.assertFalse(any('RedistributionDuration' in o.get('expression', '') for o in ops))
        self.assertTrue(any(o.get('memberName') == 'CheckOwnedRedistributionContact' for o in ops))

    def test_delta_finite_and_no_approach_timeout(self):
        expression = graph.TIME.replace('&&', ' and ')
        for dt, expected in ((0, True), (1, True), (10, True), (-1, False), (11, False), (math.nan, False), (math.inf, False)):
            self.assertEqual(eval(expression, {'__builtins__': {}}, dict(dt=dt)), expected)

    def test_abort_and_release_include_monitor_but_not_idle(self):
        for state in range(5):
            for expression, expected in ((graph.ABORT, state in (1, 4)), (graph.RELEASE, state in (2, 4))):
                self.assertEqual(eval(expression.replace('||', ' or '), {'__builtins__': {}}, dict(RedistributionState=state)), expected)

    def test_integration_reuses_tick_and_requires_inspected_ids(self):
        names = ('ownedbranch', 'update', 'tick', 'self', 'abortcondition', 'releasecondition')
        ids = {n: n+'Guid' for n in names}
        ops = graph.integration(ids)
        self.assertFalse(any(o['edit'] in ('add_function', 'add_variable') for o in ops))
        self.assertIn(dict(edit='connect_pins', **{'fromNodeId': ids['ownedbranch'], 'fromPinName': 'then',
                                                  'to': '$monitor.execute'}), ops)
        self.assertIn(dict(edit='connect_pins', **{'from': '$monitor.then', 'toNodeId': ids['update'],
                                                  'toPinName': 'execute'}), ops)
        with self.assertRaises(ValueError):
            graph.integration({})
