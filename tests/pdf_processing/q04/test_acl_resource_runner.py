"""Local tests for the fresh-only ACL resource-calibration runner; no runtime or inference."""

import ast
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from sentinel.acl_admission import policy_from_capacity
import sentinel.acl_fresh_measure as fresh_measure
import sentinel.run_acl_resource_v1 as resource_runner
from sentinel.cleanup import is_owned_controller

from sentinel.run_acl_resource_v1 import (
    ADMISSION_EVIDENCE,
    ADMISSION_RESULT,
    CAPACITY,
    DRIVER_LOCK,
    OUT,
    OBSERVATION_CGROUP_BYTES,
    PHASE,
    RELEASE,
    REMOTE,
    RESERVATION,
    RUNNER_DIR,
    build_admission_argv,
    build_capacity,
    build_runtime_command,
    launch_after_admission,
    remote_absence_paths,
    require_launch_budget,
    write_artifact_manifest,
)


class AclResourceRunner(unittest.TestCase):
    def test_local_output_collision_stops_before_any_remote_callback(self):
        with tempfile.TemporaryDirectory() as directory:
            collision = Path(directory) / "already-used"
            collision.mkdir()
            with mock.patch.object(resource_runner, "OUT", collision):
                with self.assertRaises(FileExistsError):
                    resource_runner.main(
                        [
                            "--execute",
                            "--owner",
                            "test owner",
                            "--approval-reference",
                            "local collision test",
                        ]
                    )

    def test_has_new_exclusive_identity_and_separate_memory_thresholds(self):
        capacity = build_capacity(
            started_at=1_000.0,
            owner="test capacity owner",
            approval_reference="test-only authorization",
        )

        self.assertEqual(PHASE, "acl-fresh-resource-v1")
        self.assertEqual(OUT.as_posix(), "/private/tmp/q04-acl-fresh-resource-20260917-v1")
        for path in (
            CAPACITY,
            RESERVATION,
            RELEASE,
            ADMISSION_EVIDENCE,
            ADMISSION_RESULT,
            RUNNER_DIR,
        ):
            self.assertIn("acl-fresh-resource-v1", path)
            self.assertNotIn("acl-window-v3-b", path)

        absence_contract = remote_absence_paths()
        self.assertEqual(absence_contract["driver_lock_absent"], DRIVER_LOCK)
        self.assertEqual(DRIVER_LOCK, REMOTE + "/acl-fresh-resource-v1.driver.lock")
        self.assertTrue(
            all("acl-fresh-resource-v1" in path for path in absence_contract.values())
        )
        self.assertTrue(
            all("acl-window-v3-b" not in path for path in absence_contract.values())
        )

        self.assertEqual(capacity["outer_admission_available_bytes"], 4_831_838_208)
        self.assertEqual(capacity["outer_observation_seconds"], 180)
        self.assertEqual(capacity["outer_continuous_seconds"], 60)
        self.assertEqual(capacity["admission_available_bytes"], 3_221_225_472)
        self.assertEqual(capacity["admission_seconds"], 60)
        self.assertEqual(capacity["minimum_work_seconds"], 825)
        self.assertEqual(capacity["cleanup_seconds"], 300)
        self.assertEqual(capacity["expected_vm_oom_kill"], 0)
        self.assertEqual(capacity["expected_cgroup_oom_kill"], 0)
        self.assertEqual(capacity["min_available_bytes"], 1_610_612_736)
        self.assertEqual(capacity["max_cgroup_bytes"], OBSERVATION_CGROUP_BYTES)
        self.assertEqual(capacity["max_cgroup_bytes"], 4_294_967_296)
        self.assertEqual(capacity["max_full_psi"], 0)
        self.assertEqual(capacity["max_sample_gap_seconds"], 3)

        policy = policy_from_capacity(
            capacity,
            expected_vm_oom_kill=0,
            expected_max_cgroup_bytes=4_294_967_296,
        )
        self.assertEqual(policy.available_bytes, 4_831_838_208)
        self.assertEqual(policy.max_cgroup_bytes, 4_294_967_296)
        with self.assertRaisesRegex(ValueError, "max_cgroup_bytes"):
            policy_from_capacity(capacity, expected_vm_oom_kill=0)

        admission = build_admission_argv("token")
        self.assertEqual(
            admission[admission.index("--expected-max-cgroup-bytes") + 1],
            "4294967296",
        )

    def test_workload_and_cleanup_reserve_remain_jointly_required(self):
        require_launch_budget(2_000.0, monotonic=lambda: 875.0)
        with self.assertRaisesRegex(RuntimeError, "insufficient workload"):
            require_launch_budget(2_000.0, monotonic=lambda: 875.1)

        command = build_runtime_command()
        self.assertIn("--kill-after=180s 825s", command)
        self.assertIn("--trial-seconds 180", command)
        self.assertIn("--attribution-interval-seconds 0.25", command)
        self.assertIn("--attribution-gap-seconds 1", command)
        self.assertIn("PYTHONSAFEPATH=1", command)
        self.assertIn("export PDF_QUALIFICATION_LOCK=" + DRIVER_LOCK, command)
        self.assertIn('test ! -e "$PDF_QUALIFICATION_LOCK"', command)
        self.assertNotIn("--phase init", command)
        self.assertNotIn("--phase matrix", command)
        self.assertNotIn("restored", command)
        self.assertNotIn("replay", command)

    def test_runtime_launch_remains_unreachable_after_failed_admission_or_deadline(self):
        launched = []
        with self.assertRaisesRegex(RuntimeError, "did not return PASS"):
            launch_after_admission(
                lambda: {"passed": False},
                lambda: launched.append(True),
                lease_ends_monotonic=2_000,
                monotonic=lambda: 0,
            )
        with self.assertRaisesRegex(RuntimeError, "insufficient workload"):
            launch_after_admission(
                lambda: {"passed": True},
                lambda: launched.append(True),
                lease_ends_monotonic=1_124.9,
                monotonic=lambda: 0,
            )
        self.assertEqual(launched, [])

    def test_artifact_manifest_is_exclusive_and_hashes_retained_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "evidence.json").write_text('{"retained":true}\n')
            with mock.patch.object(resource_runner, "OUT", output):
                write_artifact_manifest()
                manifest = json.loads((output / "artifact-manifest.json").read_text())
                self.assertEqual(manifest["phase"], PHASE)
                self.assertEqual(manifest["artifacts"][0]["name"], "evidence.json")
                with self.assertRaises(FileExistsError):
                    write_artifact_manifest()

    def test_measurement_driver_has_one_literal_fresh_fixture_09_trial(self):
        path = Path(resource_runner.__file__).with_name("acl_fresh_measure.py")
        tree = ast.parse(path.read_text())
        trials = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "trial"
        ]
        self.assertEqual(len(trials), 1)
        self.assertEqual(
            [ast.literal_eval(value) for value in trials[0].args[:3]],
            ["09", "fresh", "fresh-09"],
        )

    def test_measurement_driver_rejects_existing_identity_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "fresh-resource.driver.lock"
            with lock_path.open("a+"):
                with mock.patch.dict(
                    os.environ, {"PDF_QUALIFICATION_LOCK": str(lock_path)}
                ):
                    with mock.patch.object(
                        fresh_measure, "run_fresh", new=mock.AsyncMock()
                    ) as run:
                        with self.assertRaises(FileExistsError):
                            fresh_measure.main(
                                [
                                    "--bundle",
                                    str(Path(directory) / "bundle"),
                                    "--state",
                                    str(Path(directory) / "state"),
                                    "--capacity",
                                    str(Path(directory) / "capacity.json"),
                                    "--name",
                                    PHASE,
                                    "--expected-run-id",
                                    "run",
                                    "--expected-prefix",
                                    "prefix/",
                                    "--capacity-approved",
                                ]
                            )
                        run.assert_not_awaited()

    def test_measurement_driver_acquires_nonblocking_exclusive_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "fresh-resource.driver.lock"
            with mock.patch.dict(
                os.environ, {"PDF_QUALIFICATION_LOCK": str(lock_path)}
            ):
                with mock.patch.object(
                    fresh_measure, "run_fresh", new=mock.AsyncMock()
                ) as run:
                    with mock.patch.object(
                        fresh_measure.fcntl, "flock", wraps=fcntl.flock
                    ) as flock:
                        result = fresh_measure.main(
                            [
                                "--bundle",
                                str(Path(directory) / "bundle"),
                                "--state",
                                str(Path(directory) / "state"),
                                "--capacity",
                                str(Path(directory) / "capacity.json"),
                                "--name",
                                PHASE,
                                "--expected-run-id",
                                "run",
                                "--expected-prefix",
                                "prefix/",
                                "--capacity-approved",
                            ]
                        )
            self.assertEqual(result, 0)
            self.assertTrue(lock_path.exists())
            flock.assert_called_once()
            self.assertEqual(flock.call_args.args[1], fcntl.LOCK_EX | fcntl.LOCK_NB)
            run.assert_awaited_once()

    def test_owner_cleanup_matches_new_controller_and_rejects_near_matches(self):
        root = Path(REMOTE)
        reviewed = (
            "q04/q04_runtime.py",
            "runner-acl-fresh-resource-v1/acl_fresh_measure.py",
        )
        args = [
            "/experiment/.venv/bin/python",
            REMOTE + "/runner-acl-fresh-resource-v1/acl_fresh_measure.py",
            "--state",
            REMOTE + "/state",
        ]
        self.assertTrue(is_owned_controller(args, root, reviewed))
        self.assertFalse(
            is_owned_controller(
                [args[0], args[1] + ".copy", "--state", args[3]], root, reviewed
            )
        )
        self.assertFalse(
            is_owned_controller(
                [args[0], args[1], "--state", REMOTE + "-other/state"],
                root,
                reviewed,
            )
        )
        runner_source = Path(resource_runner.__file__).read_text()
        self.assertIn(
            '"runner-acl-fresh-resource-v1/acl_fresh_measure.py"', runner_source
        )

    def test_nested_shell_executes_preflight_then_reaches_runtime_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = (Path(directory) / "root with spaces").resolve()
            source = root / "code/src"
            runtime_dir = root / "code/tests/pdf_processing/q04"
            staged = root / "runner-acl-fresh-resource-v1"
            for path in (source, runtime_dir, staged, root / "inputs", root / "state", root / "logs"):
                path.mkdir(parents=True, exist_ok=True)

            (source / "prepare.py").write_text(
                "from pathlib import Path\n"
                "def verify_bundle(path):\n"
                "    assert path.is_absolute()\n"
                "    (path.parent / 'verified-path.txt').write_text(str(path))\n"
            )
            (staged / "telemetry.py").write_text("ORIGIN = 'staged'\n")
            (staged / "acl_resource_telemetry.py").write_text(
                "ORIGIN = 'resource-staged'\n"
            )
            (runtime_dir / "telemetry.py").write_text("ORIGIN = 'frozen'\n")
            (staged / "acl_fresh_measure.py").write_text(
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "import telemetry, acl_resource_telemetry\n"
                "root = Path(sys.argv[sys.argv.index('--bundle') + 1]).parent\n"
                "(root / 'runtime-boundary.json').write_text(json.dumps({\n"
                "    'argv': sys.argv[1:], 'telemetry': telemetry.ORIGIN,\n"
                "    'resource_telemetry': acl_resource_telemetry.ORIGIN,\n"
                "    'driver_lock': os.environ['PDF_QUALIFICATION_LOCK']\n"
                "}, sort_keys=True))\n"
            )
            timeout = root / "timeout"
            timeout.write_text("#!/bin/sh\nshift 3\nexec \"$@\"\n")
            timeout.chmod(0o755)
            capacity = root / "capacity-acl-fresh-resource-v1.json"
            capacity.write_text("{}\n")

            command = build_runtime_command(
                remote=str(root),
                capacity=str(capacity),
                python=sys.executable,
                timeout_program=str(timeout),
                driver_lock=str(root / "acl-fresh-resource-v1.driver.lock"),
            )
            subprocess.run(
                ["sh", "-eu", "-c", command],
                check=True,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            )

            self.assertEqual(
                (root / "verified-path.txt").read_text(),
                str(root / "inputs"),
            )
            reached = json.loads((root / "runtime-boundary.json").read_text())
            self.assertEqual(reached["telemetry"], "staged")
            self.assertEqual(reached["resource_telemetry"], "resource-staged")
            self.assertEqual(
                reached["driver_lock"], str(root / "acl-fresh-resource-v1.driver.lock")
            )
            self.assertEqual(
                reached["argv"],
                [
                    "--bundle",
                    str(root / "inputs"),
                    "--state",
                    str(root / "state"),
                    "--capacity",
                    str(capacity),
                    "--name",
                    "acl-fresh-resource-v1",
                    "--expected-run-id",
                    "q04-7b4f958ff3ac4e2da5b54dcaa66914b9",
                    "--expected-prefix",
                    "q04/keynote-18be1b3-20260916-b/",
                    "--trial-seconds",
                    "180",
                    "--attribution-interval-seconds",
                    "0.25",
                    "--attribution-gap-seconds",
                    "1",
                    "--capacity-approved",
                ],
            )


if __name__ == "__main__":
    unittest.main()
