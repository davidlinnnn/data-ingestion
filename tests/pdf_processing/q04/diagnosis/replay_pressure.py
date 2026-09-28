"""Replay the captured Keynote resource trace through the frozen PSI guard."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def analyze(samples_path: Path, timeline_path: Path, failure_path: Path) -> dict:
    samples = rows(samples_path)
    timeline = json.loads(timeline_path.read_text())
    failure = json.loads(failure_path.read_text())
    assert len(samples) == 133
    assert all(b["time"] > a["time"] for a, b in zip(samples, samples[1:]))
    assert max(b["time"] - a["time"] for a, b in zip(samples, samples[1:])) <= 1
    assert {row["vm_oom_kill"] for row in samples} == {28}
    assert not any(row["memory_events"].get("oom_kill", 0) for row in samples)
    assert failure == {
        "type": "ValueError",
        "reason": "VM PSI pressure",
        "injection": None,
    }

    positive = [row for row in samples if row["psi_full_avg10"] > 0]
    assert positive, "captured trace does not reproduce VM PSI pressure"
    first = positive[0]
    previous = samples[samples.index(first) - 1]
    assert previous["psi_full_avg10"] == 0
    assert first["psi_full_avg10"] == 0.18
    assert first["parser"]["stage"] == "stage_enter"
    assert first["parser"]["pid"] == 9625
    assert timeline["events"][0]["name"] == "workflow_started"
    assert timeline["events"][-1]["name"] == "worker_stopped"

    return {
        "verdict": "RED_VM_PSI_PRESSURE",
        "guard_max_full_psi": 0,
        "observed_max_full_psi": max(row["psi_full_avg10"] for row in samples),
        "first_positive_psi_time": first["time"],
        "prior_zero_psi_time": previous["time"],
        "first_parser_sample_time": next(
            row["time"] for row in samples if row["parser"].get("pid") == 9625
        ),
        "first_stage_progress_time": first["parser"]["last_local_progress"],
        "minimum_available_bytes": min(row["available"] for row in samples),
        "maximum_cgroup_bytes": max(row["memory_current"] for row in samples),
        "vm_oom_kill_values": sorted({row["vm_oom_kill"] for row in samples}),
        "sample_count": len(samples),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--samples",
        type=Path,
        default=ROOT / "sentinel/evidence/samples.jsonl",
    )
    parser.add_argument(
        "--timeline",
        type=Path,
        default=Path(__file__).with_name("evidence") / "event-timeline.json",
    )
    parser.add_argument(
        "--failure",
        type=Path,
        default=ROOT / "sentinel/evidence/failure.json",
    )
    parser.add_argument(
        "--assert-captured",
        action="store_true",
        help="exit zero after proving the captured red verdict",
    )
    args = parser.parse_args()
    result = analyze(args.samples, args.timeline, args.failure)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if args.assert_captured else 1


if __name__ == "__main__":
    raise SystemExit(main())
