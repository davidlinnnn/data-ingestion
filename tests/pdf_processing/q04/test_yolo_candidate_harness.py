"""Cancellation-marker regression for the next YOLO candidate harness."""

import unittest

from candidate.yolo_lifecycle import CancellationObservedRunMixin


class FakeRun:
    def __init__(self, cancel):
        self.cancel = cancel

    async def cancel_owned(self, handle):
        return await self.cancel(handle)


class CandidateRun(CancellationObservedRunMixin, FakeRun):
    pass


class CandidateCancellationHarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_marker_wraps_the_callback_that_actually_cancels(self):
        order = []

        def observe(label, **details):
            order.append((label, details["meaning"]))

        async def cancel(_handle):
            order.append(("base_cancel", "called"))

        run = CandidateRun(cancel, observe_cancel=observe)
        await run.cancel_owned(object())
        self.assertEqual(
            [label for label, _ in order],
            ["cancel_requested", "base_cancel", "cancel_completed"],
        )

    async def test_marker_failure_never_skips_owned_cancel(self):
        cancelled = []

        def observe(label, **_details):
            if label == "cancel_requested":
                raise RuntimeError("synthetic collector failure")

        async def cancel(handle):
            cancelled.append(handle)

        handle = object()
        run = CandidateRun(cancel, observe_cancel=observe)
        await run.cancel_owned(handle)
        self.assertEqual(cancelled, [handle])
        self.assertEqual(run.cancel_observation_errors[0]["label"], "cancel_requested")


if __name__ == "__main__":
    unittest.main()
