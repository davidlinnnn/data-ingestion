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
        for fixture_id in ("07", "08", "09", "10"):
            self.assertEqual(set(fixtures[fixture_id]["modes"].values()), {"proven"})
            self.assertEqual(fixtures[fixture_id]["q04_fresh_index"], "proven")
        self.assertEqual(fixtures["08"]["historical_reference"], "reusable")
        for fixture_id in ("native", "06"):
            self.assertEqual(set(fixtures[fixture_id]["modes"].values()), {"proven"})
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
        aima_attempt = fixtures["08"]["attempts"][-1]
        self.assertEqual(aima_attempt["phase"], "aima-pod-cgroup-q")
        self.assertEqual(aima_attempt["outcome"], "PASS_BOUNDED_FIXTURE_08_ONLY")
        self.assertEqual(aima_attempt["measurement"], "949_complete_samples")
        self.assertEqual(aima_attempt["retry_count"], 0)

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
        for gate in ("pod_drain_recovery", "supported_operating_bounds_report"):
            self.assertEqual(gates[gate]["status"], "unproven")
        self.assertEqual(gates["process_drain_recovery"]["status"], "proven")
        self.assertEqual(gates["continuation_and_four_algorithms"]["status"], "proven")
        self.assertEqual(gates["integrated_resource_bounds"]["status"], "proven")
        self.assertEqual(gates["six_fixture_matrix"]["status"], "proven")
        self.assertEqual(gates["warm_sequence"]["status"], "proven")
        self.assertEqual(gates["old_request_changed_profile_rejection"]["status"], "proven")
        self.assertEqual(gates["evidence_only_compatible_reuse"]["status"], "proven")
        self.assertEqual(gates["assembly_method_invalidation"]["status"], "proven")
        self.assertEqual(gates["required_relationship_interrupt_retry_replay"]["status"], "proven")
        self.assertEqual(gates["active_telemetry_loss_guard"]["status"], "proven")

    def test_next_step_preserves_pod_loss_boundary_and_no_retry(self):
        step = self.matrix['next_step']
        self.assertEqual(
            step['kind'], 'pod_drain_recovery'
        )
        self.assertFalse(step['runtime_started'])
        self.assertTrue(step['runtime_authorized'])
        self.assertFalse(step['automatic_retry'])
        self.assertTrue(step['keep_current_guard'])
        self.assertFalse(step['acceptance_standard_change'])
        self.assertTrue(step['unchanged_rerun_forbidden'])
        self.assertTrue((ROOT / step['evidence']).is_file())
        step = self.matrix['last_execution']
        self.assertEqual(
            step['runtime_result'],
            'PASS_NATIVE_WORKER_PROCESS_DRAIN_RECOVERY_ONLY',
        )
        self.assertEqual(step['run_identity'], 'q04-process-drain-pod-cgroup-20260925-be')
        self.assertEqual(step['business_pages'], 51)
        self.assertEqual(step['resource_samples'], 834)
        self.assertEqual(step['terminal_inventory_files'], 50)
        self.assertTrue(step['minio_trial_limit_restored'])
        self.assertFalse(step['automatic_retry'])
        self.assertTrue(step['keep_current_guard'])
        self.assertEqual(step['deployments_remain_closed'], 32)
        self.assertTrue(step['process_attribution_complete'])
        self.assertTrue(step['cgroup_resource_complete'])
        self.assertTrue(step['qualification_complete'])
        self.assertEqual(step['incomplete_sample_indexes'], [])
        for key in ('integration_manifest', 'offline_manifest', 'runner'):
            self.assertTrue((ROOT / step[key]).is_file())
        self.assertTrue((Q04 / 'pod-topology-v56/first-window-evidence/RESULTS.md').is_file())
        previous = self.matrix['previous_execution']
        self.assertEqual(previous['runtime_result'], 'PASS_ACTIVE_TELEMETRY_LOSS_GUARD_ONLY')
        self.assertEqual(previous['run_identity'], 'q04-telemetry-loss-pod-cgroup-20260925-au')

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

        self.assertIn('max_requests=1', document)
        self.assertIn('request20', document)
        self.assertIn('automatic retry', document.lower())


if __name__ == "__main__":
    unittest.main()
