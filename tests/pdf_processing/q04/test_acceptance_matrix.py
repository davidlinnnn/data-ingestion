import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
Q04 = ROOT / "tests/pdf_processing/q04"


class CurrentAcceptanceMatrixTest(unittest.TestCase):
    def setUp(self):
        self.matrix = json.loads(
            (Q04 / "evidence/current-acceptance-matrix.json").read_text()
        )
        self.fixtures = json.loads((Q04 / "fixtures.json").read_text())

    def test_fixture_inventory_and_scopes_match_fixed_manifest(self):
        expected = {row["id"]: row for row in self.fixtures}
        actual = {row["id"]: row for row in self.matrix["fixtures"]}
        self.assertEqual(set(actual), {"native", "06", "07", "08", "09", "10"})
        self.assertEqual(set(actual), set(expected))
        for fixture_id, row in actual.items():
            fixed = expected[fixture_id]
            self.assertEqual(row["pages"], len(fixed["original_pages"]))
            self.assertEqual(row["source_sha256"], fixed["sha256"])
            self.assertEqual(set(row["modes"]), {"fresh", "restored", "replay"})

    def test_direct_reusable_and_unrun_runtime_evidence_stay_distinct(self):
        fixtures = {row["id"]: row for row in self.matrix["fixtures"]}
        for fixture_id in ("09", "10"):
            self.assertEqual(set(fixtures[fixture_id]["modes"].values()), {"proven"})
            self.assertEqual(fixtures[fixture_id]["q04_fresh_index"], "proven")
        self.assertEqual(set(fixtures["08"]["modes"].values()), {"unproven"})
        self.assertEqual(fixtures["08"]["q04_fresh_index"], "unproven")
        self.assertEqual(fixtures["08"]["historical_reference"], "reusable")
        for fixture_id in ("native", "06", "07"):
            self.assertEqual(set(fixtures[fixture_id]["modes"].values()), {"unproven"})
        yolo_attempt = fixtures["07"]["attempts"][0]
        self.assertEqual(yolo_attempt["outcome"], "failed_cgroup_guard")
        self.assertEqual(yolo_attempt["fresh"], "failed_before_complete_delivery")
        self.assertEqual(yolo_attempt["restored"], "not_run")
        self.assertEqual(yolo_attempt["replay"], "not_run")
        self.assertEqual(yolo_attempt["cleanup"], "proven")
        self.assertEqual(yolo_attempt["retry_count"], 0)
        attribution_attempt = fixtures["07"]["attempts"][1]
        self.assertEqual(attribution_attempt["phase"], "yolo-attribution-b")
        self.assertEqual(
            attribution_attempt["outcome"],
            "fresh_cgroup_guard_attributed_measurement_incomplete",
        )
        self.assertEqual(
            attribution_attempt["measurement"],
            "incomplete_missing_cancel_requested_callback",
        )
        self.assertEqual(attribution_attempt["fresh"], "failed_before_complete_delivery")
        self.assertEqual(attribution_attempt["restored"], "not_run")
        self.assertEqual(attribution_attempt["replay"], "not_run")
        self.assertEqual(attribution_attempt["cleanup"], "proven")
        self.assertEqual(attribution_attempt["retry_count"], 0)
        lifecycle_attempt = fixtures["07"]["attempts"][2]
        self.assertEqual(lifecycle_attempt["phase"], "yolo-lifecycle-a")
        self.assertEqual(
            lifecycle_attempt["outcome"],
            "fresh_processing_complete_failed_graph_gate",
        )
        self.assertEqual(
            lifecycle_attempt["source_review"],
            "two_source_preserving_splits_explain_full_graph_delta",
        )
        self.assertEqual(
            lifecycle_attempt["local_oracle_proposal"],
            "inactive_pending_main_review",
        )
        self.assertEqual(lifecycle_attempt["restored"], "not_run")
        self.assertEqual(lifecycle_attempt["replay"], "not_run")
        self.assertEqual(lifecycle_attempt["cleanup"], "proven")
        self.assertEqual(lifecycle_attempt["retry_count"], 0)

    def test_release_gate_statuses_and_evidence_are_reviewable(self):
        allowed = set(self.matrix["status_definitions"])
        gates = {row["id"]: row for row in self.matrix["release_gates"]}
        self.assertEqual(len(gates), len(self.matrix["release_gates"]))
        for row in self.matrix["fixtures"] + self.matrix["release_gates"]:
            statuses = row.get("modes", {}).values()
            for status in [row.get("status"), row.get("q04_fresh_index"), row.get("oracle_and_full_graph"), *statuses]:
                if status is not None:
                    self.assertIn(status, allowed)
            for evidence in row["evidence"]:
                self.assertTrue((ROOT / evidence).is_file(), evidence)
        for gate in (
            "six_fixture_matrix",
            "assembly_method_invalidation",
            "warm_sequence",
            "integrated_resource_bounds",
            "active_telemetry_loss_guard",
            "process_drain_recovery",
            "pod_drain_recovery",
            "supported_operating_bounds_report",
        ):
            self.assertEqual(gates[gate]["status"], "unproven")

    def test_next_step_is_reviewed_candidate_window_not_runtime_authorization(self):
        step = self.matrix["next_step"]
        self.assertEqual(
            step["kind"], "authorize_reviewed_yolo_candidate_window_after_commit_review"
        )
        self.assertEqual(step["fixture"], "07")
        self.assertEqual(step["runtime_result"], "FAIL_GRAPH_AND_RESOURCE_GATES")
        self.assertEqual(step["candidate_status"], "REVIEWED_INACTIVE")
        self.assertTrue((ROOT / step["diagnosis"]).is_file())
        self.assertTrue((ROOT / step["resource_decision"]).is_file())
        self.assertTrue((ROOT / step["equivalence_candidate"]).is_file())
        self.assertTrue((ROOT / step["resource_candidate"]).is_file())
        self.assertTrue((ROOT / step["integration_manifest"]).is_file())
        self.assertTrue((ROOT / step["offline_manifest"]).is_file())
        self.assertTrue((ROOT / step["runner"]).is_file())
        self.assertFalse(step["runtime_authorized"])
        self.assertFalse(step["automatic_retry"])
        self.assertFalse(step["requires_main_disposition"])
        self.assertTrue(step["requires_new_runtime_authorization"])
        self.assertTrue(step["single_execution"])
        self.assertEqual(step["parser_max_requests"], 1)
        self.assertFalse(step["other_fixture_policy_inherited"])
        self.assertTrue(step["keep_current_guard"])
        self.assertTrue(step["all_complete_sample_gate"])
        self.assertTrue(step["historical_failure_preserved"])
        self.assertTrue(step["historical_reference_unchanged"])
        self.assertEqual(step["deployments_remain_closed"], 32)

    def test_human_matrix_and_next_step_match_machine_authority(self):
        document = (Q04 / "CURRENT-ACCEPTANCE-MATRIX.md").read_text()
        fixture_rows = {}
        names = {
            "native": "native",
            "WikiSkill `06`": "06",
            "YOLO `07`": "07",
            "AIMA `08`": "08",
            "ACL `09`": "09",
            "Keynote `10`": "10",
        }
        for line in document.splitlines():
            if not line.startswith("|"):
                continue
            columns = [column.strip().strip("*") for column in line.strip("|").split("|")]
            if columns[0] in names:
                fixture_rows[names[columns[0]]] = columns
        self.assertEqual(set(fixture_rows), set(names.values()))
        for fixture in self.matrix["fixtures"]:
            row = fixture_rows[fixture["id"]]
            self.assertEqual(row[2:5], list(fixture["modes"].values()))
            self.assertEqual(row[5], fixture["oracle_and_full_graph"])
            self.assertEqual(row[6], fixture["q04_fresh_index"])

        step = self.matrix["next_step"]
        diagnosis = (ROOT / step["diagnosis"]).read_text()
        resource = (ROOT / step["resource_decision"]).read_text()
        self.assertIn("FAIL_GRAPH_GATE", diagnosis)
        self.assertIn("PROPOSAL_NOT_ACTIVE", diagnosis)
        self.assertIn("4,403,523,584", diagnosis)
        self.assertIn("FAIL_RESOURCE_GATE", resource)
        self.assertIn("max_requests=20", resource)
        self.assertIn("post-cleanup", resource)
        self.assertIn("automatic retry", document.lower())


if __name__ == "__main__":
    unittest.main()
