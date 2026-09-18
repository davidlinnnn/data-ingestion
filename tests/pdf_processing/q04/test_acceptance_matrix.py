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
        self.assertEqual(set(fixtures["08"]["modes"].values()), {"reusable"})
        self.assertEqual(fixtures["08"]["q04_fresh_index"], "unproven")
        for fixture_id in ("native", "06", "07"):
            self.assertEqual(set(fixtures[fixture_id]["modes"].values()), {"unproven"})

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

    def test_next_batch_is_one_unrun_fixture_and_does_not_repeat_passes(self):
        batch = self.matrix["next_batch"]
        self.assertEqual(batch["fixture"], "07")
        self.assertEqual(batch["pages"], 15)
        self.assertEqual(batch["modes"], ["fresh", "restored", "replay"])
        self.assertEqual(batch["execution_mode"], "process")
        self.assertTrue((ROOT / batch["plan"]).is_file())

    def test_human_matrix_and_batch_plan_match_machine_authority(self):
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

        plan = (ROOT / self.matrix["next_batch"]["plan"]).read_text()
        batch = self.matrix["next_batch"]
        for field in (
            "source_sha256",
            "bundle_path",
            "bundle_sha256",
            "reference_sha256",
            "runner_sha256",
            "launcher_path",
            "launcher_sha256",
            "source_runtime_root",
            "source_state_sha256",
            "source_prefix",
            "remote_root",
            "prefix",
            "phase",
            "local_evidence",
        ):
            self.assertIn(str(batch[field]), plan, field)
        for field, expected, phrase in (
            ("window_seconds", 1500, "1,500-second lease"),
            ("outer_observation_seconds", 180, "at most 180 seconds"),
            ("outer_continuous_seconds", 60, "60 continuous seconds"),
            ("workload_seconds", 825, "825 seconds"),
            ("cleanup_seconds", 300, "300 seconds"),
        ):
            self.assertEqual(batch[field], expected)
            self.assertIn(phrase, plan)


if __name__ == "__main__":
    unittest.main()
