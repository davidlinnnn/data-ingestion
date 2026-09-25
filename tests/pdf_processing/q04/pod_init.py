"""Initialize the Pod candidate state and source prefix for fixture 07 only."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

from consumer import canonical, require, sha
from contracts import validate_window
from prepare import verify_bundle
from q04_runtime import capture, write


RUN_ID = "q04-yolo-pod-cgroup-20260919-a"
WORKFLOW_QUEUE = "q04-pod-cgroup-a-workflows"
ACTIVITY_QUEUE = "q04-pod-cgroup-a-07"


def fixture_profile(bundle: dict, artifact: dict) -> dict:
    fixture = next(row for row in bundle["fixtures"] if row["id"] == "07")
    profile = copy.deepcopy(bundle["base_profile"])
    review = copy.deepcopy(fixture["review"])
    review["original_source"] = {
        "artifact": artifact,
        "source_revision": fixture["source_revision"],
    }
    profile["content_evidence"] = {
        "version": "typed-source-relationships-v2",
        "reviews": {fixture["sha256"]: review},
        "relationships": {
            "method": "local-function-block-v1",
            "coverage": {"mode": "unknown"},
            "unresolved": "allow_unknown",
        },
    }
    profile.pop("release", None)
    profile["release"] = "q04-" + sha(
        canonical({"profile": profile, "producer": bundle["producer"]}).encode()
    )
    return profile


def initialize(args) -> dict:
    import boto3
    from pdf_processing.object_store import Store

    bundle = verify_bundle(args.bundle)
    window = json.loads(args.capacity.read_text())
    validate_window(window, args.now)
    require(args.capacity_approved, "new capacity approval must be acknowledged")
    require(not args.state.exists(), "new fixture-07 state required")
    fixture = next(row for row in bundle["fixtures"] if row["id"] == "07")
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
    artifact = capture(
        store, args.bundle / "originals/07.pdf", "original-07.pdf"
    )
    profile = fixture_profile(bundle, artifact)
    config = {
        "run_id": RUN_ID,
        "profiles": {"07": profile},
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
        "workflow_queue": WORKFLOW_QUEUE,
        "queues": {"07": ACTIVITY_QUEUE},
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
        "status": "PASS_FIXTURE07_INIT_ONLY",
        "fixture": fixture["id"],
        "source_artifact": artifact,
        "profile_id": profile["id"],
        "profile_release": profile["release"],
        "run_id": RUN_ID,
        "workflow_queue": WORKFLOW_QUEUE,
        "activity_queue": ACTIVITY_QUEUE,
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
    value.set_defaults(now=__import__("time").time())
    return value


def main(argv=None) -> int:
    initialize(parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
