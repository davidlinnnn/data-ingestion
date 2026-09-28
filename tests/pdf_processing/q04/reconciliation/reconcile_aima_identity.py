"""Reconcile Q03 AIMA evidence with the exact Q04 fixture-08 identity.

This is a read-only report builder.  It never copies registrations or assigns a
Q03 request to a Q04 namespace.
"""

import argparse
import hashlib
import json
from pathlib import Path


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


Q02_ORACLE_FILES = (
    "tests/pdf_processing/q02/oracle/caption-oracle.json",
    "tests/pdf_processing/q02/oracle/p2/header-oracle.json",
    "tests/pdf_processing/q02/oracle/role_oracle.py",
    "tests/pdf_processing/q02/oracle/score.py",
    "tests/pdf_processing/q02/oracle/source_segments.py",
)


def retained_input_hash(manifest, suffix):
    matches = [
        row["sha256"]
        for row in manifest["private_retained_inputs"]
        if row["path"].endswith(suffix)
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one Q03 retained input ending in {suffix!r}")
    return matches[0]


def oracle_manifests(q03_manifest, bundle):
    q03_oracles = {
        "aima-code.json": retained_input_hash(q03_manifest, "/t09a-code-oracle.json"),
        "representation.json": canonical_hash(q03_manifest["source_reviews"]),
        **{name: q03_manifest["files"][name] for name in Q02_ORACLE_FILES},
    }
    q04_oracles = {
        "aima-code.json": bundle["oracles"]["aima-code.json"],
        "continuation-oracle.json": bundle["oracles"]["continuation-oracle.json"],
        "reference-08.json": bundle["reference_graphs"]["08"],
        "representation.json": canonical_hash(bundle["representation"]),
        **{name: bundle["test_files"][name] for name in Q02_ORACLE_FILES},
    }
    shared = sorted(set(q03_oracles) & set(q04_oracles))
    return q03_oracles, q04_oracles, {
        name: q03_oracles[name] == q04_oracles[name] for name in shared
    }


def test_manifests(q03_manifest, bundle):
    q03_tests = {
        name: digest
        for name, digest in q03_manifest["files"].items()
        if name in Q02_ORACLE_FILES
        or (
            name.startswith("tests/pdf_processing/q03/")
            and Path(name).suffix in (".py", ".json")
            and "/evidence/" not in name
        )
    }
    return q03_tests, bundle["test_files"]


def build_report(q03, q03_manifest, q04_config, bundle, *, paths=None):
    fixture = next(row for row in bundle["fixtures"] if row["id"] == "08")
    old_profile = q03["profile"]
    new_profile = q04_config["profiles"]["08"]
    source_sha = fixture["sha256"]
    old_review = old_profile["content_evidence"]["reviews"][source_sha]
    new_review = new_profile["content_evidence"]["reviews"][source_sha]
    old_original = old_review["original_source"]["artifact"]
    new_original = new_review["original_source"]["artifact"]
    base_fields = ("id", "version", "group_pages")
    same_base = all(old_profile[key] == new_profile[key] for key in base_fields)
    same_relationships = (
        old_profile["content_evidence"]["relationships"]
        == new_profile["content_evidence"]["relationships"]
    )
    same_fixture_review = old_review == new_review
    same_full_profile = old_profile == new_profile
    source_equal = q03["request"]["artifact"]["sha256"] == source_sha
    producer_equal = q03["producer"] == q04_config["producer"] == bundle["producer"]
    method_equal = old_profile["method"] == new_profile["method"]
    original_equal = old_original["sha256"] == fixture["original_sha256"] == new_original["sha256"]
    q03_oracles, q04_oracles, shared_oracles = oracle_manifests(q03_manifest, bundle)
    q03_tests, q04_tests = test_manifests(q03_manifest, bundle)
    representation_equal = (
        q03_manifest["source_reviews"] == bundle["representation"]
        == old_profile["content_evidence"]["relationships"]["representation"]
        == new_profile["content_evidence"]["relationships"]["representation"]
    )
    oracle_equal = q03_oracles == q04_oracles
    test_equal = q03_tests == q04_tests
    shared_test_files = {
        name: q03_tests[name] == q04_tests[name]
        for name in sorted(set(q03_tests) & set(q04_tests))
    }
    q03_fixture = {
        "id": Path(q03["request"]["artifact"]["name"]).stem,
        "source_sha256": q03["request"]["artifact"]["sha256"],
        "original_sha256": old_original["sha256"],
        "source_revision": old_review["original_source"]["source_revision"],
        "original_pages": [
            old_review["original_pages"][str(page)]
            for page in range(1, len(old_review["original_pages"]) + 1)
        ],
    }
    q04_fixture = {
        "id": fixture["id"],
        "source_sha256": fixture["sha256"],
        "original_sha256": fixture["original_sha256"],
        "source_revision": fixture["source_revision"],
        "original_pages": fixture["original_pages"],
    }
    review_compatible = (
        {**old_review, "original_source": None}
        == {**new_review, "original_source": None}
        and old_review["original_source"]["source_revision"]
        == new_review["original_source"]["source_revision"]
        and old_original["sha256"] == new_original["sha256"]
    )
    fixture_identity_equal = q03_fixture == q04_fixture
    policy_equal = same_relationships and representation_equal
    reuse_preconditions = {
        "fixture_identity_equal": fixture_identity_equal,
        "producer_equal": producer_equal,
        "method_equal": method_equal,
        "base_profile_equal": same_base,
        "policy_equal": policy_equal,
        "reviewed_source_compatible": review_compatible,
        "shared_oracles_equal": all(shared_oracles.values()),
        "shared_test_files_equal": all(shared_test_files.values()),
    }
    historical_reference_reusable = all(reuse_preconditions.values())

    report = {
        "schema_version": 1,
        "fixture": {
            "id": "08",
            "name": "AIMA",
            "original_pages": fixture["original_pages"],
            "source_sha256": source_sha,
            "original_sha256": fixture["original_sha256"],
        },
        "comparison": {
            "fixture": {
                "identity_equal": fixture_identity_equal,
                "q03_manifest": q03_fixture,
                "q04_manifest": q04_fixture,
                "q03_sha256": canonical_hash(q03_fixture),
                "q04_sha256": canonical_hash(q04_fixture),
            },
            "source": {
                "equal_bytes": source_equal,
                "q03_artifact": q03["request"]["artifact"],
                "q04_fixture_sha256": source_sha,
                "same_original_bytes": original_equal,
                "same_original_pages": old_review["original_pages"] == new_review["original_pages"],
                "artifact_identity_equal": False,
                "artifact_identity_reason": "A Q04 fresh request must capture a new version under its own prefix.",
                "namespace_reusable": False,
            },
            "producer": {
                "equal": producer_equal,
                "file_count": len(bundle["producer"]),
                "q03_sha256": canonical_hash(q03["producer"]),
                "q04_sha256": canonical_hash(q04_config["producer"]),
            },
            "method": {
                "equal": method_equal,
                "q03_sha256": canonical_hash(old_profile["method"]),
                "q04_sha256": canonical_hash(new_profile["method"]),
            },
            "profile": {
                "equal": same_full_profile,
                "base_fields_equal": same_base,
                "q03_release": old_profile["release"],
                "q04_release": new_profile["release"],
                "q03_sha256": canonical_hash(old_profile),
                "q04_sha256": canonical_hash(new_profile),
                "q03_review_count": len(old_profile["content_evidence"]["reviews"]),
                "q04_review_count": len(new_profile["content_evidence"]["reviews"]),
            },
            "policy": {
                "relationship_policy_equal": policy_equal,
                "relationship_object_equal": same_relationships,
                "representation_equal": representation_equal,
                "fixture_review_equal": same_fixture_review,
                "review_content_differs_only_by_original_artifact_identity": review_compatible,
                "q03_review_keys": sorted(old_profile["content_evidence"]["reviews"]),
                "q04_review_keys": sorted(new_profile["content_evidence"]["reviews"]),
            },
            "oracle": {
                "identity_equal": oracle_equal,
                "q03_manifest_sha256": canonical_hash(q03_oracles),
                "q04_manifest_sha256": canonical_hash(q04_oracles),
                "q03_manifest": q03_oracles,
                "q04_manifest": q04_oracles,
                "shared_component_equality": shared_oracles,
                "q04_only_components": sorted(set(q04_oracles) - set(q03_oracles)),
                "reason": "The shared AIMA/Q02 oracle bytes match exactly, but Q04 adds its continuation and full-reference graph oracles.",
            },
            "test": {
                "identity_equal": test_equal,
                "q03_manifest_sha256": canonical_hash(q03_tests),
                "q04_manifest_sha256": canonical_hash(q04_tests),
                "q03_file_count": len(q03_tests),
                "q04_file_count": len(q04_tests),
                "shared_file_equality": shared_test_files,
                "q03_only_files": sorted(set(q03_tests) - set(q04_tests)),
                "q04_only_files": sorted(set(q04_tests) - set(q03_tests)),
                "reason": "The exact Q03 runtime/test manifest differs from the Q04 consumer/audit harness manifest.",
            },
        },
        "decision": {
            "q03_registrations_may_be_copied": False,
            "q03_request_may_be_called_q04_fresh": False,
            "q04_fresh_index_satisfied": False,
            "q04_runtime_gate_required": True,
            "reuse_preconditions": reuse_preconditions,
            "historical_reference_reuse_preconditions_met": historical_reference_reusable,
            "q04_modes": {"fresh": "unproven", "restored": "unproven", "replay": "unproven"},
            "reusable": ([
                "fixture and original source bytes/page map",
                "20-file producer inventory",
                "parser/continuation method",
                "AIMA relationship coverage and representation policy semantics",
                "Q03 graph and four-algorithm behavior as historical reference evidence",
            ] if historical_reference_reusable else []),
            "not_reusable_as_q04_acceptance": [
                "Q03 object-store registrations and request IDs",
                "Q03 profile release and full profile identity",
                "Q03 test harness identity",
                "Q04 fresh/restored/replay rows and Q04 fresh-index entry",
            ],
        },
    }
    if paths:
        report["evidence"] = {
            name: {"path": str(path), "sha256": file_hash(path)}
            for name, path in paths.items()
        }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--q03", type=Path, required=True)
    parser.add_argument("--q03-manifest", type=Path, required=True)
    parser.add_argument("--q04-config", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(
        json.loads(args.q03.read_text()),
        json.loads(args.q03_manifest.read_text()),
        json.loads(args.q04_config.read_text()),
        json.loads(args.bundle.read_text()),
        paths={
            "q03_fresh": args.q03,
            "q03_manifest": args.q03_manifest,
            "q04_config": args.q04_config,
            "q04_bundle": args.bundle,
        },
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
