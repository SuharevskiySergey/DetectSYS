"""Local facade/evidence draft with targeted synthetic standalone coverage.

No Unreal imports, numeric dispatch, capture, actuator, ownership or real stop.
Caller-supplied evidence is not authenticated engine evidence.
"""
from beholder_dogleg_pose_receipt import PoseReceiptLedger
from beholder_dogleg_sample_adapter import DoglegSamplePipeline


class DoglegSampleSession:
    """Serialize local calculation -> proposal -> supplied evidence comparison.

    Callers must not separately advance the bound pipeline/ledger. This wrapper
    is not a thread lock or a native ownership mechanism. No adapter is created.
    """
    def __init__(self, job, baseline, tolerances=None):
        self._pipeline = DoglegSamplePipeline(job)
        self._ledger = PoseReceiptLedger(self._pipeline, baseline, tolerances)
        self._state = 'idle'
        self._held_reason = None
        self._request = None
        self._proposal = None

    @property
    def state(self):
        return self._state

    @property
    def held_reason(self):
        return self._held_reason

    def hold(self, reason):
        """Sticky local invalidation only; never a physical hold/Cancel."""
        if not isinstance(reason, str) or not reason:
            raise ValueError('Nonempty session hold reason required')
        if self._held_reason is None:
            self._held_reason = reason
        self._state = 'held'
        self._request = self._proposal = None
        self._ledger.hold(self._held_reason)

    def _require(self, state):
        if (self._state != state or self._held_reason is not None
                or self._pipeline.held_reason is not None
                or self._ledger.held_reason is not None):
            raise ValueError('Session is held or the operation is out of order')

    def begin_sample(self, segment_index, elapsed_seconds):
        try:
            self._require('idle')
            if self._ledger.pending_proposal is not None:
                raise ValueError('Supplied pose evidence is still pending')
            self._request = self._pipeline.begin_sample(segment_index, elapsed_seconds)
            self._state = 'awaiting_numeric'
            return self._request
        except Exception as exc:
            self.hold('session_begin: '+type(exc).__name__+': '+str(exc))
            raise

    def accept_numeric(self, request_id, result):
        """Compare a supplied facade response; never execute the request."""
        try:
            self._require('awaiting_numeric')
            if self._request is not self._pipeline.pending_request:
                raise ValueError('Bound numeric request changed')
            sample = self._pipeline.accept_sample(request_id, result)
            self._request = None
            self._state = 'awaiting_before_evidence'
            return sample
        except Exception as exc:
            self.hold('session_numeric: '+type(exc).__name__+': '+str(exc))
            raise

    def propose(self, before):
        """Return DATA only; it is not an admitted application command."""
        try:
            self._require('awaiting_before_evidence')
            self._proposal = self._ledger.propose(before)
            self._state = 'awaiting_after_evidence'
            return self._proposal
        except Exception as exc:
            self.hold('session_proposal: '+type(exc).__name__+': '+str(exc))
            raise

    def compare_after(self, transaction_id, after):
        try:
            self._require('awaiting_after_evidence')
            if self._proposal is not self._ledger.pending_proposal:
                raise ValueError('Bound proposal changed')
            receipt = self._ledger.confirm(transaction_id, after)
            self._proposal = None
            self._state = 'idle'
            return receipt
        except Exception as exc:
            self.hold('session_after: '+type(exc).__name__+': '+str(exc))
            raise
