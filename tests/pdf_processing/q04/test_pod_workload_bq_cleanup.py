"""Interrupted cleanup must preserve an incomplete marker instead of crashing."""

import json
from pathlib import Path
import tempfile
import unittest

import pod_workload_bq as bq
import pod_remote_evidence_bq as evidence
from sentinel import run_warm_pod_cgroup_bq as outer


class BQCleanupTest(unittest.TestCase):
    def test_interrupted_worker_without_stop_marker(self):
        self.assertIs(bq.base.run.__globals__["cleanup_markers"], bq.cleanup_markers)
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            self.assertFalse(bq.cleanup_markers(state)["worker_absent"])
            phase = state / bq.PHASE
            worker = phase / "worker-1"
            worker.mkdir(parents=True)
            (phase / "worker-1.log").write_text("interrupted")

            incomplete = bq.cleanup_markers(state)
            self.assertEqual(incomplete["worker_generations"], 1)
            self.assertEqual(incomplete["missing_stopped_markers"], ["worker-1"])
            self.assertFalse(incomplete["worker_absent"])
            self.assertFalse(incomplete["owned_children_absent"])
            self.assertFalse(incomplete["scratch_absent"])
            control = state / "control"
            control.mkdir()
            (control / "cleanup-complete.json").write_text(json.dumps(incomplete))
            (control / "evidence-volume-identity.json").write_text("{}")
            self.assertEqual(
                bq.base.run.__globals__["seal_terminal"](control, returncode=1)["status"],
                "INCOMPLETE",
            )

            (worker / "stopped.json").write_text(json.dumps({
                "parser_absent": True, "scratch_absent": True,
            }))
            complete = bq.cleanup_markers(state)
            self.assertEqual(complete["missing_stopped_markers"], [])
            self.assertTrue(complete["worker_absent"])

    def test_failed_evidence_export_accepts_incomplete_cleanup_only_as_failure(self):
        boundary = outer.adapted_window.__globals__["failure_export_boundary"]
        self.assertIs(boundary, outer.failure_export_boundary)
        self.assertFalse(boundary({"supervisor_absent": True, "cleanup_complete": False}, False))
        self.assertTrue(boundary({"supervisor_absent": True, "cleanup_complete": True}, False))
        with self.assertRaisesRegex(ValueError, "supervisor remains"):
            boundary({"supervisor_absent": False, "cleanup_complete": True}, False)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "workload-exit.json").write_text('{"returncode": 1}')
            (root / "cleanup-complete.json").write_text(json.dumps({
                "worker_absent": False,
                "owned_children_absent": False,
                "scratch_absent": False,
            }))
            bq.base.seal(root, volume_identity={}, workload_succeeded=False,
                         cleanup_complete=False)
            identity = evidence.PodEvidenceIdentity("pod", "container", 1, 1, "config")
            mirror = evidence.IncrementalEvidenceMirror(root, identity)
            mirror.remote_sizes = {
                p.relative_to(root).as_posix(): p.stat().st_size
                for p in root.rglob("*") if p.is_file()
            }
            mirror.complete = set(mirror.remote_sizes)
            with self.assertRaises(ValueError):
                mirror.finalize(require_success=True)
            self.assertEqual(
                mirror.finalize(require_success=False)["status"],
                "FAILURE_EVIDENCE_RETAINED",
            )


if __name__ == "__main__":
    unittest.main()
