"""Local tests for the post-Docker-restart ACL runner; no runtime or inference."""

import unittest
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from sentinel.acl_admission import policy_from_capacity
from sentinel.run_acl_v2 import build_capacity as build_v2_capacity
from telemetry import check_sample
from sentinel.run_acl_v3 import (
    ADMISSION_EVIDENCE,
    ADMISSION_RESULT,
    CAPACITY,
    COORDINATOR_CONTAINER_ID,
    COORDINATOR_RESTART_COUNT,
    EXPECTED_BOOT_ID,
    EXPECTED_BUNDLE_SHA256,
    EXPECTED_PID1_START_TICKS,
    EXPECTED_STATE_SHA256,
    EXPECTED_VM_OOM_KILL,
    OUT,
    PHASE,
    RELEASE,
    REMOTE,
    RESERVATION,
    RUNNER_DIR,
    build_capacity,
    build_admission_argv,
    build_probe_expectation,
    build_runtime_command,
    staged_sources,
    validate_coordinator_identity,
    validate_frozen_artifacts,
    validate_remote_baseline,
)


class AclRunnerV3(unittest.TestCase):
    def test_new_identity_uses_the_reviewed_post_restart_oom_baseline(self):
        capacity = build_capacity(
            started_at=1_000.0,
            owner="test capacity owner",
            approval_reference="test-only authorization",
        )

        self.assertEqual(PHASE, "acl-window-v3-a")
        self.assertEqual(EXPECTED_VM_OOM_KILL, 0)
        self.assertEqual(capacity["expected_vm_oom_kill"], 0)
        self.assertEqual(capacity["outer_admission_available_bytes"], 4_831_838_208)
        self.assertEqual(capacity["admission_available_bytes"], 3_221_225_472)

    def test_v3_paths_are_new_and_runtime_is_still_acl_fixture_09_only(self):
        self.assertEqual(OUT.as_posix(), "/private/tmp/q04-acl-window-20260917-v3-a")
        for path in (
            CAPACITY,
            RESERVATION,
            RELEASE,
            ADMISSION_EVIDENCE,
            ADMISSION_RESULT,
            RUNNER_DIR,
        ):
            self.assertIn("acl-window-v3-a", path)
            self.assertNotIn("acl-window-v2-a", path)

        command = build_runtime_command()
        self.assertIn("--phase matrix", command)
        self.assertIn("--fixture 09", command)
        self.assertIn("--name acl-window-v3-a", command)
        self.assertNotIn("--phase init", command)
        self.assertIn(
            'export PYTHONPATH="$R/runner-acl-window-v3-a:$R/code/src',
            command,
        )
        self.assertIn("PYTHONSAFEPATH=1", command)
        self.assertEqual(
            set(staged_sources()),
            {"outer_admission.py", "acl_admission.py", "telemetry.py"},
        )

    def test_script_entrypoint_resolves_staged_telemetry_for_controller_and_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            overlay = root / "runner-acl-window-v3-a"
            frozen = root / "code" / "tests" / "pdf_processing" / "q04"
            overlay.mkdir(parents=True)
            frozen.mkdir(parents=True)
            (overlay / "telemetry.py").write_text("ORIGIN = 'staged'\n")
            (frozen / "telemetry.py").write_text("ORIGIN = 'frozen'\n")
            probe = frozen / "entrypoint.py"
            probe.write_text("import telemetry; print(telemetry.ORIGIN)\n")
            environment = dict(
                os.environ,
                PYTHONSAFEPATH="1",
                PYTHONPATH=os.pathsep.join((str(overlay), str(frozen))),
                PYTHONDONTWRITEBYTECODE="1",
            )

            origin = subprocess.check_output(
                [sys.executable, str(probe)], env=environment, text=True
            ).strip()

        self.assertEqual(origin, "staged")

    def test_probe_uses_restored_q04_paths_instead_of_missing_q03_root(self):
        expected = build_probe_expectation(
            {"base_profile": {"method": {}}, "producer": {"parse.py": "sha"}}
        )

        self.assertEqual(expected["profile_path"], REMOTE + "/inputs/inputs.json")
        self.assertEqual(
            expected["producer_roots"],
            ["/app/pdf_processing", REMOTE + "/code/src/pdf_processing"],
        )
        self.assertNotIn("q03-20260916-d", repr(expected))

    def test_coordinator_container_identity_is_fenced_after_restart(self):
        pod = {
            "metadata": {"uid": "39c4bf45-45ae-4646-8d7b-ec47b2c61785"},
            "status": {
                "containerStatuses": [
                    {
                        "name": "coordinator",
                        "containerID": COORDINATOR_CONTAINER_ID,
                        "restartCount": COORDINATOR_RESTART_COUNT,
                        "ready": True,
                        "state": {
                            "running": {"startedAt": "2026-09-17T13:46:12Z"}
                        },
                    }
                ]
            },
        }

        self.assertEqual(
            validate_coordinator_identity(pod)["container_id"],
            COORDINATOR_CONTAINER_ID,
        )
        pod["status"]["containerStatuses"][0]["restartCount"] += 1
        with self.assertRaisesRegex(ValueError, "restart count"):
            validate_coordinator_identity(pod)

    def test_policy_accepts_v3_baseline_without_reinterpreting_v2(self):
        v3 = build_capacity(
            started_at=1_000.0,
            owner="test capacity owner",
            approval_reference="test-only authorization",
        )
        policy = policy_from_capacity(v3, expected_vm_oom_kill=0)

        self.assertEqual(policy.expected_vm_oom_kill, 0)
        self.assertEqual(
            build_v2_capacity(
                started_at=1_000.0,
                owner="test capacity owner",
                approval_reference="test-only authorization",
            )["expected_vm_oom_kill"],
            28,
        )

    def test_admission_process_receives_the_new_baseline_explicitly(self):
        argv = build_admission_argv("reservation-token")

        baseline = argv.index("--expected-vm-oom-kill")
        self.assertEqual(argv[baseline + 1], "0")
        self.assertEqual(EXPECTED_BOOT_ID, "c01b81ac-b0fd-4ce6-8cda-f0da74b9bbd3")
        self.assertEqual(EXPECTED_PID1_START_TICKS, 733)

    def test_remote_baseline_rejects_a_second_restart_or_new_oom(self):
        baseline = {
            "boot_id": EXPECTED_BOOT_ID,
            "pid1_start_ticks": EXPECTED_PID1_START_TICKS,
            "vm_oom_kill": 0,
            "cgroup_oom_kill": 0,
            "qualification_lock_held": False,
        }
        validate_remote_baseline(baseline)

        for field, value in (("boot_id", "different"), ("vm_oom_kill", 1)):
            with self.subTest(field=field):
                changed = dict(baseline, **{field: value})
                with self.assertRaisesRegex(ValueError, field.replace("_", " ")):
                    validate_remote_baseline(changed)

    def test_reviewed_frozen_hashes_are_pinned(self):
        frozen = {
            "bundle_sha256_config": EXPECTED_BUNDLE_SHA256,
            "bundle_sha256_actual": EXPECTED_BUNDLE_SHA256,
            "state_sha256": EXPECTED_STATE_SHA256,
            "producer_matches": True,
            "profile_matches": True,
            "keynote_complete": True,
        }
        validate_frozen_artifacts(frozen)

        for field in ("bundle_sha256_actual", "state_sha256"):
            with self.subTest(field=field):
                changed = dict(frozen, **{field: "changed"})
                with self.assertRaisesRegex(ValueError, "frozen"):
                    validate_frozen_artifacts(changed)

    def test_per_case_guard_uses_the_capacity_oom_baseline(self):
        capacity = build_capacity(
            started_at=1_000.0,
            owner="test capacity owner",
            approval_reference="test-only authorization",
        )
        row = {
            "available": capacity["admission_available_bytes"],
            "psi_full_avg10": 0,
            "vm_oom_kill": 0,
            "memory_current": 1_000,
            "memory_events": {"oom_kill": 0},
        }
        check_sample(row, row, capacity)

        with self.assertRaisesRegex(ValueError, "VM OOM baseline"):
            changed = dict(row, vm_oom_kill=1)
            check_sample(changed, changed, capacity)


if __name__ == "__main__":
    unittest.main()
