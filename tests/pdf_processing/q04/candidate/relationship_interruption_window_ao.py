"""Interrupt current required relationship evidence, recover, and replay."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time
import uuid
from datetime import timedelta

import consumer
from candidate.warm_pod_window_r import projected_aima_oracle, validate_contract
from candidate.warm_v3_reference import reviewed_reference_checker, verify_v3_bundle
from candidate.yolo_candidate_measure import AttributedCandidateRun
from candidate.yolo_reviewed_window import evaluate_resource_gate
from consumer import Consumer, canonical, require, sha
from contracts import mode_checks, validate_window
from host_ao import Host
from prepare import verify_bundle
import q04_runtime
from sentinel.aima_attribution_telemetry_q import StrictAttributionCollector
from sentinel import aima_attribution_telemetry_q as attribution
from telemetry import check_coverage, read_rows


FIXTURES = ("native",)
MODES = ("fresh", "interrupt", "recovery", "replay")
Q04 = Path(__file__).resolve().parent.parent


def validate_scope(args):
    manifest = json.loads(args.integration_manifest.read_text())
    scope = manifest["authorization_scope"]
    require(scope == {
        "fixtures": list(FIXTURES), "modes": list(MODES),
        "max_requests": 20, "automatic_retry": False,
        "measurement": "complete process attribution and required relationship interruption",
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


def validate_recovery(root, manifest):
    fresh = json.loads((root / "fresh-native/accepted.json").read_text())
    interrupted = json.loads((root / "interrupted-native/admission.json").read_text())
    failed = json.loads((root / "interrupted-native/result.json").read_text())
    recovery = json.loads((root / "recovery-native/accepted.json").read_text())
    replay = json.loads((root / "replay-native/accepted.json").read_text())
    expected = manifest["native_document_sha256"]
    require(fresh["accepted"]["document_sha256"] == expected
            and recovery["accepted"]["document_sha256"] == expected
            and replay["accepted"]["document_sha256"] == expected,
            "original native output differs from AI baseline")
    require(interrupted["request"] == recovery["request"] == replay["request"]
            and interrupted["profile"] == recovery["profile"] == replay["profile"]
            and interrupted["request"]["request_id"] != fresh["request"]["request_id"]
            and interrupted["request"]["artifact"] == fresh["request"]["artifact"]
            and interrupted["producer"] == fresh["producer"] == recovery["producer"] == replay["producer"],
            "recovery changed accepted request, source, profile or producer")
    require(failed["status"] == "failed" and not failed["processing_complete"]
            and failed["error"] == {"category": "parser", "code": "execution_failed"}
            and failed["registered_pages"] == 51
            and failed["registered_components"] == failed["selected_components"] == 7
            and not (root / "interrupted-native/accepted.json").exists(),
            "interrupted relationship work was accepted")
    require(json.loads((root / "interrupted-native/publication-outcome.json").read_text())["ok"]
            and all(json.loads((root / "worker-1/stopped.json").read_text())[key]
                    for key in ("parser_absent", "scratch_absent")),
            "failed plan publication or owned cleanup proof missing")
    hook = json.loads((root / "worker-1/interruption-result.json").read_text())
    observation = hook["observation"]
    require(hook["plan"] == failed["plan"]
            and observation["signal"] == "SIGKILL"
            and observation["scope"] == "owned evidence child only"
            and observation["progress"] == "first_page_decoded"
            and observation["source_checked"]
            and observation["evidence_id"] == hook["evidence_id"]
            and (root / "worker-1/interruption/partial-manifest.json").exists(),
            "owned evidence-child interruption proof missing")
    history = json.loads((root / "interrupted-native/failure-history.json").read_text())
    require(sum(event["eventType"] == "EVENT_TYPE_ACTIVITY_TASK_FAILED"
                for event in history["events"]) == 1
            and history["events"][-1]["eventType"] == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED",
            "interrupted workflow retried automatically or did not finish")
    old = [step for step in fresh["result"]["steps"]
           if step["stage"] in ("group", "assembly")]
    reused = [step for step in recovery["result"]["steps"]
              if step["stage"] in ("group", "assembly")]
    require(len(old) == 12 and len(reused) == 12
            and all(not step["reused"] for step in old)
            and all(step["reused"] for step in reused)
            and [step["operation"] for step in old]
                == [step["operation"] for step in reused],
            "checked group/assembly reuse missing")
    interrupted_ocr = [step for step in failed["steps"]
                       if step["stage"] == "component_ocr"]
    ocr = [step for step in recovery["result"]["steps"]
           if step["stage"] == "component_ocr"]
    require(recovery["result"]["status"] == "complete"
            and recovery["result"]["processing_complete"]
            and recovery["result"]["registered_pages"] == 51
            and len(ocr) == recovery["result"]["registered_components"]
            and len(interrupted_ocr) == 7
            and all(not step["reused"] for step in interrupted_ocr)
            and [step["operation"] for step in ocr]
                == [step["operation"] for step in interrupted_ocr]
            and all(step["reused"] for step in ocr)
            and recovery["result"]["processing_result"] != fresh["result"]["processing_result"]
            and recovery["accepted"]["final"]["content_evidence"]
                != fresh["accepted"]["final"]["content_evidence"],
            "new evidence downstream identity missing")
    require(replay["result"]["processing_result"] == recovery["result"]["processing_result"]
            and replay["workflow_id"] != recovery["workflow_id"]
            and replay["mode"] == "replay"
            and replay["accepted"]["final"] == recovery["accepted"]["final"],
            "exact recovery replay changed final result")
    for label in ("fresh-native", "recovery-native", "replay-native"):
        accepted_history = json.loads((root / label / "history.json").read_text())
        require(accepted_history["events"][-1]["eventType"]
                == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"
                and not any(event["eventType"] == "EVENT_TYPE_ACTIVITY_TASK_FAILED"
                            for event in accepted_history["events"]),
                "accepted workflow history contains failed Activity")


def measurement_contract(outcome, summary, gate):
    return {
        "workload": "native fresh/required-relationship interruption/recovery/exact replay",
        "workload_succeeded": True,
        "qualification_complete": outcome.qualification_complete,
        "process_attribution_complete": summary["process_attribution_complete"],
        "cgroup_resource_complete": outcome.cgroup_resource_complete,
        "resource_gate": gate, "automatic_retry": False,
    }


async def exact_request_trial(run, bundle, root, request, profile, previous, mode):
    """Submit the interrupted request unchanged on its retained profile route."""
    from pdf_processing.processing_workflow import PDFProcessing

    target = root / ("recovery-native" if mode == "evidence" else "replay-native")
    target.mkdir(exist_ok=False)
    metadata = {"sid": "native", "mode": mode, "profile_key": "native-evidence",
                "request": request, "profile": profile, "producer": run.config["producer"],
                "worker_generation": run.host.generation, "window": run.config["window"],
                "config_sha256": sha(run.host.config_path.read_bytes())}
    q04_runtime.write(target / "admission.json", metadata)
    await run.guard()
    started = time.time()
    workflow_id = run.config["run_id"] + "-" + target.name + "-" + uuid.uuid4().hex
    q04_runtime.write(target / "workflow-intent.json", {
        "workflow_id": workflow_id, "phase": root.name,
        "trial": target.name, "created": started,
    })
    handle = await run.client.start_workflow(PDFProcessing.run,
        {"request": request, "activity_queue": run.config["queues"]["native-evidence"]},
        id=workflow_id, task_queue=run.config["workflow_queue"],
        execution_timeout=timedelta(seconds=min(
            run.config["trial_seconds"],
            run.config["window"]["ends_at"] - run.config["window"]["cleanup_seconds"] - time.time())))
    run.active = handle
    q04_runtime.write(target / "workflow.json", {"workflow_id": workflow_id, "started": started})
    task = asyncio.create_task(handle.result())
    result = None
    try:
        with (target / "progress.jsonl").open("x", buffering=1) as log:
            while not task.done():
                await run.guard()
                log.write(json.dumps({"time": time.time(),
                                      "progress": await handle.query(PDFProcessing.progress)}) + "\n")
                await asyncio.sleep(.5)
        result = await task
        q04_runtime.write(target / "result.json", result)
        require(result["status"] == "complete" and result["processing_complete"],
                "recovery workflow incomplete")
        fixture = next(item for item in bundle["fixtures"] if item["id"] == "native")
        accepted = await asyncio.to_thread(Consumer(run.store, target).verify,
                                           result, request, profile, fixture,
                                           Path(run.config["bundle"]) / "oracles")
        if mode == "replay":
            mode_checks(mode, result, accepted, previous)
        (target / "history.json").write_text((await handle.fetch_history()).to_json())
        finished = time.time()
        await asyncio.sleep(.6)
        await run.guard()
        coverage = check_coverage(read_rows(run.host.current / "samples.jsonl"),
                                  started, finished,
                                  run.config["window"]["max_sample_gap_seconds"])
        metadata.update(result=result, accepted=accepted, resource=coverage,
                        verified=True, directory=str(target), workflow_id=workflow_id)
        q04_runtime.write(target / "accepted.json", metadata)
        run.active = None
        return metadata
    except BaseException as error:
        outcomes = await run.retain_failure(target, error, None, handle, task, request, True)
        failures = [name for name, outcome in outcomes.items() if not outcome["ok"]]
        if failures:
            raise RuntimeError(f"{type(error).__name__}: {error}; cleanup/evidence failures: {failures}") from error
        raise


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
    original_classifier = attribution._command_class
    previous_lock = os.environ.get("PDF_PROCESS_LIFECYCLE_LOCK")
    previous_timeout = os.environ.get("PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS")
    primary_error = None
    outcome = None
    records = {}
    def classify_worker(payload):
        return "worker" if b"worker_ao.py" in payload else original_classifier(payload)

    attribution._command_class = classify_worker
    consumer.check_reference = reviewed_reference_checker(args.bundle, original_reference)
    try:
        os.environ["PDF_PROCESS_LIFECYCLE_LOCK"] = str(collector.lifecycle_lock_path)
        os.environ["PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS"] = str(args.attribution_gap_seconds)
        with projected_aima_oracle(args.bundle):
            async with Worker(client, task_queue=config["workflow_queue"], workflows=[PDFProcessing]):
                collector.start()
                await host.start()
                await run.admission()
                fresh = await run.trial("native", "fresh", "fresh-native")
                records["native"] = fresh
                interrupted_error = None
                try:
                    await run.trial("native", "evidence", "interrupted-native", fresh)
                except ValueError as error:
                    interrupted_error = error
                require(interrupted_error is not None
                        and str(interrupted_error) == "workflow incomplete",
                        "required relationship interruption did not fail closed")
                interrupted = json.loads((root / "interrupted-native/admission.json").read_text())
                failed = json.loads((root / "interrupted-native/result.json").read_text())
                require(failed["status"] == "failed"
                        and failed["error"] == {"category": "parser", "code": "execution_failed"}
                        and not failed["processing_complete"]
                        and host.process is None
                        and (root / "worker-1/interruption-result.json").exists(),
                        "interruption result or owned worker stop missing")
                run.no_complete(interrupted["request"])
                await host.prepare_start()
                await collector.process_transition("recovery_worker_start", host.launch_start)
                await host.await_ready()
                run.initial = None
                recovery = await exact_request_trial(
                    run, bundle, root, interrupted["request"], interrupted["profile"],
                    fresh, "evidence")
                await exact_request_trial(
                    run, bundle, root, interrupted["request"], interrupted["profile"],
                    recovery, "replay")
                validate_recovery(root, manifest)
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
                collector.observe("owned_cleanup_finished", source="relationship_interruption_window_ao",
                                  meaning="worker_returned_after_owned_cleanup")
                outcome = collector.stop(expect_cancel=False,
                    require_no_warm_fresh_overlap=True)
        finally:
            attribution._command_class = original_classifier
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
            "required relationship process attribution incomplete")
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
        "status": "PASS required relationship interruption recovery and replay",
        "fixtures": list(FIXTURES), "modes": list(MODES),
        "native_document_sha256": manifest["native_document_sha256"],
    })
    q04_runtime.write(root / "phase-complete.json", {
        "status": "PASS required relationship interruption recovery and replay",
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
