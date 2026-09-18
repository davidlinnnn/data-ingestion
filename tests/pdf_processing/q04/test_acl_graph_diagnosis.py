"""Deterministic offline checks for the retained ACL graph delta."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
DIAGNOSIS = HERE / "diagnosis/acl-fresh-resource-v1"
SPEC = importlib.util.spec_from_file_location(
    "acl_graph_diagnosis", DIAGNOSIS / "analyze_graph_delta.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PROFILE_SPEC = importlib.util.spec_from_file_location(
    "acl_profile_diagnosis", DIAGNOSIS / "compare_profile_provenance.py"
)
assert PROFILE_SPEC and PROFILE_SPEC.loader
PROFILE_MODULE = importlib.util.module_from_spec(PROFILE_SPEC)
PROFILE_SPEC.loader.exec_module(PROFILE_MODULE)


class AclGraphDiagnosisTests(unittest.TestCase):
    def test_minimized_split_explains_the_complete_graph_delta(self):
        fixture = json.loads(
            (DIAGNOSIS / "evidence/page2-split-repro.json").read_text()
        )
        result = MODULE.analyze(fixture["reference"], fixture["actual"])

        self.assertEqual(
            result["verdict"],
            "one_provenance_preserving_split_explains_full_graph_delta",
        )
        self.assertEqual(result["oracle_status"], "FAIL_exact_graph_mismatch_unchanged")
        self.assertEqual(
            result["split"]["actual"], ["#/texts/97", "#/texts/98"]
        )
        self.assertTrue(result["split"]["rebased_provenance_matches_reference"])
        self.assertEqual(
            result["remaining_changed_collections_after_diagnostic_normalization"],
            [],
        )

    def test_retained_profile_comparison_contains_reviewable_method_payload(self):
        retained = json.loads(
            (DIAGNOSIS / "evidence/profile-provenance.json").read_text()
        )
        shared = retained["profile_comparison"]["shared_non_continuation_method"]
        current = retained["current_provenance"]
        source = retained["source"]
        regenerated = PROFILE_MODULE.compare(
            {retained["reference_provenance"]["actual_method_sha256"]: shared},
            {
                "base_profile": {
                    "method": {**shared, "continuation": current["profile_continuation"]}
                },
                "producer": current["producer"],
                "fixtures": [source],
            },
        )
        self.assertEqual(regenerated, retained)
        self.assertTrue(
            retained["profile_comparison"]["all_non_continuation_fields_equal"]
        )
        self.assertIn("packages", shared)
        self.assertIn("model_artifacts", shared)
        self.assertEqual(
            retained["current_provenance"]["actual_method_sha256"],
            "e75b3287bbb2423e12108559fd6de0677c9c96789bf48f93797ca44c0c9bb8e2",
        )

    def test_split_does_not_discard_second_fragment_metadata_or_edges(self):
        fixture = json.loads(
            (DIAGNOSIS / "evidence/page2-split-repro.json").read_text()
        )
        mutations = {}
        metadata = copy.deepcopy(fixture["actual"])
        metadata["texts"][1]["content_layer"] = "furniture"
        mutations["metadata"] = metadata
        edge = copy.deepcopy(fixture["actual"])
        edge["texts"][1]["children"] = [{"$ref": "#/texts/0"}]
        mutations["edge"] = edge

        for name, actual in mutations.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                AssertionError,
                "split fragments differ outside self_ref/text/orig/prov",
            ):
                MODULE.analyze(fixture["reference"], actual)

    def test_third_split_edge_is_not_collapsed(self):
        fixture = json.loads(
            (DIAGNOSIS / "evidence/page2-split-repro.json").read_text()
        )
        actual = copy.deepcopy(fixture["actual"])
        actual["body"]["children"].append({"$ref": "#/texts/98"})
        result = MODULE.analyze(fixture["reference"], actual)
        self.assertEqual(
            result["remaining_changed_collections_after_diagnostic_normalization"],
            ["body"],
        )


if __name__ == "__main__":
    unittest.main()
