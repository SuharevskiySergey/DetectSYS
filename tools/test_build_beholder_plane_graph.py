import json
from pathlib import Path
import unittest

from build_beholder_plane_graph import evaluate, helpers, integration


class PlaneGraphTests(unittest.TestCase):
    def test_batches_fit_enginewire_limit(self):
        self.assertLessEqual(len(helpers()), 200)
        self.assertLessEqual(len(evaluate()), 200)

    def test_each_plane_helper_targets_self(self):
        ops = evaluate()
        calls = [op['id'] for op in ops if op.get('memberName') in ('ResetSurfacePlane', 'ConsiderSurfacePlanePoint')]
        self.assertEqual(len(calls), 13)
        for id in calls:
            self.assertIn({'edit': 'connect_pins', 'from': '$self.self', 'to': '$'+id+'.self'}, ops)

    def test_uses_all_calibrated_world_vertices(self):
        bones = json.loads((Path(__file__).parent/'fixtures/lapa5_claw_vertices.json').read_text())['bones']
        nodes = {op['id']: op for op in evaluate() if op['edit'] == 'create_node'}
        for i, (bone, vertices) in enumerate(bones.items()):
            self.assertEqual(nodes[f'socket{i}']['pinDefaults']['InSocketName'], bone)
            self.assertEqual(nodes[f'socket{i}']['pinDefaults']['TransformSpace'], 'RTS_World')
            for j, vertex in enumerate(vertices):
                self.assertEqual(list(map(float, nodes[f'v{i}{j}']['pinDefaults']['Location'].split(','))), vertex)

    def test_resets_before_testing_hit_flags(self):
        ops = evaluate()
        self.assertIn({'edit': 'connect_pins', 'from': '$entry.then', 'to': '$reset.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$reset.then', 'to': '$readybranch.execute'}, ops)
        expression = next(op['expression'] for op in ops if op.get('id') == 'ready')
        self.assertIn('bProbeValid', expression)
        self.assertIn('bProbeHit', expression)
        self.assertIn('bProbeInitialOverlap == false', expression)

    def test_minimum_updates_point_and_clearance_sequentially(self):
        ops = helpers()
        self.assertIn({'edit': 'connect_pins', 'from': '$branch.then', 'to': '$setclear.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$setclear.then', 'to': '$setpoint.execute'}, ops)

    def test_integration_has_explicit_self_and_both_tail_links(self):
        ops = integration('reset-tail', 'measure-tail')
        for id in ('resetplane', 'evalplane'):
            self.assertIn({'edit': 'connect_pins', 'from': '$'+id+'self.self', 'to': '$'+id+'.self'}, ops)
        self.assertEqual({op['fromNodeId'] for op in ops if 'fromNodeId' in op}, {'reset-tail', 'measure-tail'})
