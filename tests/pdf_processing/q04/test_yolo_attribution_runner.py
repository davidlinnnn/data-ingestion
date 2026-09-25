"""Offline checks for the fresh-only YOLO attribution runner."""

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import sentinel.run_yolo_attribution_b as runner


REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "tests/pdf_processing/q04/preflight/yolo-attribution-b/OFFLINE-MANIFEST.json"


class YoloAttributionRunner(unittest.TestCase):
    def test_identity_is_exclusive_and_scope_is_fresh_only(self):
        self.assertEqual(runner.PHASE, "yolo-attribution-b")
        self.assertEqual(runner.PREFIX, "q04/yolo-attribution-20260918-b/")
        self.assertEqual(
            runner.OUT.as_posix(), "/private/tmp/q04-yolo-attribution-20260918-b"
        )
        self.assertEqual(runner.STATE["fixture"], "07")
        self.assertEqual(runner.STATE["modes"], ["fresh"])
        for path in runner.remote_absence_paths().values():
            self.assertIn("yolo-attribution", path)
            self.assertNotIn("yolo-matrix-20260918-a", path)

    def test_capacity_preserves_outer_per_case_guard_and_cleanup_budgets(self):
        capacity = runner.build_capacity(
            started_at=1000,
            owner="main session",
            approval_reference="future separate authorization",
        )
        self.assertEqual(capacity["proposed_window_seconds"], 1500)
        self.assertEqual(capacity["outer_observation_seconds"], 180)
        self.assertEqual(capacity["outer_continuous_seconds"], 60)
        self.assertEqual(capacity["outer_admission_available_bytes"], 4_831_838_208)
        self.assertEqual(capacity["admission_seconds"], 60)
        self.assertEqual(capacity["admission_available_bytes"], 3_221_225_472)
        self.assertEqual(capacity["minimum_work_seconds"], 825)
        self.assertEqual(capacity["cleanup_seconds"], 300)
        self.assertEqual(capacity["max_cgroup_bytes"], 4_294_967_296)
        self.assertEqual(capacity["max_full_psi"], 0)

    def test_runtime_argv_is_exact_fresh_only_and_shell_quotes_that_argv(self):
        argv = runner.build_measurement_argv("q04-test-run")
        self.assertEqual(argv[0], "/experiment/.venv/bin/python")
        self.assertEqual(
            argv[1],
            "/tmp/q04-yolo-attribution-20260918-b/runner-yolo-attribution-b/yolo_fresh_measure.py",
        )
        self.assertEqual(argv[argv.index("--name") + 1], "yolo-attribution-b")
        self.assertEqual(argv[argv.index("--expected-run-id") + 1], "q04-test-run")
        self.assertEqual(argv[argv.index("--expected-prefix") + 1], runner.PREFIX)
        self.assertEqual(argv[argv.index("--attribution-interval-seconds") + 1], "0.25")
        joined = " ".join(argv)
        self.assertNotIn("restored", joined)
        self.assertNotIn("replay", joined)
        self.assertNotIn("--phase matrix", joined)
        command = runner.build_runtime_command("q04-test-run")
        self.assertIn("--signal=INT --kill-after=180s 825s", command)
        self.assertIn("yolo_fresh_measure.py", command)
        self.assertIn("PYTHONSAFEPATH=1", command)
        self.assertIn("test ! -e", command)

    def test_historical_manifest_uses_retained_collector_not_later_lifecycle_source(self):
        sources = runner.staged_sources()
        self.assertEqual(
            set(sources),
            {
                "outer_admission.py",
                "acl_admission.py",
                "telemetry.py",
                "cleanup.py",
                "acl_resource_telemetry.py",
                "yolo_attribution_telemetry.py",
                "yolo_fresh_measure.py",
                "run_yolo_attribution_b.py",
            },
        )
        retained = json.loads(MANIFEST.read_text())
        observed = {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in sources.items()
        }
        historical = (
            REPO
            / "tests/pdf_processing/q04/preflight/yolo-attribution-b/retained/yolo_attribution_telemetry.py"
        )
        self.assertEqual(
            retained["staged_sources"]["yolo_attribution_telemetry.py"],
            hashlib.sha256(historical.read_bytes()).hexdigest(),
        )
        self.assertNotEqual(
            retained["staged_sources"]["yolo_attribution_telemetry.py"],
            observed["yolo_attribution_telemetry.py"],
        )
        unchanged = {
            name: digest
            for name, digest in observed.items()
            if name != "yolo_attribution_telemetry.py"
        }
        self.assertEqual(
            {
                name: digest
                for name, digest in retained["staged_sources"].items()
                if name != "yolo_attribution_telemetry.py"
            },
            unchanged,
        )
        self.assertFalse(retained["runtime_authorized"])

    def test_reviewed_manifest_rejects_altered_source_before_staging(self):
        sources = runner.staged_sources()
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "yolo_fresh_measure.py"
            altered.write_bytes(
                sources["yolo_fresh_measure.py"].read_bytes() + b"\n# altered\n"
            )
            sources["yolo_fresh_measure.py"] = altered
            with mock.patch.object(runner, "staged_sources", return_value=sources):
                with mock.patch.object(runner, "remote") as remote:
                    with self.assertRaisesRegex(RuntimeError, "differs from reviewed"):
                        runner.stage_admission_runner()
                    remote.assert_not_called()

    def test_release_write_failure_reaps_exact_reserved_identity(self):
        identity = {
            "coordinator_uid": runner.COORDINATOR_UID,
            "token": "token",
            "phase": runner.PHASE,
            "pid": 123,
            "start_ticks": 456,
            "lock_device_major": 0,
            "lock_device_minor": 28,
            "lock_inode": 789,
        }

        class Holder:
            returncode = None

            def poll(self):
                return self.returncode

        holder = Holder()
        reaped = []

        def reap():
            reaped.append(identity.copy())
            holder.returncode = 137

        with self.assertRaisesRegex(RuntimeError, "required fallback"):
            runner.release_reservation(
                holder,
                identity,
                release_writer=lambda: (_ for _ in ()).throw(OSError("write failed")),
                remote_reaper=reap,
                remote_verifier=lambda: {
                    "identity_alive": False,
                    "qualification_lock_held": False,
                },
            )
        self.assertEqual(reaped, [identity])

    def test_release_wait_failure_reaps_exact_reserved_identity(self):
        identity = {
            "coordinator_uid": runner.COORDINATOR_UID,
            "token": "token",
            "phase": runner.PHASE,
            "pid": 123,
            "start_ticks": 456,
            "lock_device_major": 0,
            "lock_device_minor": 28,
            "lock_inode": 789,
        }

        class Holder:
            returncode = None

            def poll(self):
                return self.returncode

            def wait(self, timeout):
                raise subprocess.TimeoutExpired("kubectl", timeout)

        holder = Holder()
        reaped = []

        def reap():
            reaped.append(identity.copy())
            holder.returncode = 137

        with self.assertRaisesRegex(RuntimeError, "required fallback"):
            runner.release_reservation(
                holder,
                identity,
                release_writer=lambda: None,
                remote_reaper=reap,
                remote_verifier=lambda: {
                    "identity_alive": False,
                    "qualification_lock_held": False,
                },
            )
        self.assertEqual(reaped, [identity])

    def test_lost_acquisition_acknowledgement_reconciles_token_bound_record(self):
        identity = {
            "coordinator_uid": runner.COORDINATOR_UID,
            "token": "token",
            "phase": runner.PHASE,
            "pid": 123,
            "start_ticks": 456,
            "lock_device_major": 0,
            "lock_device_minor": 28,
            "lock_inode": 789,
        }
        holder = object()
        calls = []

        result = runner.reconcile_reservation(
            holder,
            "token",
            identity=None,
            identity_reader=lambda token: (
                calls.append(("read", token)) or identity.copy()
            ),
            releaser=lambda actual_holder, actual_identity: calls.append(
                ("release", actual_holder, actual_identity)
            ),
        )

        self.assertEqual(result, identity)
        self.assertEqual(calls[0], ("read", "token"))
        self.assertEqual(calls[1], ("release", holder, identity))

    def test_reaper_error_still_stops_transport_and_verifies_lock(self):
        identity = {
            "coordinator_uid": runner.COORDINATOR_UID,
            "token": "token",
            "phase": runner.PHASE,
            "pid": 123,
            "start_ticks": 456,
            "lock_device_major": 0,
            "lock_device_minor": 28,
            "lock_inode": 789,
        }

        class Holder:
            returncode = None
            waits = 0
            terminated = False

            def poll(self):
                return self.returncode

            def wait(self, timeout):
                self.waits += 1
                if not self.terminated:
                    raise subprocess.TimeoutExpired("kubectl", timeout)
                self.returncode = -15
                return self.returncode

            def terminate(self):
                self.terminated = True

        holder = Holder()
        verified = []
        with self.assertRaisesRegex(RuntimeError, "identity_reap"):
            runner.release_reservation(
                holder,
                identity,
                release_writer=lambda: None,
                remote_reaper=lambda: (_ for _ in ()).throw(OSError("reap failed")),
                remote_verifier=lambda: (
                    verified.append(True)
                    or {
                        "identity_alive": False,
                        "qualification_lock_held": False,
                    }
                ),
            )
        self.assertTrue(holder.terminated)
        self.assertEqual(verified, [True])

    def test_launch_budget_requires_workload_and_cleanup_reserve(self):
        runner.require_launch_budget(1125, monotonic=lambda: 0)
        with self.assertRaisesRegex(RuntimeError, "insufficient workload"):
            runner.require_launch_budget(1124.9, monotonic=lambda: 0)

    def test_runner_safety_checks_survive_python_optimization(self):
        tree = ast.parse(Path(runner.__file__).read_text())
        self.assertFalse(any(isinstance(node, ast.Assert) for node in ast.walk(tree)))

    def test_existing_local_output_stops_before_remote_work(self):
        with tempfile.TemporaryDirectory() as directory:
            collision = Path(directory) / "used"
            collision.mkdir()
            with mock.patch.object(runner, "OUT", collision):
                with self.assertRaises(FileExistsError):
                    runner.main([
                        "--execute",
                        "--owner",
                        "test owner",
                        "--approval-reference",
                        "test reference",
                    ])


if __name__ == "__main__":
    unittest.main()
