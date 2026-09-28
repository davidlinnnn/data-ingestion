"""Offline regressions for the inactive YOLO graph and resource candidates."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EQUIVALENCE = load_module(
    "yolo_equivalence_candidate",
    HERE / "candidate/yolo_equivalence_candidate.py",
)
RESOURCE_CANDIDATE = load_module(
    "yolo_resource_candidate",
    HERE / "candidate/yolo_resource_candidate.py",
)
RESOURCE_ANALYSIS = load_module(
    "yolo_resource_analysis",
    HERE / "diagnosis/yolo-lifecycle-a/analyze_resource_peak.py",
)


def text_node(ref, text, page):
    return {
        "self_ref": ref,
        "parent": {"$ref": "#/body"},
        "children": [],
        "content_layer": "body",
        "label": "text",
        "prov": [
            {
                "page_no": page,
                "bbox": {
                    "l": 1.0,
                    "t": 2.0,
                    "r": 3.0,
                    "b": 1.0,
                    "coord_origin": "BOTTOMLEFT",
                },
                "charspan": [0, len(text)],
            }
        ],
        "orig": text,
        "text": text,
    }


def graph(texts):
    return {
        "body": {
            "self_ref": "#/body",
            "children": [{"$ref": node["self_ref"]} for node in texts],
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
        "texts": texts,
        "pictures": [],
        "tables": [],
        "key_value_items": [],
        "form_items": [],
        "pages": {
            str(page): {"page_no": page, "size": {"width": 10, "height": 10}}
            for page in range(1, 5)
        },
    }


def equivalence_fixture():
    actual = graph(
        [
            text_node("#/texts/0", "alpha", 1),
            text_node("#/texts/1", "beta", 2),
            text_node("#/texts/2", "gamma", 3),
            text_node("#/texts/3", "delta", 4),
        ]
    )
    reference_nodes = [
        text_node("#/texts/0", "alpha beta", 1),
        text_node("#/texts/1", "gamma delta", 3),
    ]
    reference_nodes[0]["prov"] = EQUIVALENCE._rebase_provenance(actual["texts"][:2])
    reference_nodes[1]["prov"] = EQUIVALENCE._rebase_provenance(actual["texts"][2:])
    reference = graph(reference_nodes)
    source = b"fixed source"
    historical_payload = {"backend": "fixed", "options": {"value": 1}}
    historical_key = EQUIVALENCE.method_digest(historical_payload)
    historical = json.dumps({historical_key: historical_payload}, sort_keys=True).encode()
    continuation = {"sha256": "fixed-continuation", "version": "fixed-v1"}
    candidate_inputs = json.dumps(
        {"base_profile": {"method": {**historical_payload, "continuation": continuation}}},
        sort_keys=True,
    ).encode()
    regions = []
    for reference_ref, refs, positions in (
        ("#/texts/0", ["#/texts/0", "#/texts/1"], [0, 1]),
        ("#/texts/1", ["#/texts/2", "#/texts/3"], [2, 3]),
    ):
        nodes = [next(node for node in actual["texts"] if node["self_ref"] == ref) for ref in refs]
        reference_node = next(
            node for node in reference["texts"] if node["self_ref"] == reference_ref
        )
        regions.append(
            {
                "reference": reference_ref,
                "actual": refs,
                "reference_text_sha256": hashlib.sha256(
                    reference_node["text"].encode()
                ).hexdigest(),
                "actual_text_sha256": [
                    hashlib.sha256(node["text"].encode()).hexdigest() for node in nodes
                ],
                "source_provenance": [node["prov"] for node in nodes],
                "parents": ["#/body", "#/body"],
                "reading_order": positions,
                "intervening_reading_order": [],
                "continuation_policy_boundary": {
                    "normalized_exit_bottom": 0.9,
                    "exit_reaches_bottom_threshold_0_8": True,
                    "normalized_target_top": 0.8,
                    "target_meets_top_quarter_threshold": False,
                    "intervening_table": False,
                },
            }
        )
    bundle = {
        "schema_version": 1,
        "fixture": "07",
        "status": "PENDING_MAIN_APPROVAL",
        "runtime_active": False,
        "acceptance_effect": "none",
        "required_checks": EQUIVALENCE.REQUIRED_CHECKS,
        "reject_on": EQUIVALENCE.REJECT_ON,
        "validator_sha256": hashlib.sha256(
            Path(EQUIVALENCE.__file__).read_bytes()
        ).hexdigest(),
        "identities": {
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "candidate_inputs_sha256": hashlib.sha256(candidate_inputs).hexdigest(),
            "historical_methods_file_sha256": hashlib.sha256(historical).hexdigest(),
            "historical_method_payload_sha256": historical_key,
            "historical_reference_graph_sha256": EQUIVALENCE.graph_sha256(reference),
            "candidate_graph_sha256": EQUIVALENCE.graph_sha256(actual),
            "candidate_continuation_method": continuation,
        },
        "reviewed_regions": regions,
    }
    return bundle, reference, actual, source, candidate_inputs, historical


def sample(memory, *, post_cleanup=False, complete=True):
    return {
        "time": 1.0,
        "memory_current": memory,
        "attribution_complete": complete,
        "process_coverage": {"status": "complete" if complete else "incomplete"},
        "observations": (
            [
                {"label": "owned_cleanup_finished"},
                {"label": "post_cleanup_sample"},
            ]
            if post_cleanup
            else []
        ),
    }


class YoloReviewCandidateTests(unittest.TestCase):
    def test_equivalence_candidate_is_valid_but_cannot_accept_runtime(self):
        bundle, reference, actual, source, inputs, methods = equivalence_fixture()
        result = EQUIVALENCE.validate_candidate(
            bundle,
            reference,
            actual,
            source_bytes=source,
            candidate_inputs_bytes=inputs,
            historical_methods_bytes=methods,
        )
        self.assertEqual(result["status"], "CANDIDATE_VALID")
        self.assertFalse(result["runtime_active"])
        self.assertFalse(result["runtime_accepted"])
        self.assertEqual(result["reviewed_source_fragments"], 4)

    def test_equivalence_candidate_rejects_graph_method_region_or_activation_drift(self):
        bundle, reference, actual, source, inputs, methods = equivalence_fixture()
        changed_graph = copy.deepcopy(actual)
        changed_graph["texts"][0]["text"] = "changed"
        with self.assertRaisesRegex(AssertionError, "candidate_graph_sha256 changed"):
            EQUIVALENCE.validate_candidate(
                bundle,
                reference,
                changed_graph,
                source_bytes=source,
                candidate_inputs_bytes=inputs,
                historical_methods_bytes=methods,
            )

        changed_method = json.dumps(
            {"base_profile": {"method": {"continuation": {"version": "other"}}}},
            sort_keys=True,
        ).encode()
        method_bundle = copy.deepcopy(bundle)
        method_bundle["identities"]["candidate_inputs_sha256"] = hashlib.sha256(
            changed_method
        ).hexdigest()
        with self.assertRaisesRegex(AssertionError, "candidate continuation method"):
            EQUIVALENCE.validate_candidate(
                method_bundle,
                reference,
                actual,
                source_bytes=source,
                candidate_inputs_bytes=changed_method,
                historical_methods_bytes=methods,
            )

        changed_region = copy.deepcopy(bundle)
        changed_region["reviewed_regions"][0]["source_provenance"][0][0]["bbox"][
            "l"
        ] += 1
        with self.assertRaisesRegex(AssertionError, "source provenance changed"):
            EQUIVALENCE.validate_candidate(
                changed_region,
                reference,
                actual,
                source_bytes=source,
                candidate_inputs_bytes=inputs,
                historical_methods_bytes=methods,
            )

        changed_boundary = copy.deepcopy(bundle)
        changed_boundary["reviewed_regions"][0]["continuation_policy_boundary"][
            "intervening_table"
        ] = True
        with self.assertRaisesRegex(
            AssertionError, "continuation policy boundary changed"
        ):
            EQUIVALENCE.validate_candidate(
                changed_boundary,
                reference,
                actual,
                source_bytes=source,
                candidate_inputs_bytes=inputs,
                historical_methods_bytes=methods,
            )

        active = copy.deepcopy(bundle)
        active["runtime_active"] = True
        with self.assertRaisesRegex(AssertionError, "runtime activation changed"):
            EQUIVALENCE.validate_candidate(
                active,
                reference,
                actual,
                source_bytes=source,
                candidate_inputs_bytes=inputs,
                historical_methods_bytes=methods,
            )

    def test_equivalence_candidate_rejects_semantic_and_complete_graph_drift(self):
        bundle, reference, actual, source, inputs, methods = equivalence_fixture()

        def validate(changed_bundle, changed_actual, message):
            with self.assertRaisesRegex(AssertionError, message):
                EQUIVALENCE.validate_candidate(
                    changed_bundle,
                    reference,
                    changed_actual,
                    source_bytes=source,
                    candidate_inputs_bytes=inputs,
                    historical_methods_bytes=methods,
                )

        joined = copy.deepcopy(actual)
        joined["texts"][0]["text"] = "alphx"
        joined["texts"][0]["orig"] = "alphx"
        joined_bundle = copy.deepcopy(bundle)
        joined_bundle["identities"]["candidate_graph_sha256"] = (
            EQUIVALENCE.graph_sha256(joined)
        )
        joined_bundle["reviewed_regions"][0]["actual_text_sha256"][0] = (
            hashlib.sha256(b"alphx").hexdigest()
        )
        validate(joined_bundle, joined, "joined text changed")

        provenance = copy.deepcopy(actual)
        provenance["texts"][0]["prov"][0]["charspan"] = [0, 4]
        provenance_bundle = copy.deepcopy(bundle)
        provenance_bundle["identities"]["candidate_graph_sha256"] = (
            EQUIVALENCE.graph_sha256(provenance)
        )
        provenance_bundle["reviewed_regions"][0]["source_provenance"] = [
            node["prov"] for node in provenance["texts"][:2]
        ]
        validate(provenance_bundle, provenance, "rebased provenance changed")

        for region_count in (1, 3):
            region_bundle = copy.deepcopy(bundle)
            if region_count == 1:
                region_bundle["reviewed_regions"].pop()
            else:
                region_bundle["reviewed_regions"].append(
                    copy.deepcopy(region_bundle["reviewed_regions"][0])
                )
            validate(region_bundle, actual, "reviewed region count changed")

        parent = copy.deepcopy(actual)
        parent["texts"][0]["parent"] = {"$ref": "#/furniture"}
        parent_bundle = copy.deepcopy(bundle)
        parent_bundle["identities"]["candidate_graph_sha256"] = (
            EQUIVALENCE.graph_sha256(parent)
        )
        parent_bundle["reviewed_regions"][0]["parents"][0] = "#/furniture"
        validate(parent_bundle, parent, "split metadata changed")

        order = copy.deepcopy(actual)
        order["body"]["children"][:2] = reversed(order["body"]["children"][:2])
        order_bundle = copy.deepcopy(bundle)
        order_bundle["identities"]["candidate_graph_sha256"] = (
            EQUIVALENCE.graph_sha256(order)
        )
        order_bundle["reviewed_regions"][0]["reading_order"] = [1, 0]
        validate(order_bundle, order, "reading order is not increasing")

        residual = copy.deepcopy(actual)
        residual["furniture"]["name"] = "residual-drift"
        residual_bundle = copy.deepcopy(bundle)
        residual_bundle["identities"]["candidate_graph_sha256"] = (
            EQUIVALENCE.graph_sha256(residual)
        )
        validate(residual_bundle, residual, "normalized complete graph changed")

    def test_all_complete_sample_gate_includes_post_cleanup_and_250ms_violation(self):
        limit = RESOURCE_ANALYSIS.MAX_CGROUP_BYTES
        samples = [sample(limit - 1), sample(limit + 1), sample(limit - 2, post_cleanup=True)]
        result = RESOURCE_ANALYSIS.evaluate_all_complete_samples(samples)
        self.assertEqual(result["status"], "FAIL_RESOURCE_GATE")
        self.assertEqual([item["index"] for item in result["violations"]], [1])
        self.assertTrue(result["includes_post_cleanup"])

        samples[1]["memory_current"] = limit
        self.assertEqual(
            RESOURCE_ANALYSIS.evaluate_all_complete_samples(samples)["status"],
            "PASS",
        )
        samples[-1]["observations"] = []
        self.assertEqual(
            RESOURCE_ANALYSIS.evaluate_all_complete_samples(samples)["status"],
            "FAIL_RESOURCE_GATE",
        )

    def test_all_complete_sample_gate_requires_both_cleanup_markers_on_final_sample(self):
        limit = RESOURCE_ANALYSIS.MAX_CGROUP_BYTES
        early = sample(limit - 1, post_cleanup=True)
        later = sample(limit - 1)
        result = RESOURCE_ANALYSIS.evaluate_all_complete_samples([early, later])
        self.assertEqual(result["status"], "FAIL_RESOURCE_GATE")
        self.assertFalse(result["final_sample_has_cleanup_markers"])

        only_post_cleanup = sample(limit - 1)
        only_post_cleanup["observations"] = [{"label": "post_cleanup_sample"}]
        result = RESOURCE_ANALYSIS.evaluate_all_complete_samples([only_post_cleanup])
        self.assertEqual(result["status"], "FAIL_RESOURCE_GATE")
        self.assertFalse(result["final_sample_has_cleanup_markers"])

    def test_all_complete_sample_gate_rejects_incomplete_telemetry(self):
        result = RESOURCE_ANALYSIS.evaluate_all_complete_samples(
            [sample(1, complete=False), sample(1, post_cleanup=True)]
        )
        self.assertEqual(result["status"], "FAIL_RESOURCE_GATE")
        self.assertEqual(result["incomplete_sample_indexes"], [0])

    def test_committed_resource_analysis_locates_non_overlap_group_3_peak(self):
        report = json.loads(
            (
                HERE
                / "diagnosis/yolo-lifecycle-a/evidence/resource-peak.json"
            ).read_text()
        )
        self.assertEqual(report["status"], "FAIL_RESOURCE_GATE")
        self.assertEqual(report["peak"]["phase"], "group_3_warm_parse")
        self.assertFalse(report["peak"]["warm_fresh_overlap"])
        self.assertEqual(report["gate"]["samples_evaluated"], 397)
        self.assertEqual(len(report["gate"]["violations"]), 1)
        self.assertEqual(report["assembly_timeline"]["sample_count"], 31)
        self.assertEqual(len(report["ocr_timeline"]), 4)
        self.assertTrue(
            all(item["outcome"] == "text_detected" for item in report["ocr_timeline"])
        )
        self.assertIn(
            "warm_handoff_observed",
            [item["label"] for item in report["observation_timeline"]],
        )
        self.assertLess(
            report["exceedance_observation"][
                "upper_bound_seconds_between_adjacent_below_limit_samples"
            ],
            0.515,
        )
        self.assertEqual(
            report["preferred_minimal_disposition"]["status"],
            "PENDING_MAIN_APPROVAL",
        )

    def test_resource_candidate_changes_only_max_requests_and_stays_inactive(self):
        root = HERE / "candidate/yolo-resource-v1"
        bundle = json.loads((root / "BUNDLE.json").read_text())
        self.assertNotIn("candidate_parser_budgets", bundle)
        result = RESOURCE_CANDIDATE.validate_candidate(
            bundle,
            (root / "PARSER-BUDGETS.json").read_bytes(),
            (
                HERE
                / "diagnosis/yolo-lifecycle-a/evidence/resource-peak.json"
            ).read_bytes(),
        )
        self.assertEqual(
            result["allowed_diff"], {"max_requests": {"before": 20, "after": 1}}
        )
        self.assertFalse(result["runtime_active"])
        changed = copy.deepcopy(bundle)
        changed["unchanged_resource_gate"]["max_cgroup_bytes"] += 1
        with self.assertRaisesRegex(AssertionError, "unchanged resource gate changed"):
            RESOURCE_CANDIDATE.validate_candidate(
                changed,
                (root / "PARSER-BUDGETS.json").read_bytes(),
                (
                    HERE
                    / "diagnosis/yolo-lifecycle-a/evidence/resource-peak.json"
                ).read_bytes(),
            )

    def test_resource_candidate_rejects_source_facts_and_guard_drift(self):
        root = HERE / "candidate/yolo-resource-v1"
        analysis = (
            HERE / "diagnosis/yolo-lifecycle-a/evidence/resource-peak.json"
        ).read_bytes()
        budgets = (root / "PARSER-BUDGETS.json").read_bytes()
        bundle = json.loads((root / "BUNDLE.json").read_text())

        source_archive = copy.deepcopy(bundle)
        source_archive["source_archive_sha256"] = "0" * 64
        schema = copy.deepcopy(bundle)
        schema["schema_version"] = 2
        candidate_identity = copy.deepcopy(bundle)
        candidate_identity["candidate"] = "other"
        fixture = copy.deepcopy(bundle)
        fixture["fixture"] = "08"
        violation_index = copy.deepcopy(bundle)
        violation_index["evidence_basis"]["only_violation"]["sample_index"] = 0
        oom = copy.deepcopy(bundle)
        oom["unchanged_resource_gate"]["oom_max"] = 99
        psi = copy.deepcopy(bundle)
        psi["unchanged_resource_gate"]["psi_full_avg10_max"] = 99.0
        mutations = (
            ("schema", schema, "resource candidate schema changed"),
            (
                "candidate_identity",
                candidate_identity,
                "resource candidate identity changed",
            ),
            ("fixture", fixture, "resource candidate fixture changed"),
            ("source_archive_sha256", source_archive, "source archive changed"),
            ("violation_index", violation_index, "resource evidence basis changed"),
            ("oom", oom, "unchanged resource gate changed"),
            ("psi", psi, "unchanged resource gate changed"),
        )
        for name, changed, message in mutations:
            with self.subTest(name=name):
                with self.assertRaisesRegex(AssertionError, message):
                    RESOURCE_CANDIDATE.validate_candidate(
                        changed,
                        budgets,
                        analysis,
                    )


if __name__ == "__main__":
    unittest.main()
