"""Local no-inference contract tests for the Option A ACL runner."""

import json
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from sentinel.run_acl_option_a import (
    DRIVER_LOCK,
    EXPECTED_BUNDLE_SHA256,
    LOCAL_BUNDLE,
    MAX_CGROUP_BYTES,
    OUT,
    PHASE,
    PREFIX,
    REMOTE,
    SOURCE_PREFIX,
    build_admission_argv,
    build_capacity,
    build_old_request_binding_program,
    build_runtime_command,
    remote_absence_paths,
    require_launch_budget,
    validate_old_request_binding,
)


class AclOptionARunnerTests(unittest.TestCase):
    def test_retained_request_probe_is_valid_and_uses_v2_schema(self):
        program = build_old_request_binding_program()
        compile(program, "<retained-request-probe>", "exec")
        self.assertIn("final['source']['request_id']", program)
        self.assertNotIn("final['profile']", program)

    def test_retained_request_binding_uses_v2_source_and_provenance_schema(self):
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
        binding = validate_old_request_binding(
            accepted,
            final,
            "old-prefix/registered/record.json",
            "register",
            "abc123",
            "old-prefix/",
        )
        self.assertEqual(binding["profile_id"], "native-v1")
        self.assertEqual(binding["profile_release"], "release-1")
        self.assertNotIn("profile", final)

        final["provenance"]["profile"]["release"] = "changed"
        with self.assertRaisesRegex(ValueError, "release changed"):
            validate_old_request_binding(
                accepted,
                final,
                "old-prefix/registered/record.json",
                "register",
                "abc123",
                "old-prefix/",
            )

    def test_new_identity_and_split_capacity_thresholds(self):
        capacity = build_capacity(
            started_at=1_000.0,
            owner="test owner",
            approval_reference="test authorization",
        )
        self.assertEqual(PHASE, "acl-option-a-window-b")
        self.assertEqual(PREFIX, "q04/option-a-20260918-b/")
        self.assertNotEqual(PREFIX, SOURCE_PREFIX)
        self.assertEqual(OUT, Path("/private/tmp/q04-acl-option-a-window-20260918-b"))
        self.assertEqual(capacity["outer_admission_available_bytes"], 4_831_838_208)
        self.assertEqual(capacity["outer_observation_seconds"], 180)
        self.assertEqual(capacity["outer_continuous_seconds"], 60)
        self.assertEqual(capacity["admission_available_bytes"], 3_221_225_472)
        self.assertEqual(capacity["admission_seconds"], 60)
        self.assertEqual(capacity["max_cgroup_bytes"], MAX_CGROUP_BYTES)
        self.assertEqual(capacity["minimum_work_seconds"], 825)
        self.assertEqual(capacity["cleanup_seconds"], 300)
        argv = build_admission_argv("token")
        self.assertEqual(
            argv[argv.index("--expected-max-cgroup-bytes") + 1],
            str(MAX_CGROUP_BYTES),
        )

    def test_bundle_and_all_new_paths_are_exclusive(self):
        self.assertTrue(LOCAL_BUNDLE.is_dir())
        self.assertEqual(
            hashlib.sha256((LOCAL_BUNDLE / "inputs.json").read_bytes()).hexdigest(),
            EXPECTED_BUNDLE_SHA256,
        )
        paths = remote_absence_paths()
        self.assertEqual(paths["root_absent"], REMOTE)
        self.assertTrue(all(path.startswith(REMOTE) for path in paths.values()))

    def test_runtime_boundary_is_fixture09_matrix_only(self):
        require_launch_budget(2_000.0, monotonic=lambda: 875.0)
        with self.assertRaisesRegex(RuntimeError, "insufficient workload"):
            require_launch_budget(2_000.0, monotonic=lambda: 875.1)
        command = build_runtime_command()
        self.assertIn("--phase matrix --fixture 09", command)
        self.assertIn("--kill-after=180s 825s", command)
        self.assertIn("--trial-seconds 180", command)
        self.assertIn("--name acl-option-a-window-b", command)
        self.assertIn("export PDF_QUALIFICATION_LOCK=" + DRIVER_LOCK, command)
        self.assertNotIn("--phase warm", command)
        self.assertNotIn("--phase drain", command)

    def test_nested_shell_reaches_only_expected_runtime_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = (Path(directory) / "root with spaces").resolve()
            source = root / "code/src"
            runtime_dir = root / "code/tests/pdf_processing/q04"
            staged = root / "runner-acl-option-a-window-b"
            for path in (source, runtime_dir, staged, root / "inputs", root / "state", root / "logs"):
                path.mkdir(parents=True, exist_ok=True)
            (source / "prepare.py").write_text(
                "def verify_bundle(path):\n path.parent.joinpath('verified').write_text(str(path))\n"
            )
            (staged / "telemetry.py").write_text("ORIGIN='staged'\n")
            (runtime_dir / "q04_runtime.py").write_text(
                "import json,sys\nfrom pathlib import Path\n"
                "root=Path(sys.argv[sys.argv.index('--bundle')+1]).parent\n"
                "(root/'args.json').write_text(json.dumps(sys.argv[1:]))\n"
            )
            timeout = root / "timeout"
            timeout.write_text("#!/bin/sh\nshift 3\nexec \"$@\"\n")
            timeout.chmod(0o755)
            capacity = root / "capacity.json"
            capacity.write_text("{}\n")
            subprocess.run(
                ["sh", "-eu", "-c", build_runtime_command(
                    remote=str(root), capacity=str(capacity), python=sys.executable,
                    timeout_program=str(timeout), driver_lock=str(root / "driver.lock"),
                )],
                check=True,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            )
            args = json.loads((root / "args.json").read_text())
            self.assertEqual(args[0:4], ["--phase", "matrix", "--fixture", "09"])
            self.assertNotIn("warm", args)
            self.assertNotIn("drain", args)

    def test_staging_and_init_failures_still_cleanup_release_and_recheck_services(self):
        import sentinel.run_acl_option_a as runner

        cleanup_sha = hashlib.sha256(
            (runner.REPO / "tests/pdf_processing/q04/sentinel/cleanup.py").read_bytes()
        ).hexdigest()

        class Holder:
            def __init__(self):
                self.stdin = io.BytesIO()
                self.returncode = None

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                self.returncode = 0
                return 0

            def terminate(self):
                self.returncode = -15

            def kill(self):
                self.returncode = -9

        for failure_point in ("stage", "init"):
            with self.subTest(failure_point=failure_point), tempfile.TemporaryDirectory() as directory:
                out = Path(directory) / "evidence"
                holder = Holder()
                writes = []
                runner.STATE.clear()
                runner.STATE.update({
                    "phase": "preparing", "errors": [], "retry_count": 0,
                    "services_restored": False,
                })

                def remote_side_effect(program, timeout=60):
                    if "print(Path(" in program:
                        return b"True\n"
                    return json.dumps({"errors": []}).encode()

                stage_effect = RuntimeError("synthetic staging failure") if failure_point == "stage" else {"bundle_sha256": "ok"}
                init_effect = RuntimeError("synthetic init failure")
                with (
                    mock.patch.object(runner, "OUT", out),
                    mock.patch.object(runner, "deployment_snapshot", return_value=[]),
                    mock.patch.object(runner, "assert_candidate_pods_absent"),
                    mock.patch.object(runner, "t09a_health"),
                    mock.patch.object(runner, "frozen_precheck", return_value={
                        "state_sha256": runner.SOURCE_STATE_SHA256,
                        "old_request_binding": {"request_id": "old"},
                    }),
                    mock.patch.object(runner, "claim_remote_root"),
                    mock.patch.object(runner.subprocess, "Popen", return_value=holder),
                    mock.patch.object(runner, "remote", side_effect=remote_side_effect),
                    mock.patch.object(runner, "write_remote", side_effect=lambda path, data: writes.append(path)),
                    mock.patch.object(runner, "stage_runtime_tree", side_effect=stage_effect),
                    mock.patch.object(runner, "stage_admission_runner", return_value={"cleanup.py": cleanup_sha}),
                    mock.patch.object(runner, "run_live_init", side_effect=init_effect),
                    mock.patch.object(
                        runner,
                        "capture",
                        side_effect=lambda: (out / "remote-evidence.tar").write_bytes(b"evidence"),
                    ),
                ):
                    result = runner.main([
                        "--execute", "--owner", "test", "--approval-reference", "test authorization",
                    ])
                self.assertEqual(result, 1)
                self.assertIn(runner.RELEASE, writes)
                self.assertTrue(runner.STATE["cleanup_verified"])
                self.assertTrue(runner.STATE["services_held_closed"])
                self.assertTrue(runner.STATE["reservation_released"])
                self.assertEqual(runner.STATE["retry_count"], 0)


if __name__ == "__main__":
    unittest.main()
