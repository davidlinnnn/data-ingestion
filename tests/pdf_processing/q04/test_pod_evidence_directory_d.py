"""Filesystem contract tests for the Q04 run-owned evidence directory."""

import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

import pod_evidence_directory_d as evidence_directory


class PodEvidenceDirectoryDTests(unittest.TestCase):
    def identity(self):
        return os.getuid(), os.getgid()

    def test_creates_exclusive_0700_directory_and_proves_durable_io(self):
        uid, gid = self.identity()
        with tempfile.TemporaryDirectory() as directory:
            mount = Path(directory)
            mount.chmod(0o777)
            with mock.patch.object(
                evidence_directory,
                "_fsync_directory",
                wraps=evidence_directory._fsync_directory,
            ) as fsync_directory:
                result = evidence_directory.prepare_run_directory(
                    mount,
                    "q04-yolo-pod-cgroup-20260919-d",
                    expected_uid=uid,
                    expected_gid=gid,
                )
            run = mount / "q04-yolo-pod-cgroup-20260919-d"
            observed = os.lstat(run)
            self.assertTrue(stat.S_ISDIR(observed.st_mode))
            self.assertEqual(stat.S_IMODE(observed.st_mode), 0o700)
            self.assertEqual((observed.st_uid, observed.st_gid), (uid, gid))
            self.assertFalse((run / ".contract-probe").exists())
            self.assertEqual(result["directory"]["mode"], "0o700")
            self.assertTrue(result["durable_probe"]["atomic_rename"])
            self.assertTrue(result["durable_probe"]["readback_verified"])
            self.assertGreaterEqual(result["capacity"]["evidence_free_bytes"], 128 * 1024**2)
            self.assertEqual(fsync_directory.call_args_list[0].args[0], mount)
            self.assertGreaterEqual(fsync_directory.call_count, 3)

    def test_create_rejects_preexisting_directory_and_symlink(self):
        uid, gid = self.identity()
        for kind in ("directory", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                mount = Path(directory)
                target = mount / "q04-yolo-pod-cgroup-20260919-d"
                if kind == "directory":
                    target.mkdir(mode=0o700)
                else:
                    other = mount / "other"
                    other.mkdir()
                    target.symlink_to(other, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "already exists"):
                    evidence_directory.prepare_run_directory(
                        mount,
                        target.name,
                        expected_uid=uid,
                        expected_gid=gid,
                    )

    def test_inspection_rejects_symlink_wrong_owner_and_wrong_mode(self):
        uid, gid = self.identity()
        cases = ("symlink", "owner", "mode")
        for kind in cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                mount = Path(directory)
                run = mount / "q04-yolo-pod-cgroup-20260919-d"
                if kind == "symlink":
                    run.symlink_to(mount, target_is_directory=True)
                    message = "symlink"
                    expected_uid = uid
                else:
                    run.mkdir(mode=0o700)
                    expected_uid = uid + 1 if kind == "owner" else uid
                    message = "ownership" if kind == "owner" else "mode"
                    if kind == "mode":
                        run.chmod(0o750)
                process_uid = (
                    mock.patch(
                        "pod_evidence_directory_d.os.getuid",
                        return_value=expected_uid,
                    )
                    if kind == "owner"
                    else mock.patch(
                        "pod_evidence_directory_d.os.getuid", return_value=uid
                    )
                )
                with process_uid, self.assertRaisesRegex(ValueError, message):
                    evidence_directory.inspect_run_directory(
                        mount,
                        run.name,
                        expected_uid=expected_uid,
                        expected_gid=gid,
                    )

    def test_rejects_unsafe_name_and_symlink_mount_root(self):
        uid, gid = self.identity()
        with tempfile.TemporaryDirectory() as directory:
            mount = Path(directory)
            with self.assertRaisesRegex(ValueError, "single safe path segment"):
                evidence_directory.prepare_run_directory(
                    mount, "../escape", expected_uid=uid, expected_gid=gid
                )
            real = mount / "real"
            real.mkdir()
            link = mount / "link"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "mount root.*symlink"):
                evidence_directory.prepare_run_directory(
                    link,
                    "q04-yolo-pod-cgroup-20260919-d",
                    expected_uid=uid,
                    expected_gid=gid,
                )

    def test_rejects_foreign_entries_in_new_or_recovery_mount(self):
        uid, gid = self.identity()
        with tempfile.TemporaryDirectory() as directory:
            mount = Path(directory)
            (mount / "foreign").write_text("unexpected")
            with self.assertRaisesRegex(ValueError, "foreign entries"):
                evidence_directory.prepare_run_directory(
                    mount,
                    "q04-yolo-pod-cgroup-20260919-d",
                    expected_uid=uid,
                    expected_gid=gid,
                )
        with tempfile.TemporaryDirectory() as directory:
            mount = Path(directory)
            run = mount / "q04-yolo-pod-cgroup-20260919-d"
            run.mkdir(mode=0o700)
            (mount / "foreign").write_text("unexpected")
            with self.assertRaisesRegex(ValueError, "foreign entries"):
                evidence_directory.inspect_run_directory(
                    mount,
                    run.name,
                    expected_uid=uid,
                    expected_gid=gid,
                )


if __name__ == "__main__":
    unittest.main()
