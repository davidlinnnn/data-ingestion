"""Local tests for the corrected ACL v3-b runner; no runtime or inference."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sentinel.run_acl_v3b import (
    ADMISSION_EVIDENCE,
    ADMISSION_RESULT,
    CAPACITY,
    DRIVER_LOCK,
    OUT,
    PHASE,
    RELEASE,
    REMOTE,
    RESERVATION,
    RUNNER_DIR,
    build_capacity,
    build_runtime_command,
    remote_absence_paths,
    require_launch_budget,
)


class AclRunnerV3B(unittest.TestCase):
    def test_v3b_has_new_exclusive_identity_and_unchanged_thresholds(self):
        capacity = build_capacity(
            started_at=1_000.0,
            owner="test capacity owner",
            approval_reference="test-only authorization",
        )

        self.assertEqual(PHASE, "acl-window-v3-b")
        self.assertEqual(OUT.as_posix(), "/private/tmp/q04-acl-window-20260917-v3-b")
        for path in (
            CAPACITY,
            RESERVATION,
            RELEASE,
            ADMISSION_EVIDENCE,
            ADMISSION_RESULT,
            RUNNER_DIR,
        ):
            self.assertIn("acl-window-v3-b", path)
            self.assertNotIn("acl-window-v3-a", path)

        absence_contract = remote_absence_paths()
        self.assertEqual(absence_contract["driver_lock_absent"], DRIVER_LOCK)
        self.assertEqual(DRIVER_LOCK, REMOTE + "/acl-window-v3-b.driver.lock")
        self.assertTrue(
            all("acl-window-v3-b" in path for path in absence_contract.values())
        )
        self.assertTrue(
            all("acl-window-v3-a" not in path for path in absence_contract.values())
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
        self.assertEqual(capacity["max_cgroup_bytes"], 3_221_225_472)
        self.assertEqual(capacity["max_full_psi"], 0)
        self.assertEqual(capacity["max_sample_gap_seconds"], 3)

    def test_workload_and_cleanup_reserve_remain_jointly_required(self):
        require_launch_budget(2_000.0, monotonic=lambda: 875.0)
        with self.assertRaisesRegex(RuntimeError, "insufficient workload"):
            require_launch_budget(2_000.0, monotonic=lambda: 875.1)

        command = build_runtime_command()
        self.assertIn("--kill-after=180s 825s", command)
        self.assertIn("--trial-seconds 180", command)
        self.assertIn("PYTHONSAFEPATH=1", command)
        self.assertIn("export PDF_QUALIFICATION_LOCK=" + DRIVER_LOCK, command)
        self.assertIn('test ! -e "$PDF_QUALIFICATION_LOCK"', command)
        self.assertNotIn("--phase init", command)

    def test_nested_shell_executes_preflight_then_reaches_runtime_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = (Path(directory) / "root with spaces").resolve()
            source = root / "code/src"
            runtime_dir = root / "code/tests/pdf_processing/q04"
            staged = root / "runner-acl-window-v3-b"
            for path in (source, runtime_dir, staged, root / "inputs", root / "state", root / "logs"):
                path.mkdir(parents=True, exist_ok=True)

            (source / "prepare.py").write_text(
                "from pathlib import Path\n"
                "def verify_bundle(path):\n"
                "    assert path.is_absolute()\n"
                "    (path.parent / 'verified-path.txt').write_text(str(path))\n"
            )
            (staged / "telemetry.py").write_text("ORIGIN = 'staged'\n")
            (runtime_dir / "telemetry.py").write_text("ORIGIN = 'frozen'\n")
            (runtime_dir / "q04_runtime.py").write_text(
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "import telemetry\n"
                "root = Path(sys.argv[sys.argv.index('--bundle') + 1]).parent\n"
                "(root / 'runtime-boundary.json').write_text(json.dumps({\n"
                "    'argv': sys.argv[1:], 'telemetry': telemetry.ORIGIN,\n"
                "    'driver_lock': os.environ['PDF_QUALIFICATION_LOCK']\n"
                "}, sort_keys=True))\n"
            )
            timeout = root / "timeout"
            timeout.write_text("#!/bin/sh\nshift 3\nexec \"$@\"\n")
            timeout.chmod(0o755)
            capacity = root / "capacity-acl-window-v3-b.json"
            capacity.write_text("{}\n")

            command = build_runtime_command(
                remote=str(root),
                capacity=str(capacity),
                python=sys.executable,
                timeout_program=str(timeout),
                driver_lock=str(root / "acl-window-v3-b.driver.lock"),
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
            self.assertEqual(
                reached["driver_lock"], str(root / "acl-window-v3-b.driver.lock")
            )
            self.assertEqual(
                reached["argv"],
                [
                    "--phase",
                    "matrix",
                    "--fixture",
                    "09",
                    "--bundle",
                    str(root / "inputs"),
                    "--state",
                    str(root / "state"),
                    "--capacity",
                    str(capacity),
                    "--name",
                    "acl-window-v3-b",
                    "--trial-seconds",
                    "180",
                    "--capacity-approved",
                ],
            )


if __name__ == "__main__":
    unittest.main()
