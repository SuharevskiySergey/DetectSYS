import itertools
import unittest

import build_beholder_body_probe_graph as graph
from beholder_support_candidate import candidate, settings_valid


class BodyProbeGraphTests(unittest.TestCase):
    def test_batches_fit_and_aliases_are_unique(self):
        for build in (graph.reset, graph.classify, graph.sample, graph.update):
            ops = build()
            self.assertLessEqual(len(ops), 200)
            ids = [op['id'] for op in ops if 'id' in op]
            self.assertEqual(len(ids), len(set(ids)))

    def test_each_array_is_cleared_before_resizing_to_eight(self):
        ops = graph.reset()
        for i, (name, _, _) in enumerate(graph.ARRAYS):
            self.assertTrue(any(op.get('id') == f'resize{i}' and op['pinDefaults']['Size'] == 8 for op in ops))
            self.assertIn({'edit': 'connect_pins', 'from': f'$clear{i}.then',
                           'to': f'$resize{i}.execute'}, ops)
            self.assertTrue(any(op.get('memberName') == name for op in ops))

    def test_update_samples_fixed_order_with_explicit_self(self):
        ops = graph.update()
        previous = '$configbranch.then'
        for i in range(8):
            self.assertTrue(any(op.get('id') == f'sample{i}' and op['pinDefaults']['Index'] == i for op in ops))
            for source, target in [('$self.self', f'$sample{i}.self'),
                                    (f'$leg{i}.Leg{i}', f'$sample{i}.Component'),
                                    (previous, f'$sample{i}.execute')]:
                self.assertIn({'edit': 'connect_pins', 'from': source, 'to': target}, ops)
            previous = f'$sample{i}.then'

    def test_measurement_precedes_classification_and_publication(self):
        ops = graph.sample()
        self.assertIn({'edit': 'connect_pins', 'from': '$measure.then', 'to': '$classify.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$classify.then', 'to': '$publish0.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$self.self', 'to': '$classify.self'}, ops)
        for i in range(8):
            node = next(op for op in ops if op.get('id') == f'publish{i}')
            self.assertFalse(node['pinDefaults']['bSizeToFit'])
            self.assertIn({'edit': 'connect_pins', 'from': '$sampleentry.Index', 'to': f'$publish{i}.Index'}, ops)

    def test_candidate_requires_all_sensor_flags(self):
        ops = graph.classify()
        for source, target in [('$classentry.Valid', '$flags1.A'), ('$classentry.Hit', '$flags1.B'),
                                ('$classentry.PlaneValid', '$flags2.B')]:
            self.assertIn({'edit': 'connect_pins', 'from': source, 'to': target}, ops)

    def test_scalar_expression_matches_independent_python_classifier(self):
        # Evaluate only our own checked-in arithmetic expression, not editor data.
        expression = graph.CANDIDATE_EXPRESSION.replace('&&', ' and ')
        configs = [(0.8, 2, 0.1), (-1, 2, 0.1), (1.1, 2, 0.1), (0.8, -1, 0.1),
                   (0.8, 101, 0.1), (0.8, 2, -1), (0.8, 2, 2), (float('nan'), 2, 0.1)]
        readings = itertools.product((-1, 0, 0.8, 1, 1.01, float('nan'), float('inf')),
                                     (-1, -0.1, 0, 2, 3), (-1, 0, 1, 3))
        for normal, clearance, gap in readings:
            for minimum, maximum, tolerance in configs:
                values = dict(BodySupportMinNormalZ=minimum, BodySupportMaxGapCm=maximum,
                              BodySupportPenetrationToleranceCm=tolerance,
                              normalZ=normal, clearance=clearance, verticalGap=gap)
                actual = bool(eval(expression, {'__builtins__': {}}, values))
                self.assertEqual(actual, candidate(True, True, True, normal, clearance, gap,
                                                   minimum, maximum, tolerance))
                settings = bool(eval(graph.SETTINGS_EXPRESSION.replace('&&', ' and '), {'__builtins__': {}}, values))
                self.assertEqual(settings, settings_valid(minimum, maximum, tolerance))

    def test_no_motion_or_tick_commands_are_added(self):
        names = {op.get('memberName') for build in (graph.reset, graph.classify, graph.sample, graph.update)
                 for op in build()}
        for forbidden in ('SetBodyLegExtension', 'SetLegExtension', 'SetActorLocation', 'K2_SetActorLocation',
                          'SetActorRotation', 'SetHeadOpening'):
            self.assertNotIn(forbidden, names)
        self.assertFalse(any(op.get('eventName') == 'Tick' for op in graph.update()))
