"""Standalone-tested named-binding migration with fake Python-only APIs."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from beholder_dogleg_job import prepare_job
from beholder_dogleg_numeric_adapter import (
    _SPECS, _EditorFunctionLibraryBackend, named_numeric_kwargs)
from beholder_dogleg_sample_adapter import SAMPLE_SPEC, DoglegSamplePipeline, NumericSampleAdapter


CLOCK_ARGS = (0.0, 2.0, 0.0, 1.0, False)
CLOCK_KWARGS = dict(world_context=None, segment_elapsed_seconds=0.0,
                    segment_duration_seconds=2.0, phase_start=0.0, phase_end=1.0,
                    returning=False)


def fake_editor_api(library):
    return SimpleNamespace(
        UnrealEditorSubsystem=object, BlueprintFunctionLibrary=type(library),
        get_editor_subsystem=lambda kind: SimpleNamespace(get_game_world=lambda: None),
        load_class=lambda *args: type(library), get_default_object=lambda cls: library)


class NamedBindingTests(unittest.TestCase):
    def test_confirmed_clock_targets_and_facade_input_names(self):
        self.assertEqual(named_numeric_kwargs(_SPECS[0], CLOCK_ARGS), CLOCK_KWARGS)
        targets = named_numeric_kwargs(_SPECS[1], (0.5, 0.25, -1.0, True))
        self.assertEqual(targets, dict(world_context=None, base_extension=0.5,
                                       phase=0.25, amplitude_degrees=-1.0, use_yaw=True))
        facade = named_numeric_kwargs(SAMPLE_SPEC, CLOCK_ARGS+(0.5, -1.0, True))
        self.assertEqual(facade, dict(CLOCK_KWARGS, base_extension=0.5,
                                      amplitude_degrees=-1.0, use_yaw=True))
        self.assertNotIn('phase', facade)

    def test_unknown_signature_wrong_shape_types_and_backend_whitelist_rejected(self):
        for spec, arguments in ((replace(_SPECS[0], function_name='OtherFunction'), CLOCK_ARGS),
                                (_SPECS[0], CLOCK_ARGS[:-1]),
                                (_SPECS[0], list(CLOCK_ARGS)),
                                (_SPECS[0], CLOCK_ARGS[:-1]+(0,)),
                                (_SPECS[0], (True,)+CLOCK_ARGS[1:])):
            with self.subTest(function=spec.function_name), self.assertRaises(ValueError):
                named_numeric_kwargs(spec, arguments)
        backend = _EditorFunctionLibraryBackend.__new__(_EditorFunctionLibraryBackend)
        # Encoder supports facade, but the two-function backend must NOT.
        with self.assertRaisesRegex(ValueError, 'Unapproved'):
            backend.call(SAMPLE_SPEC, CLOCK_ARGS+(0.5, 1.0, False), require_current_request=lambda: None)

    def test_two_function_backend_uses_named_arguments_and_keeps_preconditions(self):
        calls, preconditions = [], []
        raw = (True, False, 0.0, 0.0, 0.0, False)

        class FakeLibrary:
            def call_method(self, name, *, args, kwargs):
                calls.append((name, args, kwargs))
                return raw

        backend = _EditorFunctionLibraryBackend.__new__(_EditorFunctionLibraryBackend)
        backend._unreal = fake_editor_api(FakeLibrary())
        result = backend.call(_SPECS[0], CLOCK_ARGS,
                              require_current_request=lambda: preconditions.append(True))
        self.assertIs(result, raw)
        self.assertEqual(calls, [('EvaluateDoglegSegment', (), CLOCK_KWARGS)])
        self.assertEqual(len(preconditions), 2)

    def test_facade_dispatch_uses_named_arguments_and_preserves_sample_id(self):
        job = prepare_job(half_duration=2)
        pipeline = DoglegSamplePipeline(job)
        request = pipeline.begin_sample(0, 0)
        calls = []
        # Exact synthetic zero-phase output layout: 6 clock fields, extension,
        # 10 stages and 18 joint values. Not a real Blueprint observation.
        raw = (True, False, 0.0, 0.0, 0.0, False, 0.5)+(1.0,)*5+(0.0,)*5+(0.0,)*18

        class FakeLibrary:
            def call_method(self, name, *, args, kwargs):
                calls.append((name, args, kwargs))
                return raw

        adapter = NumericSampleAdapter.__new__(NumericSampleAdapter)
        adapter._pipeline, adapter._enabled, adapter._dispatching = pipeline, True, False
        adapter._unreal = fake_editor_api(FakeLibrary())
        sample = adapter.dispatch_pending()
        self.assertEqual(calls, [('CalculateDoglegSample', (),
                                  dict(CLOCK_KWARGS, base_extension=0.5,
                                       amplitude_degrees=1.0, use_yaw=True))])
        self.assertEqual(sample.sample_id, request.request_id)
        self.assertEqual(pipeline.state, 'idle')
        self.assertFalse(adapter._dispatching)
        self.assertFalse(sample.to_dict()['motionAuthorized'])
