"""Local filesystem fault injection for the dedicated Q04 evidence PVC protocol."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import pod_durable_evidence as durable


class PodDurableEvidenceTests(unittest.TestCase):
    def identity(self):
        return {
            "pvc_name": "q04-evidence",
            "pvc_uid": "claim-uid",
            "pv_name": "pvc-claim-uid",
            "pv_uid": "pv-uid",
            "node": "worker2",
            "run_as_uid": 1000,
            "run_as_gid": 1000,
            "fs_group": 1000,
            "automatic_delete": False,
        }

    def test_write_flush_fsync_terminal_commit_and_readback_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch(
                "pod_durable_evidence.os.fsync", wraps=durable.os.fsync
            ) as fsync:
                durable.write_once(
                    root / "record.json", {"value": 1}, volume_root=root
                )
                manifest = durable.seal(
                    root,
                    volume_identity=self.identity(),
                    workload_succeeded=True,
                    cleanup_complete=True,
                )
            self.assertGreaterEqual(fsync.call_count, 5)
            self.assertEqual(manifest["status"], "PASS_CANDIDATE")
            self.assertTrue((root / durable.TERMINAL_MANIFEST).is_file())
            self.assertEqual(
                durable.recover(root, self.identity())["inventory"],
                manifest["inventory"],
            )

    def test_missing_terminal_and_partial_file_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "record.json.incomplete").write_text("partial")
            self.assertEqual(
                durable.recover(root, self.identity()),
                {"status": "INCOMPLETE", "reason": "terminal_manifest_missing"},
            )
            with self.assertRaisesRegex(ValueError, "partial durable evidence"):
                durable.seal(
                    root,
                    volume_identity=self.identity(),
                    workload_succeeded=True,
                    cleanup_complete=True,
                )

    def test_full_volume_stops_before_new_record_is_written(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            full = {
                "requested_bytes": durable.PVC_REQUEST_BYTES,
                "evidence_used_bytes": durable.MAX_USED_BYTES,
                "evidence_free_bytes": durable.STOP_FREE_BYTES,
                "filesystem_free_bytes": durable.STOP_FREE_BYTES,
            }
            with mock.patch(
                "pod_durable_evidence.volume_capacity", return_value=full
            ):
                with self.assertRaisesRegex(
                    durable.EvidenceCapacityError, "stop watermark"
                ):
                    durable.write_once(
                        root / "overflow.json", {"value": "x"}, volume_root=root
                    )
            self.assertFalse((root / "overflow.json").exists())

    def test_readback_mismatch_and_missing_inventory_file_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            durable.write_once(root / "record.json", {"value": 1}, volume_root=root)
            durable.seal(
                root,
                volume_identity=self.identity(),
                workload_succeeded=True,
                cleanup_complete=True,
            )
            (root / "record.json").write_text(json.dumps({"value": 2}))
            with self.assertRaisesRegex(ValueError, "readback mismatch"):
                durable.recover(root, self.identity())
            (root / "record.json").unlink()
            with self.assertRaises(FileNotFoundError):
                durable.recover(root, self.identity())

    def test_recovery_fences_volume_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            durable.seal(
                root,
                volume_identity=self.identity(),
                workload_succeeded=True,
                cleanup_complete=True,
            )
            changed = {**self.identity(), "pvc_uid": "replacement"}
            with self.assertRaisesRegex(ValueError, "identity changed"):
                durable.recover(root, changed)


if __name__ == "__main__":
    unittest.main()
