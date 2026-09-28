"""Execute the fixed fixture-08 lifecycle matrix with attribution evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import time

from candidate.yolo_candidate_measure import AttributedCandidateRun
from consumer import canonical, require, sha
from contracts import validate_window
import q04_runtime
from prepare import verify_bundle
try:
    from sentinel.yolo_reviewed_attribution_telemetry import StrictAttributionCollector
except ImportError:
    # The reviewed source is staged under the historical module name remotely.
    from sentinel.yolo_attribution_telemetry import StrictAttributionCollector


def validate_contract(config, bundle):
    require(config['parser_budgets'] == {'startup_seconds':120, 'no_progress_seconds':180, 'terminate_seconds':5, 'reap_seconds':5, 'max_requests':20}, 'original parser budget changed')
    originals = {f['id']: config['profiles'][f['id']]['content_evidence']['reviews'][f['sha256']]['original_source']['artifact'] for f in bundle['fixtures']}
    require(config['profiles'] == q04_runtime.profiles(bundle, originals), 'original fixture profile contract changed')


def validate_scope(args):
    manifest = json.loads(args.integration_manifest.read_text())
    scope = manifest['authorization_scope']
    require(scope == {'fixture':'08', 'modes':['fresh','restored','replay'],
        'max_requests':20, 'oracle':'unchanged Q04 AIMA source oracle',
        'automatic_retry':False}, 'fixture08 authorization scope changed')
    require(sha(canonical(scope).encode()) == args.authorization_scope_sha256
            == manifest['authorization_scope_sha256'], 'runtime scope digest changed')
    require(manifest['identity'] == {'phase':args.name, 'run_id':args.expected_run_id,
        'prefix':args.expected_prefix}, 'runtime identity changed')


def validate_matrix_records(trial_root, fixture="08"):
    """Bind restored comparison and replay to the accepted fresh baseline."""
    accepted = {
        mode: json.loads(
            (trial_root / f"{mode}-{fixture}/accepted.json").read_text()
        )
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


async def run_measured_window(args):
    bundle = verify_bundle(args.bundle)
    window = json.loads(args.capacity.read_text())
    validate_window(window, time.time())
    require(args.capacity_approved, "new capacity approval must be acknowledged")
    state_path = args.state / "config.json"
    require(state_path.is_file(), "initialized candidate state is required")
    config = json.loads(state_path.read_text())
    require(
        window == config.get("window"),
        "capacity window differs from initialized candidate state",
    )
    require(config["run_id"] == args.expected_run_id, "candidate run identity changed")
    require(config["prefix"] == args.expected_prefix, "candidate prefix changed")
    require(config["bundle"] == str(args.bundle.resolve()), "candidate bundle path changed")
    require(
        config["bundle_sha256"] == sha((args.bundle / "inputs.json").read_bytes()),
        "candidate bundle hash changed",
    )
    require(config["producer"] == bundle["producer"], "candidate producer changed")
    require(
        config["profiles"]["08"]["method"] == bundle["base_profile"]["method"],
        "fixture-08 method changed",
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
    request_recycle_exit = config.get("parser_budgets", {}).get("max_requests") == 1
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
        fixture=["08"],
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
                require_handoff=not request_recycle_exit,
                require_recycle_exit=request_recycle_exit,
                require_no_warm_fresh_overlap=True,
            )
            summary = json.loads(
                (measurement_root / "resource-attribution-summary.json").read_text()
            )
        contract = {
            "workload": "fixture-08 fresh/restored/exact-fresh-replay",
            "workload_succeeded": primary_error is None,
            "cancel_callback_invoked": cancel_invoked,
            "cancel_marker_required": cancel_invoked,
            "successful_fresh_requires_cancel_marker": False,
            "attribution_complete": bool(outcome and outcome.attribution_complete),
            "qualification_complete": bool(
                outcome and outcome.qualification_complete
            ),
            "cgroup_resource_complete": bool(
                outcome and outcome.cgroup_resource_complete
            ),
            "process_attribution_complete": bool(
                summary and summary["process_attribution_complete"]
            ),
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
    require(outcome is not None and outcome.qualification_complete,
            "candidate qualification evidence incomplete")
    require(not any(run.cancel_invoked for run in instances),
            "successful matrix unexpectedly invoked cancellation")
    validate_matrix_records(trial_root)


async def run_window(args):
    from candidate.yolo_reviewed_window import evaluate_resource_gate
    config = json.loads((args.state / 'config.json').read_text())
    validate_scope(args)
    validate_contract(config, json.loads((args.bundle/'inputs.json').read_text()))
    root = args.state / args.name
    original_write = q04_runtime.write
    def gated_write(path, value):
        if path.name == 'fresh-index.json': path = path.with_name('fresh-index.pending.json')
        elif path.name == 'phase-complete.json': path = path.with_name('runtime-phase-complete.pending.json')
        return original_write(path, value)
    q04_runtime.write = gated_write
    try:
        await run_measured_window(args)
    finally:
        q04_runtime.write = original_write
    measurement = args.state / (args.name+'-measurement')
    samples = [json.loads(line) for line in (measurement/'resource-attribution.jsonl').read_text().splitlines()]
    gate = evaluate_resource_gate(samples, json.loads((measurement/'resource-attribution-summary.json').read_text()))
    original_write(measurement/'all-sample-resource-gate.json', gate)
    require(gate['status'] == 'PASS', 'all-sample resource gate failed')
    original_write(root/'fresh-index.json', json.loads((root/'fresh-index.pending.json').read_text()))
    original_write(root/'reviewed-window-contract.json', {'status':'PASS bounded fixture-08 only', 'fixture':'08', 'max_requests':20, 'oracle':'unchanged Q04 AIMA source oracle', 'resource_gate':gate})
    original_write(root/'phase-complete.json', {'status':'PASS bounded fixture-08 only'})


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
