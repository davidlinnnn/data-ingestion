"""Offline contract tests for the fixture-09 Option A review package."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
REVIEW = HERE / "diagnosis/acl-fresh-resource-v1/candidate-review"
PACKAGE = REVIEW / "artifacts"
PRIVATE_PACKAGE = Path("/private/tmp/q04-option-a-review-v3")

VERIFY_SPEC = importlib.util.spec_from_file_location(
    "acl_option_a_verify", REVIEW / "verify_candidate.py"
)
assert VERIFY_SPEC and VERIFY_SPEC.loader
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)
BUILD = VERIFY.BUILD

ACTIVE_REFERENCE = Path("/private/tmp/q04-inputs-local-v5/references/09.json")
ACTIVE_QUALITY = Path("/private/tmp/q04-inputs-local-v5/oracles/quality-oracle.json")


class AclOptionACandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(ACTIVE_REFERENCE.read_text())
        cls.active_quality = json.loads(ACTIVE_QUALITY.read_text())
        cls.candidate_raw = (PRIVATE_PACKAGE / "candidate-reference-09.json").read_bytes()
        cls.report_raw = (PRIVATE_PACKAGE / "candidate-content-evidence-09.json").read_bytes()
        cls.quality_raw = (PACKAGE / "candidate-quality-oracle.json").read_bytes()
        cls.manifest = json.loads((PACKAGE / "review-manifest.json").read_text())

    def verify(self, candidate_raw=None):
        return VERIFY.verify(
            reference=self.reference,
            active_quality=self.active_quality,
            candidate_raw=candidate_raw or self.candidate_raw,
            report_raw=self.report_raw,
            quality_raw=self.quality_raw,
            manifest=self.manifest,
        )

    def test_complete_candidate_is_reviewable_but_not_accepted(self):
        result = self.verify()
        self.assertEqual(result["status"], "PASS_REVIEW_PACKAGE_ONLY")
        self.assertEqual(result["acceptance_status"], "NOT_ACCEPTED")
        self.assertEqual(result["quality_items"], {1: 40, 2: 69, 3: 21})
        self.assertEqual(result["graph"]["items"], 134)
        self.assertEqual(self.manifest["acceptance_result"], "FAIL_exact_graph_against_active_reference")

    def test_page_two_oracle_is_derived_from_semantic_source_alignment(self):
        report = json.loads(self.report_raw)
        candidate_quality = json.loads(self.quality_raw)
        regenerated = BUILD.candidate_quality_oracle(self.active_quality, report)
        self.assertEqual(regenerated, candidate_quality)
        page = next(
            item
            for item in candidate_quality["pages"]
            if item["source_id"] == "09" and item["processed_page"] == 2
        )
        self.assertEqual(len(page["items"]), 69)
        fragment_hashes = {
            BUILD.text_sha(
                next(
                    node["text"]
                    for node in report["items"]
                    if node["ref"] == fragment
                )
            )
            for fragment in BUILD.SPLIT_CANDIDATE
        }
        self.assertTrue(fragment_hashes.issubset({item["text_sha256"] for item in page["items"]}))

    def test_full_split_record_has_text_order_parent_bbox_provenance_and_mapping(self):
        split = json.loads((PACKAGE / "split-review.json").read_text())
        self.assertEqual(split["mapping_counts"], {
            "reference_texts": 127,
            "candidate_texts": 128,
            "one_to_two": 1,
        })
        self.assertEqual(
            [entry["reading_order"] for entry in split["candidate"]], [16, 17]
        )
        self.assertEqual(
            [entry["text_position"] for entry in split["candidate"]], [97, 98]
        )
        for entry in split["candidate"]:
            node = entry["node"]
            self.assertEqual(node["label"], "text")
            self.assertEqual(node["parent"], {"$ref": "#/body"})
            self.assertTrue(node["text"])
            self.assertEqual(len(node["prov"]), 1)
            self.assertIn("bbox", node["prov"][0])
            self.assertIn("charspan", node["prov"][0])
            self.assertEqual(entry["maps_to"], "#/texts/97")

    def test_byte_integrity_rejects_mutation_before_semantic_review(self):
        with self.assertRaisesRegex(ValueError, "candidate file hash changed"):
            self.verify(self.candidate_raw + b" ")

    def test_semantic_negative_matrix_reaches_specific_relational_checks(self):
        original = json.loads(self.candidate_raw)

        missing_fragment = copy.deepcopy(original)
        missing_fragment["texts"].pop(98)

        missing_provenance = copy.deepcopy(original)
        missing_provenance["texts"][98]["prov"] = []

        changed_text = copy.deepcopy(original)
        changed_text["texts"][98]["text"] += " changed"

        wrong_order = copy.deepcopy(original)
        wrong_order["body"]["children"][16:18] = reversed(
            wrong_order["body"]["children"][16:18]
        )

        wrong_parent = copy.deepcopy(original)
        wrong_parent["texts"][98]["parent"] = {"$ref": "#/groups/1"}

        unexpected_extra = copy.deepcopy(original)
        extra = copy.deepcopy(unexpected_extra["texts"][-1])
        extra["self_ref"] = "#/texts/128"
        extra["parent"] = {"$ref": "#/body"}
        unexpected_extra["texts"].append(extra)
        unexpected_extra["body"]["children"].append({"$ref": "#/texts/128"})

        mutations = {
            "missing fragment": (missing_fragment, "reviewed fragment missing"),
            "missing provenance": (
                missing_provenance,
                "split provenance does not reconstruct reference",
            ),
            "changed text": (
                changed_text,
                "split text does not reconstruct reference",
            ),
            "wrong order": (wrong_order, "split reading order changed"),
            "wrong parent": (wrong_parent, "split parent changed"),
            "unexpected extra node": (
                unexpected_extra,
                "candidate text count is not one greater than reference",
            ),
        }
        for name, (candidate, reason) in mutations.items():
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, reason):
                BUILD.reviewed_delta(self.reference, candidate)

    def test_relational_delta_proof_rejects_non_split_graph_changes(self):
        original = json.loads(self.candidate_raw)

        changed_group = copy.deepcopy(original)
        changed_group["groups"][0]["children"] = []
        with self.assertRaisesRegex(
            ValueError, "additional graph differences remain: groups"
        ):
            BUILD.reviewed_delta(self.reference, changed_group)

        changed_parent = copy.deepcopy(original)
        changed_parent["texts"][96]["parent"] = {"$ref": "#/groups/1"}
        with self.assertRaisesRegex(
            ValueError, "additional graph differences remain: texts"
        ):
            BUILD.reviewed_delta(self.reference, changed_parent)

    def test_second_fragment_metadata_and_edges_are_not_discarded(self):
        original = json.loads(self.candidate_raw)
        metadata = copy.deepcopy(original)
        metadata["texts"][98]["content_layer"] = "furniture"
        edge = copy.deepcopy(original)
        edge["texts"][98]["children"] = [{"$ref": "#/texts/0"}]

        for name, candidate in {"metadata": metadata, "edge": edge}.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError,
                "reviewed relational proof failed: split fragments differ outside",
            ):
                BUILD.reviewed_delta(self.reference, candidate)

    def test_only_the_one_reviewed_split_edge_is_collapsed(self):
        original = json.loads(self.candidate_raw)
        third_split_edge = copy.deepcopy(original)
        third_split_edge["body"]["children"].insert(18, {"$ref": "#/texts/98"})
        non_split_duplicate = copy.deepcopy(original)
        non_split_duplicate["body"]["children"].append(
            copy.deepcopy(non_split_duplicate["body"]["children"][-1])
        )

        for name, candidate in {
            "third split edge": third_split_edge,
            "non-split duplicate edge": non_split_duplicate,
        }.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError, "additional graph differences remain: body"
            ):
                BUILD.reviewed_delta(self.reference, candidate)

    def test_other_fixtures_and_q01_anchors_are_bound_unchanged(self):
        candidate_quality = json.loads(self.quality_raw)
        self.assertEqual(
            [page for page in candidate_quality["pages"] if page["source_id"] != "09"],
            [page for page in self.active_quality["pages"] if page["source_id"] != "09"],
        )
        hashes = self.manifest["hashes"]
        self.assertEqual(
            hashes["q01_continuation_oracle"],
            BUILD.file_sha(Path("/private/tmp/q04-inputs-local-v5/oracles/continuation-oracle.json")),
        )
        self.assertEqual(
            hashes["q03_reviewed_representation"],
            BUILD.file_sha(HERE.parent / "q03/reviewed-representation.json"),
        )
        self.assertEqual(hashes["q04_fixtures_manifest"], BUILD.file_sha(HERE / "fixtures.json"))

    def test_builder_refuses_an_existing_output_directory(self):
        with tempfile.TemporaryDirectory() as existing:
            with self.assertRaises(FileExistsError):
                BUILD.build(argparse.Namespace(output=Path(existing)))

    def test_builder_refuses_full_candidate_output_inside_repository(self):
        target = REVIEW / "must-not-exist"
        self.assertFalse(target.exists())
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            BUILD.build(argparse.Namespace(
                output=target,
                reference=Path("unused"),
                candidate=Path("unused"),
                retained_report=Path("unused"),
                quality_oracle=Path("unused"),
                original_pdf=Path("unused"),
                fixture_pdf=Path("unused"),
                ocr_summary=Path("unused"),
                continuation_oracle=Path("unused"),
                reviewed_representation=Path("unused"),
                fixtures_manifest=Path("unused"),
            ))


if __name__ == "__main__":
    unittest.main()
