"""Run the reviewed fixture-07 matrix behind its local oracle and resource gate.

This adapter is deliberately fixture-local.  It consumes the exact reviewed
equivalence and parser-budget bundles, leaves the historical reference intact,
and creates the fresh index only after the final 250 ms resource gate passes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import re
import sys
from typing import Any

import consumer
from consumer import canonical, require, sha
import q04_runtime
try:
    from candidate.yolo_reviewed_candidate_window import (
        run_window as run_lifecycle_window,
        validate_matrix_records,
    )
except ImportError:
    # The reviewed source is staged under the historical module name remotely.
    from candidate.yolo_candidate_window import (
        run_window as run_lifecycle_window,
        validate_matrix_records,
    )

try:
    from .yolo_equivalence_candidate import validate_candidate as validate_equivalence
    from .yolo_resource_candidate import validate_candidate as validate_resource
except ImportError:
    from yolo_equivalence_candidate import validate_candidate as validate_equivalence
    from yolo_resource_candidate import validate_candidate as validate_resource


FIXTURE = "07"
MODES = ["fresh", "restored", "replay"]
MAX_CGROUP_BYTES = 4 * 1024**3
PARSER_BUDGETS = {
    "startup_seconds": 120,
    "no_progress_seconds": 180,
    "terminate_seconds": 5,
    "reap_seconds": 5,
    "max_requests": 1,
}
BASELINE_PARSER_BUDGETS = {**PARSER_BUDGETS, "max_requests": 20}
MAIN_REVIEW_STATUS = "ACCEPTED_FOR_NEXT_FIXTURE07_CANDIDATE_ONLY"


def _full_psi_avg10(raw: str) -> float:
    match = re.search(r"^full\s+.*\bavg10=([0-9.]+)", raw, re.MULTILINE)
    if match is None:
        raise ValueError("full PSI avg10 is missing")
    return float(match.group(1))


def evaluate_resource_gate(
    samples: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    limit_bytes: int = MAX_CGROUP_BYTES,
) -> dict[str, Any]:
    process_incomplete = [
        index
        for index, sample in enumerate(samples)
        if sample.get("attribution_complete") is not True
        or sample.get("process_coverage", {}).get("status") != "complete"
    ]
    classified_transitions = summary.get(
        "classified_cgroup_transition_sample_indexes", []
    )
    incomplete = sorted(set(process_incomplete) - set(classified_transitions))
    memory_violations = []
    for index, sample in enumerate(samples):
        value = sample.get("memory_current")
        if not isinstance(value, int) or value > limit_bytes:
            memory_violations.append(
                {
                    "index": index,
                    "memory_current_bytes": value,
                    "excess_bytes": None if not isinstance(value, int) else value - limit_bytes,
                }
            )
    oom_violations = []
    for index, sample in enumerate(samples):
        events = sample.get("memory_events")
        required_events = {"oom", "oom_kill", "oom_group_kill"}
        missing = (
            sorted(required_events - set(events))
            if isinstance(events, dict)
            else ["oom", "oom_group_kill", "oom_kill"]
        )
        invalid_required = (
            {
                key: events[key]
                for key in sorted(required_events - set(missing))
                if type(events[key]) is not int or events[key] != 0
            }
            if isinstance(events, dict)
            else {}
        )
        nonzero = (
            {
                key: value
                for key, value in events.items()
                if key.startswith("oom") and key not in required_events and value
            }
            if isinstance(events, dict)
            else {}
        )
        invalid = {**invalid_required, **nonzero}
        if missing or invalid:
            oom_violations.append(
                {"index": index, "missing_events": missing, "events": invalid}
            )
    psi_violations = []
    for index, sample in enumerate(samples):
        try:
            value = _full_psi_avg10(sample.get("memory_pressure_raw", ""))
        except ValueError:
            value = None
        if value is None or value > 0.0:
            psi_violations.append({"index": index, "full_avg10": value})

    final_index = len(samples) - 1 if samples else None
    final_labels = (
        {
            observation.get("label")
            for observation in samples[-1].get("observations", [])
        }
        if samples
        else set()
    )
    required_final_labels = {"owned_cleanup_finished", "post_cleanup_sample"}
    final_cleanup = required_final_labels.issubset(final_labels)
    summary_errors = []
    expected_summary = {
        "qualification_complete": True,
        "cgroup_resource_complete": True,
        "unclassified_incomplete_sample_indexes": [],
        "samples": len(samples),
        "errors": [],
        "missing_required_observation_labels": [],
        "required_observations_in_order": True,
        "no_warm_fresh_overlap": True,
        "warm_fresh_overlap_sample_indexes": [],
    }
    for field, expected in expected_summary.items():
        if summary.get(field) != expected:
            summary_errors.append(
                {"field": field, "expected": expected, "actual": summary.get(field)}
            )
    if summary.get("maximum_gap_seconds", float("inf")) > 1.0:
        summary_errors.append(
            {
                "field": "maximum_gap_seconds",
                "maximum": 1.0,
                "actual": summary.get("maximum_gap_seconds"),
            }
        )
    parser_contract = summary.get("parser_lifecycle_contract", {})
    if parser_contract.get("complete") is not True:
        summary_errors.append(
            {"field": "parser_lifecycle_contract", "actual": parser_contract}
        )

    passed = not any(
        (
            not samples,
            incomplete,
            memory_violations,
            oom_violations,
            psi_violations,
            not final_cleanup,
            summary_errors,
        )
    )
    return {
        "status": "PASS" if passed else "FAIL_RESOURCE_GATE",
        "limit_bytes": limit_bytes,
        "samples_evaluated": len(samples),
        "incomplete_sample_indexes": incomplete,
        "process_attribution_incomplete_sample_indexes": process_incomplete,
        "classified_cgroup_transition_sample_indexes": classified_transitions,
        "memory_violations": memory_violations,
        "oom_violations": oom_violations,
        "psi_violations": psi_violations,
        "final_sample_index": final_index,
        "final_sample_labels": sorted(final_labels),
        "final_sample_has_cleanup_markers": final_cleanup,
        "summary_errors": summary_errors,
        "rule": (
            "all 250 ms cgroup readings must remain continuous, at or below "
            "4 GiB with zero OOM and full PSI avg10; process PSS remains "
            "unknown for a separately classified confirmed-exit transition; "
            "the final sample must carry both cleanup markers"
        ),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def validate_parser_recycle_contract(
    accepted: dict[str, dict[str, Any]], bundle: dict[str, Any]
) -> dict[str, Any]:
    """Prove the fixture-local one-request parser policy from accepted results.

    Only fresh group work starts the warm parser. Restored and exact replay must
    reuse those same three group operations, so their accepted steps carry no
    new parser observation.
    """
    fixture = next(row for row in bundle["fixtures"] if row["id"] == FIXTURE)
    expected_pages = list(range(1, 16))
    require(
        fixture["original_pages"] == expected_pages,
        "fixture-07 page identity changed",
    )
    require(bundle["base_profile"].get("group_pages") == 5, "group size changed")

    mode_records = {}
    fresh_operations = None
    for mode in MODES:
        record = accepted[mode]
        result = record["result"]
        require(record["sid"] == FIXTURE and record["mode"] == mode,
                f"{mode} accepted identity changed")
        require(record["profile"].get("group_pages") == 5,
                f"{mode} group size changed")
        require(
            result.get("status") == "complete"
            and result.get("processing_complete") is True
            and result.get("pages") == 15,
            f"{mode} result is not a complete 15-page delivery",
        )
        groups = [step for step in result["steps"] if step.get("stage") == "group"]
        require(len(groups) == 3, f"{mode} did not retain three five-page groups")
        operations = [step["operation"] for step in groups]
        if fresh_operations is None:
            fresh_operations = operations
        else:
            require(operations == fresh_operations,
                    f"{mode} group operation identities changed")

        expected_reuse = mode != "fresh"
        require(
            [step.get("reused") for step in groups] == [expected_reuse] * 3,
            f"{mode} group reuse contract changed",
        )
        if expected_reuse:
            require(all("parser" not in step for step in groups),
                    f"{mode} unexpectedly started parser work")
        mode_records[mode] = {
            "pages": result["pages"],
            "group_pages": record["profile"]["group_pages"],
            "group_count": len(groups),
            "operations": operations,
            "reused": expected_reuse,
        }

    fresh_groups = [
        step
        for step in accepted["fresh"]["result"]["steps"]
        if step.get("stage") == "group"
    ]
    parser = [step.get("parser") for step in fresh_groups]
    require(all(isinstance(row, dict) for row in parser),
            "fresh group parser observation missing")
    require([row.get("recycles") for row in parser] == [1, 2, 3],
            "parser did not recycle after every completed group")
    require([row.get("restarts") for row in parser] == [1, 2, 3],
            "parser restart sequence does not match per-group recycle")
    pids = [row.get("pid") for row in parser]
    require(all(type(pid) is int and pid > 0 for pid in pids),
            "fresh group parser PID missing")
    require(all(left != right for left, right in zip(pids, pids[1:])),
            "parser PID was reused across adjacent groups")

    return {
        "status": "PASS fixture-07 parser recycle contract",
        "fixture": FIXTURE,
        "expected_page_groups": [[1, 5], [6, 10], [11, 15]],
        "group_scheduling": "sequential",
        "maximum_concurrent_activities": 1,
        "fresh_parser_pids": pids,
        "fresh_parser_recycles": [row["recycles"] for row in parser],
        "fresh_parser_restarts": [row["restarts"] for row in parser],
        "modes": mode_records,
    }


def validate_reviewed_inputs(args, config, bundle) -> dict[str, Any]:
    require(args.fixture == FIXTURE, "reviewed runner is fixture-07 only")
    require(args.modes == MODES, "reviewed mode sequence changed")
    require(config["parser_budgets"] == PARSER_BUDGETS, "parser budget identity changed")
    require(
        config["profiles"][FIXTURE]["method"] == bundle["base_profile"]["method"],
        "fixture-07 method changed",
    )

    manifest = _read_json(args.integration_manifest)
    review = _read_json(args.main_review)
    require(manifest.get("schema_version") == 1, "integration manifest schema changed")
    require(manifest.get("candidate") == "q04-yolo-reviewed-v1", "candidate changed")
    require(manifest.get("fixture") == FIXTURE, "manifest fixture changed")
    require(manifest.get("modes") == MODES, "manifest modes changed")
    require(manifest.get("runtime_authorized") is False, "manifest embeds authorization")
    require(
        manifest.get("status") == "HISTORICAL_FAILED_RECONCILED_OFFLINE",
        "manifest status changed",
    )
    require(
        manifest.get("production_default_changed") is False,
        "manifest changes production defaults",
    )
    require(
        manifest.get("identity", {}).get("phase") == args.name
        and manifest.get("identity", {}).get("prefix") == args.expected_prefix,
        "manifest runtime identity changed",
    )
    require(
        manifest.get("parser_policy")
        == {
            "scope": "this fixture-07 candidate window only",
            "before_max_requests": 20,
            "after_max_requests": 1,
            "group_size_changed": False,
            "concurrency_changed": False,
            "production_default_changed": False,
            "parser_budgets": PARSER_BUDGETS,
        },
        "manifest parser policy changed",
    )
    require(
        manifest.get("resource_gate")
        == {
            "sample_interval_seconds": 0.25,
            "maximum_gap_seconds": 1.0,
            "max_cgroup_bytes": MAX_CGROUP_BYTES,
            "full_psi_avg10_max": 0.0,
            "oom_increment_max": 0,
            "required_oom_counters": ["oom", "oom_group_kill", "oom_kill"],
            "all_cgroup_samples_complete": True,
            "process_attribution_policy": {
                "raw_incomplete_preserved": True,
                "pss_substitution_allowed": False,
                "classified_exit_applies_to_cgroup_qualification_only": True,
                "same_cgroup_required": True,
                "same_pid_start_ticks_required": True,
                "adjacent_complete_enumeration_required": True,
                "exact_exit_event_required": True,
                "peak_process_attribution_complete_required": True,
            },
            "final_sample_labels": [
                "owned_cleanup_finished",
                "post_cleanup_sample",
            ],
        },
        "manifest resource gate changed",
    )
    require(
        review.get("status") == MAIN_REVIEW_STATUS,
        "main source-review disposition changed",
    )
    require(review.get("fixture") == FIXTURE, "main review fixture changed")
    require(
        review.get("historical_reference_mutated") is False
        and review.get("general_normalization") is False,
        "review scope expanded",
    )
    require(
        review.get("accepted_pairs")
        == [
            {"reference": "#/texts/20", "actual": ["#/texts/20", "#/texts/25"]},
            {"reference": "#/texts/156", "actual": ["#/texts/157", "#/texts/162"]},
        ],
        "reviewed continuation pairs changed",
    )
    artifact_paths = {
        "main_review": args.main_review,
        "equivalence_bundle": args.equivalence_bundle,
        "resource_bundle": args.resource_bundle,
        "parser_budgets": args.parser_budgets,
        "resource_analysis": args.resource_analysis,
        "historical_methods": args.historical_methods,
        "candidate_inputs": args.bundle / "inputs.json",
        "source_pdf": args.bundle / "originals/07.pdf",
        "reference_graph": args.bundle / "references/07.json",
    }
    observed = {name: sha(path.read_bytes()) for name, path in artifact_paths.items()}
    require(observed == manifest.get("artifacts"), "reviewed artifact identity changed")
    scope_sha = sha(canonical(manifest["authorization_scope"]).encode())
    require(
        scope_sha == manifest.get("authorization_scope_sha256")
        == args.authorization_scope_sha256,
        "authorization scope identity changed",
    )

    resource_result = validate_resource(
        _read_json(args.resource_bundle),
        args.parser_budgets.read_bytes(),
        args.resource_analysis.read_bytes(),
    )
    require(resource_result["status"] == "CANDIDATE_VALID", "resource candidate invalid")
    return {
        "manifest": manifest,
        "review": review,
        "artifact_sha256": observed,
        "resource_candidate": resource_result,
    }


def _reviewed_reference_checker(args, calls: list[str]):
    equivalence_bundle = _read_json(args.equivalence_bundle)
    source_bytes = (args.bundle / "originals/07.pdf").read_bytes()
    candidate_inputs_bytes = (args.bundle / "inputs.json").read_bytes()
    historical_methods_bytes = args.historical_methods.read_bytes()

    def check(document, reference, out):
        try:
            result = validate_equivalence(
                equivalence_bundle,
                reference,
                document,
                source_bytes=source_bytes,
                candidate_inputs_bytes=candidate_inputs_bytes,
                historical_methods_bytes=historical_methods_bytes,
            )
        except BaseException as error:
            (out / "source-reviewed-equivalence-failure.json").write_text(
                json.dumps(
                    {
                        "status": "FAIL_REVIEWED_EQUIVALENCE",
                        "type": type(error).__name__,
                        "reason": str(error),
                        "automatic_retry": False,
                    },
                    indent=2,
                )
                + "\n"
            )
            raise
        require(result["status"] == "CANDIDATE_VALID", "equivalence candidate invalid")
        integration = {
            "status": "PASS_FIXTURE_LOCAL_REVIEWED_EQUIVALENCE",
            "fixture": FIXTURE,
            "candidate_validation": result,
            "main_review_status": MAIN_REVIEW_STATUS,
            "historical_reference_mutated": False,
            "general_normalization": False,
            "runtime_scope": "this fixture-07 candidate window only",
        }
        (out / "source-reviewed-equivalence.json").write_text(
            json.dumps(integration, indent=2, ensure_ascii=False) + "\n"
        )
        calls.append(out.name)
        return result["identities"]["historical_reference_graph_sha256"]

    return check


async def run_window(args):
    bundle = json.loads((args.bundle / "inputs.json").read_text())
    config = _read_json(args.state / "config.json")
    reviewed = validate_reviewed_inputs(args, config, bundle)
    trial_root = args.state / args.name
    measurement_root = args.state / (args.name + "-measurement")
    calls: list[str] = []
    original_reference = consumer.check_reference
    original_write = q04_runtime.write

    def gated_write(path, value):
        if path.name == "fresh-index.json":
            path = path.with_name("fresh-index.pending.json")
        elif path.name == "phase-complete.json":
            path = path.with_name("runtime-phase-complete.pending.json")
        return original_write(path, value)

    consumer.check_reference = _reviewed_reference_checker(args, calls)
    q04_runtime.write = gated_write
    try:
        await run_lifecycle_window(args)
    finally:
        consumer.check_reference = original_reference
        q04_runtime.write = original_write

    require(sorted(calls) == ["fresh-07", "replay-07", "restored-07"],
            "reviewed oracle did not check all three modes")
    try:
        recycle_contract = validate_parser_recycle_contract(
            validate_matrix_records(trial_root), bundle
        )
    except BaseException as error:
        original_write(
            trial_root / "reviewed-window-failure.json",
            {
                "status": "FAIL_PARSER_RECYCLE_CONTRACT",
                "type": type(error).__name__,
                "reason": str(error),
                "fresh_index_integrated": False,
                "automatic_retry": False,
            },
        )
        raise
    samples = _read_jsonl(measurement_root / "resource-attribution.jsonl")
    summary = _read_json(measurement_root / "resource-attribution-summary.json")
    gate = evaluate_resource_gate(samples, summary)
    (measurement_root / "all-sample-resource-gate.json").write_text(
        json.dumps(gate, indent=2, sort_keys=True) + "\n"
    )
    if gate["status"] != "PASS":
        original_write(
            trial_root / "reviewed-window-failure.json",
            {
                "status": gate["status"],
                "fresh_index_integrated": False,
                "automatic_retry": False,
            },
        )
        raise ValueError("reviewed fixture-07 all-sample resource gate failed")

    pending_index = trial_root / "fresh-index.pending.json"
    require(pending_index.is_file(), "pending fresh index missing")
    fresh_index = _read_json(pending_index)
    require(set(fresh_index) == {FIXTURE}, "fresh index fixture scope changed")
    original_write(trial_root / "fresh-index.json", fresh_index)
    contract = {
        "status": "PASS bounded fixture-07 candidate only",
        "fixture": FIXTURE,
        "modes": MODES,
        "fresh_index_integrated": True,
        "equivalence_bundle_sha256": reviewed["artifact_sha256"][
            "equivalence_bundle"
        ],
        "parser_budget_identity_sha256": reviewed["artifact_sha256"][
            "parser_budgets"
        ],
        "parser_budgets": PARSER_BUDGETS,
        "parser_recycle_contract": recycle_contract,
        "resource_gate": gate,
        "automatic_retry": False,
        "production_default_changed": False,
        "historical_reference_mutated": False,
        "general_normalization": False,
    }
    original_write(trial_root / "reviewed-window-contract.json", contract)
    original_write(
        trial_root / "phase-complete.json",
        {
            "phase": args.name,
            "fixture": FIXTURE,
            "modes": MODES,
            "status": contract["status"],
            "fresh_index": str(trial_root / "fresh-index.json"),
        },
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "bundle",
        "state",
        "capacity",
        "integration-manifest",
        "main-review",
        "equivalence-bundle",
        "resource-bundle",
        "parser-budgets",
        "resource-analysis",
        "historical-methods",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--fixture", default=FIXTURE, choices=[FIXTURE])
    parser.add_argument("--modes", nargs=3, default=MODES)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--expected-prefix", required=True)
    parser.add_argument("--authorization-scope-sha256", required=True)
    parser.add_argument("--attribution-interval-seconds", type=float, default=0.25)
    parser.add_argument("--attribution-gap-seconds", type=float, default=1.0)
    parser.add_argument("--capacity-approved", action="store_true")
    args = parser.parse_args(argv)
    if not args.capacity_approved:
        parser.error("new capacity approval is required")
    if args.attribution_interval_seconds != 0.25 or args.attribution_gap_seconds != 1:
        parser.error("reviewed attribution cadence is 250 ms with a 1-second gap")
    asyncio.run(run_window(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
