import math
import unittest

import build_beholder_redistribution_graph as graph


class RedistributionGraphTests(unittest.TestCase):
    def test_plans_fit_and_aliases_unique(self):
        for build in (graph.members, lambda: graph.apply_group(range(5)), lambda: graph.apply_group(range(5, 10)),
                      graph.request, graph.abort, graph.cancel, graph.release, graph.update):
            ops = build()
            self.assertLessEqual(len(ops), 200)
            ids = [o['id'] for o in ops if 'id' in o]
            self.assertEqual(len(ids), len(set(ids)))

    def test_default_off_and_separate_asset(self):
        self.assertNotEqual(graph.BP, graph.LEG)
        flag = next(o for o in graph.members() if o['variableName'] == 'bEnableStageRedistribution')
        self.assertFalse(flag['defaultValue'])
        state = next(o for o in graph.members() if o['variableName'] == 'RedistributionState')
        self.assertEqual(state['defaultValue'], 0)

    def test_one_progress_drives_all_stages_and_conserves_sum(self):
        ops = graph.apply_group(range(10))
        expressions = [o['expression'] for o in ops if str(o.get('id', '')).startswith('value')]
        self.assertEqual(len(expressions), 10)
        for extension in (0.1, 0.2, 0.333333, 0.5, 0.899999, 0.9):
            for k in range(101):
                values = [eval(e, {'__builtins__': {}, 'clamp': lambda x, a, b: max(a, min(b, x))},
                               dict(RedistributionExtension=extension, RedistributionProgress=k/100)) for e in expressions]
                self.assertTrue(all(0 <= v <= 1 for v in values))
                self.assertAlmostEqual(math.fsum(values), extension*10)

    def test_request_does_not_retarget_or_change_stage_values(self):
        ops = graph.request()
        names = [o.get('memberName', '') for o in ops if o.get('nodeType') == 'VariableSet']
        self.assertNotIn('ExtensionAmount', names)
        self.assertFalse(any(n.startswith('Stage') for n in names))
        self.assertTrue(any(o.get('memberName') == 'IsExperimentalContactPoseSafe' for o in ops))
        expression = next(o['expression'] for o in ops if o.get('id') == 'eligible')
        self.assertIn('RedistributionState == 0', expression)
        self.assertIn('ExtensionSeconds <= seconds', expression)

    def test_tick_exclusively_selects_parent_or_owned_update(self):
        ops = graph.tick({'tick': 'tickGuid', 'parent': 'parentGuid'})
        self.assertIn(dict(edit='connect_pins', **{'from': '$dispatch.else', 'toNodeId': 'parentGuid', 'toPinName': 'execute'}), ops)
        self.assertIn(dict(edit='connect_pins', **{'from': '$dispatch.then', 'to': '$update.execute'}), ops)
        self.assertFalse(any(o.get('nodeType') == 'Event' for o in ops))

    def test_preflight_numeric_guards_reject_invalid_or_unsettled_snapshot(self):
        expression = next(o['expression'] for o in graph.request() if o.get('id') == 'eligible')
        expression = expression.replace('&&', ' and ').replace('false', 'False')
        base = dict(bEnableStageRedistribution=True, RedistributionState=0, bSequentialMotion=False,
                    ExtensionPosition=0.5, ExtensionAmount=0.5, seconds=1,
                    ExtensionSeconds=0.5, RetractionSeconds=0.5)
        base.update({f'Stage{i}Position': 0.5 for i in range(10)})
        def allowed(**changes):
            return eval(expression, {'__builtins__': {}, 'abs': abs}, {**base, **changes})
        self.assertTrue(allowed())
        for changes in (dict(seconds=math.nan), dict(seconds=0.1), dict(ExtensionPosition=math.inf),
                        dict(ExtensionAmount=0.2), dict(Stage9Position=math.nan), dict(Stage2Position=0.6),
                        dict(RedistributionState=1), dict(bEnableStageRedistribution=False)):
            self.assertFalse(allowed(**changes))

    def test_aborted_state_cannot_be_released_into_unsynchronised_parent_motion(self):
        expression = next(o['expression'] for o in graph.release() if o.get('id') == 'complete')
        self.assertEqual(expression, 'RedistributionState == 2')

    def test_update_rejects_changed_goal_pose_mode_and_time(self):
        ops = graph.update()
        expr = next(o['expression'] for o in ops if o.get('id') == 'snapshot')
        self.assertIn('ExtensionAmount-RedistributionExtension', expr)
        self.assertIn('bSequentialMotion == false', expr)
        for i in range(10):
            self.assertIn(f'Stage{i}Position-', expr)
        self.assertTrue(any(o.get('memberName') == 'NearlyEqual_TransformTransform' for o in ops))
        time = next(o['expression'] for o in ops if o.get('id') == 'time').replace('&&', ' and ')
        for dt, valid in ((0, True), (0.1, True), (-1, False), (11, False), (math.nan, False)):
            self.assertEqual(eval(time, {'__builtins__': {}}, dict(dt=dt, RedistributionElapsed=0, RedistributionDuration=4)), valid)
