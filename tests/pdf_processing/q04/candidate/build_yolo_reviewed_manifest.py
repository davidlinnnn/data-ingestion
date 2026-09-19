"""Build the fixed manifest for the reviewed fixture-07 candidate window."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build(repo: Path, bundle: Path) -> dict:
    q04 = repo / "tests/pdf_processing/q04"
    artifacts = {
        "main_review": q04 / "candidate/yolo-reviewed-v1/MAIN-REVIEW.json",
        "equivalence_bundle": q04 / "candidate/yolo-equivalence-v1/BUNDLE.json",
        "resource_bundle": q04 / "candidate/yolo-resource-v1/BUNDLE.json",
        "parser_budgets": q04 / "candidate/yolo-resource-v1/PARSER-BUDGETS.json",
        "resource_analysis": q04
        / "diagnosis/yolo-lifecycle-a/evidence/resource-peak.json",
        "historical_methods": repo
        / "tests/pdf_processing/t09a_r3/evidence/20260914-0b537d0-c/actual-methods.json",
        "candidate_inputs": bundle / "inputs.json",
        "source_pdf": bundle / "originals/07.pdf",
        "reference_graph": bundle / "references/07.json",
    }
    scope = {
        "single_execution": True,
        "window_seconds": 1500,
        "outer_observation_seconds_max": 180,
        "outer_available_bytes_min": 4_831_838_208,
        "outer_continuous_seconds": 60,
        "per_case_available_bytes_min": 3_221_225_472,
        "per_case_continuous_seconds": 60,
        "workload_seconds": 825,
        "cleanup_seconds": 300,
        "fixture": "07",
        "modes": ["fresh", "restored", "replay"],
        "exact_replay_of_fresh": True,
        "automatic_retry": False,
        "max_cgroup_bytes": 4_294_967_296,
        "full_psi_avg10_max": 0.0,
        "oom_increment_max": 0,
        "held_deployments": 32,
        "restore_held_deployments": False,
        "requires_new_explicit_authorization": True,
    }
    parser_budgets = json.loads(artifacts["parser_budgets"].read_text())
    return {
        "schema_version": 1,
        "candidate": "q04-yolo-reviewed-v1",
        "status": "REVIEWED_INACTIVE",
        "runtime_authorized": False,
        "production_default_changed": False,
        "fixture": "07",
        "modes": ["fresh", "restored", "replay"],
        "identity": {
            "phase": "yolo-reviewed-b",
            "remote_root": "/tmp/q04-yolo-reviewed-20260919-b",
            "prefix": "q04/yolo-reviewed-20260919-b/",
            "local_output": "/private/tmp/q04-yolo-reviewed-20260919-b",
            "runner_dir": "/tmp/q04-yolo-reviewed-20260919-b/runner-yolo-reviewed-b",
            "driver_lock": "/tmp/q04-yolo-reviewed-20260919-b/yolo-reviewed-b.driver.lock",
        },
        "oracle_policy": {
            "kind": "fixture-local-source-reviewed-equivalence",
            "accepted_pair_count": 2,
            "historical_reference_mutated": False,
            "historical_failure_reclassified": False,
            "general_normalization": False,
        },
        "parser_policy": {
            "scope": "this fixture-07 candidate window only",
            "before_max_requests": 20,
            "after_max_requests": 1,
            "group_size_changed": False,
            "concurrency_changed": False,
            "production_default_changed": False,
            "parser_budgets": parser_budgets,
        },
        "resource_gate": {
            "sample_interval_seconds": 0.25,
            "maximum_gap_seconds": 1.0,
            "max_cgroup_bytes": 4_294_967_296,
            "full_psi_avg10_max": 0.0,
            "oom_increment_max": 0,
            "required_oom_counters": ["oom", "oom_group_kill", "oom_kill"],
            "all_samples_complete": True,
            "final_sample_labels": [
                "owned_cleanup_finished",
                "post_cleanup_sample",
            ],
        },
        "authorization_scope": scope,
        "authorization_scope_sha256": hashlib.sha256(
            canonical(scope).encode()
        ).hexdigest(),
        "artifacts": {name: sha(path) for name, path in artifacts.items()},
        "failure_policy": {
            "automatic_retry": False,
            "resource_failure_next_step": "return to main for a dedicated cgroup or Linux host decision",
            "other_fixture_policy_inherited": False,
            "historical_evidence_preserved": True,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build(args.repo.resolve(), args.bundle.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
