"""Prove an old native request rejects a changed profile and replays on its original route."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

import consumer
from candidate.warm_pod_window_r import projected_aima_oracle, validate_contract
from candidate.warm_v3_reference import reviewed_reference_checker, verify_v3_bundle
from candidate.yolo_candidate_measure import AttributedCandidateRun
from candidate.yolo_reviewed_window import evaluate_resource_gate
from consumer import canonical, require, sha
from contracts import validate_window
from host import Host
from prepare import verify_bundle
import q04_runtime
from sentinel.aima_attribution_telemetry_q import StrictAttributionCollector


FIXTURES = ("native",)
MODES = ("fresh", "old-request", "replay")
Q04 = Path(__file__).resolve().parent.parent


def validate_scope(args):
    manifest = json.loads(args.integration_manifest.read_text())
    scope = manifest["authorization_scope"]
    require(scope == {
        "fixtures": list(FIXTURES), "modes": list(MODES),
        "max_requests": 20, "automatic_retry": False,
        "measurement": "complete process attribution and changed-profile rejection",
    }, "matrix authorization scope changed")
    require(sha(canonical(scope).encode()) == args.authorization_scope_sha256
            == manifest["authorization_scope_sha256"], "runtime scope digest changed")
    require(manifest["identity"] == {
        "phase": args.name, "run_id": args.expected_run_id,
        "prefix": args.expected_prefix,
    }, "runtime identity changed")
    ai = json.loads((Q04 / "pod-topology-v34/first-window-evidence/INDEPENDENT-VERIFICATION.json").read_text())
    require(ai["status"] == "PASS_AI_WIKI_NATIVE_MATRIX_AND_AH_WARM_EQUALITY_ONLY"
            and ai["resource"]["gate_status"] == "PASS"
            and ai["terminal"]["cleanup_complete"], "AI native baseline changed")
    require(manifest["native_document_sha256"] == next(
        row["document_sha256"] for row in ai["workflows"]
        if row["fixture"] == "native" and row["mode"] == "fresh"
    ), "AI native document target changed")
    return manifest


def validate_rejection(root, manifest):
    fresh = json.loads((root / "fresh-native/accepted.json").read_text())
    rejected = json.loads((root / "old-request-native/accepted.json").read_text())
    replay = json.loads((root / "replay-native/accepted.json").read_text())
    expected = manifest["native_document_sha256"]
    require(fresh["accepted"]["document_sha256"] == expected
            and replay["accepted"]["document_sha256"] == expected,
            "original native output differs from AI baseline")
    require(fresh["request"] == rejected["request"] == replay["request"],
            "old request identity changed")
    require(fresh["profile"] != rejected["profile"]
            and fresh["profile"] == replay["profile"]
            and fresh["profile"]["id"] == rejected["profile"]["id"]
            and fresh["profile"]["method"] == rejected["profile"]["method"]
            and fresh["producer"] == rejected["producer"] == replay["producer"],
            "changed profile or retained route missing")
    require(rejected["verified"] and rejected["result"]["status"] == "failed"
            and rejected["result"]["error"]["code"] == "worker_method_mismatch"
            and not rejected["result"]["processing_complete"]
            and "processing_result" not in rejected["result"],
            "changed profile accepted old plan")
    require(replay["result"]["processing_result"] == fresh["result"]["processing_result"],
            "original accepted processing result changed")


def measurement_contract(outcome, summary, gate):
    return {
        "workload": "native fresh/changed-profile rejection/original-route replay",
        "workload_succeeded": True,
        "qualification_complete": outcome.qualification_complete,
        "process_attribution_complete": summary["process_attribution_complete"],
        "cgroup_resource_complete": outcome.cgroup_resource_complete,
        "resource_gate": gate, "automatic_retry": False,
    }


async def run_window(args):
    import boto3
    from pdf_processing.object_store import Store
    from pdf_processing.processing_workflow import PDFProcessing
    from temporalio.client import Client
    from temporalio.worker import Worker

    bundle = verify_bundle(args.bundle)
    verify_v3_bundle(args.bundle)
    window = json.loads(args.capacity.read_text())
    validate_window(window, time.time())
    require(args.capacity_approved, "capacity approval must be acknowledged")
    manifest = validate_scope(args)
    config = json.loads((args.state / "config.json").read_text())
    require(config["window"] == window and config["run_id"] == args.expected_run_id
            and config["prefix"] == args.expected_prefix, "initialized runtime changed")
    require(config["bundle"] == str(args.bundle.resolve())
            and config["bundle_sha256"] == sha((args.bundle / "inputs.json").read_bytes())
            and config["producer"] == bundle["producer"], "frozen bundle changed")
    validate_contract(config, bundle)
    root = args.state / args.name
    root.mkdir(exist_ok=False)
    measurement = args.state / (args.name + "-measurement")
    measurement.mkdir(exist_ok=False)
    q04_runtime.write(root / "config.json", config)
    collector = StrictAttributionCollector(
        measurement / "resource-attribution.jsonl",
        measurement / "resource-attribution-summary.json",
        observation_root=root, interval_seconds=args.attribution_interval_seconds,
        attribution_gap_seconds=args.attribution_gap_seconds,
        lifecycle_lock_path=measurement / "process-lifecycle.lock",
    )
    client = await Client.connect(config["temporal"])
    store = Store(boto3.client("s3", endpoint_url=config["endpoint"]),
                  config["bucket"], config["prefix"])
    host = Host(root / "config.json", root, config)
    run = AttributedCandidateRun(config, bundle, root, client, store, host,
                                 collector=collector)
    original_reference = consumer.check_reference
    previous_lock = os.environ.get("PDF_PROCESS_LIFECYCLE_LOCK")
    previous_timeout = os.environ.get("PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS")
    primary_error = None
    outcome = None
    records = {}
    consumer.check_reference = reviewed_reference_checker(args.bundle, original_reference)
    try:
        os.environ["PDF_PROCESS_LIFECYCLE_LOCK"] = str(collector.lifecycle_lock_path)
        os.environ["PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS"] = str(args.attribution_gap_seconds)
        with projected_aima_oracle(args.bundle):
            async with Worker(client, task_queue=config["workflow_queue"], workflows=[PDFProcessing]):
                collector.start()
                await host.start()
                await run.admission()
                for mode in MODES:
                    record = await run.trial("native", mode, f"{mode}-native",
                                             records.get("native"))
                    if mode == "fresh":
                        records["native"] = record
                validate_rejection(root, manifest)
                q04_runtime.write(root / "fresh-index.pending.json", {
                    sid: record["directory"] for sid, record in records.items()
                })
                await collector.process_transition("controlled_worker_shutdown", host.stop)
    except BaseException as error:
        primary_error = error
    finally:
        consumer.check_reference = original_reference
        if run.active:
            try:
                await asyncio.wait_for(run.cancel_owned(run.active), 30)
            except BaseException:
                pass
        try:
            if collector.started and host.process is not None:
                await collector.process_transition("failure_worker_shutdown", host.stop)
            else:
                await host.stop()
        except BaseException as error:
            primary_error = primary_error or error
        try:
            if collector.started:
                collector.observe("owned_cleanup_finished", source="profile_rejection_window_ak",
                                  meaning="worker_returned_after_owned_cleanup")
                outcome = collector.stop(expect_cancel=False,
                    require_no_warm_fresh_overlap=True)
        finally:
            for key, previous in (("PDF_PROCESS_LIFECYCLE_LOCK", previous_lock),
                                  ("PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS", previous_timeout)):
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous
    if primary_error is not None:
        q04_runtime.write(root / "phase-failure.json", {
            "type": type(primary_error).__name__, "reason": str(primary_error),
        })
        raise primary_error
    require(outcome is not None and outcome.attribution_complete,
            "profile rejection process attribution incomplete")
    summary = json.loads((measurement / "resource-attribution-summary.json").read_text())
    samples = [json.loads(line) for line in
               (measurement / "resource-attribution.jsonl").read_text().splitlines()]
    gate = evaluate_resource_gate(samples, summary)
    q04_runtime.write(measurement / "all-sample-resource-gate.json", gate)
    require(gate["status"] == "PASS", "all-sample resource gate failed")
    q04_runtime.write(measurement / "measurement-contract.json",
                      measurement_contract(outcome, summary, gate))
    q04_runtime.write(root / "fresh-index.json", json.loads(
        (root / "fresh-index.pending.json").read_text()))
    q04_runtime.write(root / "reviewed-window-contract.json", {
        "status": "PASS changed-profile old-request rejection and original replay",
        "fixtures": list(FIXTURES), "modes": list(MODES),
        "native_document_sha256": manifest["native_document_sha256"],
    })
    q04_runtime.write(root / "phase-complete.json", {
        "status": "PASS changed-profile old-request rejection and original replay",
    })


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "state", "capacity", "integration-manifest"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("name", "expected-run-id", "expected-prefix",
                 "authorization-scope-sha256"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--attribution-interval-seconds", type=float, default=0.25)
    parser.add_argument("--attribution-gap-seconds", type=float, default=1.0)
    parser.add_argument("--capacity-approved", action="store_true")
    args = parser.parse_args(argv)
    if not args.capacity_approved:
        parser.error("capacity approval is required")
    if args.attribution_interval_seconds != 0.25 or args.attribution_gap_seconds != 1:
        parser.error("reviewed attribution cadence is 250 ms with a 1-second gap")
    asyncio.run(run_window(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
