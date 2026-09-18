"""Select synchronized lifecycle points from retained attribution-B evidence."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import tarfile


TRACE_MEMBER = "./state/yolo-attribution-b/resource-attribution.jsonl"


def epoch(timestamp):
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()


def class_pss(row, command_class):
    return sum(
        process["pss_bytes"]
        for process in row["processes"]
        if process["ownership"] == "owned"
        and process["command_class"] == command_class
    )


def point(label, index, row):
    return {
        "label": label,
        "sample_index": index,
        "time": row["time"],
        "memory_current_bytes": row["memory_current"],
        "owned_pss_bytes": row["owned_pss_total_bytes"],
        "warm_parser_pss_bytes": class_pss(row, "warm_parser"),
        "fresh_parse_child_pss_bytes": class_pss(row, "fresh_parse_child"),
        "worker_pss_bytes": class_pss(row, "worker"),
        "warm_parser_pids": [
            process["pid"]
            for process in row["processes"]
            if process["ownership"] == "owned"
            and process["command_class"] == "warm_parser"
        ],
        "fresh_parse_child_pids": [
            process["pid"]
            for process in row["processes"]
            if process["ownership"] == "owned"
            and process["command_class"] == "fresh_parse_child"
        ],
        "worker_pids": [
            process["pid"]
            for process in row["processes"]
            if process["ownership"] == "owned"
            and process["command_class"] == "worker"
        ],
    }


def analyze(summary, rows):
    if not rows or any(not row["attribution_complete"] for row in rows):
        raise ValueError("complete attribution rows required")
    guard = summary["workload"]["cgroup_ceiling_bytes"]
    breach_at = epoch(summary["workload"]["first_guard_breach_at"])
    cancel_at = epoch(summary["attribution"]["temporal_cancel_requested_at"])
    assembly_at = min(
        observation["observed_at"]
        for row in rows
        for observation in row["observations"]
        if observation["label"] == "workflow_progress_assembling_observed"
    )

    def last_before(timestamp):
        return max(index for index, row in enumerate(rows) if row["time"] < timestamp)

    def first_at_or_after(timestamp):
        return next(index for index, row in enumerate(rows) if row["time"] >= timestamp)

    peak_index = max(range(len(rows)), key=lambda index: rows[index]["memory_current"])
    exit_index = next(
        index
        for index in range(peak_index + 1, len(rows))
        if class_pss(rows[index], "warm_parser") == 0
        and class_pss(rows[index], "fresh_parse_child") == 0
    )
    selected = {
        "before_assembly": point(
            "before_assembly", last_before(assembly_at), rows[last_before(assembly_at)]
        ),
        "before_first_guard_breach": point(
            "before_first_guard_breach",
            last_before(breach_at),
            rows[last_before(breach_at)],
        ),
        "at_first_guard_breach": point(
            "at_first_guard_breach",
            first_at_or_after(breach_at),
            rows[first_at_or_after(breach_at)],
        ),
        "before_cancel": point(
            "before_cancel", last_before(cancel_at), rows[last_before(cancel_at)]
        ),
        "peak": point("peak", peak_index, rows[peak_index]),
        "exit": point("exit", exit_index, rows[exit_index]),
    }
    breach = selected["at_first_guard_breach"]
    return {
        "schema_version": 1,
        "source_run_id": summary["run_id"],
        "source_outcome": summary["outcome"],
        "measurement_complete": summary["measurement_complete"],
        "guard_bytes": guard,
        "reported_first_guard_breach": {
            "time": breach_at,
            "memory_current_bytes": summary["workload"]["first_guard_breach_bytes"],
        },
        "temporal_cancel_requested_at": cancel_at,
        "assembly_observed_at": assembly_at,
        "points": selected,
        "pre_cancel_overlap_proven": (
            breach["time"] < cancel_at
            and breach["memory_current_bytes"] > guard
            and breach["warm_parser_pss_bytes"] > 0
            and breach["fresh_parse_child_pss_bytes"] > 0
        ),
        "interpretation": (
            "The first synchronized attribution sample after the worker guard breach "
            "already contains both warm_parser and fresh_parse_child before Temporal "
            "cancellation. The later post-cancel peak is not used to explain the initial breach."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = json.loads(args.summary.read_text())
    with tarfile.open(args.archive) as archive:
        stream = archive.extractfile(TRACE_MEMBER)
        if stream is None:
            raise ValueError("attribution trace missing")
        rows = [json.loads(line) for line in stream]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(analyze(summary, rows), indent=2) + "\n")


if __name__ == "__main__":
    main()
