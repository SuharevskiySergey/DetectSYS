import json
from pathlib import Path
import unittest

from build_beholder_surface_graph import CONFIG_EXPRESSION, operations


class RuntimeProbeGraphTests(unittest.TestCase):
    def test_batch_fits_and_ids_are_unique(self):
        ops = operations()
        self.assertLessEqual(len(ops), 200)
        ids = [op['id'] for op in ops if 'id' in op]
        self.assertEqual(len(ids), len(set(ids)))

    def test_helpers_explicitly_target_limb_instance(self):
        ops = operations()
        helpers = [op['id'] for op in ops if op.get('memberName') in ('ResetSurfaceProbe', 'ConsiderSurfacePoint')]
        self.assertEqual(len(helpers), 13)
        for id in helpers:
            self.assertTrue(any(op.get('from') == '$self.self' and op.get('to') == '$'+id+'.self' for op in ops))

    def test_all_fixture_vertices_are_used_without_recalibration(self):
        bones = json.loads((Path(__file__).parent/'fixtures/lapa5_claw_vertices.json').read_text())['bones']
        nodes = {op.get('id'): op for op in operations() if op['edit'] == 'create_node'}
        for i, (bone, vertices) in enumerate(bones.items()):
            self.assertEqual(nodes[f'socket{i}']['pinDefaults']['InSocketName'], bone)
            self.assertEqual(nodes[f'socket{i}']['pinDefaults']['TransformSpace'], 'RTS_World')
            for j, vertex in enumerate(vertices):
                actual = list(map(float, nodes[f'p{i}{j}']['pinDefaults']['Location'].split(',')))
                self.assertEqual(actual, vertex)

    def test_ignore_list_includes_parent_and_descendants(self):
        ops = operations()
        self.assertTrue(any(op.get('memberName') == 'GetAllChildActors' and op['pinDefaults']['bIncludeDescendants'] for op in ops))
        self.assertIn({'edit': 'connect_pins', 'from': '$parent.ReturnValue', 'to': '$addparent.NewItem'}, ops)

    def test_settings_and_world_scale_are_bounded(self):
        self.assertIn('ProbeTraceDistance <= 100000.000000', CONFIG_EXPRESSION)
        self.assertIn('ProbeTraceLift <= 100.000000', CONFIG_EXPRESSION)
        for axis in 'XYZ':
            self.assertIn(f'abs(scale{axis}) <= 10000.000000', CONFIG_EXPRESSION)
