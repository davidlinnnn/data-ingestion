"""Temporal wrappers around the stage bodies, and worker start-up (#131). A wrapper adds only
heartbeats, cancellation and the runtime; ProcessingFailure crosses Temporal as a
non-retryable ApplicationError whose details the workflow turns into the failure report.

One worker serves one task queue of its Processing Profile version, so each queue scales as its
own Kubernetes Deployment: orchestration
runs the workflow and the light Activities, inference runs docling one call at a time and is
the only one that loads it, vlm sends the VLM requests, summary the Document Summary's and d3
the Quality Check's."""

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import timedelta
from typing import Any, TypeVar

from temporalio import activity
from temporalio.client import Client
from temporalio.common import VersioningBehavior, WorkerDeploymentVersion
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker, WorkerDeploymentConfig

from kp_canonicalization import metrics, weights
from kp_canonicalization.ports.object_store import ObjectStore
from kp_canonicalization.ports.status_reporter import StatusReport
from kp_canonicalization.stages import (
    AssembleInput,
    CheckInput,
    ChunkInput,
    EnrichInput,
    FailureInput,
    FinalizeInput,
    GroupInput,
    GroupRef,
    InventoryInput,
    InventoryRef,
    OutcomeRef,
    OverviewInput,
    Plan,
    Ports,
    PrepareInput,
    ProcessingFailure,
    Registered,
    Runtime,
    SummaryPlan,
    check,
    enrich_vlm,
    finalize,
    inventory,
    prepare,
    report,
    summary,
)
from kp_canonicalization.workflow import (
    FAILURE_TYPE,
    SEARCH_ATTRIBUTES,
    PaperPdfWorkflow,
    Queue,
    deployment_name,
    task_queue,
    tier,
)

VLM_SLOTS = 5  # #93 §7: documents in VLM enrichment at once per worker
SUMMARY_SLOTS = 5  # #93 §7: summary Activities (a chunk each) at once per worker
D3_SLOTS = 5  # documents in the Quality Check at once per worker, as VLM_SLOTS

T = TypeVar("T")


class _Activities:
    def __init__(self, ports: Ports, runtime: Runtime) -> None:
        self.ports = replace(ports, heartbeat=activity.heartbeat)
        self.runtime = runtime

    async def _run(self, body: Callable[..., Awaitable[T]], input: Any) -> T:
        info = activity.info()
        label = _tier()
        age = (info.started_time - info.current_attempt_scheduled_time).total_seconds()
        metrics.queue_age.labels(info.task_queue, label).observe(age)
        started = self.ports.clock.monotonic()
        heartbeat = asyncio.create_task(self._heartbeat())
        try:
            result = await body(input, self.ports, self.runtime)
            # prepare and finalize are status stages: the workflow times them.
            if info.activity_type not in ("prepare", "finalize"):
                metrics.stage_duration.labels(info.activity_type, label).observe(
                    self.ports.clock.monotonic() - started
                )
            return result
        except ProcessingFailure as failure:
            activity.logger.warning(
                "%s: %s (cause %s) %s", failure.reason, failure.message, failure.cause,
                failure.metadata,
            )  # fmt: skip
            raise ApplicationError(
                failure.message, failure.details(), type=FAILURE_TYPE, non_retryable=True
            ) from failure
        finally:
            heartbeat.cancel()

    async def _heartbeat(self) -> None:
        while True:
            activity.heartbeat()
            await asyncio.sleep(self.runtime.profile.runtime["heartbeat_interval_s"])


class Orchestration(_Activities):
    @activity.defn(name="prepare")
    async def prepare(self, input: PrepareInput) -> Plan:
        start = input.start if isinstance(input.start, dict) else {}
        correlation = {field: start.get(field) for field in SEARCH_ATTRIBUTES}
        activity.logger.info("preparing", extra={"correlation": correlation})
        return await self._run(prepare.run, input)

    @activity.defn(name="inventory")
    async def inventory(self, input: InventoryInput) -> InventoryRef:
        return await self._run(inventory.run, input)

    @activity.defn(name="finalize")
    async def finalize(self, input: FinalizeInput) -> str:
        ref = await self._run(finalize.run, input)
        result = json.loads(await self.ports.store.get(ref))
        for e in result["enrichments"]:
            method = f"{e['method_ref']['id']}@{e['method_ref']['version']}"
            metrics.item_outcomes.labels(method, e["status"], e["status_reason"] or "").inc()
        metrics.document_outcomes.labels("complete", _tier()).inc()
        return ref

    @activity.defn(name="register_failure")
    async def register_failure(self, input: FailureInput) -> str:
        ref = await self._run(finalize.run_failure, input)
        metrics.document_outcomes.labels("failed", _tier()).inc()
        return ref

    @activity.defn(name="report")
    async def report(self, input: StatusReport) -> bool:
        return await self._run(report.run, input)

    def all(self) -> list[Callable[..., Any]]:
        return [self.prepare, self.inventory, self.finalize, self.register_failure, self.report]


class Inference(_Activities):
    def __init__(self, ports: Ports, runtime: Runtime) -> None:
        super().__init__(ports, runtime)
        # Load docling and RapidOCR here, so that the orchestration worker stays light.
        from kp_canonicalization.stages import enrich_local, parse

        self.parse = parse
        self.enrich_local_stage = enrich_local

    @activity.defn(name="parse_group")
    async def parse_group(self, input: GroupInput) -> GroupRef:
        group = await self._run(self.parse.run_group, input)
        if not group.reused:
            first, last = group.pages
            metrics.stage_work.labels("parse_group", _tier()).inc(last - first + 1)
        return group

    @activity.defn(name="assemble")
    async def assemble(self, input: AssembleInput) -> Registered:
        return await self._run(self.parse.run_assemble, input)

    @activity.defn(name="enrich_local")
    async def enrich_local(self, input: EnrichInput) -> list[OutcomeRef]:
        return _count_enriched(await self._run(self.enrich_local_stage.run, input))

    def all(self) -> list[Callable[..., Any]]:
        return [self.parse_group, self.assemble, self.enrich_local]


class Vlm(_Activities):
    @activity.defn(name="enrich_vlm")
    async def enrich_vlm(self, input: EnrichInput) -> list[OutcomeRef]:
        return _count_enriched(await self._run(enrich_vlm.run, input))

    def all(self) -> list[Callable[..., Any]]:
        return [self.enrich_vlm]


class Summary(_Activities):
    @activity.defn(name="summary_sections")
    async def summary_sections(self, input: EnrichInput) -> SummaryPlan:
        return await self._run(summary.run_sections, input)

    @activity.defn(name="summary_chunk")
    async def summary_chunk(self, input: ChunkInput) -> None:
        return await self._run(summary.run_chunk, input)

    @activity.defn(name="summary_overview")
    async def summary_overview(self, input: OverviewInput) -> OutcomeRef:
        (outcome,) = _count_enriched([await self._run(summary.run_overview, input)])
        return outcome

    def all(self) -> list[Callable[..., Any]]:
        return [self.summary_sections, self.summary_chunk, self.summary_overview]


class D3(_Activities):
    @activity.defn(name="check")
    async def check(self, input: CheckInput) -> list[OutcomeRef]:
        return _count_enriched(await self._run(check.run, input))

    def all(self) -> list[Callable[..., Any]]:
        return [self.check]


def _tier() -> str:
    return tier(activity.info().priority.priority_key)


def _count_enriched(outcomes: list[OutcomeRef]) -> list[OutcomeRef]:
    """Count the items this Activity enriched or checked (not reused) as its stage work."""
    fresh = sum(not outcome.reused for outcome in outcomes)
    metrics.stage_work.labels(activity.info().activity_type, _tier()).inc(fresh)
    return outcomes


class WriteOnceUnsupported(RuntimeError):
    pass


async def check_write_once(store: ObjectStore) -> None:
    """Refuse to start on a store that silently overwrites: registration relies on one write
    per key (#129). Probes a fresh key twice; the first put must win, the second must not."""
    key = f"worker-probes/{uuid.uuid4().hex}"
    first = await store.put_if_absent(key, b"probe")
    second = await store.put_if_absent(key, b"probe")
    if (first, second) != (True, False):
        raise WriteOnceUnsupported(
            f"object store does not honour conditional writes (probe {key}: {first}, {second})"
        )


async def make_worker(
    client: Client,
    ports: Ports,
    runtime: Runtime,
    queue: Queue,
    shutdown_grace_s: float = 0,
    versioned: bool = False,
) -> Worker:
    """The worker of one task queue of runtime.profile's version. The inference worker refuses
    to start when its profile's model weights differ from the manifest. On shutdown, running
    Activities get shutdown_grace_s to finish before they are cancelled and retried elsewhere. A
    versioned worker joins the Worker Deployment of its Processing Profile version
    (deployment_name) as build runtime.build_id, and its workflows stay Pinned to that build."""
    await check_write_once(ports.store)
    common: dict[str, Any] = {
        "task_queue": task_queue(runtime.profile.id, queue),
        "graceful_shutdown_timeout": timedelta(seconds=shutdown_grace_s),
    }
    if versioned:
        common["deployment_config"] = WorkerDeploymentConfig(
            WorkerDeploymentVersion(deployment_name(runtime.profile.id), runtime.build_id),
            use_worker_versioning=True,
            default_versioning_behavior=VersioningBehavior.PINNED,
        )
    if queue == "vlm":
        return Worker(
            client,
            activities=Vlm(ports, runtime).all(),
            max_concurrent_activities=VLM_SLOTS,
            **common,
        )
    if queue == "summary":
        return Worker(
            client,
            activities=Summary(ports, runtime).all(),
            max_concurrent_activities=SUMMARY_SLOTS,
            **common,
        )
    if queue == "d3":
        return Worker(
            client,
            activities=D3(ports, runtime).all(),
            max_concurrent_activities=D3_SLOTS,
            **common,
        )
    if queue == "inference":
        components = [c for method in runtime.profile.methods.values() for c in method.components]
        await asyncio.to_thread(weights.verify, components, weights.root())
        # One slot: the worker polls only when its parser is free, so waiting work stays in
        # Temporal, visible as backlog, open to other workers and ordered by priority.
        return Worker(
            client,
            activities=Inference(ports, runtime).all(),
            max_concurrent_activities=1,
            **common,
        )
    return Worker(
        client,
        workflows=[PaperPdfWorkflow],
        activities=Orchestration(ports, runtime).all(),
        **common,
        # Eager Activities skip matching: they would carry no priority and no queue age.
        disable_eager_activity_execution=True,
    )
