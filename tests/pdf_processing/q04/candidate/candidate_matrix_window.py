"""Run one reviewed non-YOLO fixture matrix under an immutable Q04 state."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import time

from consumer import require, sha
from contracts import validate_window
from prepare import verify_bundle
import q04_runtime
from candidate.yolo_candidate_window import validate_matrix_records


ALLOWED_FIXTURES = {"06", "08", "09", "10", "native"}


async def run_window(args):
    require(args.fixture in ALLOWED_FIXTURES, "fixture is outside the reviewed batch")
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
        config["profiles"][args.fixture]["method"]
        == bundle["base_profile"]["method"],
        "fixture method changed",
    )
    trial_root = args.state / args.name
    require(not trial_root.exists(), "candidate phase identity already exists")

    runtime_args = SimpleNamespace(
        bundle=args.bundle,
        state=args.state,
        capacity=args.capacity,
        phase="matrix",
        name=args.name,
        fresh=None,
        fixture=[args.fixture],
        capacity_approved=True,
    )
    await q04_runtime.main(runtime_args)
    accepted = validate_matrix_records(trial_root, args.fixture)
    contract = {
        "fixture": args.fixture,
        "modes": ["fresh", "restored", "replay"],
        "fresh_request_id": accepted["fresh"]["request"]["request_id"],
        "restored_request_id": accepted["restored"]["request"]["request_id"],
        "exact_replay": True,
        "automatic_retry": False,
    }
    (trial_root / "batch-matrix-contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "state", "capacity"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--fixture", required=True, choices=sorted(ALLOWED_FIXTURES))
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--expected-prefix", required=True)
    parser.add_argument("--capacity-approved", action="store_true")
    args = parser.parse_args(argv)
    if not args.capacity_approved:
        parser.error("new capacity approval is required")
    asyncio.run(run_window(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
