"""Regression checks for the retained YOLO attribution-B result."""

import hashlib
import json
from pathlib import Path
import tarfile
import unittest


HERE = Path(__file__).parent
SUMMARY_PATH = HERE / "sentinel/yolo-attribution-b/evidence/summary.json"
PRIVATE_ROOT = Path("/private/tmp/q04-yolo-attribution-20260918-b")
FOUR_GIB = 4 * 1024**3


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class YoloAttributionResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(SUMMARY_PATH.read_text())

    def test_result_remains_fail_closed_and_measurement_incomplete(self):
        result = self.summary
        self.assertEqual(
            result["outcome"],
            "FRESH_CGROUP_GUARD_ATTRIBUTED_MEASUREMENT_INCOMPLETE",
        )
        self.assertFalse(result["acceptance"])
        self.assertFalse(result["measurement_complete"])
        self.assertEqual(result["window"]["retry_count"], 0)
        self.assertEqual(result["modes"], ["fresh"])
        self.assertEqual(result["workload"]["outcome"], "guard_stop")
        self.assertFalse(result["workload"]["complete_delivery"])
        self.assertFalse(result["workload"]["consumer_oracles_evaluated"])
        self.assertEqual(
            result["attribution"]["missing_required_observation_labels"],
            ["cancel_requested"],
        )
        self.assertEqual(result["attribution"]["samples"], 379)
        self.assertEqual(result["attribution"]["incomplete_samples"], 0)
        self.assertEqual(result["attribution"]["hard_incomplete_sample_indexes"], [])

    def test_peak_is_owned_anonymous_memory_with_parser_overlap(self):
        attribution = self.summary["attribution"]
        peak = attribution["peak"]
        delta = attribution["baseline_to_peak_delta"]
        self.assertGreater(peak["memory_current_bytes"], FOUR_GIB)
        self.assertEqual(
            peak["bytes_over_guard"], peak["memory_current_bytes"] - FOUR_GIB
        )
        self.assertGreater(
            delta["owned_pss_bytes"], delta["memory_current_bytes"]
        )
        self.assertGreater(
            delta["memory_stat_bytes"]["anon"],
            delta["memory_stat_bytes"]["file"] * 50,
        )
        self.assertLess(delta["diagnostic_unattributed_bytes"], 0)
        owned_classes = {
            row["command_class"]
            for row in peak["processes"]
            if row["ownership"] == "owned"
        }
        self.assertIn("warm_parser", owned_classes)
        self.assertIn("fresh_parse_child", owned_classes)
        self.assertGreater(attribution["peak_seconds_after_cancel_request"], 0)

    def test_admission_cleanup_and_held_services_are_verified(self):
        result = self.summary
        self.assertTrue(result["outer_admission"]["passed"])
        self.assertTrue(result["per_case_admission"]["passed"])
        self.assertTrue(result["cleanup"]["verified"])
        self.assertEqual(result["cleanup"]["owner_cleanup_errors"], [])
        self.assertEqual(result["cleanup"]["running_after_cleanup"], [])
        self.assertTrue(result["cleanup"]["reservation_released"])
        self.assertEqual(result["services"]["historical_deployments"], 32)
        self.assertTrue(result["services"]["all_replicas_zero_before"])
        self.assertTrue(result["services"]["all_replicas_zero_after"])
        self.assertEqual(
            result["private_artifacts"]["held-services-before.json"],
            result["private_artifacts"]["held-services-after.json"],
        )

    @unittest.skipUnless(PRIVATE_ROOT.is_dir(), "private runtime evidence is local-only")
    def test_private_evidence_matches_hashes_and_attribution_trace(self):
        for name, expected in self.summary["private_artifacts"].items():
            with self.subTest(name=name):
                self.assertEqual(sha256(PRIVATE_ROOT / name), expected)

        archive = PRIVATE_ROOT / "remote-evidence.tar"
        with tarfile.open(archive) as evidence:
            stream = evidence.extractfile(
                "./state/yolo-attribution-b/resource-attribution.jsonl"
            )
            self.assertIsNotNone(stream)
            samples = [json.loads(line) for line in stream]
        attribution = self.summary["attribution"]
        self.assertEqual(len(samples), attribution["samples"])
        self.assertEqual(
            max(sample["memory_current"] for sample in samples),
            attribution["peak"]["memory_current_bytes"],
        )


if __name__ == "__main__":
    unittest.main()
