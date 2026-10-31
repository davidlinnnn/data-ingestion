"""Temporal wrappers around the stage bodies, and worker start-up (#131). A wrapper adds only
heartbeats, cancellation and the runtime; ProcessingFailure crosses Temporal as a
non-retryable ApplicationError whose details the workflow turns into the failure report.

One worker serves one task queue, so each queue scales as its own deployment: orchestration
runs the workflow and the light Activities, inference runs docling one call at a time and is
the only one that loads it."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import timedelta
from typing import Any, TypeVar

from temporalio import activity
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from kp_processing import weights
from kp_processing.ports.object_store import ObjectStore
from kp_processing.ports.status_reporter import StatusReport
from kp_processing.stages import (
    AssembleInput,
    EnrichInput,
    FailureInput,
    FinalizeInput,
    GroupInput,
    GroupRef,
    InventoryInput,
    InventoryRef,
    OutcomeRef,
    Plan,
    Ports,
    PrepareInput,
    ProcessingFailure,
    Registered,
    Runtime,
    finalize,
    inventory,
    prepare,
    report,
)
from kp_processing.workflow import (
    FAILURE_TYPE,
    INFERENCE_QUEUE,
    ORCHESTRATION_QUEUE,
    PaperPdfWorkflow,
    Queue,
)

T = TypeVar("T")


class _Activities:
    def __init__(self, ports: Ports, runtime: Runtime) -> None:
        self.ports = replace(ports, heartbeat=activity.heartbeat)
        self.runtime = runtime

    async def _run(self, body: Callable[..., Awaitable[T]], input: Any) -> T:
        heartbeat = asyncio.create_task(self._heartbeat())
        try:
            return await body(input, self.ports, self.runtime)
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
        return await self._run(prepare.run, input)

    @activity.defn(name="inventory")
    async def inventory(self, input: InventoryInput) -> InventoryRef:
        return await self._run(inventory.run, input)

    @activity.defn(name="finalize")
    async def finalize(self, input: FinalizeInput) -> str:
        return await self._run(finalize.run, input)

    @activity.defn(name="register_failure")
    async def register_failure(self, input: FailureInput) -> str:
        return await self._run(finalize.run_failure, input)

    @activity.defn(name="report")
    async def report(self, input: StatusReport) -> bool:
        return await self._run(report.run, input)

    def all(self) -> list[Callable[..., Any]]:
        return [self.prepare, self.inventory, self.finalize, self.register_failure, self.report]


class Inference(_Activities):
    def __init__(self, ports: Ports, runtime: Runtime) -> None:
        super().__init__(ports, runtime)
        # Load docling and RapidOCR here, so that the orchestration worker stays light.
        from kp_processing.stages import enrich_local, parse

        self.parse = parse
        self.enrich_local_stage = enrich_local

    @activity.defn(name="parse_group")
    async def parse_group(self, input: GroupInput) -> GroupRef:
        return await self._run(self.parse.run_group, input)

    @activity.defn(name="assemble")
    async def assemble(self, input: AssembleInput) -> Registered:
        return await self._run(self.parse.run_assemble, input)

    @activity.defn(name="enrich_local")
    async def enrich_local(self, input: EnrichInput) -> list[OutcomeRef]:
        return await self._run(self.enrich_local_stage.run, input)

    def all(self) -> list[Callable[..., Any]]:
        return [self.parse_group, self.assemble, self.enrich_local]


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
    client: Client, ports: Ports, runtime: Runtime, queue: Queue, shutdown_grace_s: float = 0
) -> Worker:
    """The worker of one task queue. The inference worker refuses to start when its profile's
    model weights differ from the manifest. On shutdown, running Activities get
    shutdown_grace_s to finish before they are cancelled and retried elsewhere."""
    await check_write_once(ports.store)
    grace = timedelta(seconds=shutdown_grace_s)
    if queue == "inference":
        components = [c for method in runtime.profile.methods.values() for c in method.components]
        await asyncio.to_thread(weights.verify, components, weights.root())
        # One slot: the worker polls only when its parser is free, so waiting work stays in
        # Temporal, visible as backlog, open to other workers and ordered by priority.
        return Worker(
            client,
            task_queue=INFERENCE_QUEUE,
            activities=Inference(ports, runtime).all(),
            max_concurrent_activities=1,
            graceful_shutdown_timeout=grace,
        )
    return Worker(
        client,
        task_queue=ORCHESTRATION_QUEUE,
        workflows=[PaperPdfWorkflow],
        activities=Orchestration(ports, runtime).all(),
        graceful_shutdown_timeout=grace,
    )
