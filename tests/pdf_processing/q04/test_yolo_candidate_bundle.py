"""Candidate bundle identity and frozen-input separation checks."""

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
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

    def verify_bundle(self, path):
        prepare_path = HERE / "prepare.py"
        spec = importlib.util.spec_from_file_location("candidate_prepare_test", prepare_path)
        prepare = importlib.util.module_from_spec(spec)
        previous = sys.modules.get("consumer")
        fake = types.SimpleNamespace(
            ROOT=HERE.parents[2],
            require=lambda condition, message: condition or (_ for _ in ()).throw(ValueError(message)),
            sha=lambda data: hashlib.sha256(data).hexdigest(),
        )
        sys.modules["consumer"] = fake
        try:
            spec.loader.exec_module(prepare)
        finally:
            if previous is None:
                del sys.modules["consumer"]
            else:
                sys.modules["consumer"] = previous
        return prepare.verify_bundle(path)

    def test_builder_copies_payload_and_never_mutates_frozen_source(self):
        source = Path("/private/tmp/q04-inputs-option-a-v7")
        if not source.is_dir():
            self.skipTest("frozen source bundle is local-only")
        source_inputs_before = (source / "inputs.json").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "candidate"
            result = module.build(source, destination, PRODUCER_ROOT)
            verified = self.verify_bundle(destination)
            self.assertEqual((source / "inputs.json").read_bytes(), source_inputs_before)
            self.assertEqual(verified["producer"], result["producer"])
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
