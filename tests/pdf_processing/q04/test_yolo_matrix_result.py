"""Regression checks for the retained YOLO matrix A result."""

import hashlib
import json
from pathlib import Path
import tarfile
import unittest


HERE = Path(__file__).parent
SUMMARY_PATH = HERE / "sentinel/yolo-matrix-a/evidence/summary.json"
PRIVATE_ROOT = Path("/private/tmp/q04-yolo-matrix-20260918-a")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class YoloMatrixResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(SUMMARY_PATH.read_text())

    def test_result_preserves_fail_closed_acceptance_boundary(self):
        result = self.summary
        self.assertEqual(result["outcome"], "FRESH_CGROUP_GUARD_REJECTION")
        self.assertFalse(result["acceptance"])
        self.assertEqual(result["window"]["retry_count"], 0)
        self.assertTrue(result["modes"]["fresh"]["started"])
        self.assertFalse(result["modes"]["fresh"]["complete_delivery"])
        self.assertFalse(result["modes"]["fresh"]["consumer_oracles_evaluated"])
        self.assertFalse(result["modes"]["restored"]["started"])
        self.assertFalse(result["modes"]["exact_replay"]["started"])
        self.assertFalse(result["fresh_index_integrated"])

    def test_admission_and_active_guard_are_distinct(self):
        result = self.summary
        self.assertTrue(result["outer_admission"]["passed"])
        self.assertGreaterEqual(
            result["outer_admission"]["minimum_available_bytes"], 4_831_838_208
        )
        self.assertTrue(result["per_case_admission"]["passed"])
        self.assertGreaterEqual(
            result["per_case_admission"]["minimum_available_bytes"], 3_221_225_472
        )
        resources = result["fresh_resources"]
        self.assertGreater(
            resources["maximum_cgroup_bytes"], resources["cgroup_ceiling_bytes"]
        )
        self.assertEqual(resources["maximum_psi_full_avg10"], 0)
        self.assertEqual(resources["vm_oom_kill_values"], [0])
        self.assertTrue(all(value == 0 for value in resources["memory_event_maxima"].values()))

    def test_cleanup_and_held_services_are_verified(self):
        result = self.summary
        self.assertTrue(result["cleanup"]["verified"])
        self.assertTrue(all(result["cleanup"]["case_outcomes"].values()))
        self.assertEqual(result["cleanup"]["errors"], [])
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
    def test_private_evidence_matches_committed_hashes_and_resource_trace(self):
        artifacts = self.summary["private_artifacts"]
        for name, expected in artifacts.items():
            with self.subTest(name=name):
                self.assertEqual(sha256(PRIVATE_ROOT / name), expected)

        archive = PRIVATE_ROOT / "remote-evidence.tar"
        with tarfile.open(archive) as evidence:
            stream = evidence.extractfile(
                "./state/yolo-matrix-a/worker-1/samples.jsonl"
            )
            self.assertIsNotNone(stream)
            samples = [json.loads(line) for line in stream]
        resources = self.summary["fresh_resources"]
        self.assertEqual(len(samples), resources["samples"])
        self.assertEqual(
            max(sample["memory_current"] for sample in samples),
            resources["maximum_cgroup_bytes"],
        )
        self.assertEqual(
            min(sample["available"] for sample in samples),
            resources["minimum_available_bytes"],
        )


if __name__ == "__main__":
    unittest.main()
