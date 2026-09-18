"""Candidate bundle identity and frozen-input separation checks."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).parent
BUILDER = HERE / "candidate/build_yolo_lifecycle_bundle.py"
MANIFEST = HERE / "candidate/yolo-lifecycle-v1/MANIFEST.json"
PRODUCER_ROOT = HERE.parents[2] / "src/pdf_processing"
spec = importlib.util.spec_from_file_location("build_yolo_lifecycle_bundle", BUILDER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class YoloCandidateBundleTests(unittest.TestCase):
    def test_manifest_is_bound_to_current_candidate_producer(self):
        manifest = json.loads(MANIFEST.read_text())
        observed = {
            path.name: module.sha256(path)
            for path in sorted(PRODUCER_ROOT.glob("*.py"))
        }
        self.assertEqual(manifest["candidate_version"], "q04-yolo-lifecycle-v1")
        self.assertEqual(manifest["producer"], observed)
        self.assertEqual(
            set(manifest["changed_producer_files"]),
            module.EXPECTED_CHANGED_PRODUCER_FILES,
        )
        self.assertTrue(manifest["fixture_oracle_payload_unchanged"])
        self.assertFalse(manifest["runtime_authorized"])

    def test_builder_copies_payload_and_never_mutates_frozen_source(self):
        source = Path("/private/tmp/q04-inputs-option-a-v7")
        if not source.is_dir():
            self.skipTest("frozen source bundle is local-only")
        source_inputs_before = (source / "inputs.json").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "candidate"
            result = module.build(source, destination, PRODUCER_ROOT)
            self.assertEqual((source / "inputs.json").read_bytes(), source_inputs_before)
            self.assertNotEqual(
                result["candidate_inputs_sha256"],
                result["baseline_inputs_sha256"],
            )
            self.assertEqual(
                module.tree_digest(source, exclude={"inputs.json"}),
                module.tree_digest(destination, exclude={"inputs.json"}),
            )


if __name__ == "__main__":
    unittest.main()
