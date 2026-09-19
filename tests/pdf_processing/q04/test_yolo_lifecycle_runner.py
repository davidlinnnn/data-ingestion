"""Offline end-to-end checks for the fixed YOLO lifecycle candidate window."""

import json
from pathlib import Path
import tempfile
import unittest

from candidate.yolo_candidate_window import validate_matrix_records
from sentinel import run_yolo_lifecycle_a as runner


class YoloLifecycleRunnerTests(unittest.TestCase):
    def test_batch_plan_separates_executable_and_unready_gates(self):
        q04 = Path(__file__).resolve().parent
        batch = (q04 / "BATCH-ACCEPTANCE-PLAN.md").read_text()
        window = (
            q04 / "candidate/yolo-lifecycle-v1/VALIDATION-PLAN.md"
        ).read_text()
        self.assertIn("8,025 seconds", batch)
        self.assertIn("Only the first", batch)
        self.assertIn("Not executable yet", batch)
        self.assertIn("there is no per-case confirmation", batch)
        self.assertIn("Warm sequence behavior is still unproven", window)
        self.assertIn(
            "/Users/david/work/data-ingestion/docs/prototypes/"
            "pdf-checkpoint-prototype/.venv/bin/python",
            window,
        )
        self.assertIn("export Q04_APPROVAL_REFERENCE=", window)

    def test_single_offline_validation_covers_staging_init_schema_and_argv(self):
        record = runner.offline_validation_record()
        self.assertEqual(record["status"], "PASS offline only")
        self.assertFalse(record["runtime_authorized"])
        self.assertEqual(record["identity"]["phase"], "yolo-lifecycle-a")
        self.assertEqual(record["outer_observation_seconds"], 180)
        self.assertEqual(record["outer_continuous_seconds"], 60)
        self.assertEqual(record["cleanup_seconds"], 300)
        argv = record["measurement_argv"]
        self.assertEqual(
            argv[1],
            "/tmp/q04-yolo-lifecycle-20260919-a/runner-yolo-lifecycle-a/yolo_candidate_window.py",
        )
        self.assertEqual(argv[argv.index("--name") + 1], "yolo-lifecycle-a")
        self.assertEqual(
            argv[argv.index("--expected-prefix") + 1],
            "q04/yolo-lifecycle-20260919-a/",
        )

    def test_candidate_staging_binds_producer_worker_and_adapter(self):
        files = runner.candidate_staging_files()
        self.assertIn("src/pdf_processing/supervision.py", files)
        self.assertIn("src/pdf_processing/execution.py", files)
        self.assertIn("tests/pdf_processing/q04/worker.py", files)
        self.assertIn(
            "tests/pdf_processing/q04/candidate/yolo_candidate_window.py", files
        )
        self.assertIn(
            "tests/pdf_processing/q04/sentinel/yolo_attribution_telemetry.py",
            files,
        )
        self.assertNotEqual(
            runner.copy_log_path(runner.REMOTE + "/code/deploy/pdf-processing/worker.py"),
            runner.copy_log_path(
                runner.REMOTE + "/code/tests/pdf_processing/q04/worker.py"
            ),
        )

    def test_runtime_command_has_fixed_workload_and_cleanup_deadlines(self):
        command = runner.build_runtime_command("q04-offline-candidate")
        self.assertIn("--signal=INT --kill-after=180s 825s", command)
        self.assertIn("yolo_candidate_window.py", command)
        self.assertIn("PYTHONSAFEPATH=1", command)
        self.assertIn("test ! -e", command)
        self.assertNotIn("yolo_fresh_measure.py", command)

    def test_matrix_contract_replays_fresh_and_keeps_restored_new(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fresh_request = {
                "request_id": "fresh-id",
                "artifact": {"key": "new-prefix/sources/source"},
            }
            records = {
                "fresh": {"request": fresh_request},
                "restored": {
                    "request": {
                        "request_id": "restored-id",
                        "artifact": fresh_request["artifact"],
                    }
                },
                "replay": {"request": fresh_request},
            }
            for mode, record in records.items():
                target = root / f"{mode}-07"
                target.mkdir()
                (target / "accepted.json").write_text(json.dumps(record))
            self.assertEqual(validate_matrix_records(root), records)

            records["replay"]["request"] = {
                "request_id": "restored-id",
                "artifact": fresh_request["artifact"],
            }
            (root / "replay-07/accepted.json").write_text(
                json.dumps(records["replay"])
            )
            with self.assertRaisesRegex(ValueError, "exact replay"):
                validate_matrix_records(root)


if __name__ == "__main__":
    unittest.main()
