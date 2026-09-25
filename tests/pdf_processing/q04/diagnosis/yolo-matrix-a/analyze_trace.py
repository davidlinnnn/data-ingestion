"""Replay and attribute the immutable YOLO matrix A guard trace offline."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from typing import Any


HERE = Path(__file__).resolve().parent
Q04 = HERE.parents[1]
REPO = HERE.parents[4]
DEFAULT_EVIDENCE = Path("/private/tmp/q04-yolo-matrix-20260918-a")
DEFAULT_ACL_RESOURCE = Path(
    "/private/tmp/q04-acl-fresh-resource-20260917-v1/resource-decomposition.json"
)
SUMMARY = Q04 / "sentinel/yolo-matrix-a/evidence/summary.json"
SAMPLES_MEMBER = "./state/yolo-matrix-a/worker-1/samples.jsonl"
PROGRESS_MEMBER = "./state/yolo-matrix-a/fresh-07/progress.jsonl"
HISTORY_MEMBER = "./state/yolo-matrix-a/fresh-07/failure-history.json"
FAILURE_MEMBER = "./state/yolo-matrix-a/fresh-07/failure.json"
WORKER_LOG_MEMBER = "./state/yolo-matrix-a/worker-1.log"


def require(condition: bool, message: str) -> None:
    """Reject evidence that no longer satisfies a diagnosed invariant."""
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def member_json(archive: tarfile.TarFile, name: str) -> Any:
    stream = archive.extractfile(name)
    require(stream is not None, f"missing archive member: {name}")
    return json.load(stream)


def member_rows(archive: tarfile.TarFile, name: str) -> list[dict[str, Any]]:
    stream = archive.extractfile(name)
    require(stream is not None, f"missing archive member: {name}")
    return [json.loads(line) for line in stream if line.strip()]


def epoch(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def payload(attributes: dict[str, Any]) -> dict[str, Any]:
    encoded = attributes["input"]["payloads"][0]["data"]
    return json.loads(base64.b64decode(encoded))


def nearest_sample(samples: list[dict[str, Any]], timestamp: float) -> dict[str, Any]:
    return min(samples, key=lambda row: abs(row["time"] - timestamp))


def verify_private_artifacts(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    summary = json.loads(SUMMARY.read_text())
    observed = {}
    for name, expected in summary["private_artifacts"].items():
        observed[name] = sha256(root / name)
        require(observed[name] == expected, f"artifact hash mismatch: {name}")
    return summary, observed


def code_semantics() -> dict[str, Any]:
    worker = (Q04 / "worker.py").read_text()
    supervision_path = REPO / "src/pdf_processing/supervision.py"
    execution_path = REPO / "src/pdf_processing/execution.py"
    supervision = supervision_path.read_text()
    execution = execution_path.read_text()

    require("parser_count=parser.count" in worker, "worker parser_count semantics changed")
    require("self.count += 1" in supervision, "WarmParser increment semantics changed")
    require("self.count = 0" in supervision, "WarmParser reset semantics changed")
    require(
        "module == 'pdf_processing.parse' and request.get('mode') == 'capture'" in execution,
        "capture delegation semantics changed",
    )
    require("{**request, 'mode': 'restore'" in execution, "assembly restore semantics changed")
    return {
        "parser_count_meaning": "completed requests in one WarmParser lifetime",
        "parser_count_is_process_count": False,
        "capture_uses_warm_parser": True,
        "assembly_restore_would_use_fresh_child_if_invoked": True,
        "fresh_child_spawn_observed": False,
        "fresh_child_identity_in_worker_samples": False,
        "source_hashes": {
            "execution.py": sha256(execution_path),
            "supervision.py": sha256(supervision_path),
            "worker.py": sha256(Q04 / "worker.py"),
        },
    }


def activity_timeline(history: dict[str, Any]) -> list[dict[str, Any]]:
    completed = {}
    for event in history["events"]:
        attributes = event.get("activityTaskCompletedEventAttributes")
        if attributes:
            completed[str(attributes["scheduledEventId"])] = event["eventTime"]

    timeline = []
    for event in history["events"]:
        attributes = event.get("activityTaskScheduledEventAttributes")
        if not attributes:
            continue
        value = payload(attributes)
        operation = value.get("operation") or {}
        kind = operation.get("kind", value.get("stage"))
        row = {
            "scheduled_event_id": event["eventId"],
            "kind": kind,
            "scheduled_at": event["eventTime"],
            "completed_at": completed.get(event["eventId"]),
        }
        if kind == "group":
            row["pages"] = [operation["start"], operation["end"]]
        timeline.append(row)
    return timeline


def summarize(
    root: Path = DEFAULT_EVIDENCE,
    acl_resource_path: Path = DEFAULT_ACL_RESOURCE,
) -> dict[str, Any]:
    summary, hashes = verify_private_artifacts(root)
    capacity = json.loads((root / "capacity.json").read_text())
    cleanup = json.loads((root / "cleanup.json").read_text())
    runtime_staging = json.loads((root / "runtime-staging.json").read_text())
    acl = json.loads(acl_resource_path.read_text())
    semantics = code_semantics()
    for name in ("execution.py", "supervision.py"):
        require(
            semantics["source_hashes"][name] == runtime_staging["producer"][name],
            f"diagnosed producer differs from staged runtime: {name}",
        )

    with tarfile.open(root / "remote-evidence.tar") as archive:
        samples = member_rows(archive, SAMPLES_MEMBER)
        progress = member_rows(archive, PROGRESS_MEMBER)
        history = member_json(archive, HISTORY_MEMBER)
        failure = member_json(archive, FAILURE_MEMBER)
        worker_log_stream = archive.extractfile(WORKER_LOG_MEMBER)
        require(worker_log_stream is not None, f"missing archive member: {WORKER_LOG_MEMBER}")
        worker_log = worker_log_stream.read().decode(errors="replace")

    require(failure["reason"] == "cgroup budget exceeded", "unexpected failure reason")
    require(len(samples) >= 2, "insufficient worker samples")
    require(
        all(b["time"] > a["time"] for a, b in zip(samples, samples[1:])),
        "worker samples are not strictly ordered",
    )
    ceiling = capacity["max_cgroup_bytes"]
    breaches = [row for row in samples if row["memory_current"] > ceiling]
    require(bool(breaches), "captured trace no longer reproduces the cgroup rejection")
    first_breach = breaches[0]
    peak = max(samples, key=lambda row: row["memory_current"])
    activities = activity_timeline(history)
    groups = [row for row in activities if row["kind"] == "group"]
    assembly = next(row for row in activities if row["kind"] == "assembly")
    require(len(groups) == 3, "expected exactly three group activities")
    require(all(row["completed_at"] for row in groups), "group activity did not complete")
    require(assembly["completed_at"] is None, "assembly unexpectedly completed in history")
    assembly_time = epoch(assembly["scheduled_at"])
    assembly_samples = [row for row in samples if row["time"] >= assembly_time]
    require(bool(assembly_samples), "no samples at or after assembly scheduling")

    last_progress = progress[-1]["progress"]
    group_steps = [row for row in last_progress["steps"] if row["stage"] == "group"]
    warm_pids = sorted({row["parser"]["pid"] for row in group_steps})
    request_ids = [row["parser"]["request_id"] for row in group_steps]
    require(len(warm_pids) == 1, "group records do not identify one warm parser PID")
    require(len(set(request_ids)) == 3, "group records do not identify three requests")
    require(max(row["parser_count"] for row in samples) == 3, "unexpected parser_count maximum")

    last_group = group_steps[-1]["parser"]
    post_assembly_observations = [row["parser"] for row in assembly_samples]
    require(
        all(row.get("request_id") == last_group["request_id"] for row in post_assembly_observations),
        "warm-parser request observation changed after assembly scheduling",
    )
    require(
        all(row.get("stage") == "checkpoint_commit" for row in post_assembly_observations),
        "warm-parser stage observation changed after assembly scheduling",
    )
    require(
        epoch(last_group["completed_at"]) < assembly_time,
        "last warm-parser request did not precede assembly scheduling",
    )

    boundaries = []
    workflow_start = epoch(history["events"][0]["eventTime"])
    for name, timestamp in [
        ("workflow_started", workflow_start),
        *[(f"group_{index}_completed", epoch(row["completed_at"])) for index, row in enumerate(groups, 1)],
        ("assembly_scheduled", assembly_time),
        ("first_guard_breach", first_breach["time"]),
        ("sampled_maximum", peak["time"]),
    ]:
        observed = nearest_sample(samples, timestamp)
        boundaries.append({
            "name": name,
            "event_time": timestamp,
            "sample_time": observed["time"],
            "sample_offset_seconds": observed["time"] - timestamp,
            "memory_current_bytes": observed["memory_current"],
            "available_bytes": observed["available"],
            "parser_count": observed["parser_count"],
            "sampled_parser_stage": observed["parser"].get("stage"),
        })

    acl_cgroup = acl["cgroup"]
    acl_owned = acl["owned_processes"]
    comparison = {
        "acl_fixture_09_attribution_trace": {
            "source_sha256": sha256(acl_resource_path),
            "baseline_cgroup_bytes": acl_cgroup["baseline"]["memory_current"],
            "sampled_peak_cgroup_bytes": acl_cgroup["maximum_memory_current"],
            "cleanup_cgroup_bytes": acl_cgroup["cleanup_final"]["memory_current"],
            "owned_pss_at_peak_bytes": acl_owned["pss_at_cgroup_peak_bytes"],
            "diagnostic_residual_at_peak_bytes": acl["diagnostic_residual"]["at_cgroup_peak_bytes"],
            "parser_max_pss_bytes": acl_owned["classes"]["parser"]["max_pss_bytes"],
            "owned_descendant_max_pss_bytes": acl_owned["classes"]["owned_descendant"]["max_pss_bytes"],
        },
        "yolo_fixture_07_guard_trace": {
            "first_worker_sample_cgroup_bytes": samples[0]["memory_current"],
            "sampled_peak_cgroup_bytes": peak["memory_current"],
            "cleanup_cgroup_bytes": None,
            "owned_pss_at_peak_bytes": None,
            "diagnostic_residual_at_peak_bytes": None,
            "parser_reported_peak_rss_kib": max(
                (row["parser"].get("memory") or {}).get("peak_rss", 0)
                for row in samples
            ),
        },
        "limits": [
            "ACL PSS class maxima are not simultaneous and cannot be summed.",
            "YOLO captured a warm-parser lifetime peak RSS, but no synchronized current RSS/PSS, memory.stat, complete process tree, or post-cleanup cgroup sample.",
            "Different fixture phases make the cgroup values comparative observations, not a scaling ratio.",
        ],
    }

    return {
        "scope": "offline_only_no_runtime",
        "verdict": "RED_CGROUP_GUARD_DURING_ASSEMBLY",
        "immutable_evidence": {
            "artifact_count": len(hashes),
            "remote_tar_sha256": hashes["remote-evidence.tar"],
            "all_top_level_hashes_verified": True,
            "diagnosed_producer_hashes_match_staged_runtime": True,
        },
        "guard": {
            "ceiling_bytes": ceiling,
            "first_breach_bytes": first_breach["memory_current"],
            "sampled_maximum_bytes": peak["memory_current"],
            "sampled_maximum_bytes_over_ceiling": peak["memory_current"] - ceiling,
            "censored_at_guard_stop": True,
            "sampled_maximum_after_cancel_request": peak["time"] > epoch(next(
                event["eventTime"] for event in history["events"]
                if event["eventType"] == "EVENT_TYPE_WORKFLOW_EXECUTION_CANCEL_REQUESTED"
            )),
            "counterfactual_uncensored_peak_bounded": False,
            "sampled_maximum_is_required_limit": False,
        },
        "timeline": {
            "activities": activities,
            "boundaries": boundaries,
            "workflow_cancel_requested_at": next(
                event["eventTime"] for event in history["events"]
                if event["eventType"] == "EVENT_TYPE_WORKFLOW_EXECUTION_CANCEL_REQUESTED"
            ),
            "cleanup_started_at": cleanup["started"],
            "cleanup_finished_at": cleanup["finished"],
            "post_cancel_activity_completion_warning": "Activity not found on completion" in worker_log,
            "last_progress_status": last_progress["status"],
            "processing_complete": last_progress["processing_complete"],
        },
        "parser_semantics": {
            **semantics,
            "warm_parser_pids": warm_pids,
            "warm_parser_request_ids": request_ids,
            "maximum_parser_count": max(row["parser_count"] for row in samples),
            "sampled_stage_is_stale_during_assembly": True,
            "last_warm_parser_completed_at": last_group["completed_at"],
            "assembly_scheduled_at": assembly["scheduled_at"],
        },
        "resource_scope": {
            "sample_count": len(samples),
            "minimum_available_bytes": min(row["available"] for row in samples),
            "maximum_psi_full_avg10": max(row["psi_full_avg10"] for row in samples),
            "vm_oom_kill_values": sorted({row["vm_oom_kill"] for row in samples}),
            "cgroup_oom_kill_values": sorted({row["memory_events"]["oom_kill"] for row in samples}),
            "maximum_sample_gap_seconds": max(
                b["time"] - a["time"] for a, b in zip(samples, samples[1:])
            ),
            "shared_coordinator_cgroup": True,
            "warm_parser_lifetime_peak_rss_present": True,
            "synchronized_current_process_rss_or_pss_present": False,
            "memory_stat_present": False,
            "post_cleanup_memory_sample_present": False,
            "exclusive_owner_attribution_supported": False,
        },
        "acl_comparison": comparison,
        "cause_boundary": {
            "established": [
                "the sampled shared cgroup crossed the fixed guard after assembly was scheduled",
                "one warm parser completed three capture requests and remained represented as ready",
                "the configured assembly restore code path would use a fresh child if restore invocation was reached",
                "PSI, VM OOM, cgroup OOM, telemetry-gap, and VM-memory-floor guards did not fire",
            ],
            "supported_not_proven": [
                "assembly-period materialization or restore-document construction contributed to the rise",
            ],
            "unresolved": [
                "whether and when assembly spawned a fresh restore child",
                "whether the warm parser and a fresh child were simultaneously alive",
                "simultaneous RSS/PSS of warm parser, assembly child, worker, and controller",
                "anon/file/kernel split and page-cache contribution",
                "concurrent unrelated coordinator-process contribution",
                "post-cleanup cgroup release",
            ],
        },
        "recommendation": {
            "next_measurement": "one fresh-only attribution calibration after separate authorization",
            "keep_current_guard": True,
            "raise_guard_from_this_trace": False,
            "capture": [
                "250 ms cgroup memory.current/memory.stat/memory.events/PSI through post-cleanup",
                "identity-fenced process tree with RSS/PSS, faults, and CPU for controller, worker, warm parser, and fresh child",
                "explicit warm-parser request state plus fresh-child PID and operation kind",
            ],
            "isolated_worker_cgroup": {
                "benefit": "separates owned worker and children from unrelated coordinator processes",
                "cost": "changes measurement topology and still does not prove Kubernetes Pod replacement or emptyDir cleanup",
                "use": "second step if shared-cgroup attribution remains ambiguous",
            },
            "pod_drain_relation": "an owned single-container Pod would provide a distinct container cgroup and better attribution, but requires the separately reviewed Deployment, UID/label fencing, shared bundle/state/evidence paths, replacement readiness, CRI absence, and emptyDir proof before drain testing",
        },
        "analysis_actions": {
            "runtime_started": False,
            "workflow_submitted": False,
            "deployment_mutation": False,
            "production_changed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--acl-resource", type=Path, default=DEFAULT_ACL_RESOURCE)
    parser.add_argument(
        "--require-within-guard",
        action="store_true",
        help="require a green cgroup trace; intentionally fails for matrix A",
    )
    parser.add_argument(
        "--require-exclusive-attribution",
        action="store_true",
        help="require process/PSS attribution that this trace intentionally lacks",
    )
    args = parser.parse_args()
    result = summarize(args.evidence_root, args.acl_resource)
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.require_within_guard:
        print(result["verdict"], file=sys.stderr)
        return 1
    if args.require_exclusive_attribution:
        print("ATTRIBUTION_INCOMPLETE", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
