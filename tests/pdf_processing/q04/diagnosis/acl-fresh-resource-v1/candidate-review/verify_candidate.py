"""Strict offline verifier for the fixture-09 Option A review candidate."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
BUILD_SPEC = importlib.util.spec_from_file_location(
    "acl_option_a_build", HERE / "build_candidate.py"
)
assert BUILD_SPEC and BUILD_SPEC.loader
BUILD = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(BUILD)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def verify(
    *,
    reference: dict[str, Any],
    active_quality: dict[str, Any],
    candidate_raw: bytes,
    report_raw: bytes,
    quality_raw: bytes,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    candidate = json.loads(candidate_raw)
    report = json.loads(report_raw)
    quality = json.loads(quality_raw)
    require(manifest["status"] == "NOT_ACCEPTED", "candidate status changed")
    require(not manifest["boundaries"]["candidate_is_pass"], "candidate claims PASS")
    require(
        BUILD.sha(candidate_raw) == manifest["hashes"]["candidate_reference_09"],
        "candidate file hash changed",
    )
    require(
        BUILD.sha(BUILD.canonical(BUILD.graph_projection(candidate)).encode())
        == manifest["hashes"]["candidate_reference_graph"],
        "candidate exact graph changed",
    )
    require(
        BUILD.sha(report_raw) == manifest["hashes"]["candidate_content_evidence"],
        "candidate content evidence changed",
    )
    require(
        BUILD.sha(quality_raw) == manifest["hashes"]["candidate_quality_oracle"],
        "candidate quality oracle changed",
    )
    require(report["document_sha256"] == BUILD.sha(candidate_raw), "document binding changed")
    checks = BUILD.check_graph(candidate, report)
    graph_delta = BUILD.reviewed_delta(reference, candidate)
    mapping = BUILD.text_mapping(reference, candidate)
    require(
        mapping[BUILD.SPLIT_REFERENCE] == list(BUILD.SPLIT_CANDIDATE),
        "reviewed split changed",
    )
    require(
        graph_delta == manifest["proof"]["full_graph_delta"],
        "full graph delta proof changed",
    )
    require(
        not graph_delta["remaining_changed_collections_after_diagnostic_normalization"],
        "additional graph differences remain",
    )

    regenerated = BUILD.candidate_quality_oracle(active_quality, report)
    require(regenerated == quality, "quality oracle is not derived from candidate evidence")
    candidate_pages = [page for page in quality["pages"] if page["source_id"] == "09"]
    require(
        {page["processed_page"]: len(page["items"]) for page in candidate_pages}
        == {1: 40, 2: 69, 3: 21},
        "fixture-09 full-page coverage changed",
    )
    old_other = [page for page in active_quality["pages"] if page["source_id"] != "09"]
    new_other = [page for page in quality["pages"] if page["source_id"] != "09"]
    require(old_other == new_other, "another fixture changed")

    typed = {item["ref"]: item for item in report["items"]}
    reviewed = {
        formula["review_id"]: formula
        for formula in report["formula_occurrences"]
        if "review_id" in formula
    }
    require(set(reviewed) == {f"eq{number}" for number in range(1, 7)}, "formula set changed")
    require(
        all(typed[item]["actual_type"] == "text" for item in reviewed["eq2"]["refs"]),
        "equation 2 is no longer TextItem-backed",
    )
    required_ocr = manifest["proof"]["required_ocr"]
    require(
        len(required_ocr) == 2
        and {item["component"] for item in required_ocr}
        == {"#/pictures/0", "#/pictures/1"}
        and all(item["outcome"] == "text_detected" for item in required_ocr),
        "required OCR evidence changed",
    )
    require(
        manifest["proof"]["caption_edges"]
        == sum(len(item["captions"]) for item in report["items"]),
        "caption evidence changed",
    )
    return {
        "status": "PASS_REVIEW_PACKAGE_ONLY",
        "acceptance_status": "NOT_ACCEPTED",
        "graph": checks,
        "quality_items": {page["processed_page"]: len(page["items"]) for page in candidate_pages},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--active-quality", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args(argv)
    result = verify(
        reference=json.loads(args.reference.read_text()),
        active_quality=json.loads(args.active_quality.read_text()),
        candidate_raw=(args.package / "candidate-reference-09.json").read_bytes(),
        report_raw=(args.package / "candidate-content-evidence-09.json").read_bytes(),
        quality_raw=(args.package / "candidate-quality-oracle.json").read_bytes(),
        manifest=json.loads((args.package / "review-manifest.json").read_text()),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
