import math
import unittest

import build_beholder_step_cap_graph as graph


def evaluate(text, **values):
    return eval(text.replace('&&', ' and '), {'__builtins__': {}, 'min': min, 'max': max}, values)


class StepCapTests(unittest.TestCase):
    def test_default_unrestricted_and_both_directions_bound_each_stage(self):
        for e in (0.1, 0.2, 0.333333, 0.5, 0.9):
            for cap in (0.001, 0.02, 0.1, 1):
                for dt in (0, 0.001, 0.02, 0.2, 3, 10):
                    elapsed = evaluate(graph.ELAPSED, RedistributionElapsed=0.3, RedistributionDuration=1,
                                       RedistributionExtension=e, RedistributionMaxStageStep=cap, dt=dt)
                    self.assertLessEqual(elapsed, min(0.3+dt, 1)+1e-12)
                    for i in range(10):
                        distance = abs(max(0, min(1, 10*e-i))-e)*(elapsed-0.3)
                        self.assertLessEqual(distance, cap+1e-12)
                    if cap == 1:
                        self.assertAlmostEqual(elapsed, min(0.3+dt, 1))

    def test_invalid_cap_rejected_including_nan_and_infinity(self):
        for v in (-1, 0, 0.0009, 1.1, math.nan, math.inf):
            self.assertFalse(evaluate(graph.CAP_VALID, RedistributionMaxStageStep=v))
        for v in (0.001, 0.02, 1):
            self.assertTrue(evaluate(graph.CAP_VALID, RedistributionMaxStageStep=v))
        import build_beholder_native_stage_audit as native
        expression = next(o['expression'] for o in native.record() if o.get('id') == 'record_Invalid_value')
        expression = expression.replace('&&',' and ').replace('||',' or ').replace('false','False')
        values = {native.PREFIX+'Invalid': False}
        for i in range(10):
            values[f'Stage{i}Position'] = values[native.PREFIX+f'Before{i}'] = 0.5
        self.assertFalse(eval(expression, {'__builtins__': {}}, values))
        for name in list(values)[1:]:
            broken = dict(values); broken[name] = math.nan
            self.assertTrue(eval(expression, {'__builtins__': {}}, broken))

    def test_plans_keep_prior_ownership_and_default(self):
        p = graph.plans({key: key+'Guid' for key in ('time', 'elapsed', 'forward', 'reverse')})
        self.assertEqual(p['members'][0]['defaultValue'], 1)
        self.assertEqual(len(p['integration']), 4)
        self.assertIn('bRedistributionContactOwned', p['integration'][-1]['propertyValue'])
        self.assertTrue(all(o['edit'] == 'set_node_property' for o in p['integration']))
        import build_beholder_native_stage_audit as native
        ops = native.capture()+native.record()
        setters = [o['memberName'] for o in ops if o.get('nodeType') == 'VariableSet']
        self.assertTrue(all(n.startswith(native.PREFIX) for n in setters))
        self.assertEqual(sum(n.startswith(native.PREFIX+'Before') for n in setters), 10)
        expression = next(o['expression'] for o in ops if o.get('id') == 'record_Last_value')
        values = {}
        for i in range(10):
            values[f'Stage{i}Position'] = 0.5
            values[native.PREFIX+f'Before{i}'] = 0.5
        values['Stage7Position'] = 0.51
        self.assertAlmostEqual(eval(expression, {'__builtins__': {}, 'max': max, 'abs': abs}, values), 0.01)
        self.assertEqual(len(native.integration({k:k+'Guid' for k in ('self','progress','first','second','contact_after')})),8)
