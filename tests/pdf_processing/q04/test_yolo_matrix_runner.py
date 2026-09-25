"""Local no-inference contract tests for the proposed YOLO matrix runner."""

import json
import inspect
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from sentinel import run_acl_option_a_c as accepted_acl_runner
from sentinel import run_yolo_matrix_a as yolo_runner
from sentinel.run_yolo_matrix_a import (
    EXPECTED_BUNDLE_SHA256,
    LOCAL_BUNDLE,
    OUT,
    PHASE,
    PREFIX,
    REMOTE,
    SOURCE_PREFIX,
    SOURCE_RUN_ID,
    SOURCE_STATE_SHA256,
    build_capacity,
    build_runtime_command,
    build_staging_probe_program,
    remote_absence_paths,
    validate_frozen_artifacts,
    validate_old_request_binding,
    validate_staged_runtime,
)


class YoloMatrixRunnerTests(unittest.TestCase):
    FROZEN_CODE = Path("/private/tmp/q04-option-a-window-c-source-code-20260918")
    RUNNER = Path(__file__).with_name("sentinel") / "run_yolo_matrix_a.py"

    def staged_root(self, directory):
        root = Path(directory)
        shutil.copytree(self.FROZEN_CODE, root / "code")
        shutil.copy2(
            Path(__file__).with_name("q04_runtime.py"),
            root / "code/tests/pdf_processing/q04/q04_runtime.py",
        )
        (root / "inputs").symlink_to(LOCAL_BUNDLE)
        return root

    def test_identity_scope_capacity_and_cleanup_budget_are_fixed(self):
        self.assertEqual(PHASE, "yolo-matrix-a")
        self.assertEqual(REMOTE, "/tmp/q04-yolo-matrix-20260918-a")
        self.assertEqual(PREFIX, "q04/yolo-matrix-20260918-a/")
        self.assertEqual(SOURCE_PREFIX, "q04/option-a-20260918-c/")
        self.assertNotEqual(PREFIX, SOURCE_PREFIX)
        self.assertEqual(OUT, Path("/private/tmp/q04-yolo-matrix-20260918-a"))
        self.assertEqual(set(remote_absence_paths()), {
            "root_absent", "phase_absent", "capacity_absent", "log_absent",
            "reservation_absent", "release_absent", "admission_absent",
            "admission_result_absent", "runner_absent", "driver_lock_absent",
        })
        capacity = build_capacity(
            started_at=1_000.0,
            owner="test owner",
            approval_reference="test authorization",
        )
        self.assertEqual(capacity["proposed_window_seconds"], 1_500)
        self.assertEqual(capacity["outer_observation_seconds"], 180)
        self.assertEqual(capacity["outer_continuous_seconds"], 60)
        self.assertEqual(capacity["outer_admission_available_bytes"], 4_831_838_208)
        self.assertEqual(capacity["admission_seconds"], 60)
        self.assertEqual(capacity["admission_available_bytes"], 3_221_225_472)
        self.assertEqual(capacity["minimum_work_seconds"], 825)
        self.assertEqual(capacity["cleanup_seconds"], 300)

        command = build_runtime_command()
        self.assertIn("--phase matrix --fixture 07", command)
        self.assertIn("--name yolo-matrix-a", command)
        self.assertIn("--kill-after=180s 825s", command)
        for excluded in ("--fixture 09", "--phase warm", "--phase drain", "--phase guard"):
            self.assertNotIn(excluded, command)

    def test_actual_bundle_runtime_reference_and_table_oracle_are_bound(self):
        self.assertTrue(self.FROZEN_CODE.is_dir())
        with tempfile.TemporaryDirectory() as directory:
            root = self.staged_root(directory)
            completed = subprocess.run(
                [sys.executable, "-c", build_staging_probe_program(root=str(root))],
                check=True,
                capture_output=True,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            )
            staged = json.loads(completed.stdout)
        bundle = json.loads((LOCAL_BUNDLE / "inputs.json").read_text())
        validate_staged_runtime(staged, bundle)
        for field in (
            "bundle_sha256",
            "runtime_sha256",
            "reference_07_sha256",
            "quality_oracle_sha256",
            "table_oracle_sha256",
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field + " changed"):
                    validate_staged_runtime(dict(staged, **{field: "0" * 64}), bundle)

    def test_source_state_and_accepted_phase_must_remain_exact(self):
        frozen = {
            "bundle_sha256_config": EXPECTED_BUNDLE_SHA256,
            "bundle_sha256_actual": EXPECTED_BUNDLE_SHA256,
            "state_sha256": SOURCE_STATE_SHA256,
            "producer_matches": True,
            "profile_matches": True,
            "accepted_phase_complete": True,
        }
        validate_frozen_artifacts(frozen)
        for field in ("bundle_sha256_config", "state_sha256", "accepted_phase_complete"):
            with self.subTest(field=field):
                changed = dict(frozen)
                changed[field] = False if field == "accepted_phase_complete" else "changed"
                with self.assertRaises(ValueError):
                    validate_frozen_artifacts(changed)
        self.assertEqual(SOURCE_RUN_ID, "q04-41aad36cffde419b95f92ba48b8abf26")

    def test_retained_acl_request_binding_is_checked_without_reinterpretation(self):
        accepted = {
            "request": {"request_id": "acl-request", "profile": "native-v1"},
            "profile": {"id": "native-v1", "release": "release-1"},
        }
        final = {
            "source": {
                "request_id": "acl-request",
                "profile": "native-v1",
                "artifact": {"key": SOURCE_PREFIX + "sources/09.pdf"},
            },
            "provenance": {"profile": {"id": "native-v1", "release": "release-1"}},
            "status": "complete",
        }
        result = validate_old_request_binding(
            accepted,
            final,
            SOURCE_PREFIX + "registered/record.json",
            "register",
            "abc123",
            SOURCE_PREFIX,
        )
        self.assertEqual(result["request_id"], "acl-request")
        final["provenance"]["profile"]["release"] = "changed"
        with self.assertRaisesRegex(ValueError, "release changed"):
            validate_old_request_binding(
                accepted, final, "record", "register", "abc123", SOURCE_PREFIX
            )

    def test_cli_refuses_to_claim_output_without_execute_and_authorization(self):
        completed = subprocess.run(
            [sys.executable, str(self.RUNNER)],
            check=False,
            capture_output=True,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(b"runtime execution requires explicit --execute", completed.stderr)

    def test_operational_flow_matches_accepted_launcher_except_reviewed_substitutions(self):
        unchanged = (
            "validate_old_request_binding",
            "validate_coordinator_identity",
            "validate_remote_baseline",
            "build_capacity",
            "build_admission_argv",
            "require_launch_budget",
            "launch_after_admission",
            "save",
            "k",
            "remote",
            "write_remote",
            "stage_admission_runner",
            "deployment_snapshot",
            "assert_candidate_pods_absent",
            "t09a_health",
            "copy_to_remote",
            "claim_remote_root",
            "stage_runtime_tree",
            "run_live_init",
        )
        for name in unchanged:
            with self.subTest(name=name):
                self.assertEqual(
                    inspect.getsource(getattr(yolo_runner, name)),
                    inspect.getsource(getattr(accepted_acl_runner, name)),
                )

        yolo_main = inspect.getsource(yolo_runner.main)
        normalized_main = (
            yolo_main.replace('"running-yolo"', '"running-acl"')
            .replace("YOLO driver failed", "ACL driver failed")
            .replace('STATE["matrix_passed"]', 'STATE["sentinel_passed"]')
        )
        self.assertEqual(normalized_main, inspect.getsource(accepted_acl_runner.main))

        normalized_capture = inspect.getsource(yolo_runner.capture).replace(
            "./state/acl-option-a-window-c", "./state/keynote-window-2"
        )
        self.assertEqual(
            normalized_capture, inspect.getsource(accepted_acl_runner.capture)
        )


if __name__ == "__main__":
    unittest.main()
