"""kp-processing command line.

Connections come from the environment: TEMPORAL_ADDRESS (default localhost:7233),
TEMPORAL_NAMESPACE (default "default"), KP_S3_* (see S3ObjectStore.from_env) and
KP_ADMISSION_URL, the status-report receiver (tools/fake_admission until #97), which only the
orchestration worker needs; KP_VLM_BASE_URL and KP_VLM_API_KEY, the OpenAI-compatible VLM
endpoint, which only the vlm worker needs (the model comes from the profile);
KP_SUMMARY_BASE_URL and KP_SUMMARY_API_KEY, the OpenAI-compatible endpoint of the Document
Summary's model, which only the summary worker needs (the model comes from the profile);
KP_D3_BASE_URL and KP_D3_API_KEY, the root of the d3 decision model's System One service and
its bearer key, which only the d3 worker needs (the model comes from the d3-check package).
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import prometheus_client
import yaml
from temporalio.client import Client, WorkflowFailureError
from temporalio.common import (
    PinnedVersioningOverride,
    SearchAttributePair,
    TypedSearchAttributes,
    WorkerDeploymentVersion,
    WorkflowIDReusePolicy,
)
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.runtime import PrometheusConfig, TelemetryConfig
from temporalio.runtime import Runtime as TemporalRuntime

from kp_processing.ports.inference import Bounded, OpenAIChat, SystemOne
from kp_processing.ports.object_store import S3ObjectStore
from kp_processing.ports.status_reporter import HttpStatusReporter
from kp_processing.profile import PROFILES_DIR, ProfileError, load_profile
from kp_processing.stages import Ports, Runtime, finalize
from kp_processing.workflow import (
    DEPLOYMENT,
    ORCHESTRATION_QUEUE,
    SEARCH_ATTRIBUTES,
    WORKFLOW,
    Queue,
    priority,
)


def main(argv: list[str] | None = None) -> int:
    """`kp-processing profile [PATH]`: load the profile (default: the bundled
    paper-pdf@1) and print one line per method:
    `<id>@<version>  module_digest=<hex>  components=<c1>,<c2>,...` (components empty when
    none). A ProfileError prints to stderr and exits 1.

    `kp-processing worker --queue orchestration|inference|vlm|summary|d3 [--profile PATH]
    [--build-id ID] [--shutdown-grace-s S] [--metrics-port P] [--temporal-metrics-port Q]`:
    serve one task queue until SIGTERM or SIGINT, then stop polling and give running Activities
    S seconds (default 0) to finish before they are cancelled and retried elsewhere; keep S
    below the pod's termination grace period. With --build-id the worker joins Worker
    Deployment canonicalization as that build and its workflows stay Pinned to it; without, it is
    unversioned and its results name build "dev". It refuses to start on a store without
    write-once. It logs JSON lines to stderr, serves kp_processing.metrics at
    http://0.0.0.0:P/metrics and the Temporal SDK's metrics, the status-stage durations
    included, at http://0.0.0.0:Q/metrics; each endpoint is off without its port.

    `kp-processing start-request START.json [--wait] [--builds MAP]`: start the workflow for an
    admission spec §10 start input, with the workflow ID set to its request_id. Starting a
    request that already exists counts as success. --wait prints the workflow's outcome.
    --builds is the dispatcher's map, a yaml mapping of adopted_version to build ID: the
    workflow starts Pinned to that build of canonicalization; an adopted_version the map lacks
    exits 2 without starting. The server refuses a build until its workers have polled.

    `kp-processing list-service-unavailable`: one JSON line {"document_uid", "request_id"}
    per redrive marker, for #98's redrive; it does not check that the request is still its
    document's current revision.
    """
    parser = argparse.ArgumentParser(prog="kp-processing")
    commands = parser.add_subparsers(dest="command", required=True)
    profile = commands.add_parser("profile")
    profile.add_argument("path", nargs="?", type=Path, default=PROFILES_DIR / "paper-pdf@1.yaml")
    worker = commands.add_parser("worker")
    worker.add_argument(
        "--queue", choices=["orchestration", "inference", "vlm", "summary", "d3"], required=True
    )
    worker.add_argument("--profile", type=Path, default=PROFILES_DIR / "paper-pdf@1.yaml")
    worker.add_argument("--build-id")
    worker.add_argument("--shutdown-grace-s", type=float, default=0)
    worker.add_argument("--metrics-port", type=int)
    worker.add_argument("--temporal-metrics-port", type=int)
    start = commands.add_parser("start-request")
    start.add_argument("start_input", type=Path)
    start.add_argument("--wait", action="store_true")
    start.add_argument("--builds", type=Path)
    commands.add_parser("list-service-unavailable")
    args = parser.parse_args(argv)

    if args.command == "worker":
        return asyncio.run(
            run_worker(
                args.queue,
                args.profile,
                args.build_id,
                args.shutdown_grace_s,
                args.metrics_port,
                args.temporal_metrics_port,
            )  # fmt: skip
        )
    if args.command == "start-request":
        start_input = json.loads(args.start_input.read_text())
        return asyncio.run(start_request(start_input, args.wait, args.builds))
    if args.command == "list-service-unavailable":
        for marker in asyncio.run(finalize.service_unavailable(S3ObjectStore.from_env())):
            print(json.dumps(marker))
        return 0
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


class JsonFormatter(logging.Formatter):
    """One JSON object per log line. The SDK's workflow and Activity loggers add the workflow
    ID, which is the request_id, and the run ID, which is the attempt_id; a record's
    `correlation` extra adds its fields (prepare logs document_uid, source_revision_id and
    trace_id once per request)."""

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }  # fmt: skip
        context = getattr(record, "temporal_activity", None) or {}
        if context:
            line.update(request_id=context.get("workflow_id"),
                        attempt_id=context.get("workflow_run_id"),
                        activity=context.get("activity_type"))  # fmt: skip
        workflow = getattr(record, "temporal_workflow", None) or {}
        if workflow:
            line.update(request_id=workflow.get("workflow_id"), attempt_id=workflow.get("run_id"))
        line.update(getattr(record, "correlation", None) or {})
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line)


async def connect(runtime: TemporalRuntime | None = None) -> Client:
    return await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        runtime=runtime,
    )


async def run_worker(
    queue: Queue,
    profile_path: Path,
    build_id: str | None,
    shutdown_grace_s: float,
    metrics_port: int | None = None,
    temporal_metrics_port: int | None = None,
) -> int:
    admission = os.environ.get("KP_ADMISSION_URL")
    if queue == "orchestration" and not admission:
        print("KP_ADMISSION_URL is required for the orchestration worker", file=sys.stderr)
        return 2
    vlm_url, vlm_key = os.environ.get("KP_VLM_BASE_URL"), os.environ.get("KP_VLM_API_KEY", "")
    if queue == "vlm" and not vlm_url:
        print("KP_VLM_BASE_URL is required for the vlm worker", file=sys.stderr)
        return 2
    summary_url = os.environ.get("KP_SUMMARY_BASE_URL")
    summary_key = os.environ.get("KP_SUMMARY_API_KEY", "")
    if queue == "summary" and not summary_url:
        print("KP_SUMMARY_BASE_URL is required for the summary worker", file=sys.stderr)
        return 2
    d3_url, d3_key = os.environ.get("KP_D3_BASE_URL"), os.environ.get("KP_D3_API_KEY", "")
    if queue == "d3" and not d3_url:
        print("KP_D3_BASE_URL is required for the d3 worker", file=sys.stderr)
        return 2
    from kp_processing import metrics
    from kp_processing.stages import enrich_vlm
    from kp_processing.worker import make_worker  # loads docling; other commands stay fast

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    if metrics_port is not None:
        prometheus_client.start_http_server(metrics_port)
    temporal_runtime = None
    if temporal_metrics_port is not None:
        prometheus = PrometheusConfig(
            bind_address=f"0.0.0.0:{temporal_metrics_port}",
            durations_as_seconds=True,
            histogram_bucket_overrides={metrics.STAGE_DURATION: metrics.STAGE_BUCKETS},
        )
        temporal_runtime = TemporalRuntime(telemetry=TelemetryConfig(metrics=prometheus))

    store = S3ObjectStore.from_env()
    runtime = Runtime(
        profile=load_profile(profile_path), build_id=build_id or "dev", custody_bucket=store.bucket
    )
    async with httpx.AsyncClient(timeout=10) as http, httpx.AsyncClient() as external_http:
        # Only orchestration Activities send status reports, only vlm ones VLM requests, only
        # summary ones summary requests and only d3 ones Quality Check requests.
        reporter = HttpStatusReporter(http, admission or "")
        vlm = summary = d3 = None
        if queue == "vlm":
            deadline = runtime.profile.runtime["vlm_request_deadline_s"]
            vlm = OpenAIChat(external_http, vlm_url or "", vlm_key,
                             enrich_vlm.model(runtime.profile), deadline["connect"],
                             deadline["total"])  # fmt: skip
        if queue == "summary":
            settings = runtime.profile.runtime
            deadline = settings["summary_request_deadline_s"]
            # #155: a chunk's calls run in parallel, so slots alone do not bound the requests.
            summary = Bounded(OpenAIChat(external_http, summary_url or "", summary_key,
                                         enrich_vlm.model(runtime.profile, "summary"),
                                         deadline["connect"], deadline["total"]),
                              settings["summary_requests_per_worker"])  # fmt: skip
        if queue == "d3":
            deadline = runtime.profile.runtime["d3_request_deadline_s"]
            d3 = SystemOne(external_http, d3_url or "", d3_key, deadline["connect"],
                           deadline["total"])  # fmt: skip
        ports = Ports(store, reporter, vlm=vlm, summary=summary, d3=d3)
        client = await connect(temporal_runtime)
        worker = await make_worker(
            client, ports, runtime, queue, shutdown_grace_s, versioned=build_id is not None
        )
        print(f"worker {runtime.profile.id} build {runtime.build_id} on {worker.task_queue}",
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


async def start_request(start: dict[str, Any], wait: bool, builds: Path | None = None) -> int:
    override = None
    if builds is not None:
        build_id = (yaml.safe_load(builds.read_text()) or {}).get(start.get("adopted_version"))
        if not isinstance(build_id, str):
            print(f"{builds} maps no build for {start.get('adopted_version')}", file=sys.stderr)
            return 2
        override = PinnedVersioningOverride(WorkerDeploymentVersion(DEPLOYMENT, build_id))
    client = await connect()
    request_id = start["request_id"]
    try:
        await client.start_workflow(
            WORKFLOW,
            start,
            id=request_id,
            task_queue=ORCHESTRATION_QUEUE,
            priority=priority(start.get("priority")),
            search_attributes=TypedSearchAttributes(
                [
                    SearchAttributePair(key, start[field])
                    for field, key in SEARCH_ATTRIBUTES.items()
                    if isinstance(start.get(field), str)
                ]
            ),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            versioning_override=override,
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
