# pyright: reportMissingImports=false
"""Fresh-only YOLO fixture-07 attribution calibration driver."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import sys
import time

try:
    from .yolo_attribution_telemetry import StrictAttributionCollector
except ImportError:
    from yolo_attribution_telemetry import StrictAttributionCollector
from consumer import require, sha
from contracts import validate_window
from host import Host
from prepare import verify_bundle
from q04_runtime import Run, write


class AttributedRun(Run):
    """Keep the unchanged worker guard authoritative and check collector health."""

    def __init__(self, *args, collector: StrictAttributionCollector, **kwargs):
        super().__init__(*args, **kwargs)
        self.collector = collector

    async def guard(self):
        self.collector.require_healthy()
        row = await super().guard()
        self.collector.require_healthy()
        return row


def is_expected_guard_stop(error: BaseException) -> bool:
    return str(error) == "cgroup budget exceeded"


async def run_fresh(args):
    import boto3
    from temporalio.client import Client
    from temporalio.worker import Worker
    from pdf_processing.object_store import Store
    from pdf_processing.processing_workflow import PDFProcessing

    bundle = verify_bundle(args.bundle)
    window = json.loads(args.capacity.read_text())
    validate_window(window, time.time())
    require(args.capacity_approved, "new capacity approval must be acknowledged")
    state_path = args.state / "config.json"
    require(state_path.exists(), "existing frozen state is required")
    config = json.loads(state_path.read_text())
    require(config["run_id"] == args.expected_run_id, "frozen run identity changed")
    require(config["prefix"] == args.expected_prefix, "frozen object prefix changed")
    require(
        config["bundle_sha256"] == sha((args.bundle / "inputs.json").read_bytes()),
        "input bundle differs from frozen run",
    )
    require(str(args.bundle.resolve()) == config["bundle"], "runtime bundle path changed")
    require(config["producer"] == bundle["producer"], "frozen producer changed")
    require(
        config["profiles"]["07"]["method"] == bundle["base_profile"]["method"],
        "fixture-07 profile changed",
    )

    config["window"] = window
    config["trial_seconds"] = args.trial_seconds
    trial_root = args.state / args.name
    trial_root.mkdir(exist_ok=False)
    config_path = trial_root / "config.json"
    write(config_path, config)
    os.environ["Q02_SOURCE_ORACLE"] = str(args.bundle / "oracles/aima-code.json")

    client = await Client.connect(config["temporal"])
    store = Store(
        boto3.client("s3", endpoint_url=config["endpoint"]),
        config["bucket"],
        config["prefix"],
    )
    host = Host(config_path, trial_root, config)
    collector = StrictAttributionCollector(
        trial_root / "resource-attribution.jsonl",
        trial_root / "resource-attribution-summary.json",
        observation_root=trial_root,
        interval_seconds=args.attribution_interval_seconds,
        attribution_gap_seconds=args.attribution_gap_seconds,
    )
    run = AttributedRun(config, bundle, trial_root, client, store, host, collector=collector)
    primary_error = None
    cleanup_errors = {}
    record = None
    collector_outcome = None
    workload_outcome = None

    try:
        collector.start()
        collector.observe(
            "before_worker_start",
            source="controller_callback",
            meaning="callback_before_host_start",
        )
        async with Worker(
            client, task_queue=config["workflow_queue"], workflows=[PDFProcessing]
        ):
            await host.start()
            collector.observe(
                "worker_ready",
                source="controller_callback",
                meaning="host_ready_file_verified",
            )
            run.initial = None
            await run.admission()
            collector.observe(
                "per_case_admission_passed",
                source="controller_callback",
                meaning="unchanged_worker_guard_admission_completed",
            )
            try:
                record = await run.trial("07", "fresh", "fresh-07")
                workload_outcome = "fresh_completed"
            except BaseException as error:
                if is_expected_guard_stop(error):
                    workload_outcome = "guard_stop"
                    primary_error = error
                else:
                    raise
    except BaseException as error:
        primary_error = error
    finally:
        if run.active:
            try:
                collector.observe(
                    "cancel_requested",
                    source="controller_callback",
                    meaning="owned_workflow_cancel_callback_invoked",
                )
                await asyncio.wait_for(run.cancel_owned(run.active), 30)
                collector.observe(
                    "cancel_completed",
                    source="controller_callback",
                    meaning="owned_workflow_cancel_callback_returned",
                )
            except BaseException as error:
                cleanup_errors["cancel"] = str(error)
        try:
            await host.stop()
        except BaseException as error:
            cleanup_errors["worker_stop"] = str(error)
        if collector.started:
            try:
                collector.observe(
                    "owned_cleanup_finished",
                    source="controller_callback",
                    meaning="cancel_and_host_stop_callbacks_returned",
                )
                collector_outcome = collector.stop()
            except BaseException as error:
                cleanup_errors["collector_stop"] = str(error)
        write(
            trial_root / "phase-cleanup.json",
            {
                "errors": cleanup_errors,
                "collector": None if collector_outcome is None else {
                    "samples": collector_outcome.samples,
                    "maximum_gap_seconds": collector_outcome.maximum_gap_seconds,
                    "status": collector_outcome.status,
                    "complete": collector_outcome.attribution_complete,
                    "incomplete_samples": collector_outcome.incomplete_samples,
                    "errors": list(collector_outcome.errors),
                },
            },
        )

    unexpected_error = primary_error is not None and not is_expected_guard_stop(primary_error)
    if unexpected_error or cleanup_errors:
        error = primary_error or RuntimeError("owned cleanup failed")
        write(
            trial_root / "phase-failure.json",
            {
                "type": type(error).__name__,
                "reason": str(error),
                "cleanup_errors": cleanup_errors,
                "automatic_retry": False,
            },
        )
        raise error
    if collector_outcome is None or not collector_outcome.attribution_complete:
        error = ValueError("attribution evidence incomplete; guard is not reinterpreted")
        write(
            trial_root / "measurement-incomplete.json",
            {
                "type": type(error).__name__,
                "reason": str(error),
                "workload_outcome": workload_outcome,
                "fresh_accepted": False,
                "guard_result_reinterpreted": False,
            },
        )
        raise error

    write(
        trial_root / "phase-complete.json",
        {
            "phase": args.name,
            "fixture": "07",
            "modes": ["fresh"],
            "measurement_status": "COMPLETE",
            "workload_outcome": workload_outcome,
            "fresh_accepted": False,
            "acceptance_claimed": False,
            "request_id": None if record is None else record["request"]["request_id"],
            "artifact": None if record is None else record["request"]["artifact"],
            "frozen_run_id": config["run_id"],
            "frozen_prefix": config["prefix"],
            "attribution_samples": collector_outcome.samples,
            "automatic_retry": False,
            "time": time.time(),
        },
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "state", "capacity"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--expected-prefix", required=True)
    parser.add_argument("--trial-seconds", type=int, default=180)
    parser.add_argument("--attribution-interval-seconds", type=float, default=0.25)
    parser.add_argument("--attribution-gap-seconds", type=float, default=1.0)
    parser.add_argument("--capacity-approved", action="store_true")
    args = parser.parse_args(argv)
    if not args.capacity_approved or args.trial_seconds <= 0:
        parser.error("new capacity approval and positive trial timeout required")
    if args.attribution_interval_seconds != 0.25 or args.attribution_gap_seconds != 1:
        parser.error("reviewed attribution cadence is 250 ms with a 1-second gap")
    lock_path = Path(os.environ.get("PDF_QUALIFICATION_LOCK", "/tmp/data-ingestion-pdf-qualification.lock"))
    with lock_path.open("x+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run_fresh(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
