"""Offline tests for the immutable YOLO matrix A diagnosis."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("yolo_matrix_a_trace", HERE / "analyze_trace.py")
assert SPEC and SPEC.loader
TRACE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRACE)


@unittest.skipUnless(
    TRACE.DEFAULT_EVIDENCE.exists() and TRACE.DEFAULT_ACL_RESOURCE.exists(),
    "private immutable runtime evidence is not present",
)
class CapturedTrace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = TRACE.summarize()

    def test_reproduces_guard_stop_during_assembly(self):
        result = self.result
        self.assertEqual(result["verdict"], "RED_CGROUP_GUARD_DURING_ASSEMBLY")
        self.assertGreater(
            result["guard"]["sampled_maximum_bytes"],
            result["guard"]["ceiling_bytes"],
        )
        self.assertTrue(result["guard"]["censored_at_guard_stop"])
        self.assertTrue(result["guard"]["sampled_maximum_after_cancel_request"])
        self.assertFalse(result["guard"]["counterfactual_uncensored_peak_bounded"])
        self.assertFalse(result["guard"]["sampled_maximum_is_required_limit"])
        self.assertEqual(result["timeline"]["last_progress_status"], "assembling")
        self.assertFalse(result["timeline"]["processing_complete"])

    def test_committed_analysis_matches_offline_replay(self):
        committed = json.loads((HERE / "evidence/trace-analysis.json").read_text())
        self.assertEqual(committed, self.result)

    def test_parser_count_and_stage_are_not_process_or_current_stage(self):
        semantics = self.result["parser_semantics"]
        self.assertEqual(semantics["warm_parser_pids"], [2327])
        self.assertEqual(len(semantics["warm_parser_request_ids"]), 3)
        self.assertEqual(semantics["maximum_parser_count"], 3)
        self.assertFalse(semantics["parser_count_is_process_count"])
        self.assertTrue(semantics["assembly_restore_would_use_fresh_child_if_invoked"])
        self.assertFalse(semantics["fresh_child_spawn_observed"])
        self.assertTrue(semantics["sampled_stage_is_stale_during_assembly"])
        self.assertIn(
            "whether and when assembly spawned a fresh restore child",
            self.result["cause_boundary"]["unresolved"],
        )

    def test_cancel_and_cleanup_boundaries_are_distinct(self):
        timeline = self.result["timeline"]
        self.assertGreater(
            timeline["cleanup_started_at"],
            TRACE.epoch(timeline["workflow_cancel_requested_at"]),
        )

    def test_trace_does_not_claim_exclusive_attribution_or_sizing(self):
        scope = self.result["resource_scope"]
        self.assertTrue(scope["warm_parser_lifetime_peak_rss_present"])
        self.assertFalse(scope["synchronized_current_process_rss_or_pss_present"])
        self.assertFalse(scope["memory_stat_present"])
        self.assertFalse(scope["post_cleanup_memory_sample_present"])
        self.assertFalse(scope["exclusive_owner_attribution_supported"])
        self.assertFalse(self.result["recommendation"]["raise_guard_from_this_trace"])

    def test_acl_comparison_retains_its_attribution_boundary(self):
        comparison = self.result["acl_comparison"]
        acl = comparison["acl_fixture_09_attribution_trace"]
        yolo = comparison["yolo_fixture_07_guard_trace"]
        self.assertIsNotNone(acl["owned_pss_at_peak_bytes"])
        self.assertIsNotNone(acl["cleanup_cgroup_bytes"])
        self.assertIsNone(yolo["owned_pss_at_peak_bytes"])
        self.assertIsNone(yolo["cleanup_cgroup_bytes"])

    def test_guard_and_attribution_requirements_are_deterministically_red(self):
        for flag, signal in (
            ("--require-within-guard", "RED_CGROUP_GUARD_DURING_ASSEMBLY"),
            ("--require-exclusive-attribution", "ATTRIBUTION_INCOMPLETE"),
        ):
            with self.subTest(flag=flag):
                completed = subprocess.run(
                    [sys.executable, str(HERE / "analyze_trace.py"), flag],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 1)
                self.assertIn(signal, completed.stderr)

    def test_tampered_top_level_artifact_is_rejected_even_with_optimization(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "evidence"
            shutil.copytree(TRACE.DEFAULT_EVIDENCE, copied)
            capacity = json.loads((copied / "capacity.json").read_text())
            capacity["max_cgroup_bytes"] += 1
            (copied / "capacity.json").write_text(json.dumps(capacity))
            completed = subprocess.run(
                [
                    sys.executable,
                    "-O",
                    str(HERE / "analyze_trace.py"),
                    "--evidence-root",
                    str(copied),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("artifact hash mismatch: capacity.json", completed.stderr)


if __name__ == "__main__":
    unittest.main()
