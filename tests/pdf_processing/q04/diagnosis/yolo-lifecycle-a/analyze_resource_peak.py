"""Explain the retained YOLO peak and enforce the future all-sample gate."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tarfile
from typing import Any


ARCHIVE_SHA256 = "5c183da78740cb68cc7114dc06a4e2a7bd890b17c7f7637dd69adc8495bb9bc9"
MAX_CGROUP_BYTES = 4 * 1024**3
EXPECTED_SAMPLES = 397
EXPECTED_PEAK_BYTES = 4_403_523_584


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iso_epoch(value: str) -> float:
    return datetime.fromisoformat(value).timestamp()


def evaluate_all_complete_samples(
    samples: list[dict[str, Any]],
    *,
    limit_bytes: int = MAX_CGROUP_BYTES,
    require_post_cleanup: bool = True,
) -> dict[str, Any]:
    incomplete = [
        index
        for index, sample in enumerate(samples)
        if not sample.get("attribution_complete")
        or sample.get("process_coverage", {}).get("status") != "complete"
    ]
    post_cleanup = [
        index
        for index, sample in enumerate(samples)
        if any(
            observation.get("label") == "post_cleanup_sample"
            for observation in sample.get("observations", [])
        )
    ]
    cleanup_finished = [
        index
        for index, sample in enumerate(samples)
        if any(
            observation.get("label") == "owned_cleanup_finished"
            for observation in sample.get("observations", [])
        )
    ]
    final_index = len(samples) - 1 if samples else None
    final_sample_has_cleanup_markers = (
        final_index is not None
        and final_index in post_cleanup
        and final_index in cleanup_finished
    )
    violations = [
        {
            "index": index,
            "time": sample["time"],
            "memory_current_bytes": sample["memory_current"],
            "excess_bytes": sample["memory_current"] - limit_bytes,
        }
        for index, sample in enumerate(samples)
        if sample["memory_current"] > limit_bytes
    ]
    passed = not incomplete and not violations and (
        final_sample_has_cleanup_markers or not require_post_cleanup
    )
    return {
        "status": "PASS" if passed else "FAIL_RESOURCE_GATE",
        "limit_bytes": limit_bytes,
        "samples_evaluated": len(samples),
        "incomplete_sample_indexes": incomplete,
        "violations": violations,
        "post_cleanup_sample_indexes": post_cleanup,
        "owned_cleanup_finished_sample_indexes": cleanup_finished,
        "final_sample_index": final_index,
        "final_sample_has_cleanup_markers": final_sample_has_cleanup_markers,
        "includes_post_cleanup": final_sample_has_cleanup_markers,
        "rule": "every attribution sample must be complete and at or below the unchanged 4 GiB limit; the final sample must carry owned_cleanup_finished and post_cleanup_sample",
    }


def _class_pss(sample: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for process in sample["processes"]:
        result[process["command_class"]] += process["pss_bytes"]
    return dict(result)


def _owned_class_pss(sample: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for process in sample["processes"]:
        if process["ownership"] == "owned":
            result[process["command_class"]] += process["pss_bytes"]
    return dict(result)


def _latest_steps(progress: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return max(progress, key=lambda row: len(row["progress"].get("steps", [])))[
        "progress"
    ]["steps"]


def _interval_summary(
    samples: list[dict[str, Any]], start: float, end: float
) -> dict[str, Any]:
    selected = [
        (index, sample)
        for index, sample in enumerate(samples)
        if start <= sample["time"] <= end
    ]
    if not selected:
        raise AssertionError("retained workload interval has no attribution sample")
    peak_index, peak = max(selected, key=lambda item: item[1]["memory_current"])
    return {
        "start": start,
        "end": end,
        "sample_count": len(selected),
        "maximum_sample_index": peak_index,
        "maximum_memory_current_bytes": peak["memory_current"],
        "maximum_owned_pss_bytes": max(
            sample["owned_pss_total_bytes"] for _, sample in selected
        ),
        "peak_owned_process_pss_by_class": _owned_class_pss(peak),
    }


def analyze(
    samples: list[dict[str, Any]],
    progress: list[dict[str, Any]],
    measurement_summary: dict[str, Any],
    runtime_config: dict[str, Any],
) -> dict[str, Any]:
    if len(samples) != EXPECTED_SAMPLES:
        raise AssertionError("retained attribution sample count changed")
    if any(not sample["attribution_complete"] for sample in samples):
        raise AssertionError("retained attribution is incomplete")
    if measurement_summary["incomplete_samples"] != 0:
        raise AssertionError("retained summary reports incomplete samples")
    peak_index = max(range(len(samples)), key=lambda index: samples[index]["memory_current"])
    peak = samples[peak_index]
    if peak["memory_current"] != EXPECTED_PEAK_BYTES:
        raise AssertionError("retained peak changed")

    gate = evaluate_all_complete_samples(samples)
    if [item["index"] for item in gate["violations"]] != [peak_index]:
        raise AssertionError("expected exactly the retained peak violation")

    steps = _latest_steps(progress)
    group_steps = [step for step in steps if step["stage"] == "group"]
    if len(group_steps) != 3:
        raise AssertionError("retained group sequence changed")
    intervals = []
    for number, step in enumerate(group_steps, 1):
        start = iso_epoch(step["parser"]["observed_at"])
        end = iso_epoch(step["observed_at"])
        intervals.append(
            {
                "group": number,
                "seconds": step["seconds"],
                "parser_pid": step["parser"]["pid"],
                "parser_peak_rss": step["parser"]["memory"],
                "parser_restarts": step["parser"]["restarts"],
                "parser_recycles": step["parser"]["recycles"],
                **_interval_summary(samples, start, end),
            }
        )

    peak_group = next(
        item for item in intervals if item["start"] <= peak["time"] <= item["end"]
    )
    if peak_group["group"] != 3:
        raise AssertionError("retained peak is no longer in group 3")
    peak_owned = _owned_class_pss(peak)
    if "fresh_parse_child" in peak_owned:
        raise AssertionError("retained peak unexpectedly overlaps a fresh parse child")
    if "warm_parser" not in peak_owned:
        raise AssertionError("retained peak lost its warm parser")

    baseline = samples[0]
    before = samples[peak_index - 1]
    after = samples[peak_index + 1]
    stat_delta = {
        key: peak["memory_stat"][key] - baseline["memory_stat"][key]
        for key in peak["memory_stat"]
    }
    parser_peaks = [item["parser_peak_rss"]["peak_rss"] for item in intervals]
    same_pid = len({item["parser_pid"] for item in intervals}) == 1
    monotonically_increasing_high_water = parser_peaks == sorted(parser_peaks)

    assembly_steps = [step for step in steps if step["stage"] == "assembly"]
    if len(assembly_steps) != 1:
        raise AssertionError("retained assembly sequence changed")
    assembly_step = assembly_steps[0]
    assembly_start = iso_epoch(group_steps[-1]["observed_at"])
    assembly_end = iso_epoch(assembly_step["observed_at"])
    assembly = {
        "stage": "assembly",
        "seconds": assembly_step["seconds"],
        **_interval_summary(samples, assembly_start, assembly_end),
    }

    ocr_steps = [step for step in steps if step["stage"] == "component_ocr"]
    if len(ocr_steps) != 4:
        raise AssertionError("retained OCR sequence changed")
    ocr = []
    ocr_start = assembly_end
    for step in ocr_steps:
        ocr_end = iso_epoch(step["observed_at"])
        ocr.append(
            {
                "stage": "component_ocr",
                "component": step["component"],
                "outcome": step["outcome"],
                **_interval_summary(samples, ocr_start, ocr_end),
            }
        )
        ocr_start = ocr_end

    observation_timeline = [
        {
            "sample_index": index,
            "sample_time": sample["time"],
            "label": observation["label"],
        }
        for index, sample in enumerate(samples)
        for observation in sample["observations"]
    ]

    return {
        "status": "FAIL_RESOURCE_GATE",
        "source_run": "yolo-lifecycle-a",
        "archive_sha256": ARCHIVE_SHA256,
        "gate": gate,
        "peak": {
            "index": peak_index,
            "time": peak["time"],
            "phase": "group_3_warm_parse",
            "memory_current_bytes": peak["memory_current"],
            "excess_bytes": peak["memory_current"] - MAX_CGROUP_BYTES,
            "owned_pss_total_bytes": peak["owned_pss_total_bytes"],
            "shared_cgroup_process_pss_total_bytes": peak[
                "shared_cgroup_process_pss_total_bytes"
            ],
            "diagnostic_unattributed_bytes": peak["diagnostic_unattributed_bytes"],
            "owned_process_pss_by_class": peak_owned,
            "all_process_pss_by_class": _class_pss(peak),
            "memory_stat": peak["memory_stat"],
            "memory_events": peak["memory_events"],
            "psi": peak["memory_pressure_raw"],
            "fresh_parse_child_present": False,
            "warm_fresh_overlap": False,
        },
        "exceedance_observation": {
            "sample_count": 1,
            "duration_directly_measured_seconds": None,
            "duration_reason": "one discrete sample cannot establish a nonzero duration",
            "upper_bound_seconds_between_adjacent_below_limit_samples": after["time"]
            - before["time"],
            "previous_sample": {
                "index": peak_index - 1,
                "time": before["time"],
                "memory_current_bytes": before["memory_current"],
            },
            "next_sample": {
                "index": peak_index + 1,
                "time": after["time"],
                "memory_current_bytes": after["memory_current"],
            },
        },
        "baseline": {
            "index": 0,
            "time": baseline["time"],
            "memory_current_bytes": baseline["memory_current"],
            "owned_pss_total_bytes": baseline["owned_pss_total_bytes"],
            "memory_stat": baseline["memory_stat"],
            "peak_minus_baseline_memory_current_bytes": peak["memory_current"]
            - baseline["memory_current"],
            "peak_minus_baseline_memory_stat": stat_delta,
        },
        "group_timeline": intervals,
        "assembly_timeline": assembly,
        "ocr_timeline": ocr,
        "observation_timeline": observation_timeline,
        "lifecycle_finding": {
            "same_warm_parser_pid_for_all_groups": same_pid,
            "parser_pid": intervals[0]["parser_pid"],
            "configured_max_requests": runtime_config["parser_budgets"][
                "max_requests"
            ],
            "reported_restarts": [item["parser_restarts"] for item in intervals],
            "reported_recycles": [item["parser_recycles"] for item in intervals],
            "parser_peak_rss_high_water_kib": parser_peaks,
            "monotonically_increasing_high_water": monotonically_increasing_high_water,
            "handoff_observed_after_group_3": measurement_summary[
                "no_warm_fresh_overlap"
            ]
            and "warm_handoff_observed"
            in measurement_summary["observed_observation_labels"],
            "cause": "the fixed overlap was removed; the only violation occurs while one retained warm parser serves its third sequential group request",
        },
        "cleanup": {
            "last_sample_index": len(samples) - 1,
            "last_memory_current_bytes": samples[-1]["memory_current"],
            "last_owned_pss_total_bytes": samples[-1]["owned_pss_total_bytes"],
            "post_cleanup_observed": gate["includes_post_cleanup"],
        },
        "preferred_minimal_disposition": {
            "kind": "fixture_window_parser_recycle_policy",
            "candidate_change": "set parser_budgets.max_requests from 20 to 1 for the next fixture-07 candidate window",
            "production_change": False,
            "status": "PENDING_MAIN_APPROVAL",
            "reason": "three sequential groups use one PID with zero recycles and increasing parser RSS high-water; only group 3 exceeds the unchanged limit",
            "required_future_validation": [
                "all attribution samples are complete",
                "every complete sample, including post-cleanup, is at or below 4,294,967,296 bytes",
                "no warm/fresh overlap and the handoff remains observed",
                "fresh graph/oracle and cleanup gates pass under a new identity",
            ],
        },
        "fallback_if_recycle_still_fails": {
            "kind": "dedicated_cgroup_or_linux_validation_host",
            "reason": "the shared baseline is 2,564,382,720 bytes (2.388 GiB) and includes 2,446,516,224 bytes (2.278 GiB) inactive file; isolate accounting rather than raising the 4 GiB limit or adding collectors",
            "limit_bytes": MAX_CGROUP_BYTES,
            "additional_measurement_window": False,
        },
    }


def load_archive(archive: Path) -> tuple[list, list, dict, dict]:
    if sha256(archive) != ARCHIVE_SHA256:
        raise AssertionError("retained archive changed")
    with tarfile.open(archive) as retained:
        def load_json(name: str) -> Any:
            member = retained.extractfile(name)
            if member is None:
                raise AssertionError(f"missing retained member: {name}")
            return json.load(member)

        def load_lines(name: str) -> list[dict[str, Any]]:
            member = retained.extractfile(name)
            if member is None:
                raise AssertionError(f"missing retained member: {name}")
            return [json.loads(line) for line in member]

        return (
            load_lines(
                "./state/yolo-lifecycle-a-measurement/resource-attribution.jsonl"
            ),
            load_lines("./state/yolo-lifecycle-a/fresh-07/progress.jsonl"),
            load_json(
                "./state/yolo-lifecycle-a-measurement/resource-attribution-summary.json"
            ),
            load_json("./state/yolo-lifecycle-a/config.json"),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(*load_archive(args.archive))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
