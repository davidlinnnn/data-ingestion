"""Harness seam for observing cancellation at the callback that owns it."""


class CancellationObservedRunMixin:
    """Emit measurement markers around the actual owned-cancel callback.

    Observation failure is retained for measurement review but never prevents
    owned-work cleanup. The wrapped ``Run`` remains the cancellation authority.
    """

    def __init__(self, *args, observe_cancel, **kwargs):
        super().__init__(*args, **kwargs)
        self.observe_cancel = observe_cancel
        self.cancel_observation_errors = []

    def _observe_cancel(self, label, meaning):
        try:
            self.observe_cancel(
                label,
                source="controller_callback",
                meaning=meaning,
            )
        except Exception as error:
            self.cancel_observation_errors.append(
                {"label": label, "type": type(error).__name__, "reason": str(error)}
            )

    async def cancel_owned(self, handle):
        self._observe_cancel(
            "cancel_requested",
            "owned_workflow_cancel_callback_invoked",
        )
        try:
            result = await super().cancel_owned(handle)
        except BaseException:
            self._observe_cancel(
                "cancel_failed",
                "owned_workflow_cancel_callback_raised",
            )
            raise
        self._observe_cancel(
            "cancel_completed",
            "owned_workflow_cancel_callback_returned",
        )
        return result
