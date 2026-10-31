"""kp-processing command line. A later ticket adds `list-service-unavailable`.

Connections come from the environment: TEMPORAL_ADDRESS (default localhost:7233),
TEMPORAL_NAMESPACE (default "default"), KP_S3_* (see S3ObjectStore.from_env) and
KP_ADMISSION_URL, the status-report receiver (tools/fake_admission until #97), which only the
orchestration worker needs.
"""

import argparse
import asyncio
import json
import os
import signal
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
from kp_processing.workflow import ORCHESTRATION_QUEUE, WORKFLOW, Queue, priority


def main(argv: list[str] | None = None) -> int:
    """`kp-processing profile [PATH]`: load the profile (default: the bundled
    paper-pdf@1) and print one line per method:
    `<id>@<version>  module_digest=<hex>  components=<c1>,<c2>,...` (components empty when
    none). A ProfileError prints to stderr and exits 1.

    `kp-processing worker --queue orchestration|inference [--profile PATH] [--build-id ID]
    [--shutdown-grace-s S]`: serve one task queue until SIGTERM or SIGINT, then stop polling
    and give running Activities S seconds (default 0) to finish before they are cancelled and
    retried elsewhere; keep S below the pod's termination grace period. It refuses to start
    on a store without write-once.

    `kp-processing start-request START.json [--wait]`: start the workflow for an admission
    spec §10 start input, with the workflow ID set to its request_id. Starting a request
    that already exists counts as success. --wait prints the workflow's outcome.
    """
    parser = argparse.ArgumentParser(prog="kp-processing")
    commands = parser.add_subparsers(dest="command", required=True)
    profile = commands.add_parser("profile")
    profile.add_argument("path", nargs="?", type=Path, default=PROFILES_DIR / "paper-pdf@1.yaml")
    worker = commands.add_parser("worker")
    worker.add_argument("--queue", choices=["orchestration", "inference"], required=True)
    worker.add_argument("--profile", type=Path, default=PROFILES_DIR / "paper-pdf@1.yaml")
    worker.add_argument("--build-id", default="dev")
    worker.add_argument("--shutdown-grace-s", type=float, default=0)
    start = commands.add_parser("start-request")
    start.add_argument("start_input", type=Path)
    start.add_argument("--wait", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "worker":
        return asyncio.run(
            run_worker(args.queue, args.profile, args.build_id, args.shutdown_grace_s)
        )
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


async def run_worker(
    queue: Queue, profile_path: Path, build_id: str, shutdown_grace_s: float
) -> int:
    admission = os.environ.get("KP_ADMISSION_URL")
    if queue == "orchestration" and not admission:
        print("KP_ADMISSION_URL is required for the orchestration worker", file=sys.stderr)
        return 2
    from kp_processing.worker import make_worker  # loads docling; other commands stay fast

    runtime = Runtime(profile=load_profile(profile_path), build_id=build_id)
    async with httpx.AsyncClient(timeout=10) as http:
        # Only orchestration Activities send status reports.
        reporter = HttpStatusReporter(http, admission or "")
        worker = await make_worker(await connect(), Ports(S3ObjectStore.from_env(), reporter),
                                   runtime, queue, shutdown_grace_s)  # fmt: skip
        print(f"worker {runtime.profile.profile} build {build_id} on {worker.task_queue}",
              flush=True)  # fmt: skip
        stop = asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        async with worker:  # leaving it shuts the worker down
            await stop.wait()
    print("worker stopped", flush=True)
    # A cancelled docling call keeps its thread running; its Activity is already back in
    # Temporal, so exit without waiting for the thread.
    os._exit(0)


async def start_request(start: dict[str, Any], wait: bool) -> int:
    client = await connect()
    request_id = start["request_id"]
    try:
        await client.start_workflow(
            WORKFLOW,
            start,
            id=request_id,
            task_queue=ORCHESTRATION_QUEUE,
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
