"""Offline fake-client tests for Q04 workflow cleanup ownership."""

import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from sentinel.cleanup import cleanup_processes, cleanup_workflows


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


def record(
    root: Path,
    phase: str,
    workflow_id: str,
    name="workflow.json",
    trial=None,
):
    trial = workflow_id if trial is None else trial
    directory = root / "state" / phase / trial
    directory.mkdir(parents=True, exist_ok=True)
    value = {"workflow_id": workflow_id}
    if name == "workflow-intent.json":
        value.update(phase=phase, trial=trial)
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

    async def test_same_id_for_intent_and_record_in_one_trial_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record(root, "current", "run-current", "workflow-intent.json")
            record(root, "current", "run-current", "workflow.json")
            handle = Handle("run-current", status="RUNNING")
            report, errors = await self.run_cleanup(root, {"run-current": handle})
        self.assertEqual(errors, [])
        self.assertTrue(handle.cancelled)
        self.assertEqual(report["workflow_ownership"]["invalid_unowned"], [])

    async def test_cross_owner_workflow_id_collision_never_mutates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record(root, "current", "run-collision", trial="fresh-09")
            record(root, "old-phase", "run-collision", trial="replay-09")
            handle = Handle("run-collision", status="RUNNING")
            report, errors = await self.run_cleanup(root, {"run-collision": handle})
        self.assertFalse(handle.cancelled)
        self.assertFalse(handle.terminated)
        self.assertEqual(report["workflow_ownership"]["current_recorded"], [])
        self.assertEqual(report["workflow_ownership"]["historical_recorded"], [])
        self.assertEqual(
            report["workflow_ownership"]["invalid_unowned"], ["run-collision"]
        )
        self.assertEqual(
            errors[0]["workflow_ownership_invalid"][0]["reason"],
            "workflow_id_owner_collision",
        )
        self.assertIn(
            {"unexpected_active_workflow": "run-collision"}, errors
        )


class FakeNoSuchProcess(Exception):
    pass


class FakeTimeoutExpired(Exception):
    pass


class FakeProcess:
    def __init__(self, pid, command, *, created=1.0, cwd="/experiment/code"):
        self.pid = pid
        self.command = list(command)
        self.created = created
        self.directory = cwd
        self.running = True
        self.signals = []
        self.child_processes = []
        self.parent_processes = []
        self.reuse_after_snapshot = False
        self.create_time_calls = 0
        self.wait_failures = 0
        self.ignore_soft_signals = False
        self.kill_sticks = False
        self.parents_disappear = False

    def create_time(self):
        self.create_time_calls += 1
        if self.reuse_after_snapshot and self.create_time_calls > 1:
            return self.created + 100
        return self.created

    def cmdline(self):
        return list(self.command)

    def cwd(self):
        return self.directory

    def is_running(self):
        return self.running

    def status(self):
        return "running" if self.running else "zombie"

    def send_signal(self, value):
        self.signals.append(value)
        if not self.ignore_soft_signals:
            self.running = False

    def terminate(self):
        self.signals.append("terminate")
        if not self.ignore_soft_signals:
            self.running = False

    def kill(self):
        self.signals.append("kill")
        if not self.kill_sticks:
            self.running = False

    def wait(self, timeout):
        if self.wait_failures:
            self.wait_failures -= 1
            raise FakeTimeoutExpired()
        self.running = False
        return 0

    def children(self, recursive=False):
        return list(self.child_processes)

    def parents(self):
        if self.parents_disappear:
            raise FakeNoSuchProcess(self.pid)
        return list(self.parent_processes)


class FakePsutil:
    STATUS_ZOMBIE = "zombie"
    NoSuchProcess = FakeNoSuchProcess
    TimeoutExpired = FakeTimeoutExpired

    def __init__(self, processes):
        self.processes = {process.pid: process for process in processes}

    def process_iter(self):
        return list(self.processes.values())

    def Process(self, pid):
        if pid not in self.processes:
            raise FakeNoSuchProcess(pid)
        return self.processes[pid]

    @staticmethod
    def wait_procs(processes, timeout):
        for process in processes:
            process.running = False
        return list(processes), []


def controller(root, phase, pid=10):
    return FakeProcess(
        pid,
        [
            "/experiment/.venv/bin/python",
            str(root / "acl_fresh_measure.py"),
            "--state",
            str(root / "state"),
            "--name",
            phase,
        ],
    )


def worker(root, phase, generation, pid, created=1.0):
    directory = root / "state" / phase / f"worker-{generation}"
    directory.mkdir(parents=True, exist_ok=True)
    config = root / "state" / phase / "config.json"
    config.write_text('{"frozen":true}\n')
    (directory / "ownership.json").write_text(
        json.dumps(
            {
                "pid": pid,
                "created": created,
                "generation": generation,
                "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            }
        )
    )
    process = FakeProcess(
        pid,
        [
            "/experiment/.venv/bin/python",
            str(root / "code/tests/pdf_processing/q04/worker.py"),
            "--config",
            str(root / "state" / phase / "config.json"),
            "--out",
            str(directory),
            "--generation",
            str(generation),
        ],
        created=created,
        cwd=str(root / "code"),
    )
    return process, directory


class CleanupProcessTests(unittest.IsolatedAsyncioTestCase):
    async def run_cleanup(self, root, processes):
        report = {}
        errors = []
        await cleanup_processes(
            FakePsutil(processes),
            root,
            "current",
            ("acl_fresh_measure.py",),
            report,
            errors,
        )
        return report, errors

    async def test_exact_current_processes_and_scratch_are_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current_controller = controller(root, "current")
            current_worker, worker_directory = worker(root, "current", 1, 20)
            parser = FakeProcess(
                21,
                ["python", "-m", "pdf_processing.warm_child"],
                created=2.0,
                cwd=str(root / "code"),
            )
            parser.parent_processes = [current_worker]
            current_worker.child_processes = [parser]
            scratch = worker_directory / "scratch"
            scratch.mkdir()
            report, errors = await self.run_cleanup(
                root, [current_controller, current_worker, parser]
            )
            scratch_exists = scratch.exists()
        self.assertEqual(errors, [])
        self.assertFalse(current_controller.running)
        self.assertFalse(current_worker.running)
        self.assertFalse(parser.running)
        self.assertFalse(scratch_exists)
        self.assertEqual(report["current_scratch_remaining"], [])

    async def test_historical_and_unowned_processes_and_scratch_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_controller = controller(root, "old-phase", pid=30)
            old_worker, old_directory = worker(root, "old-phase", 1, 31)
            old_parser = FakeProcess(
                32,
                ["python", "-m", "pdf_processing.warm_child"],
                cwd=str(root / "code"),
            )
            old_parser.parent_processes = [old_worker]
            old_worker.child_processes = [old_parser]
            ambiguous_controller = controller(root, "ignored", pid=33)
            ambiguous_controller.command = ambiguous_controller.command[:-2]
            unrecorded_worker = FakeProcess(
                34,
                [
                    "/experiment/.venv/bin/python",
                    str(root / "code/tests/pdf_processing/q04/worker.py"),
                    "--config",
                    str(root / "state/unrecorded/config.json"),
                    "--out",
                    str(root / "state/unrecorded/worker-1"),
                    "--generation",
                    "1",
                ],
                cwd=str(root / "code"),
            )
            old_scratch = old_directory / "scratch"
            old_scratch.mkdir()
            report, errors = await self.run_cleanup(
                root,
                [
                    old_controller,
                    old_worker,
                    old_parser,
                    ambiguous_controller,
                    unrecorded_worker,
                ],
            )
            old_scratch_exists = old_scratch.exists()
        self.assertTrue(old_controller.running)
        self.assertTrue(old_worker.running)
        self.assertTrue(old_parser.running)
        self.assertTrue(ambiguous_controller.running)
        self.assertTrue(unrecorded_worker.running)
        self.assertTrue(old_scratch_exists)
        self.assertEqual(old_controller.signals, [])
        self.assertEqual(old_worker.signals, [])
        self.assertEqual(old_parser.signals, [])
        self.assertEqual(ambiguous_controller.signals, [])
        self.assertEqual(unrecorded_worker.signals, [])
        self.assertEqual(report["historical_scratch_retained"], [str(old_scratch)])
        self.assertTrue(any("unexpected_active_process" in error for error in errors))

    async def test_pid_reuse_and_ambiguous_owner_are_never_signalled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reused, worker_directory = worker(root, "current", 1, 40, created=1.0)
            reused.created = 2.0
            scratch = worker_directory / "scratch"
            scratch.mkdir()
            report, errors = await self.run_cleanup(root, [reused])
            scratch_exists = scratch.exists()
        self.assertTrue(reused.running)
        self.assertEqual(reused.signals, [])
        self.assertTrue(scratch_exists)
        self.assertEqual(report["current_scratch_remaining"], [str(scratch)])
        self.assertTrue(any("process_ownership_invalid" in error for error in errors))

    async def test_controller_identity_change_before_signal_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reused = controller(root, "current", pid=50)
            reused.reuse_after_snapshot = True
            report, errors = await self.run_cleanup(root, [reused])
        self.assertTrue(reused.running)
        self.assertEqual(reused.signals, [])
        self.assertEqual(
            report["unexpected_active_processes"][0]["scope"],
            "current_ambiguous",
        )
        self.assertTrue(any("process_ownership_invalid" in error for error in errors))

    async def test_controller_forced_kill_is_waited_and_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            forced = controller(root, "current", pid=55)
            forced.ignore_soft_signals = True
            forced.wait_failures = 2
            report, errors = await self.run_cleanup(root, [forced])
        self.assertFalse(forced.running)
        self.assertEqual(forced.signals[-2:], ["terminate", "kill"])
        self.assertTrue(report["controllers"][0]["forced"])
        self.assertIn({"controller_forced": 55}, errors)

    async def test_child_exit_during_identity_probe_does_not_verify_scratch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current, worker_directory = worker(root, "current", 1, 56)
            child = FakeProcess(
                57,
                ["python", "-m", "pdf_processing.warm_child"],
                cwd=str(root / "code"),
            )
            child.parent_processes = [current]
            child.parents_disappear = True
            current.child_processes = [child]
            scratch = worker_directory / "scratch"
            scratch.mkdir()
            report, errors = await self.run_cleanup(root, [current, child])
            scratch_exists = scratch.exists()
        self.assertTrue(current.running)
        self.assertEqual(current.signals, [])
        self.assertTrue(scratch_exists)
        self.assertEqual(report["current_scratch_remaining"], [str(scratch)])
        self.assertTrue(any("worker_process_audit" in error for error in errors))

    async def test_absent_worker_with_live_reparented_parser_retains_scratch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, worker_directory = worker(root, "current", 1, 58)
            parser = FakeProcess(
                59,
                ["python", "-m", "pdf_processing.warm_child"],
                cwd=str(root / "code"),
            )
            scratch = worker_directory / "scratch"
            scratch.mkdir()
            report, errors = await self.run_cleanup(root, [parser])
            scratch_exists = scratch.exists()
        self.assertTrue(parser.running)
        self.assertEqual(parser.signals, [])
        self.assertTrue(scratch_exists)
        self.assertEqual(report["current_scratch_remaining"], [str(scratch)])
        self.assertEqual(report["workers"][0]["descendant_absence"], "unproven")
        self.assertTrue(
            any("worker_descendant_absence_unproven" in error for error in errors)
        )
        self.assertTrue(any("unexpected_active_process" in error for error in errors))

    async def test_zombie_worker_with_exact_stopped_proof_allows_scratch_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            zombie, worker_directory = worker(root, "current", 2, 61)
            zombie.running = False
            (worker_directory / "stopped.json").write_text(
                json.dumps(
                    {
                        "pid": 61,
                        "generation": 2,
                        "parser_absent": True,
                        "scratch_absent": False,
                    }
                )
            )
            scratch = worker_directory / "scratch"
            scratch.mkdir()
            report, errors = await self.run_cleanup(root, [zombie])
            scratch_exists = scratch.exists()
        self.assertEqual(errors, [])
        self.assertFalse(scratch_exists)
        self.assertEqual(report["current_scratch_remaining"], [])
        self.assertTrue(report["workers"][0]["stopped"]["parser_absent"])

    async def test_worker_recorded_by_two_phases_is_never_signalled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current, current_directory = worker(root, "current", 1, 60)
            _, historical_directory = worker(root, "old-phase", 1, 60)
            current_scratch = current_directory / "scratch"
            historical_scratch = historical_directory / "scratch"
            current_scratch.mkdir()
            historical_scratch.mkdir()
            report, errors = await self.run_cleanup(root, [current])
            current_scratch_exists = current_scratch.exists()
            historical_scratch_exists = historical_scratch.exists()
        self.assertTrue(current.running)
        self.assertEqual(current.signals, [])
        self.assertTrue(current_scratch_exists)
        self.assertTrue(historical_scratch_exists)
        self.assertEqual(
            report["current_scratch_remaining"], [str(current_scratch)]
        )
        self.assertTrue(any("process_ownership_invalid" in error for error in errors))

    async def test_duplicate_exact_current_controllers_are_never_signalled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = controller(root, "current", pid=70)
            second = controller(root, "current", pid=71)
            report, errors = await self.run_cleanup(root, [first, second])
        self.assertTrue(first.running)
        self.assertTrue(second.running)
        self.assertEqual(first.signals, [])
        self.assertEqual(second.signals, [])
        self.assertEqual(
            {row["scope"] for row in report["unexpected_active_processes"]},
            {"current_ambiguous_duplicate"},
        )
        self.assertEqual(
            sum("process_ownership_invalid" in error for error in errors), 2
        )

    async def test_current_phase_lookalike_entrypoint_is_reported_not_signalled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lookalike = controller(root, "current", pid=75)
            lookalike.command[1] = "/unowned" + lookalike.command[1]
            report, errors = await self.run_cleanup(root, [lookalike])
        self.assertTrue(lookalike.running)
        self.assertEqual(lookalike.signals, [])
        self.assertEqual(
            report["unexpected_active_processes"][0]["scope"],
            "unapproved_entrypoint",
        )
        self.assertTrue(any("process_ownership_invalid" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
