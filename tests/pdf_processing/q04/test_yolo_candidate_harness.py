"""Cancellation-marker regression for the next YOLO candidate harness."""

import importlib.util
from pathlib import Path
import sys
import types
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

    async def test_actual_candidate_adapter_wraps_real_run_seam(self):
        order = []

        class BaseRun:
            def __init__(self, *args, **kwargs):
                pass

            async def cancel_owned(self, _handle):
                order.append("base_cancel")

            async def guard(self):
                order.append("base_guard")
                return {"ok": True}

        class Collector:
            def observe(self, label, **_details):
                order.append(label)

            def require_healthy(self):
                order.append("healthy")

        path = Path(__file__).parent / "candidate/yolo_candidate_measure.py"
        spec = importlib.util.spec_from_file_location("candidate_measure_test", path)
        module = importlib.util.module_from_spec(spec)
        previous = sys.modules.get("q04_runtime")
        sys.modules["q04_runtime"] = types.SimpleNamespace(Run=BaseRun)
        try:
            spec.loader.exec_module(module)
        finally:
            if previous is None:
                del sys.modules["q04_runtime"]
            else:
                sys.modules["q04_runtime"] = previous

        run = module.AttributedCandidateRun(collector=Collector())
        await run.guard()
        await run.cancel_owned(object())
        self.assertEqual(
            order,
            [
                "healthy", "base_guard", "healthy",
                "cancel_requested", "base_cancel", "cancel_completed",
            ],
        )


if __name__ == "__main__":
    unittest.main()
