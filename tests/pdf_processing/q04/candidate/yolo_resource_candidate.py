"""Validate the inactive max-requests=1 YOLO resource candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SAMPLE_CONTRACT = (
    "all complete 250 ms attribution samples, with owned_cleanup_finished and "
    "post_cleanup_sample on the final sample"
)
UNCHANGED_RESOURCE_GATE = {
    "max_cgroup_bytes": 4 * 1024**3,
    "sample_contract": SAMPLE_CONTRACT,
    "oom_max": 0,
    "psi_full_avg10_max": 0.0,
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_candidate(
    bundle: dict[str, Any],
    parser_budgets_bytes: bytes,
    resource_analysis_bytes: bytes,
) -> dict[str, Any]:
    if bundle.get("schema_version") != 1:
        raise AssertionError("resource candidate schema changed")
    if bundle.get("candidate") != "q04-yolo-resource-v1":
        raise AssertionError("resource candidate identity changed")
    if bundle.get("fixture") != "07":
        raise AssertionError("resource candidate fixture changed")
    if bundle.get("status") != "PENDING_MAIN_APPROVAL":
        raise AssertionError("resource candidate status changed")
    if bundle.get("runtime_active") is not False:
        raise AssertionError("resource candidate must remain inactive")
    if bundle.get("production_change") is not False:
        raise AssertionError("resource candidate must remain window-local")
    if sha256_bytes(Path(__file__).read_bytes()) != bundle["validator_sha256"]:
        raise AssertionError("resource candidate validator changed")
    if sha256_bytes(parser_budgets_bytes) != bundle[
        "candidate_parser_budgets_sha256"
    ]:
        raise AssertionError("candidate parser budgets changed")
    if sha256_bytes(resource_analysis_bytes) != bundle["source_analysis_sha256"]:
        raise AssertionError("retained resource analysis changed")

    candidate = json.loads(parser_budgets_bytes)
    analysis = json.loads(resource_analysis_bytes)
    if bundle.get("source_run") != analysis["source_run"]:
        raise AssertionError("source run changed")
    if bundle.get("source_archive_sha256") != analysis["archive_sha256"]:
        raise AssertionError("source archive changed")
    baseline = bundle["baseline_parser_budgets"]
    changed = {
        key: {"before": baseline.get(key), "after": candidate.get(key)}
        for key in set(baseline) | set(candidate)
        if baseline.get(key) != candidate.get(key)
    }
    if changed != bundle["allowed_diff"]:
        raise AssertionError("candidate changes more than max_requests")
    if candidate["max_requests"] != 1:
        raise AssertionError("candidate does not recycle after each request")
    if analysis["status"] != "FAIL_RESOURCE_GATE":
        raise AssertionError("candidate lost its retained failure basis")
    finding = analysis["lifecycle_finding"]
    if not finding["same_warm_parser_pid_for_all_groups"]:
        raise AssertionError("retained groups no longer share one parser")
    if finding["reported_recycles"] != [0, 0, 0]:
        raise AssertionError("retained recycle evidence changed")
    if not finding["monotonically_increasing_high_water"]:
        raise AssertionError("retained high-water evidence changed")
    if analysis["peak"]["warm_fresh_overlap"]:
        raise AssertionError("retained peak is an overlap case")
    expected_evidence_basis = {
        "same_warm_parser_pid_for_three_groups": finding[
            "same_warm_parser_pid_for_all_groups"
        ],
        "reported_recycles": finding["reported_recycles"],
        "parser_peak_rss_high_water_kib": finding[
            "parser_peak_rss_high_water_kib"
        ],
        "only_violation": {
            "sample_index": analysis["peak"]["index"],
            "phase": analysis["peak"]["phase"],
            "memory_current_bytes": analysis["peak"]["memory_current_bytes"],
        },
        "warm_fresh_overlap": analysis["peak"]["warm_fresh_overlap"],
    }
    if bundle.get("evidence_basis") != expected_evidence_basis:
        raise AssertionError("resource evidence basis changed")
    gate = bundle["unchanged_resource_gate"]
    if gate != UNCHANGED_RESOURCE_GATE:
        raise AssertionError("unchanged resource gate changed")
    source_gate = analysis["gate"]
    if not source_gate["final_sample_has_cleanup_markers"]:
        raise AssertionError("retained final cleanup markers changed")
    if source_gate["final_sample_index"] != source_gate["samples_evaluated"] - 1:
        raise AssertionError("retained final cleanup sample index changed")
    return {
        "status": "CANDIDATE_VALID",
        "runtime_active": False,
        "production_change": False,
        "allowed_diff": changed,
        "source_failure": analysis["status"],
        "future_limit_bytes": gate["max_cgroup_bytes"],
        "next_step": "main approval is required before a new fixture-07 window",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--parser-budgets", type=Path, required=True)
    parser.add_argument("--resource-analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_candidate(
        json.loads(args.bundle.read_text()),
        args.parser_budgets.read_bytes(),
        args.resource_analysis.read_bytes(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
