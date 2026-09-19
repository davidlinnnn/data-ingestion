"""Offline acceptance checks for the fixed six-fixture candidate batch."""

import hashlib
import json
from pathlib import Path
import signal
import subprocess
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from candidate.candidate_matrix_window import run_window
from candidate.yolo_candidate_window import validate_matrix_records
from sentinel import run_candidate_batch as batch
from sentinel import run_candidate_matrix_phase as phase_runner
from sentinel import run_yolo_lifecycle_a as yolo_runner


CLEANUP_SHA256 = hashlib.sha256(
    (phase_runner.REPO / "tests/pdf_processing/q04/sentinel/cleanup.py").read_bytes()
).hexdigest()


class CandidateBatchTests(unittest.TestCase):
    def test_manifest_fixes_six_serial_phases_and_total_lease_budget(self):
        manifest = phase_runner.load_manifest()
        phases = manifest["phases"]
        self.assertEqual(
            [phase["fixture"] for phase in phases],
            ["07", "09", "10", "08", "06", "native"],
        )
        self.assertEqual(sum(phase["window_seconds"] for phase in phases), 8025)
        self.assertTrue(all(phase["prelease_seconds"] == 300 for phase in phases))
        self.assertTrue(
            all(phase["outer_cleanup_grace_seconds"] == 300 for phase in phases)
        )
        identities = {
            value
            for phase in phases
            for value in (phase["phase"], phase["remote_root"], phase["prefix"],
                          phase["local_output"])
        }
        self.assertEqual(len(identities), len(phases) * 4)

    def test_every_non_yolo_phase_has_a_fixed_offline_record(self):
        manifest = phase_runner.load_manifest()
        records = [
            phase_runner.offline_phase_record(phase["key"], manifest)
            for phase in manifest["phases"][1:]
        ]
        self.assertEqual([row["fixture"] for row in records],
                         ["09", "10", "08", "06", "native"])
        for record in records:
            self.assertFalse(record["runtime_authorized"])
            self.assertEqual(record["measurement_argv"], next(
                phase["measurement_argv"] for phase in manifest["phases"]
                if phase["key"] == record["key"]
            ))

    def test_first_gate_is_the_existing_attributed_yolo_window(self):
        manifest = phase_runner.load_manifest()
        yolo = manifest["phases"][0]
        self.assertEqual(
            yolo["measurement_argv"],
            yolo_runner.build_measurement_argv("q04-offline-candidate"),
        )
        command = yolo_runner.build_runtime_command("q04-offline-candidate")
        self.assertEqual(
            yolo["runtime_command_sha256"],
            hashlib.sha256(command.encode()).hexdigest(),
        )
        retained = json.loads(yolo_runner.OFFLINE_MANIFEST.read_text())
        self.assertEqual(retained["identity"]["phase"], yolo["phase"])
        self.assertEqual(retained["identity"]["remote_root"], yolo["remote_root"])
        self.assertEqual(retained["candidate_inputs_sha256"],
                         manifest["candidate_inputs_sha256"])

    def test_batch_uses_repo_cwd_and_explicit_repo_pythonpath(self):
        manifest = phase_runner.load_manifest()
        argv = batch.build_phase_argv(
            manifest["phases"][1], owner="owner", approval_reference="approval"
        )
        self.assertEqual(argv[0], str(batch.PROJECT_PYTHON))
        self.assertIn("--phase-key", argv)
        environment = batch.fixed_environment()
        paths = environment["PYTHONPATH"].split(":")
        self.assertEqual(paths[0], str(batch.REPO))
        self.assertIn(str(batch.REPO / "src"), paths)

    def test_result_gate_requires_acceptance_cleanup_and_held_services(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            phase = {"key": "acl", "local_output": str(root)}
            good = {
                "phase": "complete", "errors": [], "acceptance_passed": True,
                "cleanup_verified": True, "services_held_closed": True,
                "reservation_released": True,
            }
            (root / "lease-state.json").write_text(json.dumps(good))
            self.assertEqual(batch.validate_phase_result(phase), good)
            good["cleanup_verified"] = False
            (root / "lease-state.json").write_text(json.dumps(good))
            with self.assertRaisesRegex(RuntimeError, "cleanup"):
                batch.validate_phase_result(phase)

    def test_failed_phase_stops_without_retry(self):
        phase = {
            "key": "acl", "fixture": "09", "local_output": "/does/not/exist",
            "prelease_seconds": 300, "window_seconds": 1200,
            "outer_cleanup_grace_seconds": 300,
        }
        process = mock.Mock(returncode=7)
        process.poll.return_value = 7
        with mock.patch("sentinel.run_candidate_batch.subprocess.Popen",
                        return_value=process) as popen:
            with self.assertRaisesRegex(RuntimeError, "failed; batch stopped"):
                batch.run_phase(
                    phase, owner="owner", approval_reference="approval",
                    reviewed_cleanup_sha256=CLEANUP_SHA256,
                )
        popen.assert_called_once()

    def test_interruption_always_settles_active_phase_process(self):
        phase = {
            "key": "acl", "fixture": "09", "local_output": "/does/not/exist",
            "prelease_seconds": 300, "window_seconds": 1200,
            "outer_cleanup_grace_seconds": 300,
        }
        process = mock.Mock(returncode=None)
        process.poll.return_value = None
        with mock.patch(
            "sentinel.run_candidate_batch.subprocess.Popen", return_value=process
        ) as popen, mock.patch(
            "sentinel.run_candidate_batch.time.sleep", side_effect=KeyboardInterrupt
        ), mock.patch(
            "sentinel.run_candidate_batch.settle_phase_process"
        ) as settle:
            with self.assertRaises(KeyboardInterrupt):
                batch.run_phase(
                    phase, owner="owner", approval_reference="approval",
                    reviewed_cleanup_sha256=CLEANUP_SHA256,
                )
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        settle.assert_called_once_with(process, phase, CLEANUP_SHA256)

    def test_cleanup_grace_expiry_terminates_owned_process_group(self):
        process = mock.Mock(pid=4242)
        process.poll.return_value = None
        process.wait.side_effect = [
            subprocess.TimeoutExpired("phase", 30),
            subprocess.TimeoutExpired("phase", 5),
            0,
        ]
        with mock.patch("sentinel.run_candidate_batch.os.killpg") as killpg:
            with self.assertRaisesRegex(TimeoutError, "cleanup grace"):
                batch.stop_with_cleanup(process, 300)
        self.assertEqual(
            [call.args for call in killpg.call_args_list],
            [(4242, signal.SIGINT), (4242, signal.SIGTERM), (4242, signal.SIGKILL)],
        )

    def test_unsettled_exit_runs_identity_fenced_external_cleanup(self):
        phase = {"key": "acl", "local_output": "/does/not/exist"}
        process = mock.Mock()
        process.poll.return_value = 1
        with mock.patch(
            "sentinel.run_candidate_batch.phase_is_settled", return_value=False
        ), mock.patch(
            "sentinel.run_candidate_batch.emergency_cleanup"
        ) as cleanup:
            batch.settle_phase_process(process, phase, CLEANUP_SHA256)
        cleanup.assert_called_once_with(phase, CLEANUP_SHA256)

    def test_emergency_cleanup_binds_driver_and_reservation_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "phase"
            output.mkdir()
            identity = {
                "coordinator_uid": yolo_runner.COORDINATOR_UID,
                "hostname": "coordinator",
                "pid": 4242, "start_ticks": 73, "lock_device_major": 1,
                "lock_device_minor": 2, "lock_inode": 3,
                "token": "owned-token", "phase": "candidate-batch-a-acl",
            }
            (output / "lease-state.json").write_text(json.dumps({
                "remote_claimed": True, "reservation_token": "owned-token",
                "reservation_identity": identity,
            }))
            phase = {
                "key": "acl", "fixture": "09", "local_output": str(output),
                "remote_root": "/tmp/q04-candidate-batch-20260919-a-acl",
                "phase": "candidate-batch-a-acl",
                "runner_dir": "/tmp/q04-candidate-batch-20260919-a-acl/"
                "runner-candidate-batch-a-acl",
                "reservation": "/tmp/reservation.json", "release": "/tmp/release",
            }
            replies = [
                json.dumps({
                    "claim": {"phase": "candidate-batch-a-acl",
                              "token": "owned-token"},
                    "reservation": identity,
                }).encode(),
                json.dumps({"errors": []}).encode(),
                json.dumps({"reservation_released": True,
                            "identity": identity}).encode(),
            ]
            with mock.patch.object(batch, "BATCH_OUT", root), mock.patch(
                "sentinel.run_candidate_batch.kubectl_python",
                side_effect=replies,
            ) as remote:
                evidence = batch.emergency_cleanup(phase, CLEANUP_SHA256)
            self.assertEqual(evidence["errors"], [])
            ownership_program = remote.call_args_list[0].args[0]
            cleanup_program = remote.call_args_list[1].args[0]
            release_program = remote.call_args_list[2].args[0]
            self.assertIn("setup claim identity mismatch", ownership_program)
            self.assertIn("setup claim identity mismatch", cleanup_program)
            self.assertIn("runner-candidate-batch-a-acl/candidate_matrix_window.py",
                          cleanup_program)
            self.assertIn("owned-token", release_program)
            self.assertIn("observed!=expected", release_program)

    def test_mismatched_remote_claim_blocks_cleanup_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "phase"
            output.mkdir()
            (output / "lease-state.json").write_text(json.dumps({
                "remote_claimed": True, "reservation_token": "owned-token",
                "reservation_identity": None,
            }))
            phase = {
                "key": "acl", "fixture": "09", "local_output": str(output),
                "remote_root": "/tmp/q04-candidate-batch-20260919-a-acl",
                "phase": "candidate-batch-a-acl",
                "runner_dir": "/tmp/root/runner", "reservation": "/tmp/reservation",
                "release": "/tmp/release",
            }
            with mock.patch(
                "sentinel.run_candidate_batch.kubectl_python",
                side_effect=RuntimeError("setup claim identity mismatch"),
            ) as remote:
                with self.assertRaisesRegex(RuntimeError, "setup claim"):
                    batch.emergency_cleanup(phase, CLEANUP_SHA256)
            remote.assert_called_once()

    def test_cleanup_source_mutation_blocks_remote_cleanup_program(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "phase"
            output.mkdir()
            cleanup_path = root / "tests/pdf_processing/q04/sentinel/cleanup.py"
            cleanup_path.parent.mkdir(parents=True)
            cleanup_path.write_text("# mutated after startup\n")
            identity = {
                "coordinator_uid": yolo_runner.COORDINATOR_UID,
                "hostname": "coordinator", "pid": 4242, "start_ticks": 73,
                "lock_device_major": 1, "lock_device_minor": 2,
                "lock_inode": 3, "token": "owned-token",
                "phase": "candidate-batch-a-acl",
            }
            (output / "lease-state.json").write_text(json.dumps({
                "remote_claimed": True, "reservation_token": "owned-token",
                "reservation_identity": identity,
            }))
            phase = {
                "key": "acl", "fixture": "09", "local_output": str(output),
                "remote_root": "/tmp/root", "phase": "candidate-batch-a-acl",
                "runner_dir": "/tmp/root/runner", "reservation": "/tmp/reservation",
                "release": "/tmp/release",
            }
            guard = json.dumps({
                "claim": {"phase": phase["phase"], "token": "owned-token"},
                "reservation": identity,
            }).encode()
            with mock.patch.object(batch, "REPO", root), mock.patch(
                "sentinel.run_candidate_batch.kubectl_python", return_value=guard
            ) as remote:
                with self.assertRaisesRegex(RuntimeError, "cleanup source changed"):
                    batch.emergency_cleanup(phase, CLEANUP_SHA256)
            remote.assert_called_once()


class CandidateMatrixDriverTests(unittest.IsolatedAsyncioTestCase):
    async def test_acl_records_bind_exact_fresh_replay_and_new_restored_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = {"key": "q04/candidate/sources/acl", "sha256": "abc"}
            fresh = {"request": {"request_id": "fresh-09", "artifact": artifact}}
            restored = {
                "request": {"request_id": "restored-09", "artifact": artifact}
            }
            replay = {"request": fresh["request"]}
            for mode, record in (
                ("fresh", fresh), ("restored", restored), ("replay", replay)
            ):
                target = root / f"{mode}-09"
                target.mkdir()
                (target / "accepted.json").write_text(json.dumps(record))
            self.assertEqual(
                validate_matrix_records(root, "09"),
                {"fresh": fresh, "restored": restored, "replay": replay},
            )

    async def test_capacity_mutation_after_init_rejects_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            bundle.mkdir()
            inputs = bundle / "inputs.json"
            inputs.write_text("{}")
            state = root / "state"
            state.mkdir()
            capacity = root / "capacity.json"
            capacity.write_text(json.dumps({"min_available_bytes": 1}))
            (state / "config.json").write_text(json.dumps({
                "run_id": "q04-test-run", "prefix": "q04/test/",
                "bundle": str(bundle.resolve()),
                "bundle_sha256": hashlib.sha256(inputs.read_bytes()).hexdigest(),
                "producer": {"commit": "candidate"},
                "profiles": {"09": {"method": {"parser": "acl"}}},
                "window": {"min_available_bytes": 3 * 1024**3},
            }))
            args = SimpleNamespace(
                fixture="09", bundle=bundle, state=state, capacity=capacity,
                name="candidate", expected_run_id="q04-test-run",
                expected_prefix="q04/test/", capacity_approved=True,
            )
            verified = {
                "producer": {"commit": "candidate"},
                "base_profile": {"method": {"parser": "acl"}},
            }
            with mock.patch(
                "candidate.candidate_matrix_window.verify_bundle",
                return_value=verified,
            ), mock.patch(
                "candidate.candidate_matrix_window.validate_window"
            ), mock.patch(
                "candidate.candidate_matrix_window.q04_runtime.main",
                new=mock.AsyncMock(),
            ) as runtime_main:
                with self.assertRaisesRegex(ValueError, "capacity window differs"):
                    await run_window(args)
            runtime_main.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
