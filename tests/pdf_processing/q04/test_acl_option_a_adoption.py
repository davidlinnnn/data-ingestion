"""Offline tests for the adopted fixture-09 bundle and state-plan boundary."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "diagnosis/acl-fresh-resource-v1/adoption-v1/build_adoption.py"
SPEC = importlib.util.spec_from_file_location("q04_option_a_adoption", MODULE_PATH)
assert SPEC and SPEC.loader
ADOPTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADOPTION)


class AclOptionAAdoptionTests(unittest.TestCase):
    def test_private_adopted_bundle_is_bound_and_not_live_initialized(self):
        result = ADOPTION.verify(ADOPTION.DEFAULT_OUTPUT, ADOPTION.DEFAULT_STATE_PLAN)
        self.assertEqual(result["status"], "PASS_OFFLINE_ADOPTION")
        bundle = json.loads((ADOPTION.DEFAULT_OUTPUT / "inputs.json").read_text())
        plan = json.loads((ADOPTION.DEFAULT_STATE_PLAN / "plan.json").read_text())
        self.assertEqual(bundle["reference_graphs"]["09"], ADOPTION.CANDIDATE_REFERENCE_SHA)
        adoption = bundle["qualification_adoption"]
        self.assertEqual(bundle["oracles"]["quality-oracle.json"], adoption["quality_oracle_sha256"])
        self.assertNotEqual(adoption["quality_oracle_sha256"], ADOPTION.CANDIDATE_QUALITY_SHA)
        self.assertNotEqual(adoption["content_evidence_09_sha256"], ADOPTION.CANDIDATE_EVIDENCE_SHA)
        quality = json.loads((ADOPTION.DEFAULT_OUTPUT / "oracles/quality-oracle.json").read_text())
        evidence = json.loads((ADOPTION.DEFAULT_OUTPUT / "content-evidence/09.json").read_text())
        self.assertEqual(quality["adoption_decision"], ADOPTION.DECISION_ID)
        self.assertNotIn("candidate_status", quality)
        self.assertEqual(evidence["qualification_expectation"], "ADOPTED_FIXED_FIXTURE_09")
        self.assertFalse(evidence["historical_runtime_canonical_accepted"])
        self.assertNotIn("candidate_status", evidence)
        self.assertNotIn("canonical_accepted", evidence)
        self.assertEqual(plan["status"], "PLANNED_NOT_INITIALIZED")
        self.assertIsNone(plan["run_id"])
        self.assertIsNone(plan["state_sha256"])
        self.assertNotEqual(plan["object_prefix"], "q04/keynote-18be1b3-20260916-b/")
        self.assertFalse(plan["old_request_boundary"]["copy_registrations"])

    def test_adoption_does_not_change_production_identity(self):
        old = json.loads((ADOPTION.ACTIVE / "inputs.json").read_text())
        new = json.loads((ADOPTION.DEFAULT_OUTPUT / "inputs.json").read_text())
        self.assertEqual(new["producer"], old["producer"])
        self.assertEqual(new["base_profile"], old["base_profile"])
        self.assertEqual(new["fixtures"], old["fixtures"])
        self.assertEqual(new["representation"], old["representation"])
        self.assertEqual(new["qualification_adoption"]["historical_candidate_status"], "NOT_ACCEPTED")

    def test_builder_rejects_repository_and_existing_outputs(self):
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            ADOPTION.build(MODULE_PATH.parent / "private", Path("/private/tmp/unused-state"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileExistsError):
                ADOPTION.build(root, root / "state")


if __name__ == "__main__":
    unittest.main()
