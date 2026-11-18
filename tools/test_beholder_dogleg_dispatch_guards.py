"""Standalone-tested adapter guards with fake backends; no Unreal calls."""
from types import SimpleNamespace
import unittest

from beholder_dogleg_job import prepare_job
from beholder_dogleg_numeric_adapter import NumericBlueprintAdapter
from beholder_dogleg_pipeline import DoglegCalculationPipeline
from beholder_dogleg_sample_adapter import DoglegSamplePipeline, NumericSampleAdapter


def two_function_adapter():
    # Bypass the opt-in constructor ONLY for an isolated fake-backend fixture.
    # This never authorizes or creates an actual editor backend.
    pipeline = DoglegCalculationPipeline(prepare_job(half_duration=2))
    pipeline.begin_sample(0, 0)
    adapter = NumericBlueprintAdapter.__new__(NumericBlueprintAdapter)
    adapter._pipeline, adapter._enabled, adapter._dispatching = pipeline, True, False
    return adapter, pipeline


class DispatchGuardTests(unittest.TestCase):
    def test_two_function_reentry_holds_without_clearing_outer_guard(self):
        adapter, pipeline = two_function_adapter()
        observed = []

        def call(spec, arguments, *, require_current_request):
            with self.assertRaisesRegex(RuntimeError, 'Re-entrant'):
                adapter.dispatch_pending()
            observed.append(adapter._dispatching)
            # Model the real backend's final pre-call predicate after loading.
            require_current_request()
            self.fail('Held request reached fake library execution')

        adapter._backend = SimpleNamespace(call=call)
        with self.assertRaisesRegex(ValueError, 'changed during dispatch'):
            adapter.dispatch_pending()
        self.assertEqual(observed, [True])
        self.assertFalse(adapter._dispatching)
        self.assertEqual(pipeline.state, 'held')
        self.assertIsNone(pipeline.pending_request)

    def test_two_function_changed_request_is_rejected_before_fake_execution(self):
        adapter, pipeline = two_function_adapter()

        def call(spec, arguments, *, require_current_request):
            pipeline.hold('changed during fake load')
            require_current_request()
            self.fail('Changed request reached fake library execution')

        adapter._backend = SimpleNamespace(call=call)
        with self.assertRaisesRegex(ValueError, 'changed during dispatch'):
            adapter.dispatch_pending()
        self.assertFalse(adapter._dispatching)
        self.assertEqual(pipeline.held_reason, 'changed during fake load')

    def test_two_function_exception_clears_guard_but_keeps_pipeline_held(self):
        adapter, pipeline = two_function_adapter()
        original = RuntimeError('fake backend failure')

        def call(spec, arguments, *, require_current_request):
            require_current_request()
            raise original

        adapter._backend = SimpleNamespace(call=call)
        with self.assertRaises(RuntimeError) as caught:
            adapter.dispatch_pending()
        self.assertIs(caught.exception, original)
        self.assertFalse(adapter._dispatching)
        self.assertEqual(pipeline.state, 'held')
        self.assertIsNone(pipeline.numeric_sample)

    def test_facade_reentry_during_load_does_not_execute_library(self):
        pipeline = DoglegSamplePipeline(prepare_job(half_duration=2))
        pipeline.begin_sample(0, 0)
        adapter = NumericSampleAdapter.__new__(NumericSampleAdapter)
        adapter._pipeline, adapter._enabled, adapter._dispatching = pipeline, True, False
        calls, guards = [], []

        class FakeLibrary:
            def call_method(self, *arguments):
                calls.append(arguments)
                raise AssertionError('Unexpected fake library execution')

        def load_class(*arguments):
            with self.assertRaisesRegex(RuntimeError, 'Re-entrant'):
                adapter.dispatch_pending()
            guards.append(adapter._dispatching)
            return FakeLibrary

        # Python-only object with the minimal API names the draft expects.
        adapter._unreal = SimpleNamespace(
            UnrealEditorSubsystem=object,
            get_editor_subsystem=lambda kind: SimpleNamespace(get_game_world=lambda: None),
            BlueprintFunctionLibrary=FakeLibrary,
            load_class=load_class, get_default_object=lambda cls: cls())
        with self.assertRaisesRegex(ValueError, 'changed while loading'):
            adapter.dispatch_pending()
        self.assertEqual(calls, [])
        self.assertEqual(guards, [True])
        self.assertFalse(adapter._dispatching)
        self.assertEqual(pipeline.state, 'held')
