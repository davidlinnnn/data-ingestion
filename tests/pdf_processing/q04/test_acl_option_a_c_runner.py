"""Local no-inference contract tests for the Option A window-c runner."""

import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest

from sentinel.run_acl_option_a_c import (
    LOCAL_BUNDLE,
    OUT,
    PHASE,
    PREFIX,
    REMOTE,
    SOURCE_PREFIX,
    build_capacity,
    build_initialized_state_probe_program,
    build_runtime_command,
    build_staging_probe_program,
    validate_initialized_state,
    validate_old_request_binding,
    validate_staged_runtime,
)


class AclOptionACRunnerTests(unittest.TestCase):
    FROZEN_CODE = Path("/private/tmp/q04-option-a-window-c-source-code-20260918")
    LAUNCHER = Path(__file__).with_name("sentinel") / "run_acl_option_a_c.sh"

    def staged_root(self, directory):
        root = Path(directory)
        shutil.copytree(self.FROZEN_CODE, root / "code")
        shutil.copy2(
            Path(__file__).with_name("q04_runtime.py"),
            root / "code/tests/pdf_processing/q04/q04_runtime.py",
        )
        (root / "inputs").symlink_to(LOCAL_BUNDLE)
        return root

    def test_new_identity_budget_and_fixture_scope(self):
        self.assertEqual(PHASE, "acl-option-a-window-c")
        self.assertEqual(REMOTE, "/tmp/q04-option-a-20260918-c")
        self.assertEqual(PREFIX, "q04/option-a-20260918-c/")
        self.assertNotEqual(PREFIX, SOURCE_PREFIX)
        self.assertEqual(OUT, Path("/private/tmp/q04-acl-option-a-window-20260918-c"))
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
        self.assertIn("--phase matrix --fixture 09", command)
        self.assertIn("--name acl-option-a-window-c", command)
        self.assertIn("--kill-after=180s 825s", command)
        self.assertNotIn("--phase warm", command)
        self.assertNotIn("--phase drain", command)

    def test_actual_shell_launcher_captures_complete_nonempty_argv(self):
        approval = (
            "new main user authorization for one ACL Option A window c attempt "
            "after review of the argument-validation failure; fixture09 three "
            "modes only, 1500 seconds, stop on failure/no retry, 32 Deployments "
            "held closed"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            captured = root / "argv.txt"
            stub = root / "capture-argv"
            stub.write_text(
                "#!/bin/sh\n"
                ": > \"$Q04_CAPTURE_OUTPUT\"\n"
                "for argument in \"$@\"; do printf '%s\\n' \"$argument\" >> \"$Q04_CAPTURE_OUTPUT\"; done\n"
            )
            stub.chmod(0o700)
            environment = dict(
                os.environ,
                Q04_APPROVAL_REFERENCE=approval,
                Q04_ARGV_CAPTURE="1",
                Q04_CAPTURE_STUB=str(stub),
                Q04_CAPTURE_OUTPUT=str(captured),
            )
            subprocess.run(
                [str(self.LAUNCHER)],
                check=True,
                cwd=Path(__file__).resolve().parents[3],
                env=environment,
            )
            argv = captured.read_text().splitlines()
        expected_runner = str(
            Path(__file__).with_name("sentinel").resolve()
            / "run_acl_option_a_c.py"
        )
        self.assertEqual(argv[0], expected_runner)
        self.assertEqual(argv[1:4], ["--execute", "--owner", "Q04 main task 01a0aa25-3a23-7fb2-b13c-6936f95ccbc7"])
        self.assertEqual(argv[4:], ["--approval-reference", approval])
        self.assertTrue(argv[-1])
        plan = (
            Path(__file__).with_name("diagnosis")
            / "acl-fresh-resource-v1/adoption-v1/ACL-OPTION-A-WINDOW-C-PLAN.md"
        ).read_text()
        self.assertIn(
            "export Q04_APPROVAL_REFERENCE=" + shlex.quote(approval),
            plan,
        )
        self.assertIn(
            "tests/pdf_processing/q04/sentinel/run_acl_option_a_c.sh",
            plan,
        )

    def test_shell_launcher_refuses_missing_approval_before_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            captured = Path(directory) / "argv.txt"
            environment = dict(
                os.environ,
                Q04_ARGV_CAPTURE="1",
                Q04_CAPTURE_STUB="/bin/false",
                Q04_CAPTURE_OUTPUT=str(captured),
            )
            environment.pop("Q04_APPROVAL_REFERENCE", None)
            completed = subprocess.run(
                [str(self.LAUNCHER)],
                check=False,
                capture_output=True,
                cwd=Path(__file__).resolve().parents[3],
                env=environment,
            )
            self.assertFalse(captured.exists())
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(b"export the verbatim new window-c authorization", completed.stderr)

    def test_retained_binding_rejects_request_profile_and_release_mismatches(self):
        accepted = {
            "request": {"request_id": "old-request", "profile": "native-v1"},
            "profile": {"id": "native-v1", "release": "release-1"},
        }
        final = {
            "source": {
                "request_id": "old-request",
                "profile": "native-v1",
                "artifact": {"key": "old-prefix/sources/original.pdf"},
            },
            "provenance": {
                "profile": {"id": "native-v1", "release": "release-1"}
            },
            "status": "complete",
        }

        def validate():
            return validate_old_request_binding(
                accepted,
                final,
                "old-prefix/registered/record.json",
                "register",
                "abc123",
                "old-prefix/",
            )

        self.assertEqual(validate()["request_id"], "old-request")
        cases = (
            (final["source"], "request_id", "changed", "request changed"),
            (accepted["request"], "profile", "other", "accepted request profile"),
            (final["source"], "profile", "other", "source profile changed"),
            (final["provenance"]["profile"], "id", "other", "provenance profile changed"),
            (final["provenance"]["profile"], "release", "changed", "release changed"),
        )
        for mapping, key, changed, message in cases:
            with self.subTest(message=message):
                original = mapping[key]
                mapping[key] = changed
                try:
                    with self.assertRaisesRegex(ValueError, message):
                        validate()
                finally:
                    mapping[key] = original

    def test_actual_option_a_bundle_passes_complete_staging_probe(self):
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

    def test_staging_probe_rejects_each_bound_artifact_hash(self):
        bundle = json.loads((LOCAL_BUNDLE / "inputs.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = self.staged_root(directory)
            completed = subprocess.run(
                [sys.executable, "-c", build_staging_probe_program(root=str(root))],
                check=True,
                capture_output=True,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            )
            staged = json.loads(completed.stdout)
        for field in (
            "bundle_sha256",
            "runtime_sha256",
            "reference_09_sha256",
            "quality_oracle_sha256",
            "content_evidence_sha256",
        ):
            with self.subTest(field=field):
                changed = dict(staged, **{field: "0" * 64})
                with self.assertRaisesRegex(ValueError, field + " changed"):
                    validate_staged_runtime(changed, bundle)

    def test_init_probe_schema_matches_q04_runtime_contract(self):
        compile(
            build_initialized_state_probe_program(),
            "<generated-init-state-probe>",
            "exec",
        )
        bundle = json.loads((LOCAL_BUNDLE / "inputs.json").read_text())
        profiles = sorted(
            {row["id"] for row in bundle["fixtures"]}
            | {"native-evidence", "native-method"}
        )
        capacity = build_capacity(
            started_at=1_000.0,
            owner="test owner",
            approval_reference="test authorization",
        )
        initialized = {
            "run_id": "q04-new-run",
            "prefix": PREFIX,
            "bundle": REMOTE + "/inputs",
            "bundle_sha256": "9e46ad75379dffed05c5e25ec36b22fdf0d680e30e7d2b298d5ac355d0e039f2",
            "state_sha256": "state-hash",
            "producer": bundle["producer"],
            "profile_method": bundle["base_profile"]["method"],
            "profile_id": bundle["base_profile"]["id"],
            "profile_release": "q04-release",
            "config_keys": sorted({
                "run_id", "profiles", "producer", "bundle", "state", "temporal",
                "endpoint", "bucket", "prefix", "window", "model_cache", "python",
                "pod_namespace", "trial_seconds", "workflow_queue", "queues",
                "limits", "parser_budgets", "drain_seconds", "bundle_sha256",
            }),
            "profile_keys": profiles,
            "queue_keys": profiles,
            "window_keys": sorted(capacity),
        }
        validate_initialized_state(initialized, bundle)
        initialized["queue_keys"] = profiles[:-1]
        with self.assertRaisesRegex(ValueError, "queue/profile"):
            validate_initialized_state(initialized, bundle)


if __name__ == "__main__":
    unittest.main()
