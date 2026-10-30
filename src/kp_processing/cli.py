"""kp-processing command line. A later ticket adds `list-service-unavailable`.

Connections come from the environment: TEMPORAL_ADDRESS (default localhost:7233),
TEMPORAL_NAMESPACE (default "default"), KP_S3_* (see S3ObjectStore.from_env) and
KP_ADMISSION_URL, the status-report receiver (tools/fake_admission until #97).
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from temporalio.client import Client, WorkflowFailureError
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from kp_processing.ports.object_store import S3ObjectStore
from kp_processing.ports.status_reporter import HttpStatusReporter
from kp_processing.profile import PROFILES_DIR, ProfileError, load_profile
from kp_processing.stages import Ports, Runtime
from kp_processing.workflow import CPU_QUEUE, WORKFLOW, priority


def main(argv: list[str] | None = None) -> int:
    """`kp-processing profile [PATH]`: load the profile (default: the bundled
    paper-pdf@1) and print one line per method:
    `<id>@<version>  module_digest=<hex>  components=<c1>,<c2>,...` (components empty when
    none). A ProfileError prints to stderr and exits 1.

    `kp-processing worker --pool cpu [--profile PATH] [--build-id ID]`: run
    a worker until interrupted; it refuses to start on a store without write-once.

    `kp-processing start-request START.json [--wait]`: start the workflow for an admission
    spec §10 start input, with the workflow ID set to its request_id. Starting a request
    that already exists counts as success. --wait prints the workflow's outcome.
    """
    parser = argparse.ArgumentParser(prog="kp-processing")
    commands = parser.add_subparsers(dest="command", required=True)
    profile = commands.add_parser("profile")
    profile.add_argument("path", nargs="?", type=Path, default=PROFILES_DIR / "paper-pdf@1.yaml")
    worker = commands.add_parser("worker")
    worker.add_argument("--pool", choices=["cpu"], required=True)
    worker.add_argument("--profile", type=Path, default=PROFILES_DIR / "paper-pdf@1.yaml")
    worker.add_argument("--build-id", default="dev")
    start = commands.add_parser("start-request")
    start.add_argument("start_input", type=Path)
    start.add_argument("--wait", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "worker":
        return asyncio.run(run_worker(args.profile, args.build_id))
    if args.command == "start-request":
        return asyncio.run(start_request(json.loads(args.start_input.read_text()), args.wait))
    try:
        loaded = load_profile(args.path)
    except ProfileError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for method in loaded.methods.values():
        print(
            f"{method.ref}  module_digest={method.module_digest}  "
            f"components={','.join(method.components)}"
        )
    return 0


async def connect() -> Client:
    return await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
    )


async def run_worker(profile_path: Path, build_id: str) -> int:
    from kp_processing.worker import make_worker  # loads docling; other commands stay fast

    runtime = Runtime(profile=load_profile(profile_path), build_id=build_id)
    async with httpx.AsyncClient(timeout=10) as http:
        reporter = HttpStatusReporter(http, os.environ["KP_ADMISSION_URL"])
        worker = await make_worker(await connect(), Ports(S3ObjectStore.from_env(), reporter),
                                   runtime)  # fmt: skip
        print(f"worker {runtime.profile.profile} build {build_id} on {worker.task_queue}")
        await worker.run()
    return 0


async def start_request(start: dict[str, Any], wait: bool) -> int:
    client = await connect()
    request_id = start["request_id"]
    try:
        await client.start_workflow(
            WORKFLOW,
            start,
            id=request_id,
            task_queue=CPU_QUEUE,
            priority=priority(start.get("priority")),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
        print(f"started {request_id}")
    except WorkflowAlreadyStartedError:
        print(f"{request_id} already started")
    if wait:
        try:
            print(json.dumps(await client.get_workflow_handle(request_id).result()))
        except WorkflowFailureError as exc:
            print(f"{request_id} failed: {exc.cause}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
