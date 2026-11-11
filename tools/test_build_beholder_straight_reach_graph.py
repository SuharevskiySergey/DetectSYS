import unittest

from build_beholder_straight_reach_graph import reset, solve, plan, integration
from generate_beholder_telescope import COUNT, STROKE


class StraightReachGraphTests(unittest.TestCase):
    def test_batches_fit_and_ids_are_unique(self):
        for build in (reset, solve, plan):
            ops = build()
            self.assertLessEqual(len(ops), 200)
            ids = [op['id'] for op in ops if 'id' in op]
            self.assertEqual(len(ids), len(set(ids)))

    def test_full_stroke_comes_from_telescope_generator(self):
        expression = next(op['expression'] for op in plan() if op.get('id') == 'projected')
        self.assertTrue(expression.startswith(f'{float(COUNT*STROKE):.6f}*worldScale'))

    def test_guards_cover_all_joints_and_closed_claws(self):
        nodes = {op.get('id'): op for op in plan() if op['edit'] == 'create_node'}
        for i in range(1, COUNT):
            self.assertIn(f'abs(Joint{i}Magnitude)', nodes['conditions']['expression'])
        for i in range(3):
            self.assertIn(f'abs(c{i})', nodes['closed']['expression'])
        self.assertIn('ExtensionAmount-ExtensionPosition', nodes['conditions']['expression'])

    def test_helper_calls_explicitly_target_self(self):
        for ops in (plan(), solve()):
            calls = [op['id'] for op in ops if op.get('memberName') in ('ResetStraightSurfacePlan', 'SolveStraightPlaneTarget')]
            for id in calls:
                self.assertIn({'edit': 'connect_pins', 'from': '$self.self', 'to': '$'+id+'.self'}, ops)

    def test_solver_guards_division_and_does_not_clamp_unreachable_target(self):
        ops = solve()
        self.assertIn({'edit': 'connect_pins', 'from': '$reset.then', 'to': '$branch.execute'}, ops)
        self.assertIn({'edit': 'connect_pins', 'from': '$reachable.then', 'to': '$settarget.execute'}, ops)
        self.assertFalse(any('clamp' in op.get('expression', '').lower() for op in ops))

    def test_no_actuator_calls_and_both_integration_tails_are_explicit(self):
        names = {op.get('memberName') for build in (reset, solve, plan) for op in build()}
        for forbidden in ('SetLegExtension', 'SetBodyLegExtension', 'SetActorLocation', 'SetJointBend', 'SetHeadOpening'):
            self.assertNotIn(forbidden, names)
        ops = integration('reset-tail', 'plane-tail')
        self.assertEqual({op['fromNodeId'] for op in ops if 'fromNodeId' in op}, {'reset-tail', 'plane-tail'})
