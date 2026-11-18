"""Execute only the harness cleanup against fake actors; no Unreal import."""
import ast
from collections import deque
import json
from pathlib import Path
from types import SimpleNamespace
import traceback
import time
import tempfile
import unittest
import uuid


class FakeActor:
    def __init__(self, state, fail_cancel=False):
        self.fields = dict(RedistributionState=state, RedistributionReason=0,
                           RedistributionUpdates=7, RedistributionContactSamples=15,
                           RedistributionMonitoringUpdates=0, ExtensionAmount=0.5, ExtensionPosition=0.5)
        self.fields.update({f'Stage{i}Position': 0.5 for i in range(10)})
        self.calls = []
        self.fail_cancel = fail_cancel

    def get_editor_property(self, name):
        return self.fields[name]

    def call_method(self, name, args):
        self.calls.append((name, args))
        if self.fail_cancel:
            raise RuntimeError('cancel unavailable')
        assert name == 'CancelStageRedistribution' and args == ()
        self.fields.update(RedistributionState=3, RedistributionReason=5)


class FailureCleanupTests(unittest.TestCase):
    def run_finish(self, actor, error):
        tree = ast.parse(Path(__file__).with_name('exercise_beholder_redistribution.py').read_text(encoding='utf-8'))
        function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'finish')
        writer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'write_terminal_report')
        removed = []
        report = {}
        namespace = dict(actor=actor, COUNT=10, report=report,
            state=dict(recent_samples=deque([{'updates': 7}], maxlen=8), handle='observer'),
            traceback=traceback, time=time, pause_motion='none', cycles=1, dilation_owned=False,
            json=json, uuid=uuid, unreal=SimpleNamespace(unregister_slate_post_tick_callback=removed.append))
        exec(compile(ast.Module(body=[writer, function], type_ignores=[]), '<failure cleanup>', 'exec'), namespace)
        with tempfile.TemporaryDirectory(prefix='beholder_cleanup_') as directory:
            path = Path(directory)/'report.json'
            namespace['path'] = path
            namespace['finish'](error)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), report)
            archives = list(path.parent.glob('report_Archive_*.json'))
            self.assertEqual(len(archives), 1)
            self.assertEqual(str(archives[0]), report['terminalArchivePath'])
            self.assertEqual(json.loads(archives[0].read_text(encoding='utf-8')), report)
        self.assertEqual(removed, ['observer'])
        self.assertTrue(report['callbackUnregistered'])
        return report

    def test_errors_cancel_only_active_test_controller_without_rewriting_pose(self):
        for state in (1, 4):
            actor = FakeActor(state)
            report = self.run_finish(actor, AssertionError('original observation error'))
            self.assertFalse(report['passed'])
            self.assertFalse(report['running'])
            self.assertEqual(actor.calls, [('CancelStageRedistribution', ())])
            self.assertEqual(report['failureCleanup']['stateAfter'], 3)
            self.assertEqual(report['failureCleanup']['reasonAfter'], 5)
            self.assertTrue(report['failureCleanup']['snapshotUnchanged'])
            self.assertEqual(report['recentSamplesAtFailure'], [{'updates': 7}])

    def test_success_and_inactive_states_do_not_trigger_cancel(self):
        for state, error in ((1, None), (0, AssertionError('error')), (2, AssertionError('error')), (3, AssertionError('error'))):
            actor = FakeActor(state)
            report = self.run_finish(actor, error)
            self.assertFalse(actor.calls)
            self.assertNotIn('failureCleanup', report)
            self.assertEqual(report['passed'], error is None)

    def test_cancel_error_is_recorded_without_masking_original_failure(self):
        actor = FakeActor(1, fail_cancel=True)
        report = self.run_finish(actor, AssertionError('original observation error'))
        self.assertFalse(report['passed'])
        self.assertIn('original observation error', report['error'])
        self.assertIn('cancel unavailable', report['failureCleanupError'])
