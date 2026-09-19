"""Local transport and integrity tests for Pod evidence mirroring."""

import base64
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from pod_remote_evidence import (
    FINAL_REQUIRED,
    IncrementalEvidenceMirror,
    PodEvidenceIdentity,
    sha256,
    snapshot_program,
)


def envelope(sequence, rows, identity=None):
    files = []
    for path, offset, raw in rows:
        files.append(
            {
                "path": path,
                "offset": offset,
                "size": len(raw),
                "total_size": offset + len(raw),
                "eof": True,
                "sha256": sha256(raw),
                "data": base64.b64encode(raw).decode(),
            }
        )
    identity = identity or PodEvidenceIdentity(
        "pod-uid", "container-id", 42, 99, "a" * 64
    )
    return {
        "schema_version": 1,
        "sequence": sequence,
        "identity": identity.__dict__,
        "process_state": "live",
        "files": files,
    }


class PodRemoteEvidenceTests(unittest.TestCase):
    def identity(self):
        return PodEvidenceIdentity("pod-uid", "container-id", 42, 99, "a" * 64)

    def test_incremental_stream_is_exact_and_identity_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            mirror = IncrementalEvidenceMirror(Path(directory), self.identity())
            name = "state/yolo-pod-cgroup-a-measurement/resource-attribution.jsonl"
            first = b'{"sample":1}\n'
            second = b'{"sample":2}\n'
            one = mirror.ingest(envelope(1, [(name, 0, first)]), received_at=10)
            two = mirror.ingest(
                envelope(2, [(name, len(first), second)]), received_at=12
            )
            self.assertEqual((Path(directory) / name).read_bytes(), first + second)
            self.assertEqual(one["pod_uid"], "pod-uid")
            self.assertEqual(two["worker_start_ticks"], 99)
            combined = first + second
            mirror.verify_archive_fingerprint(
                [[name, len(combined), sha256(combined)]]
            )
            with self.assertRaisesRegex(ValueError, "digest"):
                mirror.verify_archive_fingerprint(
                    [[name, len(combined), "0" * 64]]
                )

    def test_sequence_offset_hash_partial_record_and_gap_fail_closed(self):
        cases = []
        cases.append(envelope(2, []))
        wrong_identity = envelope(1, [])
        wrong_identity["identity"]["config_sha256"] = "b" * 64
        cases.append(wrong_identity)
        cases.append(envelope(1, [("x", 1, b"a")]))
        bad_hash = envelope(1, [("x", 0, b"a")])
        bad_hash["files"][0]["sha256"] = "0" * 64
        cases.append(bad_hash)
        partial = envelope(
            1,
            [("state/yolo-pod-cgroup-a-measurement/resource-attribution.jsonl", 0, b"{}")],
        )
        cases.append(partial)
        for value in cases:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                mirror = IncrementalEvidenceMirror(Path(directory), self.identity())
                with self.assertRaises(ValueError):
                    mirror.ingest(value, received_at=10)
        with tempfile.TemporaryDirectory() as directory:
            mirror = IncrementalEvidenceMirror(Path(directory), self.identity())
            mirror.ingest(envelope(1, []), received_at=10)
            with self.assertRaisesRegex(ValueError, "gap"):
                mirror.ingest(envelope(2, []), received_at=16)

    def test_remote_file_cannot_disappear_after_reaching_eof(self):
        with tempfile.TemporaryDirectory() as directory:
            mirror = IncrementalEvidenceMirror(Path(directory), self.identity())
            mirror.ingest(envelope(1, [("workload-exit.json", 0, b"{}\n")]), received_at=10)
            with self.assertRaisesRegex(ValueError, "disappeared"):
                mirror.ingest(envelope(2, []), received_at=11)

    def test_finalize_requires_success_and_cleanup_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mirror = IncrementalEvidenceMirror(root, self.identity())
            rows = []
            required = {
                "state/yolo-pod-cgroup-a/phase-complete.json": {},
                "state/yolo-pod-cgroup-a/reviewed-window-contract.json": {},
                "state/yolo-pod-cgroup-a-measurement/resource-attribution-summary.json": {},
                "state/yolo-pod-cgroup-a-measurement/measurement-contract.json": {
                    "workload_succeeded": True,
                    "qualification_complete": True,
                    "cgroup_resource_complete": True,
                },
                "workload-exit.json": {"returncode": 0},
                "cleanup-complete.json": {
                    "worker_absent": True,
                    "owned_children_absent": True,
                    "scratch_absent": True,
                },
            }
            for name in FINAL_REQUIRED:
                required.setdefault(name, {})
            for name, value in required.items():
                raw = (json.dumps(value) + "\n").encode()
                rows.append((name, 0, raw))
            mirror.ingest(envelope(1, rows), received_at=10)
            self.assertEqual(mirror.finalize(require_success=True)["status"], "PASS")

    def test_snapshot_program_is_read_only_and_caps_chunks(self):
        program = snapshot_program("/q04-control", {"a": 4}, 8, self.identity())
        self.assertIn("stream.read(4*1024*1024)", program)
        self.assertIn("path.is_symlink()", program)
        self.assertNotIn("unlink(", program)
        self.assertNotIn("write_bytes", program)
        self.assertIn("transport-identity.json", program)
        self.assertIn("name.startswith('inputs/')", program)

    def test_supervisor_exit_is_verified_by_terminal_markers_during_final_drain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = PodEvidenceIdentity(
                "pod-uid", "container-id", 99_999_999, 123, "a" * 64
            )
            (root / "transport-identity.json").write_text(
                json.dumps(identity.__dict__, sort_keys=True)
            )
            (root / "supervisor-ownership.json").write_text(
                json.dumps({"pid": identity.worker_pid, "start_ticks": 123})
            )
            (root / "ownership.json").write_text(
                json.dumps({"config_sha256": identity.config_sha256})
            )
            (root / "state").mkdir()
            (root / "state/config.json").write_bytes(b"fixed-config")
            identity = PodEvidenceIdentity(
                identity.pod_uid,
                identity.container_id,
                identity.worker_pid,
                identity.worker_start_ticks,
                sha256(b"fixed-config"),
            )
            (root / "transport-identity.json").write_text(
                json.dumps(identity.__dict__, sort_keys=True)
            )
            (root / "ownership.json").write_text(
                json.dumps({"config_sha256": identity.config_sha256})
            )
            (root / "workload-exit.json").write_text("{}\n")
            (root / "cleanup-complete.json").write_text("{}\n")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(snapshot_program(str(root), {}, 1, identity), {})
            value = json.loads(output.getvalue())
            self.assertEqual(value["process_state"], "confirmed_absent_terminal")
            (root / "state/config.json").write_bytes(b"drift")
            with self.assertRaisesRegex(ValueError, "live transport identity changed"):
                exec(snapshot_program(str(root), {}, 2, identity), {})
            (root / "state/config.json").write_bytes(b"fixed-config")
            (root / "unexpected-private.bin").write_bytes(b"private")
            with self.assertRaisesRegex(ValueError, "unexpected evidence path"):
                exec(snapshot_program(str(root), {}, 2, identity), {})

    def test_required_file_larger_than_one_chunk_cannot_finalize_truncated(self):
        with tempfile.TemporaryDirectory() as directory:
            mirror = IncrementalEvidenceMirror(Path(directory), self.identity())
            name = "workload-exit.json"
            first = b"x" * (4 * 1024 * 1024)
            value = envelope(1, [(name, 0, first)])
            value["files"][0]["total_size"] = len(first) + 1
            value["files"][0]["eof"] = False
            mirror.ingest(value, received_at=10)
            with self.assertRaisesRegex(ValueError, "incomplete"):
                mirror.finalize(require_success=False)
            mirror.ingest(envelope(2, [(name, len(first), b"\n")]), received_at=11)
            self.assertEqual(
                mirror.finalize(require_success=False)["status"],
                "FAILURE_EVIDENCE_RETAINED",
            )


if __name__ == "__main__":
    unittest.main()
