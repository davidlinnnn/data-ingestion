"""Capture the fixed Q04 bundle and original profiles before fixture08 validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from consumer import canonical, require, sha
from contracts import validate_window
from prepare import verify_bundle
from q04_runtime import capture, profiles, write


RUN_ID = "q04-aima-pod-cgroup-20260920-n"
WORKFLOW_QUEUE = "q04-pod-cgroup-n-workflows"
ACTIVITY_QUEUE = "q04-pod-cgroup-n-08"



def initialize(args) -> dict:
    import boto3
    from pdf_processing.object_store import Store

    bundle = verify_bundle(args.bundle)
    window = json.loads(args.capacity.read_text())
    validate_window(window, args.now)
    require(args.capacity_approved, "new capacity approval must be acknowledged")
    require(not args.state.exists(), "new fixture-08 state required")
    fixture = next(row for row in bundle["fixtures"] if row["id"] == "08")
    s3 = boto3.client("s3", endpoint_url=args.endpoint)
    require(
        s3.get_bucket_versioning(Bucket=args.bucket).get("Status") == "Enabled",
        "versioned bucket required",
    )
    store = Store(s3, args.bucket, args.prefix)
    require(
        not s3.list_objects_v2(
            Bucket=args.bucket, Prefix=store.prefix, MaxKeys=1
        ).get("Contents"),
        "unused object prefix required",
    )
    originals = {entry['id']: capture(store, args.bundle / 'originals' / (entry['id']+'.pdf'), 'original-'+entry['id']+'.pdf') for entry in bundle['fixtures']}
    profs = profiles(bundle, originals)
    profile = profs['08']
    artifact = originals['08']
    config = {
        "run_id": args.run_id,
        "profiles": profs,
        "producer": bundle["producer"],
        "bundle": str(args.bundle.resolve()),
        "state": str(args.state.resolve()),
        "temporal": args.temporal,
        "endpoint": args.endpoint,
        "bucket": args.bucket,
        "prefix": args.prefix,
        "window": window,
        "model_cache": str(args.model_cache),
        "python": sys.executable,
        "pod_namespace": None,
        "trial_seconds": 180,
        "workflow_queue": args.workflow_queue,
        "queues": {sid: args.run_id+"-"+sid for sid in profs},
        "limits": {
            "max_bytes": 100 * 1024 * 1024,
            "max_pages": 51,
            "max_page_pixels": 20_000_000,
            "preflight_seconds": 30,
            "child_seconds": 540,
        },
        "parser_budgets": {
            "startup_seconds": 120,
            "no_progress_seconds": 180,
            "terminate_seconds": 5,
            "reap_seconds": 5,
            "max_requests": 20,
        },
        "drain_seconds": 30,
        "bundle_sha256": sha((args.bundle / "inputs.json").read_bytes()),
    }
    args.state.mkdir()
    write(args.state / "config.json", config)
    result = {
        "status": "PASS_FIXED_BUNDLE_INIT_ONLY",
        "fixture": fixture["id"],
        "source_artifact": artifact,
        "profile_id": profile["id"],
        "profile_release": profile["release"],
        "run_id": args.run_id,
        "workflow_queue": args.workflow_queue,
        "activity_queue": args.activity_queue,
    }
    write(args.state / "pod-init.json", result)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--bundle", type=Path, required=True)
    value.add_argument("--state", type=Path, required=True)
    value.add_argument("--capacity", type=Path, required=True)
    value.add_argument("--temporal", required=True)
    value.add_argument("--endpoint", required=True)
    value.add_argument("--bucket", required=True)
    value.add_argument("--prefix", required=True)
    value.add_argument("--model-cache", type=Path, required=True)
    value.add_argument("--capacity-approved", action="store_true")
    value.add_argument("--run-id", default=RUN_ID)
    value.add_argument("--workflow-queue", default=WORKFLOW_QUEUE)
    value.add_argument("--activity-queue", default=ACTIVITY_QUEUE)
    value.set_defaults(now=__import__("time").time())
    return value


def main(argv=None) -> int:
    initialize(parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
