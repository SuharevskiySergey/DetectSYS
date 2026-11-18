"""Numeric facade adapter with limited real integration coverage; no actuation.

No import-time Unreal access, auto-run, clocks, actor writes or motion admission.
The two-function protocol remains separate. No permission is granted here.
"""
from beholder_dogleg_job_contract import (
    SAMPLE_BLUEPRINT, SAMPLE_FUNCTION, SAMPLE_INPUT_LAYOUT, SAMPLE_OUTPUT_LAYOUT)
from beholder_dogleg_numeric_adapter import (
    NumericFunctionSpec, decode_outputs, typed_scalar, named_numeric_kwargs)
from beholder_dogleg_pipeline import CalculationRequest, DoglegCalculationPipeline


SAMPLE_SPEC = NumericFunctionSpec('sample', SAMPLE_BLUEPRINT, SAMPLE_FUNCTION,
                                  SAMPLE_INPUT_LAYOUT, SAMPLE_OUTPUT_LAYOUT)


class DoglegSamplePipeline(DoglegCalculationPipeline):
    """One facade request; reuse reference validators without extra UE calls.

    No intermediate clock/targets receipt or request is manufactured when
    accepting the combined response. No sample is published until both validate.
    """
    def begin_sample(self, segment_index, elapsed_seconds):
        try:
            clock = super().begin_sample(segment_index, elapsed_seconds)
            arguments = dict(clock.arguments)
            arguments.update({name: value for name, value in
                              self.job.target_arguments(0).items() if name != 'Phase'})
            self._pending = CalculationRequest(
                f'{self.session}:{self._sequence}:sample', 'sample',
                SAMPLE_BLUEPRINT, SAMPLE_FUNCTION,
                tuple((name, arguments[name]) for name, _kind in SAMPLE_INPUT_LAYOUT))
            self.state = 'awaiting_sample'
            return self._pending
        except Exception as exc:
            self.hold('sample_request: '+type(exc).__name__+': '+str(exc))
            raise

    def accept_clock(self, request_id, result):
        self.hold('Separate clock receipts are not accepted by the facade pipeline')
        raise ValueError(self.held_reason)

    def accept_targets(self, request_id, result):
        self.hold('Separate targets receipts are not accepted by the facade pipeline')
        raise ValueError(self.held_reason)

    def accept_sample(self, request_id, result):
        try:
            self._expect(request_id, 'sample')
            result = decode_outputs(result, SAMPLE_SPEC)
            candidate = self._validated_clock_candidate(result)
            sample = self._validated_target_sample(request_id, result, candidate)
            return self._publish_sample(sample)
        except Exception as exc:
            self.hold('sample_receipt: '+type(exc).__name__+': '+str(exc))
            raise


class NumericSampleAdapter:
    """Draft, disabled by default; one facade call per explicit dispatch.

    Named binding and limited real numeric cycles were separately verified.
    Extreme UE precision and native-application cases are still open.
    No fallback to two calls or guessed context arguments is attempted.
    """
    def __init__(self, pipeline, *, allow_numeric_calls=False):
        if allow_numeric_calls is not True:
            raise PermissionError('Separate user permission and explicit numeric opt-in required')
        if not isinstance(pipeline, DoglegSamplePipeline):
            raise TypeError('A facade-specific numeric pipeline is required')
        self._pipeline = pipeline
        self._enabled = False
        self._unreal = None
        self._dispatching = False
        try:
            import unreal
            self._unreal = unreal
            self._require_edit_mode()
            self._enabled = True
        except Exception as exc:
            self._pipeline.hold('sample_adapter_setup: '+type(exc).__name__+': '+str(exc))
            raise

    @property
    def enabled(self):
        return self._enabled

    def _require_edit_mode(self):
        unreal = self._unreal
        if unreal is None:
            raise PermissionError('Numeric sample adapter has no editor backend')
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor is None:
            raise RuntimeError('Editor subsystem unavailable; numeric sample calls are not allowed')
        if editor.get_game_world() is not None:
            raise RuntimeError('PIE/simulation is not allowed by the numeric sample adapter')

    def close(self):
        self._enabled, self._unreal = False, None
        self._pipeline.hold('Numeric sample adapter closed; local hold only')

    def dispatch_pending(self):
        dispatch_started = False
        try:
            if self._dispatching:
                raise RuntimeError('Re-entrant facade dispatch is not allowed')
            if not self._enabled or self._unreal is None:
                raise PermissionError('Numeric sample adapter is disabled')
            self._dispatching = True
            dispatch_started = True
            request = self._pipeline.pending_request
            if (not isinstance(request, CalculationRequest) or request.kind != 'sample'
                    or request.blueprint_path != SAMPLE_BLUEPRINT
                    or request.function_name != SAMPLE_FUNCTION
                    or self._pipeline.state != 'awaiting_sample'):
                raise ValueError('No matching facade request is pending')
            values = dict(request.arguments)
            if (len(request.arguments) != len(SAMPLE_INPUT_LAYOUT)
                    or set(values) != {name for name, _kind in SAMPLE_INPUT_LAYOUT}):
                raise ValueError('Missing, extra or duplicate facade input names')
            arguments = tuple(typed_scalar(values[name], kind, name)
                              for name, kind in SAMPLE_INPUT_LAYOUT)
            kwargs = named_numeric_kwargs(SAMPLE_SPEC, arguments)
            self._require_edit_mode()
            unreal = self._unreal
            name = SAMPLE_BLUEPRINT.rsplit('/', 1)[-1]
            cls = unreal.load_class(None, SAMPLE_BLUEPRINT+'.'+name+'_C')
            if cls is None:
                raise RuntimeError('Compiled facade class is unavailable')
            library = unreal.get_default_object(cls)
            if not isinstance(library, unreal.BlueprintFunctionLibrary):
                raise TypeError('Facade must be a Blueprint Function Library')
            self._require_edit_mode()
            if (not self._enabled or self._unreal is not unreal
                    or self._pipeline.pending_request is not request
                    or self._pipeline.state != 'awaiting_sample'):
                raise ValueError('Facade request or adapter changed while loading the library')
            raw = library.call_method(SAMPLE_FUNCTION, args=(), kwargs=kwargs)
            self._require_edit_mode()
            if (not self._enabled or self._unreal is not unreal
                    or self._pipeline.pending_request is not request
                    or self._pipeline.state != 'awaiting_sample'):
                raise ValueError('Facade request or adapter changed during the call')
            return self._pipeline.accept_sample(request.request_id, decode_outputs(raw, SAMPLE_SPEC))
        except Exception as exc:
            self._pipeline.hold('sample_adapter: '+type(exc).__name__+': '+str(exc))
            raise
        finally:
            if dispatch_started:
                self._dispatching = False
