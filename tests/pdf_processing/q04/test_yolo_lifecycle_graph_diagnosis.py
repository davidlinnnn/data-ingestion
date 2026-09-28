"""Deterministic offline checks for the retained YOLO graph-gate failure."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
DIAGNOSIS = HERE / "diagnosis/yolo-lifecycle-a"
SPEC = importlib.util.spec_from_file_location(
    "yolo_lifecycle_graph_diagnosis", DIAGNOSIS / "analyze_graph_delta.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def node(ref, text, page, start, end, parent="#/body"):
    return {
        "self_ref": ref,
        "parent": {"$ref": parent},
        "children": [],
        "content_layer": "body",
        "label": "text",
        "prov": [
            {
                "page_no": page,
                "bbox": {
                    "l": 72.0,
                    "t": 100.0,
                    "r": 540.0,
                    "b": 70.0,
                    "coord_origin": "BOTTOMLEFT",
                },
                "charspan": [start, end],
            }
        ],
        "orig": text,
        "text": text,
    }


def fixture():
    first = node("#/texts/0", "alpha beta", 1, 0, 10)
    first["prov"][0]["charspan"] = [0, 5]
    first["prov"] = [
        first["prov"][0],
        {
            **node("unused", "beta", 2, 0, 4)["prov"][0],
            "charspan": [6, 10],
        },
    ]
    second = node("#/texts/1", "gamma delta", 3, 0, 11)
    second["prov"][0]["charspan"] = [0, 5]
    second["prov"] = [
        second["prov"][0],
        {
            **node("unused", "delta", 4, 0, 5)["prov"][0],
            "charspan": [6, 11],
        },
    ]
    caption = node("#/texts/2", "Figure caption", 1, 0, 14, "#/pictures/0")
    caption["label"] = "caption"
    picture = {
        "self_ref": "#/pictures/0",
        "parent": {"$ref": "#/body"},
        "children": [{"$ref": "#/texts/2"}],
        "content_layer": "body",
        "label": "picture",
        "prov": [],
        "captions": [{"$ref": "#/texts/2"}],
        "references": [],
        "footnotes": [],
    }
    reference = {
        "body": {
            "self_ref": "#/body",
            "children": [
                {"$ref": "#/texts/0"},
                {"$ref": "#/texts/1"},
                {"$ref": "#/pictures/0"},
            ],
            "content_layer": "body",
            "name": "_root_",
            "label": "unspecified",
        },
        "furniture": {
            "self_ref": "#/furniture",
            "children": [],
            "content_layer": "furniture",
            "name": "_root_",
            "label": "unspecified",
        },
        "groups": [],
        "texts": [first, second, caption],
        "pictures": [picture],
        "tables": [],
        "key_value_items": [],
        "form_items": [],
        "pages": {
            str(page): {"page_no": page, "size": {"width": 612, "height": 792}}
            for page in range(1, 5)
        },
    }
    actual = copy.deepcopy(reference)
    actual["texts"] = [
        node("#/texts/0", "alpha", 1, 0, 5),
        node("#/texts/1", "gamma", 3, 0, 5),
        node("#/texts/2", "beta", 2, 0, 4),
        node("#/texts/3", "delta", 4, 0, 5),
        node("#/texts/4", "Figure caption", 1, 0, 14, "#/pictures/0"),
    ]
    actual["texts"][4]["label"] = "caption"
    actual["pictures"][0]["children"] = [{"$ref": "#/texts/4"}]
    actual["pictures"][0]["captions"] = [{"$ref": "#/texts/4"}]
    actual["body"]["children"] = [
        {"$ref": "#/texts/0"},
        {"$ref": "#/texts/1"},
        {"$ref": "#/texts/2"},
        {"$ref": "#/texts/3"},
        {"$ref": "#/pictures/0"},
    ]
    return reference, actual


class YoloLifecycleGraphDiagnosisTests(unittest.TestCase):
    def test_two_nonadjacent_splits_explain_the_complete_graph_delta(self):
        reference, actual = fixture()
        result = MODULE.analyze(reference, actual, required_split_count=2)

        self.assertEqual(
            result["verdict"],
            "two_source_preserving_splits_explain_full_graph_delta",
        )
        self.assertEqual(result["oracle_status"], "FAIL_GRAPH_GATE_unchanged")
        self.assertEqual(
            [split["actual"] for split in result["splits"]],
            [["#/texts/0", "#/texts/2"], ["#/texts/1", "#/texts/3"]],
        )
        self.assertEqual(
            result["remaining_changed_collections_after_diagnostic_normalization"],
            [],
        )

    def test_parent_or_geometry_change_is_not_treated_as_equivalent(self):
        reference, actual = fixture()
        parent = copy.deepcopy(actual)
        parent["texts"][2]["parent"] = {"$ref": "#/furniture"}
        geometry = copy.deepcopy(actual)
        geometry["texts"][2]["prov"][0]["bbox"]["l"] += 1

        with self.assertRaisesRegex(AssertionError, "split metadata differs"):
            MODULE.analyze(reference, parent, required_split_count=2)
        with self.assertRaisesRegex(AssertionError, "unique two-node split"):
            MODULE.analyze(reference, geometry, required_split_count=2)

    def test_extra_reading_order_edge_remains_a_delta(self):
        reference, actual = fixture()
        actual["body"]["children"].append({"$ref": "#/texts/3"})
        result = MODULE.analyze(reference, actual, required_split_count=2)
        self.assertEqual(
            result["remaining_changed_collections_after_diagnostic_normalization"],
            ["body"],
        )

    def test_caption_linkage_change_remains_a_delta(self):
        reference, actual = fixture()
        actual["pictures"][0]["captions"] = []
        result = MODULE.analyze(reference, actual, required_split_count=2)
        self.assertEqual(
            result["remaining_changed_collections_after_diagnostic_normalization"],
            ["pictures"],
        )

    def test_table_oracle_rejects_a_cell_change(self):
        document = {
            "tables": [
                {
                    "self_ref": "#/tables/0",
                    "data": {
                        "num_rows": 15,
                        "num_cols": 1,
                        "table_cells": [
                            {
                                "start_row_offset_idx": 0,
                                "end_row_offset_idx": 1,
                                "start_col_offset_idx": 0,
                                "end_col_offset_idx": 1,
                                "row_span": 1,
                                "col_span": 1,
                                "text": "source cell",
                            }
                        ],
                    },
                }
            ]
        }
        oracle = [
            {
                "row": 0,
                "col": 0,
                "rowspan": 1,
                "source_text": "source cell",
                "parsed_text": "source cell",
            }
        ]
        self.assertEqual(MODULE.audit_table(document, oracle)["audited_table_cells"], 1)
        document["tables"][0]["data"]["table_cells"][0]["text"] = "changed"
        with self.assertRaisesRegex(AssertionError, "source-audited cell changed"):
            MODULE.audit_table(document, oracle)

    def test_retained_report_keeps_runtime_failure_and_post_run_boundary(self):
        report = json.loads((DIAGNOSIS / "evidence/full-semantic-delta.json").read_text())
        runtime = json.loads((DIAGNOSIS / "evidence/runtime-summary.json").read_text())
        proposal = json.loads(
            (DIAGNOSIS / "evidence/local-oracle-proposal.json").read_text()
        )

        self.assertEqual(report["oracle_status"], "FAIL_GRAPH_GATE_unchanged")
        self.assertEqual(len(report["splits"]), 2)
        self.assertEqual(
            report["remaining_changed_collections_after_diagnostic_normalization"],
            [],
        )
        self.assertEqual(report["post_run_document_checks"]["audited_table_cells"], 60)
        self.assertEqual(report["post_run_document_checks"]["captions"], 9)
        self.assertEqual(report["post_run_document_checks"]["required_ocr"], 4)
        self.assertFalse(runtime["batch"]["fresh_accepted"])
        self.assertEqual(runtime["batch"]["completed_phases"], [])
        self.assertEqual(runtime["batch"]["retry_count"], 0)
        self.assertTrue(runtime["cleanup"]["verified"])
        self.assertTrue(runtime["resource_attribution"]["no_warm_fresh_overlap"])
        self.assertGreater(
            runtime["resource_attribution"]["maximum_memory_current_bytes"],
            runtime["guards"]["max_cgroup_bytes"],
        )
        self.assertLess(
            runtime["guards"]["maximum_sampled_memory_current_bytes"],
            runtime["guards"]["max_cgroup_bytes"],
        )
        self.assertEqual(
            runtime["retained_evidence"]["runtime_files_sha256"],
            MODULE.EXPECTED_RUNTIME_FILE_SHA256,
        )
        self.assertEqual(proposal["status"], "PROPOSAL_NOT_ACTIVE")
        self.assertEqual(proposal["acceptance_effect"], "none")
        self.assertEqual(len(proposal["reviewed_regions"]), 2)
        self.assertEqual(
            proposal["historical_runtime_disposition"],
            "FAIL_GRAPH_GATE_unchanged",
        )

    def test_proposed_oracle_is_bound_to_the_reviewed_method_and_regions(self):
        report = json.loads((DIAGNOSIS / "evidence/full-semantic-delta.json").read_text())
        proposal = MODULE.build_local_oracle_proposal(report)

        self.assertEqual(
            proposal["candidate_continuation_method"],
            report["method_comparison"]["candidate_continuation"],
        )
        self.assertEqual(
            proposal["source_sha256"], report["source_review"]["source_sha256"]
        )
        self.assertEqual(
            proposal["candidate_inputs_sha256"], MODULE.EXPECTED_INPUTS_SHA256
        )
        self.assertEqual(
            proposal["historical_methods_file_sha256"],
            MODULE.EXPECTED_HISTORICAL_METHODS_FILE_SHA256,
        )
        self.assertEqual(
            [region["actual"] for region in proposal["reviewed_regions"]],
            [["#/texts/20", "#/texts/25"], ["#/texts/157", "#/texts/162"]],
        )
        self.assertIn("any additional or missing split", proposal["reject_on"])

    def test_method_comparison_rejects_an_unreviewed_continuation_identity(self):
        historical = json.loads(
            (
                HERE.parent
                / "t09a_r3/evidence/20260914-0b537d0-c/actual-methods.json"
            ).read_text()
        )
        candidate_method = {
            **next(iter(historical.values())),
            "continuation": {
                "sha256": "unreviewed",
                "version": "column-edge-continuation-v1",
            },
        }
        with self.assertRaisesRegex(
            AssertionError, "candidate continuation method identity changed"
        ):
            MODULE.compare_method_payloads(historical, candidate_method)

    def test_method_comparison_rejects_a_payload_that_does_not_match_its_key(self):
        historical = {
            MODULE.EXPECTED_HISTORICAL_METHOD_SHA256: {"backend": "mutated"}
        }
        with self.assertRaisesRegex(
            AssertionError, "historical method payload digest changed"
        ):
            MODULE.compare_method_payloads(historical, {"backend": "mutated"})

    def test_retained_file_hashes_fail_closed_after_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "evidence.json"
            evidence.write_text('{"status":"fixed"}\n')
            expected = {"evidence.json": MODULE.file_sha(evidence)}
            self.assertEqual(MODULE.verify_file_hashes(root, expected), expected)
            evidence.write_text('{"status":"changed"}\n')
            with self.assertRaisesRegex(
                AssertionError, "retained evidence changed.*evidence.json"
            ):
                MODULE.verify_file_hashes(root, expected)


if __name__ == "__main__":
    unittest.main()
