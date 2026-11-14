import math
import unittest

import build_beholder_game_timeout_graph as graph


def evaluate(text, **values):
    return eval(text.replace('&&', ' and ').replace('||', ' or '), {'__builtins__': {}}, values)


class GameTimeoutTests(unittest.TestCase):
    def test_zero_disabled_and_deadline_uses_game_clock_not_controller_elapsed(self):
        for elapsed in (0, 0.1, 1):
            values = dict(game_now=15, RedistributionGameStart=10, RedistributionGameTimeout=2,
                          RedistributionElapsed=elapsed)
            self.assertFalse(evaluate(graph.WITHIN_BUDGET, **values))
            self.assertTrue(evaluate(graph.WITHIN_BUDGET, **{**values, 'RedistributionGameTimeout': 0}))
        self.assertTrue(evaluate(graph.WITHIN_BUDGET, game_now=12, RedistributionGameStart=10, RedistributionGameTimeout=2))

    def test_invalid_budgets_and_clock_rejected(self):
        # Unreal MathExpression's equality path accepted NaN in PIE; mandatory
        # ordered range checks must guard the disabled-zero branch as well.
        self.assertIn('(RedistributionGameTimeout >= 0.000000) && (RedistributionGameTimeout <= 600.000000)', graph.TIMEOUT_VALID)
        for value in (-1, 0.001, 601, math.nan, math.inf):
            self.assertFalse(evaluate(graph.TIMEOUT_VALID, RedistributionGameTimeout=value))
        for now, start in ((1, 2), (math.nan, 0), (math.inf, 0), (2, math.nan), (0, -1)):
            self.assertFalse(evaluate(graph.CLOCK_VALID, game_now=now, RedistributionGameStart=start))

    def test_fresh_start_is_committed_in_both_requests_and_step_cap_preserved(self):
        keys = ('time', 'elapsed', 'forward', 'reverse', 'forward_prev', 'forward_next', 'reverse_prev', 'reverse_next')
        p = graph.plans({key: key+'Guid' for key in keys})
        self.assertTrue(all(o['defaultValue'] == 0 for o in p['members']))
        ops = p['integration']
        self.assertEqual(sum(o.get('memberName') == 'RedistributionGameStart' for o in ops), 2)
        self.assertFalse(any(o.get('nodeId') == 'elapsedGuid' for o in ops))
        guards = [o['propertyValue'] for o in ops if o['edit'] == 'set_node_property']
        self.assertEqual(len(guards), 3)
        self.assertTrue(all('RedistributionMaxStageStep' in e for e in guards))
        self.assertIn('bRedistributionContactOwned', guards[-1])
