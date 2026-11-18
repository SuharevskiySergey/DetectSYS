"""Standalone-tested terminal I/O/teardown cases with no Unreal import."""
import ast
from collections import deque
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import traceback
import unittest
from unittest.mock import patch
import uuid

from test_beholder_observer_failure_cleanup import FakeActor


def extracted_namespace(path, unregister=lambda handle: None):
    tree = ast.parse(Path(__file__).with_name('exercise_beholder_redistribution.py').read_text(encoding='utf-8'))
    functions = [next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
                 for name in ('write_terminal_report', 'finish', 'tick')]
    namespace = dict(path=path, actor=FakeActor(1), COUNT=10, report={},
                     state=dict(recent_samples=deque(), handle='fake_callback'),
                     traceback=traceback, time=time, json=json, uuid=uuid,
                     pause_motion='none', cycles=1, dilation_owned=False,
                     unreal=SimpleNamespace(unregister_slate_post_tick_callback=unregister))
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<terminal faults>', 'exec'), namespace)
    return namespace


class TerminalFaultTests(unittest.TestCase):
    def test_archive_creation_failure_does_not_replace_rolling_report(self):
        with tempfile.TemporaryDirectory(prefix='beholder_terminal_') as directory:
            path = Path(directory)/'report.json'
            path.write_text('previous evidence', encoding='utf-8')
            ns = extracted_namespace(path)
            with patch.object(Path, 'open', side_effect=PermissionError('archive denied')):
                with self.assertRaisesRegex(PermissionError, 'archive denied'):
                    ns['write_terminal_report'](path, dict(running=False, passed=False))
            self.assertEqual(path.read_text(encoding='utf-8'), 'previous evidence')
            self.assertEqual(list(path.parent.glob('*_Archive_*.json')), [])

    def test_original_observer_error_survives_unregister_failure(self):
        with tempfile.TemporaryDirectory(prefix='beholder_terminal_') as directory:
            path = Path(directory)/'report.json'

            def failed_unregister(handle):
                raise RuntimeError('secondary detach fault')

            ns = extracted_namespace(path, failed_unregister)
            try:
                raise AssertionError('primary observer fault')
            except AssertionError as original:
                ns['finish'](original)
            report = json.loads(path.read_text(encoding='utf-8'))
            self.assertIn('primary observer fault', report['error'])
            self.assertIn('primary observer fault', report['traceback'])
            self.assertFalse(report['passed'])
            self.assertFalse(report['callbackUnregistered'])
            self.assertEqual(report['finishErrors'][0]['phase'], 'unregister_callback')
            self.assertIn('secondary detach fault', report['finishErrors'][0]['traceback'])
            self.assertEqual(ns['actor'].calls, [('CancelStageRedistribution', ())])
            self.assertTrue(report['failureCleanup']['snapshotUnchanged'])
            archived = json.loads(Path(report['terminalArchivePath']).read_text(encoding='utf-8'))
            self.assertEqual(archived, report)
            ns['tick'](0)
            self.assertEqual(len(ns['actor'].calls), 1)

    def test_archive_collision_preserves_existing_archive_and_rolling_report(self):
        with tempfile.TemporaryDirectory(prefix='beholder_terminal_') as directory:
            path = Path(directory)/'report.json'
            archive = path.with_name('report_Archive_collision.json')
            path.write_text('old rolling', encoding='utf-8')
            archive.write_text('old archive', encoding='utf-8')
            ns = extracted_namespace(path)
            ns['uuid'] = SimpleNamespace(uuid4=lambda: SimpleNamespace(hex='collision'))
            with self.assertRaises(FileExistsError):
                ns['write_terminal_report'](path, dict(running=False, passed=False))
            self.assertEqual(path.read_text(encoding='utf-8'), 'old rolling')
            self.assertEqual(archive.read_text(encoding='utf-8'), 'old archive')

    def test_rolling_write_failure_leaves_terminal_archive(self):
        with tempfile.TemporaryDirectory(prefix='beholder_terminal_') as directory:
            path = Path(directory)/'report.json'
            ns = extracted_namespace(path)
            report = dict(running=False, passed=False, error='original')
            with patch.object(Path, 'write_text', side_effect=OSError('rolling unavailable')):
                with self.assertRaises(OSError):
                    ns['write_terminal_report'](path, report)
            self.assertEqual(json.loads(Path(report['terminalArchivePath']).read_text(encoding='utf-8')), report)

    def test_original_failure_is_primary_when_persistence_also_fails(self):
        with tempfile.TemporaryDirectory(prefix='beholder_terminal_') as directory:
            removed = []
            ns = extracted_namespace(Path(directory)/'report.json', removed.append)
            persistence = OSError('disk unavailable')

            def failed_writer(*args):
                raise persistence

            ns['write_terminal_report'] = failed_writer
            original = AssertionError('observer fault')
            with self.assertRaises(AssertionError) as caught:
                ns['finish'](original)
            self.assertIs(caught.exception, original)
            self.assertIs(caught.exception.__cause__, persistence)
            self.assertEqual(removed, ['fake_callback'])
            self.assertEqual(len(ns['actor'].calls), 1)
            with self.assertRaisesRegex(RuntimeError, 'already started'):
                ns['finish'](original)
            self.assertEqual(len(ns['actor'].calls), 1)

    def test_unregister_failure_is_archived_and_retained_tick_is_inert(self):
        with tempfile.TemporaryDirectory(prefix='beholder_terminal_') as directory:
            path = Path(directory)/'report.json'

            def failed_unregister(handle):
                raise RuntimeError('detach unavailable')

            ns = extracted_namespace(path, failed_unregister)
            ns['finish']()
            report = json.loads(path.read_text(encoding='utf-8'))
            self.assertFalse(report['passed'])
            self.assertFalse(report['callbackUnregistered'])
            self.assertEqual(report['finishErrors'][0]['phase'], 'unregister_callback')
            self.assertIn('detach unavailable', report['error'])
            # No native cancellation is authorized just by teardown failure.
            self.assertEqual(ns['actor'].calls, [])
            del ns['actor']
            ns['tick'](0)  # Must return before even accessing the absent actor.
            self.assertEqual(len(list(path.parent.glob('*_Archive_*.json'))), 1)

    def test_nonfinite_or_running_report_is_not_persisted(self):
        with tempfile.TemporaryDirectory(prefix='beholder_terminal_') as directory:
            path = Path(directory)/'report.json'
            ns = extracted_namespace(path)
            for report in (dict(running=True, passed=False),
                           dict(running=False, passed=False, value=float('nan'))):
                with self.subTest(report=report), self.assertRaises(ValueError):
                    ns['write_terminal_report'](path, report)
            self.assertFalse(path.exists())
            self.assertEqual(list(path.parent.glob('*_Archive_*.json')), [])
