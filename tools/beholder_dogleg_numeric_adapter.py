"""Editor numeric adapter; limited real integration verified, no actuation.

No import-time Unreal access or calls. Construction requires an explicit opt-in
AFTER user permission; this flag itself is not a permission grant. No PIE,
actors, Tick, timers, compilation, asset writes or application integration.
"""
from dataclasses import dataclass

from beholder_dogleg_job import finite
from beholder_dogleg_job_contract import (
    CLOCK_BLUEPRINT, CLOCK_FUNCTION, CLOCK_INPUT_LAYOUT, CLOCK_OUTPUT_LAYOUT,
    TARGETS_BLUEPRINT, TARGETS_FUNCTION, TARGETS_INPUT_LAYOUT, TARGETS_OUTPUT_LAYOUT,
    SAMPLE_BLUEPRINT, SAMPLE_FUNCTION, SAMPLE_INPUT_LAYOUT, SAMPLE_OUTPUT_LAYOUT,
    REFLECTED_INPUT_NAMES)
from beholder_dogleg_pipeline import CalculationRequest, DoglegCalculationPipeline

FLOAT32_MAX = 3.4028234663852886e38


@dataclass(frozen=True)
class NumericFunctionSpec:
    kind: str
    blueprint_path: str
    function_name: str
    inputs: tuple[tuple[str, str], ...]
    outputs: tuple[tuple[str, str], ...]


_SPECS = (
    NumericFunctionSpec('clock', CLOCK_BLUEPRINT, CLOCK_FUNCTION, CLOCK_INPUT_LAYOUT, CLOCK_OUTPUT_LAYOUT),
    NumericFunctionSpec('targets', TARGETS_BLUEPRINT, TARGETS_FUNCTION, TARGETS_INPUT_LAYOUT, TARGETS_OUTPUT_LAYOUT))

_NAMED_BINDING_SPECS = _SPECS+(
    NumericFunctionSpec('sample', SAMPLE_BLUEPRINT, SAMPLE_FUNCTION, SAMPLE_INPUT_LAYOUT, SAMPLE_OUTPUT_LAYOUT),)


def typed_scalar(value, kind, name):
    if kind == 'bool':
        if type(value) is not bool:
            raise ValueError('Boolean output/input required: '+name)
        return value
    if kind != 'float' or not finite(value) or abs(value) > FLOAT32_MAX:
        raise ValueError('Finite float32-representable output/input required: '+name)
    # No bool coercion, clamping or substitution of reference values. Precision
    # conversion by the UE bridge remains unverified, particularly tiny spans.
    return float(value)


def named_numeric_kwargs(spec, arguments):
    """Encode only the three confirmed numeric signatures; no Unreal access.

    The two-function backend still admits only _SPECS, not the facade. Sharing
    this encoder does not expand its dispatch whitelist or authorize execution.
    """
    if type(spec) is not NumericFunctionSpec or spec not in _NAMED_BINDING_SPECS:
        raise ValueError('Unapproved reflected numeric signature')
    if type(arguments) is not tuple or len(arguments) != len(spec.inputs):
        raise ValueError('Exact declared numeric input tuple required')
    names = dict(REFLECTED_INPUT_NAMES)
    result = {'world_context': None}
    for (name, kind), value in zip(spec.inputs, arguments):
        result[names[name]] = typed_scalar(value, kind, name)
    return result


def decode_outputs(raw, spec):
    """Name an exact declared tuple/dict, rejecting missing/extra/bad values."""
    names = tuple(name for name, _kind in spec.outputs)
    if isinstance(raw, tuple):
        if len(raw) != len(names):
            raise ValueError('Unexpected Blueprint result tuple length')
        values = dict(zip(names, raw))
    elif isinstance(raw, dict):
        if set(raw) != set(names):
            raise ValueError('Unexpected named Blueprint output signature')
        values = dict(raw)
    else:
        raise ValueError('Expected exact tuple or named dict from the numeric function')
    return {name: typed_scalar(values[name], kind, name) for name,kind in spec.outputs}


class _EditorFunctionLibraryBackend:
    def __init__(self):
        # Lazy on purpose: merely importing this draft cannot touch the editor.
        import unreal
        self._unreal = unreal
        self._require_edit_mode()

    def _require_edit_mode(self):
        unreal = self._unreal
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor is None:
            raise RuntimeError('Editor subsystem unavailable; numeric calls are not allowed')
        if editor.get_game_world() is not None:
            raise RuntimeError('Numeric adapter is edit-mode only; PIE/simulation is not allowed')

    def call(self, spec, arguments, *, require_current_request):
        if spec not in _SPECS:
            raise ValueError('Unapproved numeric function specification')
        if not callable(require_current_request):
            raise TypeError('A bound request precondition is required')
        kwargs = named_numeric_kwargs(spec, arguments)
        self._require_edit_mode()
        unreal = self._unreal
        name = spec.blueprint_path.rsplit('/', 1)[-1]
        cls = unreal.load_class(None, spec.blueprint_path+'.'+name+'_C')
        if cls is None:
            raise RuntimeError('Compiled numeric library class is unavailable')
        default_object = unreal.get_default_object(cls)
        if not isinstance(default_object, unreal.BlueprintFunctionLibrary):
            raise TypeError('Only Blueprint Function Libraries may be called')
        # Named binding and limited adapter cycles were separately verified.
        # Further calls still need permission; no motion readiness is implied.
        self._require_edit_mode()
        require_current_request()
        raw = default_object.call_method(spec.function_name, args=(), kwargs=kwargs)
        # Reject the receipt if the editor entered a game world during a call.
        # This cannot undo a call and is not an atomic editor-state lock.
        self._require_edit_mode()
        require_current_request()
        return raw


class NumericBlueprintAdapter:
    """Execute ONE pending numeric request only after a separate explicit opt-in.

    Whitelisting is not an Unreal sandbox: the installed library bodies must
    remain the agreed state-free numeric graphs. No runtime readiness is granted.
    """
    def __init__(self, pipeline, *, allow_numeric_calls=False):
        if allow_numeric_calls is not True:
            raise PermissionError('Numeric function calls require separate user permission and explicit opt-in')
        if not isinstance(pipeline, DoglegCalculationPipeline):
            raise TypeError('A bound numeric pipeline is required')
        self._pipeline = pipeline
        self._enabled = False
        self._backend = None
        self._dispatching = False
        try:
            self._backend = _EditorFunctionLibraryBackend()
            self._enabled = True
        except Exception as exc:
            self._pipeline.hold('numeric_adapter_setup: '+type(exc).__name__+': '+str(exc))
            raise

    @property
    def enabled(self):
        return self._enabled

    def close(self):
        # Local pending calculations are invalidated; there is no native motion
        # in this adapter and this is NOT a physical stop or controller Cancel.
        self._enabled, self._backend = False, None
        self._pipeline.hold('Numeric function-call adapter closed')

    def dispatch_pending(self):
        """No loop/auto-chain: clock returns a request, targets returns a sample."""
        dispatch_started = False
        try:
            if self._dispatching:
                raise RuntimeError('Re-entrant numeric dispatch is not allowed')
            if not self._enabled or self._backend is None:
                raise PermissionError('Numeric adapter is not enabled')
            self._dispatching = True
            dispatch_started = True
            request = self._pipeline.pending_request
            if not isinstance(request, CalculationRequest):
                raise ValueError('No pending numeric request')
            spec = next((s for s in _SPECS if s.kind == request.kind), None)
            if (spec is None or request.blueprint_path != spec.blueprint_path
                    or request.function_name != spec.function_name
                    or self._pipeline.state != 'awaiting_'+spec.kind):
                raise ValueError('Request is outside the two-function numeric contract')
            pairs = request.arguments
            values = dict(pairs)
            expected = {name for name,_kind in spec.inputs}
            if len(pairs) != len(expected) or set(values) != expected:
                raise ValueError('Missing, extra or duplicate numeric input names')
            arguments = tuple(typed_scalar(values[name], kind, name) for name,kind in spec.inputs)
            backend = self._backend

            def require_current_request():
                # Re-evaluated by the backend after class/CDO loading, directly
                # before the call and before accepting its answer. No lock or
                # actor ownership is implied by these synchronous checks.
                if (not self._enabled or self._backend is not backend
                        or self._pipeline.pending_request is not request
                        or self._pipeline.state != 'awaiting_'+spec.kind):
                    raise ValueError('Numeric request or adapter changed during dispatch')

            raw = backend.call(spec, arguments, require_current_request=require_current_request)
            require_current_request()
            result = decode_outputs(raw, spec)
            if spec.kind == 'clock':
                return self._pipeline.accept_clock(request.request_id, result)
            return self._pipeline.accept_targets(request.request_id, result)
        except Exception as exc:
            self._pipeline.hold('numeric_adapter: '+type(exc).__name__+': '+str(exc))
            raise
        finally:
            # A refused nested dispatch must not clear the outer call's guard.
            if dispatch_started:
                self._dispatching = False
