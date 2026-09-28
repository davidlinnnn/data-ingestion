"""Run the original Q04 29-group warm sequence under Q's Pod telemetry."""

from __future__ import annotations

import argparse
import asyncio
import copy
from collections import Counter
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import time

import consumer
from candidate.aima_image_supplement import REFERENCE_SHA, compare
from candidate.yolo_candidate_measure import AttributedCandidateRun
from candidate.yolo_equivalence_candidate import validate_candidate as validate_yolo
from candidate.yolo_reviewed_window import evaluate_resource_gate
from consumer import canonical, graph_projection, require, sha, source_signature
from contracts import validate_window, warm_checks
from host import Host
from prepare import verify_bundle
import q04_runtime
from sentinel.aima_attribution_telemetry_q import StrictAttributionCollector


SEQUENCE = ("06", "07", "08", "native", "06")
Q04 = Path(__file__).resolve().parent.parent


def measurement_content_signature(document):
    def without_edges(value):
        if isinstance(value, dict):
            return {
                key: without_edges(child)
                for key, child in value.items()
                if key not in {"self_ref", "$ref", "cref", "parent", "children", "captions"}
            }
        if isinstance(value, list):
            return [without_edges(child) for child in value]
        return value

    text_payloads = Counter()
    for node in document.get("texts", []):
        if not node.get("prov"):
            text_payloads[canonical(without_edges(node))] += 1
            continue
        metadata = {
            key: without_edges(value)
            for key, value in node.items()
            if key not in {
                "self_ref", "parent", "children", "captions", "references",
                "footnotes", "text", "orig", "prov",
            }
        }
        for provenance in node["prov"]:
            span = slice(*provenance["charspan"])
            text_payloads[canonical([
                {key: value for key, value in provenance.items() if key != "charspan"},
                node.get("text", "")[span],
                node.get("orig", "")[span],
                metadata,
            ])] += 1
    bound_payloads = {
        collection: sorted(
            canonical(without_edges(node))
            for node in document.get(collection, [])
        )
        for collection in ("pictures", "tables", "key_value_items", "form_items")
    }
    return {
        "source_regions": sorted(source_signature(document).elements()),
        "text_payloads": sorted(text_payloads.elements()),
        "bound_payloads": bound_payloads,
        "pages": canonical(without_edges(document.get("pages", {}))),
    }


def allow_pending_graph_for_measurement(sid: str, document, reference, out: Path):
    before = graph_projection(reference)
    after = graph_projection(document)
    if before == after:
        return sha(canonical(after).encode())
    require(
        measurement_content_signature(reference)
        == measurement_content_signature(document),
        f"{sid} source content changed during warm measurement",
    )
    q04_runtime.write(out / "source-review-pending.json", {
        "status": "NOT_ACCEPTED_WARM_MEASUREMENT_ONLY",
        "fixture": sid,
        "expected_graph_sha256": sha(canonical(before).encode()),
        "actual_graph_sha256": sha(canonical(after).encode()),
        "source_signature_equal": True,
        "fixture_acceptance": "unproven",
    })
    return sha(canonical(after).encode())


def validate_scope(args) -> dict:
    manifest = json.loads(args.integration_manifest.read_text())
    scope = manifest["authorization_scope"]
    require(scope == {
        "sequence": list(SEQUENCE),
        "group_requests": 29,
        "max_requests": 20,
        "expected_parser_generations": 2,
        "automatic_retry": False,
        "measurement": "complete process attribution and exact parser recycle",
    }, "warm authorization scope changed")
    require(
        sha(canonical(scope).encode()) == args.authorization_scope_sha256
        == manifest["authorization_scope_sha256"],
        "runtime scope digest changed",
    )
    require(manifest["identity"] == {
        "phase": args.name,
        "run_id": args.expected_run_id,
        "prefix": args.expected_prefix,
    }, "runtime identity changed")
    return manifest


def validate_contract(config, bundle):
    require(config["parser_budgets"] == {
        "startup_seconds": 120,
        "no_progress_seconds": 180,
        "terminate_seconds": 5,
        "reap_seconds": 5,
        "max_requests": 20,
    }, "original parser budget changed")
    originals = {
        fixture["id"]: config["profiles"][fixture["id"]]["content_evidence"]
        ["reviews"][fixture["sha256"]]["original_source"]["artifact"]
        for fixture in bundle["fixtures"]
    }
    require(
        config["profiles"] == q04_runtime.profiles(bundle, originals),
        "original fixture profile contract changed",
    )


def validate_process_evidence(summary: dict, proof: dict) -> dict:
    require(summary["process_attribution_complete"], "process attribution incomplete")
    require(summary["qualification_complete"], "resource qualification incomplete")
    pids = proof["pids"]
    rows = [json.loads(line) for line in Path(summary["resource_attribution_path"]).read_text().splitlines()]
    identities = {
        pid: {
            (process["pid"], process["start_ticks"])
            for row in rows
            for process in row["processes"]
            if process.get("pid") == pid
            and process.get("command_class") == "warm_parser"
            and process.get("status") == "complete"
        }
        for pid in pids
    }
    require(all(len(value) == 1 for value in identities.values()), "warm parser identity not uniquely observed")
    events = [event for row in rows for event in row.get("process_events", [])]
    for pid, value in identities.items():
        identity = next(iter(value))
        require(sum(
            event.get("event") == "exit_observed"
            and (event.get("pid"), event.get("start_ticks")) == identity
            for event in events
        ) == 1, "warm parser exit not uniquely observed")
        require(not any(
            event.get("event") == "pid_reuse_observed" and event.get("pid") == pid
            for event in events
        ), "warm parser PID reuse observed")
    return {
        "status": "PASS",
        "pids": pids,
        "identities": {str(pid): list(next(iter(value))) for pid, value in identities.items()},
        "exits": 2,
    }


def reviewed_reference_checker(bundle: Path, original):
    aima_path = bundle / "references/08.json"
    require(sha(aima_path.read_bytes()) == REFERENCE_SHA, "AIMA reference changed")
    aima_reference = json.loads(aima_path.read_text())
    yolo_reference = json.loads((bundle / "references/07.json").read_text())
    yolo_bundle = json.loads((Q04 / "candidate/yolo-equivalence-v1/BUNDLE.json").read_text())
    adoption = json.loads((Q04 / "candidate/yolo-equivalence-v2/ADOPTION.json").read_text())
    source_bytes = (bundle / "originals/07.pdf").read_bytes()
    inputs_bytes = (bundle / "inputs.json").read_bytes()
    methods_bytes = (
        Q04.parent / "t09a_r3/evidence/20260914-0b537d0-c/actual-methods.json"
    ).read_bytes()
    inputs = json.loads(inputs_bytes)
    reviewed_inputs = inputs
    inputs_sha = sha(inputs_bytes)
    if inputs_sha != adoption["current_candidate_inputs_sha256"]:
        rebinding = next((
            value
            for path in sorted((Q04 / "candidate").glob("warm-lifecycle-*/MANIFEST.json"))
            if (value := json.loads(path.read_text())).get("candidate_inputs_sha256")
            == inputs_sha
        ), None)
        require(rebinding is not None, "warm harness rebinding is not reviewed")
        bindings = rebinding["harness_bindings"]
        producer_bindings = rebinding.get("producer_bindings", {})
        require(
            inputs_sha == rebinding["candidate_inputs_sha256"]
            and rebinding["source_inputs_sha256"]
            == adoption["current_candidate_inputs_sha256"]
            and sorted(bindings) == sorted(rebinding["changed_harness_bindings"]),
            "YOLO producer adoption input identity changed",
        )
        normalized = copy.deepcopy(inputs)
        for name, binding in bindings.items():
            require(
                normalized["test_files"].get(name) == binding["candidate"],
                "warm harness rebinding changed",
            )
            normalized["test_files"][name] = binding["source"]
        for name, binding in producer_bindings.items():
            require(
                normalized["producer"].get(name) == binding["candidate"],
                "warm producer rebinding changed",
            )
            if binding["source"] is None:
                normalized["producer"].pop(name)
            else:
                normalized["producer"][name] = binding["source"]
        require(
            sha(canonical(normalized).encode())
            == rebinding["source_canonical_sha256"]
            == rebinding["normalized_candidate_sha256"],
            "warm bundle changed beyond reviewed harness bindings",
        )
        reviewed_inputs = normalized
    require(
        yolo_bundle["identities"]["candidate_inputs_sha256"]
        == adoption["previous_candidate_inputs_sha256"],
        "YOLO producer adoption input identity changed",
    )
    references = {
        sid: json.loads((bundle / "references" / f"{sid}.json").read_text())
        for sid in ("06", "native")
    }
    fixture = next(row for row in inputs["fixtures"] if row["id"] == "07")
    require(
        fixture["sha256"] == adoption["source_sha256"]
        and reviewed_inputs["producer"]["continuation.py"] == adoption["continuation_sha256"]
        and sha(canonical(reviewed_inputs["producer"]).encode())
        == adoption["current_producer_set_sha256"]
        and not any(adoption[name] for name in (
            "fixture_07_changed", "base_profile_changed", "reference_07_changed",
            "equivalence_rules_changed", "automatic_oracle_regeneration",
        )),
        "YOLO reviewed equivalence boundary changed",
    )
    yolo_bundle["identities"]["candidate_inputs_sha256"] = inputs_sha

    def check(document, reference, out):
        if reference == aima_reference:
            report = compare(document, reference, bundle / "fixtures/08.pdf")
            q04_runtime.write(out / "source-image-supplement.json", report)
            return report["actual_graph_sha256"]
        if reference == yolo_reference:
            result = validate_yolo(
                yolo_bundle,
                reference,
                document,
                source_bytes=source_bytes,
                candidate_inputs_bytes=inputs_bytes,
                historical_methods_bytes=methods_bytes,
            )
            require(result["status"] == "CANDIDATE_VALID", "YOLO equivalence invalid")
            q04_runtime.write(out / "source-reviewed-equivalence.json", {
                "status": "PASS_FIXTURE_LOCAL_REVIEWED_EQUIVALENCE",
                "fixture": "07",
                "candidate_validation": result,
                "producer_adoption": adoption,
                "historical_reference_mutated": False,
                "general_normalization": False,
            })
            return result["identities"]["historical_reference_graph_sha256"]
        for sid, pending_reference in references.items():
            if reference == pending_reference:
                return allow_pending_graph_for_measurement(
                    sid, document, reference, out
                )
        return original(document, reference, out)

    return check


@contextmanager
def projected_aima_oracle(bundle: Path):
    name = "Q02_SOURCE_ORACLE"
    prior = os.environ.get(name)
    os.environ[name] = str(bundle / "oracles/aima-code.json")
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = prior


async def run_window(args):
    from temporalio.client import Client
    from temporalio.worker import Worker
    import boto3
    from pdf_processing.object_store import Store
    from pdf_processing.processing_workflow import PDFProcessing

    bundle = verify_bundle(args.bundle)
    window = json.loads(args.capacity.read_text())
    validate_window(window, time.time())
    require(args.capacity_approved, "new capacity approval must be acknowledged")
    validate_scope(args)
    state_path = args.state / "config.json"
    require(state_path.is_file(), "initialized warm state is required")
    config = json.loads(state_path.read_text())
    require(window == config["window"], "capacity window differs from initialized state")
    require(config["run_id"] == args.expected_run_id, "run identity changed")
    require(config["prefix"] == args.expected_prefix, "object prefix changed")
    require(config["producer"] == bundle["producer"], "producer changed")
    validate_contract(config, bundle)

    root = args.state / args.name
    root.mkdir(exist_ok=False)
    measurement = args.state / (args.name + "-measurement")
    measurement.mkdir(exist_ok=False)
    original_reference = consumer.check_reference

    client = await Client.connect(config["temporal"])
    store = Store(
        boto3.client("s3", endpoint_url=config["endpoint"]),
        config["bucket"],
        config["prefix"],
    )
    host = Host(root / "config.json", root, config)
    (root / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    collector = StrictAttributionCollector(
        measurement / "resource-attribution.jsonl",
        measurement / "resource-attribution-summary.json",
        observation_root=root,
        interval_seconds=args.attribution_interval_seconds,
        attribution_gap_seconds=args.attribution_gap_seconds,
        lifecycle_lock_path=measurement / "process-lifecycle.lock",
    )
    warm_run = AttributedCandidateRun(
        config, bundle, root, client, store, host, collector=collector
    )
    primary_error = None
    outcome = None
    proof = None
    consumer.check_reference = reviewed_reference_checker(args.bundle, original_reference)
    previous_lifecycle_lock = os.environ.get("PDF_PROCESS_LIFECYCLE_LOCK")
    previous_lifecycle_timeout = os.environ.get(
        "PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS"
    )
    try:
        os.environ["PDF_PROCESS_LIFECYCLE_LOCK"] = str(collector.lifecycle_lock_path)
        os.environ["PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS"] = str(
            args.attribution_gap_seconds
        )
        with projected_aima_oracle(args.bundle):
            async with Worker(client, task_queue=config["workflow_queue"], workflows=[PDFProcessing]):
                collector.start()
                await host.start()
                await warm_run.admission()
                results = []
                first = {}
                for index, sid in enumerate(SEQUENCE):
                    record = await warm_run.trial(
                        sid, "warm", f"warm-{index}-{sid}", first.get(sid)
                    )
                    results.append(record)
                    first.setdefault(sid, record)
                q04_runtime.write(root / "warm-output-index.pending.json", {
                    sid: record["directory"] for sid, record in first.items()
                })
                proof = warm_checks(results)
                q04_runtime.write(root / "warm-proof.json", proof)
                await collector.process_transition(
                    "controlled_worker_shutdown", host.stop
                )
    except BaseException as error:
        primary_error = error
    finally:
        consumer.check_reference = original_reference
        if warm_run.active:
            try:
                await asyncio.wait_for(warm_run.cancel_owned(warm_run.active), 30)
            except BaseException:
                pass
        try:
            if collector.started and host.process is not None:
                await collector.process_transition(
                    "failure_worker_shutdown", host.stop
                )
            else:
                await host.stop()
        except BaseException as error:
            primary_error = primary_error or error
        try:
            if collector.started:
                collector.observe(
                    "owned_cleanup_finished",
                    source="warm_candidate_window",
                    meaning="warm_worker_returned_after_owned_cleanup",
                )
                outcome = collector.stop(
                    expect_cancel=False,
                    require_no_warm_fresh_overlap=True,
                )
        finally:
            if previous_lifecycle_lock is None:
                os.environ.pop("PDF_PROCESS_LIFECYCLE_LOCK", None)
            else:
                os.environ["PDF_PROCESS_LIFECYCLE_LOCK"] = previous_lifecycle_lock
            if previous_lifecycle_timeout is None:
                os.environ.pop("PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS", None)
            else:
                os.environ[
                    "PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS"
                ] = previous_lifecycle_timeout

    if primary_error is not None:
        q04_runtime.write(root / "phase-failure.json", {
            "type": type(primary_error).__name__, "reason": str(primary_error)
        })
        raise primary_error
    require(proof is not None and outcome is not None, "warm evidence missing")
    summary_path = measurement / "resource-attribution-summary.json"
    summary = json.loads(summary_path.read_text())
    summary["resource_attribution_path"] = str(measurement / "resource-attribution.jsonl")
    lifecycle = validate_process_evidence(summary, proof)
    samples = [
        json.loads(line)
        for line in (measurement / "resource-attribution.jsonl").read_text().splitlines()
    ]
    gate = evaluate_resource_gate(samples, summary)
    q04_runtime.write(measurement / "all-sample-resource-gate.json", gate)
    require(gate["status"] == "PASS", "all-sample resource gate failed")
    require(outcome.attribution_complete, "warm attribution incomplete")
    q04_runtime.write(measurement / "measurement-contract.json", {
        "workload": "Wiki06-YOLO07-AIMA08-native-Wiki06",
        "workload_succeeded": True,
        "qualification_complete": outcome.qualification_complete,
        "cgroup_resource_complete": outcome.cgroup_resource_complete,
        "group_requests": 29,
        "request_recycle": 20,
        "parser_generations": 2,
        "process_lifecycle": lifecycle,
        "resource_gate": gate,
        "automatic_retry": False,
    })
    q04_runtime.write(root / "warm-output-index.json", json.loads(
        (root / "warm-output-index.pending.json").read_text()
    ))
    q04_runtime.write(root / "reviewed-window-contract.json", {
        "status": "PASS sequence/recycle/resource only; fresh-output equality pending",
        "sequence": list(SEQUENCE),
        "group_requests": 29,
        "max_requests": 20,
        "fresh_output_equality": "unproven for 06/07/native current producer",
        "resource_gate": gate,
    })
    q04_runtime.write(root / "phase-complete.json", {
        "status": "PASS sequence/recycle/resource only; fresh-output equality pending"
    })


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "state", "capacity"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--expected-prefix", required=True)
    parser.add_argument("--integration-manifest", type=Path, required=True)
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
