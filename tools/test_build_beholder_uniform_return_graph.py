import math
import unittest

import build_beholder_uniform_return_graph as graph


def evaluate(expression, values):
    return eval(expression.replace('&&', ' and ').replace('||', ' or ').replace('false', 'False'),
                {'__builtins__': {}, 'abs': abs, 'clamp': lambda x, a, b: max(a, min(b, x))}, values)


class UniformReturnTests(unittest.TestCase):
    def test_plans_fit_and_aliases_unique(self):
        for build in (graph.members, graph.request):
            ops = build()
            self.assertLessEqual(len(ops), 200)
            ids = [o['id'] for o in ops if 'id' in o]
            self.assertEqual(len(ids), len(set(ids)))

    def test_default_direction_preserves_existing_packing(self):
        self.assertEqual(graph.members()[0]['defaultValue'], 1)
        self.assertFalse(graph.members()[0]['isPublic'])

    def test_both_directions_conserve_sum_and_are_each_others_reverse(self):
        for e in (0.1, 0.199, 0.333333, 0.5, 0.899999, 0.9):
            for k in range(101):
                f = k/100
                forward = [evaluate(graph.stage_value(i), dict(RedistributionExtension=e, RedistributionDirection=1,
                                                              RedistributionProgress=f)) for i in range(10)]
                reverse = [evaluate(graph.stage_value(i), dict(RedistributionExtension=e, RedistributionDirection=-1,
                                                              RedistributionProgress=1-f)) for i in range(10)]
                for a, b in zip(forward, reverse):
                    self.assertAlmostEqual(a, b)
                    self.assertTrue(-1e-12 <= a <= 1+1e-12)
                self.assertAlmostEqual(math.fsum(forward), 10*e)
                self.assertAlmostEqual(math.fsum(reverse), 10*e)

    def test_return_is_not_recovery_and_rejects_invalid_preflight(self):
        expression = next(o['expression'] for o in graph.request() if o.get('id') == 'eligible')
        base = dict(RedistributionState=2, RedistributionDirection=1, bEnableStageRedistribution=True,
                    bRedistributionContactOwned=False,
                    bSequentialMotion=True, RedistributionExtension=0.5, ExtensionAmount=0.5,
                    ExtensionPosition=0.5, RedistributionProgress=1, seconds=1,
                    ExtensionSeconds=0.5, RetractionSeconds=0.5)
        base.update({f'Stage{i}Position': 1 if i < 5 else 0 for i in range(10)})
        self.assertTrue(evaluate(expression, base))
        self.assertTrue(evaluate(expression, {**base, 'RedistributionState': 4, 'bRedistributionContactOwned': True}))
        for changes in (dict(RedistributionState=0), dict(RedistributionState=1), dict(RedistributionState=3),
                        dict(RedistributionState=4, bRedistributionContactOwned=False),
                        dict(RedistributionDirection=-1), dict(seconds=math.nan), dict(seconds=0.1),
                        dict(ExtensionAmount=0.2), dict(Stage0Position=0.9), dict(Stage9Position=math.nan)):
            self.assertFalse(evaluate(expression, {**base, **changes}))

    def test_request_only_commits_after_fresh_contact_and_does_not_recapture(self):
        ops = graph.request()
        self.assertTrue(any(o.get('memberName') == 'CheckOwnedRedistributionContact' for o in ops))
        self.assertIn(dict(edit='connect_pins', **{'from': '$commit.then', 'to': '$duration.execute'}), ops)
        setters = {o.get('memberName') for o in ops if o.get('nodeType') == 'VariableSet'}
        for forbidden in ('ExtensionAmount', 'ExtensionPosition', 'RedistributionPose', 'RedistributionExtension',
                          'bRedistributionContactOwned', 'RedistributionContactPoint', 'RedistributionContactNormal'):
            self.assertNotIn(forbidden, setters)

    def test_motion_and_monitor_snapshots_accept_only_the_correct_pattern(self):
        for direction in (1, -1):
            for f in (0, 0.5, 1):
                values = dict(RedistributionDirection=direction, RedistributionProgress=f,
                              RedistributionExtension=0.5, ExtensionAmount=0.5, ExtensionPosition=0.5,
                              RedistributionDuration=1, ExtensionSeconds=0.5, RetractionSeconds=0.5,
                              bSequentialMotion=direction < 0, bRedistributionContactOwned=True)
                values.update({f'Stage{i}Position': evaluate(graph.stage_value(i), values) for i in range(10)})
                self.assertTrue(evaluate(graph.motion_snapshot(), values))
                self.assertFalse(evaluate(graph.motion_snapshot(), {**values, 'bSequentialMotion': direction > 0}))
                self.assertFalse(evaluate(graph.motion_snapshot(), {**values, 'RedistributionDirection': math.nan}))
                if f == 1:
                    values['bSequentialMotion'] = direction > 0
                    self.assertTrue(evaluate(graph.monitor_snapshot(), values))
                    self.assertFalse(evaluate(graph.monitor_snapshot(), {**values, 'bSequentialMotion': direction < 0}))

    def test_integration_changes_only_separate_controller_nodes(self):
        names = [f'value{i}' for i in range(10)]+['motion', 'monitor', 'completionmode', 'forwardclear', 'forwardstore']
        ops = graph.integration({name: name+'Guid' for name in names})
        self.assertEqual(sum(o['edit'] == 'set_node_property' for o in ops), 12)
        self.assertFalse(any(o['edit'] in ('add_function', 'add_variable') for o in ops))
        with self.assertRaises(ValueError):
            graph.integration({})
