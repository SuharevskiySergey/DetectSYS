import json
import math
from pathlib import Path
import unittest

import build_beholder_probe_coherence_graph as graph
from build_beholder_surface_graph import operations


def coherent(point, center=(1, 2, 3), radius=81):
    if not all(math.isfinite(v) for v in (*point, *center)):
        return False
    values = dict(zip(('px', 'py', 'pz'), point))
    values.update(zip(('cx', 'cy', 'cz'), center))
    values['radius'] = radius
    return eval(graph.CONDITION.replace('&&', ' and '), {'__builtins__': {}}, values)


class ProbeCoherenceGraphTests(unittest.TestCase):
    def test_numeric_envelope_tolerance_and_large_stale_translation(self):
        self.assertTrue(coherent((82, 2, 3)))
        self.assertTrue(coherent((82.005, 2, 3)))
        self.assertFalse(coherent((82.02, 2, 3)))
        self.assertFalse(coherent((1, 2602, 3)))

    def test_nonfinite_and_invalid_radius_are_rejected(self):
        for bad in (float('nan'), float('inf'), -float('inf')):
            self.assertFalse(coherent((1, 2, bad)))
            self.assertFalse(coherent((1, 2, 3), center=(1, 2, bad)))
        for radius in (0, -1, float('nan'), float('inf'), 1000001):
            self.assertFalse(coherent((1, 2, 3), radius=radius))

    def test_bound_matches_existing_enlarged_head_envelope(self):
        from beholder_socket_safety import HEAD_FREE_ENVELOPE_RADIUS
        self.assertAlmostEqual(graph.LOCAL_ENVELOPE_RADIUS*(60/27), HEAD_FREE_ENVELOPE_RADIUS)

    def test_every_calibrated_vertex_is_checked_without_recalibration(self):
        fixture = json.loads((Path(__file__).parent/'fixtures/lapa5_claw_vertices.json').read_text())['bones']
        ops = graph.pose()
        self.assertEqual(sum(o.get('memberName') == 'IsSurfacePointCoherent' for o in ops), 12)
        for i, (bone, vertices) in enumerate(fixture.items()):
            self.assertEqual(next(o for o in ops if o.get('id') == f'socket{i}')['pinDefaults']['InSocketName'], bone)
            for j, vertex in enumerate(vertices):
                transform = next(o for o in ops if o.get('id') == f'p{i}{j}')
                self.assertEqual(list(map(float, transform['pinDefaults']['Location'].split(','))), vertex)
                self.assertIn({'edit': 'connect_pins', 'from': f'$branchp{i}{j}.else', 'to': '$reject.execute'}, ops)

    def test_reset_precedes_coherence_and_coherence_precedes_trace(self):
        ops = operations()
        self.assertIn({'edit': 'connect_pins', 'from': '$reset.then', 'to': '$coherence.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$coherentbranch.then', 'to': '$hmvalid.exec'}, ops)
        self.assertFalse(any(o.get('from') == '$coherentbranch.else' for o in ops))
        delta = graph.integration('reset', 'next')
        self.assertIn({'edit': 'connect_pins', 'fromNodeId': 'reset', 'fromPinName': 'then', 'to': '$coherence.execute'}, delta)

    def test_batches_fit_and_guard_is_read_only(self):
        for build in (graph.point, graph.pose):
            ops = build()
            self.assertLessEqual(len(ops), 200)
            ids = [o['id'] for o in ops if 'id' in o]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertFalse(any(o['edit'] == 'add_variable' or o.get('nodeType') == 'VariableSet' for o in ops))
            self.assertFalse(any(o.get('memberName') in ('LineTraceSingle', 'SetBodyLegExtension', 'SetActorLocation') for o in ops))

    def test_nan_vectors_have_explicit_native_guards(self):
        ops = graph.point()
        self.assertEqual(sum(o.get('memberName') == 'Vector_IsNAN' for o in ops), 2)
        self.assertEqual(next(o for o in ops if o.get('id') == 'reject')['pinDefaults']['Coherent'], False)
