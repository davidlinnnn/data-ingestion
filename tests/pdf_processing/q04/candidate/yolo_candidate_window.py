"""Execute the fixed fixture-07 lifecycle matrix with attribution evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import time

from candidate.yolo_candidate_measure import AttributedCandidateRun
from consumer import require, sha
from contracts import validate_window
import q04_runtime
from prepare import verify_bundle
from sentinel.yolo_attribution_telemetry import StrictAttributionCollector


def validate_matrix_records(trial_root):
    """Bind restored comparison and replay to the accepted fresh baseline."""
    accepted = {
        mode: json.loads((trial_root / f"{mode}-07/accepted.json").read_text())
        for mode in ("fresh", "restored", "replay")
    }
    require(
        accepted["replay"]["request"] == accepted["fresh"]["request"],
        "exact replay did not preserve the fresh request",
    )
    require(
        accepted["restored"]["request"]["request_id"]
        != accepted["fresh"]["request"]["request_id"],
        "restored did not use a new request",
    )
    require(
        accepted["restored"]["request"]["artifact"]
        == accepted["fresh"]["request"]["artifact"],
        "restored did not reuse the captured source artifact",
    )
    return accepted


async def run_window(args):
    bundle = verify_bundle(args.bundle)
    window = json.loads(args.capacity.read_text())
    validate_window(window, time.time())
    require(args.capacity_approved, "new capacity approval must be acknowledged")
    state_path = args.state / "config.json"
    require(state_path.is_file(), "initialized candidate state is required")
    config = json.loads(state_path.read_text())
    require(config["run_id"] == args.expected_run_id, "candidate run identity changed")
    require(config["prefix"] == args.expected_prefix, "candidate prefix changed")
    require(config["bundle"] == str(args.bundle.resolve()), "candidate bundle path changed")
    require(
        config["bundle_sha256"] == sha((args.bundle / "inputs.json").read_bytes()),
        "candidate bundle hash changed",
    )
    require(config["producer"] == bundle["producer"], "candidate producer changed")
    require(
        config["profiles"]["07"]["method"] == bundle["base_profile"]["method"],
        "fixture-07 method changed",
    )

    trial_root = args.state / args.name
    require(not trial_root.exists(), "candidate phase identity already exists")
    measurement_root = args.state / (args.name + "-measurement")
    measurement_root.mkdir(exist_ok=False)
    collector = StrictAttributionCollector(
        measurement_root / "resource-attribution.jsonl",
        measurement_root / "resource-attribution-summary.json",
        observation_root=trial_root,
        interval_seconds=args.attribution_interval_seconds,
        attribution_gap_seconds=args.attribution_gap_seconds,
    )
    instances = []

    class BoundCandidateRun(AttributedCandidateRun):
        def __init__(self, *run_args, **run_kwargs):
            super().__init__(*run_args, collector=collector, **run_kwargs)
            instances.append(self)

    runtime_args = SimpleNamespace(
        bundle=args.bundle,
        state=args.state,
        capacity=args.capacity,
        phase="matrix",
        name=args.name,
        fresh=None,
        fixture=["07"],
        capacity_approved=True,
    )
    original_run = q04_runtime.Run
    primary_error = None
    outcome = None
    collector_started = False
    try:
        collector.start()
        collector_started = True
        q04_runtime.Run = BoundCandidateRun
        await q04_runtime.main(runtime_args)
    except BaseException as error:
        primary_error = error
    finally:
        q04_runtime.Run = original_run
        cancel_invoked = any(run.cancel_invoked for run in instances)
        summary = None
        if collector_started:
            collector.observe(
                "owned_cleanup_finished",
                source="candidate_window",
                meaning="q04_runtime_matrix_returned_after_owned_cleanup",
            )
            outcome = collector.stop(
                expect_cancel=cancel_invoked,
                require_handoff=True,
                require_no_warm_fresh_overlap=True,
            )
            summary = json.loads(
                (measurement_root / "resource-attribution-summary.json").read_text()
            )
        contract = {
            "workload": "fixture-07 fresh/restored/exact-fresh-replay",
            "workload_succeeded": primary_error is None,
            "cancel_callback_invoked": cancel_invoked,
            "cancel_marker_required": cancel_invoked,
            "successful_fresh_requires_cancel_marker": False,
            "attribution_complete": bool(outcome and outcome.attribution_complete),
            "no_warm_fresh_overlap": None
            if summary is None else summary["no_warm_fresh_overlap"],
            "handoff_observed": bool(
                summary
                and "warm_handoff_observed"
                in summary["observed_observation_labels"]
            ),
            "automatic_retry": False,
        }
        (measurement_root / "measurement-contract.json").write_text(
            json.dumps(contract, indent=2, sort_keys=True) + "\n"
        )

    if primary_error is not None:
        raise primary_error
    require(outcome is not None and outcome.attribution_complete,
            "candidate attribution evidence incomplete")
    require(not any(run.cancel_invoked for run in instances),
            "successful matrix unexpectedly invoked cancellation")
    validate_matrix_records(trial_root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "state", "capacity"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--expected-prefix", required=True)
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
