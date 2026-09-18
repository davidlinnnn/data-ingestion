"""Regression tests for the offline reconciliation and YOLO preflight."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from preflight import yolo_offline_preflight as yolo_preflight
from reconciliation.reconcile_aima_identity import build_report as build_aima_report
from reconciliation.reconcile_drain import build_report as build_drain_report
from sentinel import run_yolo_matrix_a as yolo_runner


Q04 = Path(__file__).resolve().parent
REPO = Q04.parents[2]


class ReconciliationPreflightTests(unittest.TestCase):
    def test_aima_report_keeps_q03_reference_but_q04_runtime_rows_open(self):
        report = json.loads(
            (Q04 / "reconciliation/evidence/aima-identity.json").read_text()
        )
        comparison = report["comparison"]
        self.assertTrue(comparison["fixture"]["identity_equal"])
        self.assertEqual(
            comparison["fixture"]["q03_sha256"],
            comparison["fixture"]["q04_sha256"],
        )
        self.assertTrue(comparison["source"]["equal_bytes"])
        self.assertTrue(comparison["producer"]["equal"])
        self.assertEqual(comparison["producer"]["file_count"], 20)
        self.assertTrue(comparison["method"]["equal"])
        self.assertTrue(comparison["policy"]["relationship_policy_equal"])
        self.assertFalse(comparison["profile"]["equal"])
        self.assertEqual(comparison["profile"]["q03_review_count"], 6)
        self.assertEqual(comparison["profile"]["q04_review_count"], 1)
        self.assertFalse(comparison["oracle"]["identity_equal"])
        self.assertTrue(all(comparison["oracle"]["shared_component_equality"].values()))
        self.assertEqual(
            comparison["oracle"]["q04_only_components"],
            ["continuation-oracle.json", "reference-08.json"],
        )
        self.assertFalse(comparison["test"]["identity_equal"])
        self.assertTrue(all(comparison["test"]["shared_file_equality"].values()))
        decision = report["decision"]
        self.assertEqual(set(decision["q04_modes"].values()), {"unproven"})
        self.assertFalse(decision["q03_registrations_may_be_copied"])
        self.assertFalse(decision["q03_request_may_be_called_q04_fresh"])
        self.assertFalse(decision["q04_fresh_index_satisfied"])
        self.assertTrue(decision["historical_reference_reuse_preconditions_met"])

    def test_aima_report_is_reproducible_from_retained_inputs_when_present(self):
        q03 = Path("/private/tmp/q03-results-20260916-a/fresh/accepted.json")
        q03_manifest = REPO / "tests/pdf_processing/q03/evidence/manifest.json"
        config = Path("/private/tmp/q04-acl-option-a-window-c-review/state/config.json")
        bundle = Path("/private/tmp/q04-inputs-option-a-v7/inputs.json")
        if not all(path.exists() for path in (q03, q03_manifest, config, bundle)):
            self.skipTest("private retained AIMA inputs are not present")
        actual = build_aima_report(
            json.loads(q03.read_text()),
            json.loads(q03_manifest.read_text()),
            json.loads(config.read_text()),
            json.loads(bundle.read_text()),
        )
        committed = json.loads(
            (Q04 / "reconciliation/evidence/aima-identity.json").read_text()
        )
        self.assertEqual(actual["comparison"], committed["comparison"])
        self.assertEqual(actual["decision"], committed["decision"])

    def test_aima_reuse_claim_is_removed_when_an_exact_identity_drifts(self):
        q03 = Path("/private/tmp/q03-results-20260916-a/fresh/accepted.json")
        q03_manifest = REPO / "tests/pdf_processing/q03/evidence/manifest.json"
        config = Path("/private/tmp/q04-acl-option-a-window-c-review/state/config.json")
        bundle = Path("/private/tmp/q04-inputs-option-a-v7/inputs.json")
        if not all(path.exists() for path in (q03, q03_manifest, config, bundle)):
            self.skipTest("private retained AIMA inputs are not present")
        retained = (
            json.loads(q03.read_text()),
            json.loads(q03_manifest.read_text()),
            json.loads(config.read_text()),
            json.loads(bundle.read_text()),
        )

        def shared_test_drift(q03_record, manifest, q04_config, q04_bundle):
            manifest["files"]["tests/pdf_processing/q02/oracle/score.py"] = "0" * 64

        def base_profile_drift(q03_record, manifest, q04_config, q04_bundle):
            q04_config["profiles"]["08"]["version"] += 1

        def pages_drift(q03_record, manifest, q04_config, q04_bundle):
            source = q03_record["request"]["artifact"]["sha256"]
            replacement = {str(index): index for index in range(1, 13)}
            q03_record["profile"]["content_evidence"]["reviews"][source][
                "original_pages"
            ] = replacement
            q04_config["profiles"]["08"]["content_evidence"]["reviews"][source][
                "original_pages"
            ] = replacement

        def source_revision_drift(q03_record, manifest, q04_config, q04_bundle):
            fixture = next(row for row in q04_bundle["fixtures"] if row["id"] == "08")
            fixture["source_revision"] = "drifted.pdf"
            source = q03_record["request"]["artifact"]["sha256"]
            q04_config["profiles"]["08"]["content_evidence"]["reviews"][source][
                "original_source"
            ]["source_revision"] = "drifted.pdf"

        for drift in (
            shared_test_drift,
            base_profile_drift,
            pages_drift,
            source_revision_drift,
        ):
            with self.subTest(drift=drift.__name__):
                inputs = copy.deepcopy(retained)
                drift(*inputs)
                report = build_aima_report(*inputs)
                self.assertFalse(
                    report["decision"]["historical_reference_reuse_preconditions_met"]
                )
                self.assertEqual(report["decision"]["reusable"], [])

    def test_drain_projection_requires_integrated_pod_requalification(self):
        report = json.loads(
            (Q04 / "reconciliation/evidence/drain-requalification.json").read_text()
        )
        self.assertTrue(report["stage_impact"]["all_delivery_stages_affected"])
        self.assertEqual(
            set(report["stage_impact"]["changed_stages"]),
            {"group", "assembly", "selection", "ocr", "evidence", "finalize"},
        )
        self.assertEqual(report["r3_evidence"]["status"], "supporting_method_and_topology_only")
        self.assertFalse(report["process_mode"]["pod_loss_claim"])
        self.assertEqual(report["pod_mode"]["status"], "unqualified")
        self.assertTrue(report["decision"]["issue_51_gate_remains_open"])
        self.assertFalse(report["decision"]["pod_gate_reassigned_to_issue_46"])

    def test_drain_report_is_reproducible_and_hash_binds_r3_evidence(self):
        audit_path = Q04 / "evidence/static-audit-v2.json"
        paths = {
            "r3_controller": REPO / "tests/pdf_processing/t09a_r3/evidence/20260914-0b537d0-c/drain-native-resume-controller.json",
            "r3_matrix": REPO / "tests/pdf_processing/t09a_r3/evidence/20260914-0b537d0-c/matrix.json",
            "integration_review": REPO / "tests/pdf_processing/T09A-R3-INTEGRATION.md",
        }
        actual = build_drain_report(json.loads(audit_path.read_text()), evidence_paths=paths)
        committed = json.loads(
            (Q04 / "reconciliation/evidence/drain-requalification.json").read_text()
        )
        self.assertEqual(actual, committed)

    def test_retained_acl_final_exactly_drives_generated_old_binding(self):
        snapshot = Path("/private/tmp/q04-acl-option-a-window-c-review")
        if not snapshot.exists():
            self.skipTest("retained ACL snapshot is not present")
        accepted, objects = yolo_preflight.retained_acl_store(snapshot)
        operation = accepted["result"]["processing_result"]
        artifact = next(value for key, value in objects.items() if "/attempts/" in key)
        self.assertEqual("pdf-complete-v1:" + hashlib.sha256(artifact).hexdigest(), operation)
        with tempfile.TemporaryDirectory() as directory:
            result = yolo_preflight.run_old_binding(snapshot, Path(directory))
        self.assertEqual(result["request_id"], accepted["request"]["request_id"])
        self.assertTrue(result["source_key"].endswith("/sources/09.pdf"))
        self.assertTrue(result["registration_key"].startswith(yolo_runner.SOURCE_PREFIX))

    def test_fixed_yolo_launcher_and_offline_probe_results(self):
        launcher_hash = hashlib.sha256(Path(yolo_runner.__file__).read_bytes()).hexdigest()
        self.assertEqual(launcher_hash, yolo_preflight.EXPECTED_LAUNCHER_SHA256)
        report = json.loads(
            (Q04 / "preflight/yolo-matrix-a/evidence/offline-preflight.json").read_text()
        )
        self.assertEqual(report["fixed_launcher_sha256_before"], launcher_hash)
        self.assertEqual(report["fixed_launcher_sha256_after"], launcher_hash)
        transition = report["source_transition"]
        self.assertTrue(transition["identity_changed"])
        self.assertEqual(transition["previous_live_probe"]["fixture"], "10")
        self.assertEqual(transition["offline_retained_probe"]["fixture"], "09")
        self.assertEqual(
            set(transition["changed_fields"]),
            {"fixture", "request_id", "source_key", "source_sha256", "source_revision", "profile_release"},
        )
        self.assertEqual(report["initialized"]["prefix"], yolo_runner.PREFIX)
        self.assertNotEqual(report["initialized"]["run_id"], yolo_runner.SOURCE_RUN_ID)
        self.assertEqual(report["offline_original_upload_count"], 6)
        self.assertTrue(report["cli"]["parsed"])
        for claim in ("runtime_started", "workflow_started", "inference_started", "deployment_changed"):
            self.assertFalse(report[claim])

    def test_keynote_transition_reads_retained_archive_identity(self):
        archive = Path("/private/tmp/q04-keynote-window-20260916-b/remote-evidence.tar")
        if not archive.exists():
            self.skipTest("retained Keynote archive is not present")
        actual = yolo_preflight.read_keynote_identity(archive)
        committed = json.loads(
            (Q04 / "preflight/yolo-matrix-a/evidence/offline-preflight.json").read_text()
        )["source_transition"]["previous_live_probe"]
        self.assertEqual(actual, committed)

    def test_actual_cli_parser_stops_before_remote_access(self):
        with tempfile.TemporaryDirectory() as directory:
            result = yolo_preflight.capture_cli_argv(Path(directory))
        self.assertEqual(result["argv"][0], "--execute")
        self.assertEqual(
            result["stop_point"],
            "exclusive-output-collision-before-lock-or-remote-access",
        )

    def test_current_matrix_does_not_promote_aima_q03_to_q04(self):
        matrix = json.loads((Q04 / "evidence/current-acceptance-matrix.json").read_text())
        aima = next(row for row in matrix["fixtures"] if row["id"] == "08")
        self.assertEqual(set(aima["modes"].values()), {"unproven"})
        self.assertEqual(aima["oracle_and_full_graph"], "unproven")
        self.assertEqual(aima["historical_reference"], "reusable")
        self.assertEqual(aima["q04_fresh_index"], "unproven")


if __name__ == "__main__":
    unittest.main()
