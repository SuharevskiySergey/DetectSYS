import math
import unittest

import build_beholder_redistribution_contact_graph as graph


class RedistributionContactTests(unittest.TestCase):
    def test_plans_fit_and_aliases_unique(self):
        for build in (graph.members, graph.sample, graph.owned, graph.request):
            ops = build()
            self.assertLessEqual(len(ops), 200)
            ids = [o['id'] for o in ops if 'id' in o]
            self.assertEqual(len(ids), len(set(ids)))

    def test_default_does_not_enable_contact_mode(self):
        field = next(o for o in graph.members() if o['variableName'] == 'bRedistributionContactOwned')
        self.assertFalse(field['defaultValue'])
        self.assertFalse(field['isPublic'])

    def test_request_measures_before_base_request_and_only_captures_after_acceptance(self):
        ops = graph.request()
        self.assertIn(dict(edit='connect_pins', **{'from': '$freshbranch.then', 'to': '$start.execute'}), ops)
        self.assertIn(dict(edit='connect_pins', **{'from': '$acceptedbranch.then', 'to': '$anchor.execute'}), ops)
        setters = [o.get('memberName', '') for o in ops if o.get('nodeType') == 'VariableSet']
        self.assertFalse(any(n.startswith('Stage') or n == 'ExtensionAmount' for n in setters))

    def test_sample_is_fresh_and_requires_endpoint_trace(self):
        ops = graph.sample()
        self.assertTrue(any(o.get('memberName') == 'MeasureSurfaceProbe' for o in ops))
        self.assertTrue(any(o.get('memberName') == 'LineTraceSingle' for o in ops))
        self.assertIn(dict(edit='connect_pins', **{'from': '$measure.then', 'to': '$validbranch.execute'}), ops)
        self.assertIn(dict(edit='connect_pins', **{'from': '$validbranch.then', 'to': '$trace.execute'}), ops)
        expression = next(o['expression'] for o in ops if o.get('id') == 'anchorok')
        self.assertIn('driftCm <= 0.010000', expression)
        self.assertIn('normalDifference <= 0.000100', expression)

    def test_ordinary_mode_does_not_trace(self):
        ops = graph.owned()
        self.assertIn(dict(edit='connect_pins', **{'from': '$branch.else', 'to': '$notowned.execute'}), ops)
        self.assertTrue(next(o for o in ops if o.get('id') == 'notowned')['pinDefaults']['Valid'])

    def test_contact_and_anchor_numeric_guards_fail_closed(self):
        ops = graph.sample()
        base = dict(bProbeValid=True, bProbeHit=True, bProbePlaneValid=True, bProbeInitialOverlap=False,
                    ProbePlaneClearance=0, ProbeGap=0, nz=1)
        expression = next(o['expression'] for o in ops if o.get('id') == 'valid').replace('&&', ' and ').replace('false', 'False')
        def valid(**changes):
            return eval(expression, {'__builtins__': {}, 'abs': abs}, {**base, **changes})
        self.assertTrue(valid())
        for changes in (dict(bProbeValid=False), dict(bProbeHit=False), dict(bProbePlaneValid=False),
                        dict(bProbeInitialOverlap=True), dict(ProbeGap=0.1), dict(ProbePlaneClearance=-0.1),
                        dict(ProbePlaneClearance=math.nan), dict(nz=math.nan), dict(nz=0.9)):
            self.assertFalse(valid(**changes))
        expression = next(o['expression'] for o in ops if o.get('id') == 'anchorok').replace('&&', ' and ')
        base = dict(driftCm=0, normalDifference=0, planeZ=0, RedistributionContactPlaneZ=0)
        self.assertTrue(valid())
        for changes in (dict(driftCm=0.02), dict(driftCm=math.nan), dict(normalDifference=0.001),
                        dict(normalDifference=math.nan), dict(planeZ=0.1), dict(planeZ=math.nan)):
            self.assertFalse(valid(**changes))

    def test_integration_checks_before_and_after_and_clears_ownership(self):
        ids = {n: n+'Guid' for n in ('validbranch', 'elapsedstore', 'second', 'donebranch', 'self',
                                    'requestsafe', 'extensionstore', 'releasestate', 'releasereturn')}
        ops = graph.integration(ids)
        self.assertIn(dict(edit='connect_pins', **{'fromNodeId': ids['validbranch'], 'fromPinName': 'then',
                                                  'to': '$precontact.execute'}), ops)
        self.assertIn(dict(edit='connect_pins', **{'fromNodeId': ids['second'], 'fromPinName': 'then',
                                                  'to': '$postcontact.execute'}), ops)
        self.assertEqual(sum(o.get('memberName') == 'bRedistributionContactOwned' and o.get('nodeType') == 'VariableSet'
                             for o in ops), 2)
