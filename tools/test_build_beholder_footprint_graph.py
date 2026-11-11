"""Exercise the exact emitted numeric expressions and structural guards."""
import math
import random
import unittest

import build_beholder_footprint_graph as graph
from beholder_support_polygon import evaluate_footprint


def emitted(points, reference=(0, 0, 0), minimum=0):
    expressions = {o['id']: o['expression'] for o in graph.kernel() if 'expression' in o}
    values = {'required': minimum}
    values.update(zip(('rx', 'ry', 'rz'), reference))
    for prefix, point in zip('abcd', points):
        values.update((prefix+axis, p-r) for axis, p, r in zip('xyz', point, reference))

    def evaluate(id):
        formula = expressions[id].replace('&&', ' and ').replace('||', ' or ')
        return eval(formula, {'__builtins__': {}, 'abs': abs, 'sqrt': math.sqrt, 'min': min}, values)

    if not evaluate('bounds') or not evaluate('geometry'):
        return False, False, False, 0, 0
    values['margin'] = evaluate('margin')
    return True, evaluate('inside'), evaluate('passes'), values['margin'], evaluate('area')


class FootprintGraphTests(unittest.TestCase):
    square = [(-10, -10, 0), (10, -10, 0), (10, 10, 0), (-10, 10, 0)]

    def test_both_windings_and_cyclic_order(self):
        for points in (self.square, self.square[::-1]):
            for i in range(4):
                self.assertEqual(emitted(points[i:]+points[:i]), (True, True, True, 10, 400))

    def test_boundary_outside_and_strict_margin(self):
        self.assertEqual(emitted(self.square, minimum=10), (True, True, False, 10, 400))
        self.assertEqual(emitted(self.square, (10, 0, 0))[:4], (True, True, False, 0))
        self.assertEqual(emitted(self.square, (12, 0, 0))[:4], (True, False, False, -2))

    def test_degenerate_crossed_and_concave_are_rejected_not_reordered(self):
        for points in ([self.square[0]]*4, [(i, i, 0) for i in range(4)],
                       [self.square[i] for i in (0, 2, 1, 3)],
                       [self.square[0], self.square[1], (0, -5, 0), self.square[3]]):
            self.assertEqual(emitted(points), (False, False, False, 0, 0))

    def test_bounded_finite_inputs(self):
        for minimum in (-1, float('nan'), float('inf'), 1000001):
            self.assertFalse(emitted(self.square, minimum=minimum)[0])
        for reference in ((10000001, 0, 0), (0, 0, float('nan')), (0, 0, float('inf'))):
            self.assertFalse(emitted(self.square, reference)[0])

    def test_translated_reference_and_random_oracle(self):
        rng = random.Random(912)
        for _ in range(100):
            cx, cy, radius = rng.uniform(-1000, 1000), rng.uniform(-1000, 1000), rng.uniform(1, 300)
            angle = rng.uniform(-math.pi, math.pi)
            points = [(cx+radius*math.cos(angle+i*math.pi/2),
                       cy+radius*math.sin(angle+i*math.pi/2), 0) for i in range(4)]
            reference = (cx+rng.uniform(-2, 2)*radius, cy+rng.uniform(-2, 2)*radius, 5)
            actual = emitted(points, reference, 1)
            expected = evaluate_footprint([p[:2] for p in points], reference[:2], 1)
            self.assertEqual(actual[:3], (expected['valid'], expected['inside'], expected['passesMargin']))
            self.assertAlmostEqual(actual[3], expected['marginCm'], places=8)
            self.assertAlmostEqual(actual[4], expected['areaCm2'], places=7)

    def test_batches_fit_aliases_unique_and_no_motion_commands(self):
        for build in (graph.kernel, graph.point, graph.evaluate):
            ops = build()
            self.assertLessEqual(len(ops), 200)
            ids = [o['id'] for o in ops if 'id' in o]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertFalse(any(o.get('memberName') in ('SetBodyLegExtension', 'RetractBodyLeg',
                                                        'K2_SetActorLocation', 'SetActorTransform') for o in ops))
            self.assertFalse(any(o['edit'] == 'add_variable' for o in ops))

    def test_nan_guards_and_zeroed_rejection(self):
        ops = graph.kernel()
        self.assertEqual(sum(o.get('memberName') == 'Vector_IsNAN' for o in ops), 5)
        for build in (graph.kernel, graph.evaluate):
            reject = next(o for o in build() if o.get('id') == 'reject')
            self.assertEqual(reject['pinDefaults'], graph.ZERO)

    def test_wrapper_refreshes_and_checks_actual_surface(self):
        ops = graph.evaluate()
        self.assertIn({'edit': 'connect_pins', 'from': '$entry.then', 'to': '$sample.execute'}, ops)
        self.assertTrue(any(o.get('memberName') == 'UpdateBodySurfaceProbes' for o in ops))
        condition = next(o['expression'] for o in ops if o.get('id') == 'complete')
        self.assertIn('BodySupportCandidateCount == 4', condition)
        self.assertEqual(graph.FOOTPRINT_INDICES, (0, 2, 6, 4))
        for rank, index in enumerate(graph.FOOTPRINT_INDICES):
            self.assertIn({'edit': 'connect_pins', 'from': f'$point{index}.Point',
                           'to': f'$calculate.Point{rank}'}, ops)
        point = graph.point()
        self.assertIn({'edit': 'connect_pins', 'from': '$ignore.ProbeIgnoreActors', 'to': '$trace.ActorsToIgnore'}, point)
        trace = next(o for o in point if o.get('id') == 'trace')
        self.assertTrue(trace['pinDefaults']['bTraceComplex'])
        self.assertIn({'edit': 'connect_pins', 'from': '$overlap.then', 'to': '$reject.execute'}, point)
