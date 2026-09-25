# pyright: reportMissingImports=false
"""Fresh-only ACL fixture-09 measurement driver for an existing frozen Q04 state."""

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
    from .acl_resource_telemetry import ResourceCollector
except ImportError:
    from acl_resource_telemetry import ResourceCollector
from consumer import require, sha
from contracts import validate_window
from host import Host
from prepare import verify_bundle
from q04_runtime import Run, write


class MeasuredRun(Run):
    """Existing runtime guard plus independent attribution-health checking."""

    def __init__(self, *args, collector: ResourceCollector, **kwargs):
        super().__init__(*args, **kwargs)
        self.collector = collector

    async def guard(self):
        self.collector.require_healthy()
        row = await super().guard()
        self.collector.require_healthy()
        return row


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
        config["profiles"]["09"]["method"] == bundle["base_profile"]["method"],
        "fixture-09 profile changed",
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
    collector = ResourceCollector(
        trial_root / "resource-attribution.jsonl",
        trial_root / "resource-attribution-summary.json",
        interval_seconds=args.attribution_interval_seconds,
        attribution_gap_seconds=args.attribution_gap_seconds,
    )
    run = MeasuredRun(
        config, bundle, trial_root, client, store, host, collector=collector
    )
    primary_error = None
    cleanup_errors = {}
    record = None
    outcome = None

    try:
        collector.start()
        collector.mark("before_worker_start")
        async with Worker(
            client, task_queue=config["workflow_queue"], workflows=[PDFProcessing]
        ):
            await host.start()
            collector.mark("worker_ready")
            run.initial = None
            await run.admission()
            collector.mark("per_case_admission_passed")
            record = await run.trial("09", "fresh", "fresh-09")
            collector.mark("fresh_trial_finished")
        await host.stop()
        collector.mark("worker_cleanup_finished")
    except BaseException as error:
        primary_error = error
    finally:
        if run.active:
            try:
                await asyncio.wait_for(run.cancel_owned(run.active), 30)
            except BaseException as error:
                cleanup_errors["cancel"] = str(error)
        try:
            await host.stop()
        except BaseException as error:
            cleanup_errors["worker_stop"] = str(error)
        if collector.started:
            try:
                collector.mark("after_owned_cleanup")
            except BaseException as error:
                cleanup_errors["resource_attribution_marker"] = str(error)
            try:
                outcome = collector.stop()
            except BaseException as error:
                cleanup_errors["resource_attribution_stop"] = str(error)
        write(
            trial_root / "phase-cleanup.json",
            {
                "errors": cleanup_errors,
                "attribution": None
                if outcome is None
                else {
                    "samples": outcome.samples,
                    "maximum_gap_seconds": outcome.maximum_gap_seconds,
                    "complete": outcome.attribution_complete,
                    "errors": list(outcome.errors),
                },
            },
        )

    if primary_error is not None:
        write(
            trial_root / "phase-failure.json",
            {"type": type(primary_error).__name__, "reason": str(primary_error)},
        )
        raise primary_error
    if cleanup_errors:
        error = RuntimeError("owned cleanup or attribution collector failed")
        write(
            trial_root / "phase-failure.json",
            {"type": type(error).__name__, "reason": str(error), "details": cleanup_errors},
        )
        raise error
    if outcome is None or not outcome.attribution_complete:
        error = ValueError("attribution evidence incomplete; not a memory violation")
        write(
            trial_root / "measurement-incomplete.json",
            {
                "type": type(error).__name__,
                "reason": str(error),
                "guard_result_reinterpreted": False,
            },
        )
        raise error
    assert record is not None
    write(trial_root / "fresh-index.json", {"09": record["directory"]})
    write(
        trial_root / "phase-complete.json",
        {
            "phase": args.name,
            "fixture": "09",
            "modes": ["fresh"],
            "status": "PASS fresh-only resource measurement slice",
            "request_id": record["request"]["request_id"],
            "artifact": record["request"]["artifact"],
            "frozen_run_id": config["run_id"],
            "frozen_prefix": config["prefix"],
            "attribution_samples": outcome.samples,
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
    lock_path = Path(
        os.environ.get(
            "PDF_QUALIFICATION_LOCK",
            "/tmp/data-ingestion-pdf-qualification.lock",
        )
    )
    with lock_path.open("x+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run_fresh(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
