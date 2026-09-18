"""Offline fake-client tests for Q04 workflow cleanup ownership."""

import json
from pathlib import Path
import tempfile
import unittest

from sentinel.cleanup import cleanup_workflows


class FakeNotFound(Exception):
    pass


class Status:
    def __init__(self, name):
        self.name = name


class Description:
    def __init__(self, name):
        self.status = Status(name)


class History:
    def __init__(self, workflow_id):
        self.workflow_id = workflow_id

    def to_json(self):
        return json.dumps({"workflow_id": self.workflow_id})


class Handle:
    def __init__(self, workflow_id, status="COMPLETED", error=None):
        self.workflow_id = workflow_id
        self.status = status
        self.error = error
        self.cancelled = False
        self.terminated = False

    async def describe(self):
        if self.error:
            raise self.error
        return Description(self.status)

    async def cancel(self):
        self.cancelled = True
        self.status = "CANCELED"

    async def result(self):
        return None

    async def terminate(self, reason):
        self.terminated = True
        self.status = "TERMINATED"

    async def fetch_history(self):
        if self.error:
            raise self.error
        return History(self.workflow_id)


class Summary:
    def __init__(self, workflow_id):
        self.id = workflow_id


class Client:
    def __init__(self, handles):
        self.handles = handles

    def get_workflow_handle(self, workflow_id):
        return self.handles[workflow_id]

    def list_workflows(self, query=None):
        async def rows():
            for workflow_id, handle in self.handles.items():
                if query and handle.status != "RUNNING":
                    continue
                yield Summary(workflow_id)

        return rows()


def record(root: Path, phase: str, workflow_id: str, name="workflow.json"):
    directory = root / "state" / phase / workflow_id
    directory.mkdir(parents=True)
    value = {"workflow_id": workflow_id}
    if name == "workflow-intent.json":
        value.update(phase=phase, trial=workflow_id)
    (directory / name).write_text(json.dumps(value) + "\n")


class CleanupWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def run_cleanup(self, root, handles):
        evidence = root / "evidence"
        evidence.mkdir()
        report: dict = {"workflows": []}
        errors: list = []
        await cleanup_workflows(
            Client(handles),
            root,
            "run",
            "current",
            evidence,
            report,
            errors,
            not_found=lambda error: isinstance(error, FakeNotFound),
        )
        return report, errors

    async def test_stale_historical_not_found_is_audited_without_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record(root, "old-phase", "run-old")
            report, errors = await self.run_cleanup(
                root, {"run-old": Handle("run-old", error=FakeNotFound())}
            )
        self.assertEqual(errors, [])
        self.assertEqual(report["historical_missing"], ["run-old"])

    async def test_exact_current_running_workflow_is_cancelled_and_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record(root, "current", "run-current")
            handle = Handle("run-current", status="RUNNING")
            report, errors = await self.run_cleanup(root, {"run-current": handle})
            histories = list((root / "evidence").glob("*.history.json"))
        self.assertEqual(errors, [])
        self.assertTrue(handle.cancelled)
        self.assertFalse(handle.terminated)
        self.assertEqual(report["workflows"][0]["scope"], "current")
        self.assertEqual(len(histories), 1)

    async def test_submit_record_gap_uses_exact_intent_and_is_cancelled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record(root, "current", "run-gap", "workflow-intent.json")
            handle = Handle("run-gap", status="RUNNING")
            report, errors = await self.run_cleanup(root, {"run-gap": handle})
        self.assertEqual(errors, [])
        self.assertTrue(handle.cancelled)
        self.assertEqual(report["workflow_ownership"]["current_recorded"], ["run-gap"])

    async def test_unregistered_running_workflow_is_reported_without_signalling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            handle = Handle("run-unrecorded", status="RUNNING")
            report, errors = await self.run_cleanup(root, {"run-unrecorded": handle})
        self.assertFalse(handle.cancelled)
        self.assertEqual(
            report["unexpected_active_workflows"],
            [
                {
                    "workflow_id": "run-unrecorded",
                    "source": "unregistered_unexpected",
                }
            ],
        )
        self.assertIn({"unexpected_active_workflow": "run-unrecorded"}, errors)
        self.assertIn({"running_after_cleanup": ["run-unrecorded"]}, errors)

    async def test_unexpected_running_history_is_reported_without_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record(root, "old-phase", "run-old")
            handle = Handle("run-old", status="RUNNING")
            report, errors = await self.run_cleanup(root, {"run-old": handle})
        self.assertFalse(handle.cancelled)
        self.assertEqual(
            report["unexpected_active_workflows"],
            [{"workflow_id": "run-old", "source": "historical_record"}],
        )
        self.assertIn({"unexpected_active_workflow": "run-old"}, errors)

    async def test_transport_error_that_says_not_found_is_not_swallowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record(root, "old-phase", "run-old")
            report, errors = await self.run_cleanup(
                root, {"run-old": Handle("run-old", error=OSError("not found"))}
            )
        self.assertEqual(report["historical_missing"], [])
        self.assertEqual(
            errors, [{"workflow": "run-old", "error": "not found"}]
        )

    async def test_current_owned_not_found_is_never_treated_as_stale_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record(root, "current", "run-current")
            report, errors = await self.run_cleanup(
                root, {"run-current": Handle("run-current", error=FakeNotFound())}
            )
        self.assertEqual(report["historical_missing"], [])
        self.assertEqual(errors, [{"current_owned_missing": "run-current"}])

    async def test_intent_phase_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record(root, "current", "run-current", "workflow-intent.json")
            path = root / "state/current/run-current/workflow-intent.json"
            value = json.loads(path.read_text())
            value["phase"] = "different-phase"
            path.write_text(json.dumps(value) + "\n")
            handle = Handle("run-current", status="RUNNING")
            report, errors = await self.run_cleanup(
                root, {"run-current": handle}
            )
        self.assertFalse(handle.cancelled)
        self.assertEqual(report["workflow_ownership"]["current_recorded"], [])
        self.assertEqual(
            report["workflow_ownership"]["invalid_unowned"], ["run-current"]
        )
        self.assertEqual(
            report["unexpected_active_workflows"],
            [
                {
                    "workflow_id": "run-current",
                    "source": "invalid_ownership",
                }
            ],
        )
        self.assertEqual(
            errors[0]["workflow_ownership_invalid"][0]["reason"],
            "phase_or_trial_mismatch",
        )

    async def test_foreign_run_is_ignored_by_discovery_and_never_signalled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = Handle("run-current", status="RUNNING")
            foreign = Handle("other-running", status="RUNNING")
            record(root, "current", "run-current")
            report, errors = await self.run_cleanup(
                root, {"run-current": current, "other-running": foreign}
            )
        self.assertEqual(errors, [])
        self.assertTrue(current.cancelled)
        self.assertFalse(foreign.cancelled)
        self.assertEqual(report["workflow_ownership"]["discovered"], ["run-current"])


if __name__ == "__main__":
    unittest.main()
