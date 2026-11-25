"""kp-canonicalization command line.

Connections come from the environment: TEMPORAL_ADDRESS (default localhost:7233),
TEMPORAL_NAMESPACE (default "default"), KP_S3_* (see S3ObjectStore.from_env) and
KP_ADMISSION_URL, the platform API that takes status reports, and KP_ADMISSION_TOKEN, mounted
from a Secret, the credential admission registered for canonical processing (#97), sent as
`Authorization: Bearer`, which only the orchestration worker needs (without the token, reports
carry no Authorization header, as tools/fake_admission takes them); KP_VLM_BASE_URL and
KP_VLM_API_KEY, the OpenAI-compatible VLM endpoint, which only the vlm worker needs (the model
comes from the profile);
KP_SUMMARY_BASE_URL and KP_SUMMARY_API_KEY, the OpenAI-compatible endpoint of the Document
Summary's model, which only the summary worker needs (the model comes from the profile);
KP_D3_BASE_URL and KP_D3_API_KEY, the root of the d3 decision model's System One service and
its bearer key, which only the d3 worker needs (the model comes from the d3-check package).
Without its API_KEY a service's requests carry no Authorization header. KP_VLM_HEADERS,
KP_SUMMARY_HEADERS and KP_D3_HEADERS, each optional and mounted from a Secret, are a JSON object
of fixed header names to values, such as {"X-Policy-Token": "..."}, sent on every request to
that service; an entry replaces the header of the same name, Authorization included. A worker
whose variable is not such an object exits 2 naming the variable (see service_headers).
"""

import argparse
import asyncio
import json
import logging
import os
import re
import signal
import sys
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import prometheus_client
import yaml
from temporalio.client import Client, WorkflowFailureError
from temporalio.common import SearchAttributePair, TypedSearchAttributes, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.runtime import PrometheusConfig, TelemetryConfig
from temporalio.runtime import Runtime as TemporalRuntime

from kp_canonicalization.ports.inference import Bounded, OpenAIChat, SystemOne
from kp_canonicalization.ports.object_store import S3ObjectStore
from kp_canonicalization.ports.status_reporter import HttpStatusReporter
from kp_canonicalization.profile import ProfileError, latest_profile, load_profile
from kp_canonicalization.stages import Ports, Runtime
from kp_canonicalization.workflow import (
    QUEUES,
    SEARCH_ATTRIBUTES,
    WORKFLOW,
    Queue,
    deployment_name,
    priority,
    task_queue,
)

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """`kp-canonicalization profile [PATH]`: load the profile (default: the bundled file with
    the highest version, as for the worker) and print one line per method:
    `<id>@<version>  module_digest=<hex>  components=<c1>,<c2>,...` (components empty when
    none). A ProfileError prints to stderr and exits 1.

    `kp-canonicalization worker --queue orchestration|inference|vlm|summary|d3 [--profile PATH]
    [--build-id ID] [--shutdown-grace-s S] [--metrics-port P] [--temporal-metrics-port Q]`:
    serve one task queue until SIGTERM or SIGINT, then stop polling and give running Activities
    S seconds (default 0) to finish before they are cancelled and retried elsewhere; keep S
    below the pod's termination grace period. It polls `<deployment>.<queue>`, where the Worker
    Deployment is its Processing Profile version's (`paper-pdf-2` for `paper-pdf@2`). With
    --build-id, or else TEMPORAL_WORKER_BUILD_ID, it joins that deployment as that build and its
    workflows stay Pinned to it; without either it is unversioned and its results name build
    "dev". It exits 2 when TEMPORAL_DEPLOYMENT_NAME is set and names another deployment, and
    refuses to start on a store without write-once. It logs JSON lines to stderr, serves
    kp_canonicalization.metrics at http://0.0.0.0:P/metrics and the Temporal SDK's metrics, the
    status-stage durations included, at http://0.0.0.0:Q/metrics; each endpoint is off without
    its port.

    `kp-canonicalization start-request START.json [--wait]`: start the workflow for an
    admission spec §10 start input as admission's dispatcher does (workflow_start.json, #207), on
    the orchestration queue of its adopted_version and with the workflow ID set to its request_id.
    Starting a request that already exists counts as success; an input without a field the start
    needs exits 2. --wait prints the workflow's outcome.

    `kp-canonicalization promote WANTED.yaml`: one promoter run (promoter.promote) over the
    deployment values' `profiles` mapping. It logs JSON lines: what it did, then the message
    `promoter ok`; or each alarm at level ERROR, and exits 1, as does a run that raised. Values
    without a profile exit 2.
    """
    parser = argparse.ArgumentParser(prog="kp-canonicalization")
    commands = parser.add_subparsers(dest="command", required=True)
    profile = commands.add_parser("profile")
    profile.add_argument("path", nargs="?", type=Path, default=latest_profile())
    worker = commands.add_parser("worker")
    worker.add_argument("--queue", choices=QUEUES, required=True)
    worker.add_argument("--profile", type=Path, default=latest_profile())
    worker.add_argument("--build-id", default=os.environ.get("TEMPORAL_WORKER_BUILD_ID"))
    worker.add_argument("--shutdown-grace-s", type=float, default=0)
    worker.add_argument("--metrics-port", type=int)
    worker.add_argument("--temporal-metrics-port", type=int)
    start = commands.add_parser("start-request")
    start.add_argument("start_input", type=Path)
    start.add_argument("--wait", action="store_true")
    promote = commands.add_parser("promote")
    promote.add_argument("wanted", type=Path)
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
        return asyncio.run(start_request(start_input, args.wait))
    if args.command == "promote":
        return asyncio.run(run_promoter(yaml.safe_load(args.wanted.read_text())))
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
    trace_id once per request). An exception is logged as the types and stack frames of its
    chain, without the messages: their text can quote a document, a prompt or a model answer."""

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
        error, chain = record.exc_info[1] if record.exc_info else None, []
        while error and error not in chain:
            chain.append(error)
            error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
        if chain:
            line["exception"] = "caused by ".join(
                f"{type(error).__qualname__}\n{''.join(traceback.format_tb(error.__traceback__))}"
                for error in chain
            )
        return json.dumps(line)


async def connect(runtime: TemporalRuntime | None = None, lazy: bool = False) -> Client:
    return await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        runtime=runtime,
        lazy=lazy,
    )


def log_json_lines(*filters: logging.Filter) -> None:
    """Make the root logger write JsonFormatter lines at INFO and above to stderr, each record
    passed through `filters` first."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    for each in filters:
        handler.addFilter(each)
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
HEADER_VALUE = re.compile(r"[\t\x20-\x7e]*")


def service_headers(service: str) -> httpx.Headers:
    """The headers of every request to service (vlm, summary or d3): `Authorization: Bearer
    <KP_<SERVICE>_API_KEY>` when the key is set, then each entry of KP_<SERVICE>_HEADERS, a JSON
    object of header names to string values, which replaces a header of the same name. Raises
    ValueError naming the variable, never its value, when that is not such an object."""
    key = os.environ.get(f"KP_{service.upper()}_API_KEY")
    headers = httpx.Headers({"Authorization": f"Bearer {key}"} if key else {})
    variable = f"KP_{service.upper()}_HEADERS"
    error = ValueError(
        f"{variable} must be a JSON object of header names to printable ASCII string values"
    )
    try:
        extra = json.loads(os.environ.get(variable, "{}"))
    except ValueError:
        raise error from None
    if not isinstance(extra, dict) or not all(
        isinstance(value, str) and HEADER_NAME.fullmatch(name) and HEADER_VALUE.fullmatch(value)
        for name, value in extra.items()
    ):
        raise error
    headers.update(extra)
    return headers


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
    vlm_url = os.environ.get("KP_VLM_BASE_URL")
    if queue == "vlm" and not vlm_url:
        print("KP_VLM_BASE_URL is required for the vlm worker", file=sys.stderr)
        return 2
    summary_url = os.environ.get("KP_SUMMARY_BASE_URL")
    if queue == "summary" and not summary_url:
        print("KP_SUMMARY_BASE_URL is required for the summary worker", file=sys.stderr)
        return 2
    d3_url = os.environ.get("KP_D3_BASE_URL")
    if queue == "d3" and not d3_url:
        print("KP_D3_BASE_URL is required for the d3 worker", file=sys.stderr)
        return 2
    try:
        headers = service_headers(queue) if queue in ("vlm", "summary", "d3") else httpx.Headers()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    profile = load_profile(profile_path)
    deployment = os.environ.get("TEMPORAL_DEPLOYMENT_NAME")
    if deployment not in (None, deployment_name(profile.id)):
        print(
            f"TEMPORAL_DEPLOYMENT_NAME is {deployment}, but this worker loads {profile.id}, "
            f"which belongs to {deployment_name(profile.id)}: the deployment values list this "
            "image under another Processing Profile version",
            file=sys.stderr,
        )
        return 2
    from kp_canonicalization import metrics
    from kp_canonicalization.stages import enrich_vlm
    from kp_canonicalization.worker import make_worker  # loads docling; other commands stay fast

    log_json_lines()
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
    runtime = Runtime(profile=profile, build_id=build_id or "dev", custody_bucket=store.bucket)
    token = os.environ.get("KP_ADMISSION_TOKEN")
    if queue == "orchestration" and not token:
        log.warning("KP_ADMISSION_TOKEN is not set: status reports carry no credential")
    reporting = {"Authorization": f"Bearer {token}"} if token else {}
    async with (
        httpx.AsyncClient(timeout=10, headers=reporting) as http,
        httpx.AsyncClient() as external_http,
    ):
        # Only orchestration Activities send status reports, only vlm ones VLM requests, only
        # summary ones summary requests and only d3 ones Quality Check requests.
        reporter = HttpStatusReporter(http, admission or "")
        vlm = summary = d3 = None
        if queue == "vlm":
            deadline = runtime.profile.runtime["vlm_request_deadline_s"]
            vlm = OpenAIChat(external_http, vlm_url or "", headers,
                             enrich_vlm.model(runtime.profile), deadline["connect"],
                             deadline["total"])  # fmt: skip
        if queue == "summary":
            settings = runtime.profile.runtime
            deadline = settings["summary_request_deadline_s"]
            # #155: a chunk's calls run in parallel, so slots alone do not bound the requests.
            summary = Bounded(OpenAIChat(external_http, summary_url or "", headers,
                                         enrich_vlm.model(runtime.profile, "summary"),
                                         deadline["connect"], deadline["total"]),
                              settings["summary_requests_per_worker"])  # fmt: skip
        if queue == "d3":
            deadline = runtime.profile.runtime["d3_request_deadline_s"]
            d3 = SystemOne(external_http, d3_url or "", headers, deadline["connect"],
                           deadline["total"])  # fmt: skip
        ports = Ports(store, reporter, vlm=vlm, summary=summary, d3=d3)
        client = await connect(temporal_runtime)
        worker = await make_worker(
            client, ports, runtime, queue, shutdown_grace_s, versioned=bool(build_id)
        )
        log.info(
            "worker %s build %s on %s", runtime.profile.id, runtime.build_id, worker.task_queue
        )
        stop = asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        async with worker:  # leaving it shuts the worker down
            await stop.wait()
    log.info("worker stopped")
    # A cancelled docling call keeps its thread running; its Activity is already back in
    # Temporal, so exit without waiting for the thread.
    os._exit(0)


async def start_request(start: dict[str, Any], wait: bool) -> int:
    client = await connect(lazy=True)  # a bad input is refused before anything connects
    try:
        request_id = start["request_id"]
        await client.start_workflow(
            WORKFLOW,
            start,
            id=request_id,
            task_queue=task_queue(start["adopted_version"]),
            priority=priority(start["priority"]),
            search_attributes=TypedSearchAttributes(
                [SearchAttributePair(key, start[field]) for field, key in SEARCH_ATTRIBUTES.items()]
            ),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            rpc_timeout=timedelta(seconds=10),
        )
    except (KeyError, TypeError) as exc:
        print(f"not a start input: {exc!r}", file=sys.stderr)
        return 2
    except WorkflowAlreadyStartedError:
        pass
    print(f"started {request_id}")
    if wait:
        try:
            print(json.dumps(await client.get_workflow_handle(request_id).result()))
        except WorkflowFailureError as exc:
            print(f"{request_id} failed: {exc.cause}", file=sys.stderr)
            return 1
    return 0


async def run_promoter(values: Any) -> int:
    from kp_canonicalization.promoter import promote

    log_json_lines()
    if not isinstance(values, dict) or not values.get("profiles"):
        # An empty mapping would retire every version: a chart that rendered nothing must not.
        log.error("no profiles in the deployment values")
        return 2
    try:
        alarms = await promote(await connect(), values["profiles"])
    except Exception as error:  # Temporal's text or the values': the promoter reads no document
        log.exception("promoter run failed: %r", error)
        return 1
    for alarm in alarms:
        log.error(alarm)
    if not alarms:
        log.info("promoter ok")
    return 1 if alarms else 0


if __name__ == "__main__":
    sys.exit(main())
