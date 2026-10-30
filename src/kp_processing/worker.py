"""Temporal wrappers around the stage bodies, and worker start-up (#131). A wrapper adds only
heartbeats, cancellation and the runtime; ProcessingFailure crosses Temporal as a
non-retryable ApplicationError whose details the workflow turns into the failure report."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from temporalio import activity
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from kp_processing.ports.object_store import ObjectStore
from kp_processing.ports.status_reporter import StatusReport
from kp_processing.stages import (
    AssembleInput,
    FailureInput,
    FinalizeInput,
    GroupInput,
    GroupRef,
    InventoryInput,
    Plan,
    Ports,
    PrepareInput,
    ProcessingFailure,
    Registered,
    Runtime,
    finalize,
    inventory,
    parse,
    prepare,
    report,
)
from kp_processing.workflow import FAILURE_TYPE, PaperPdfWorkflow, task_queue

T = TypeVar("T")


class Activities:
    def __init__(self, ports: Ports, runtime: Runtime) -> None:
        self.ports = ports
        self.runtime = runtime

    async def _run(self, body: Callable[..., Awaitable[T]], input: Any) -> T:
        heartbeat = asyncio.create_task(self._heartbeat())
        try:
            return await body(input, self.ports, self.runtime)
        except ProcessingFailure as failure:
            raise ApplicationError(
                failure.message, failure.details(), type=FAILURE_TYPE, non_retryable=True
            ) from failure
        finally:
            heartbeat.cancel()

    async def _heartbeat(self) -> None:
        while True:
            activity.heartbeat()
            await asyncio.sleep(self.runtime.profile.runtime["heartbeat_interval_s"])

    @activity.defn(name="prepare")
    async def prepare(self, input: PrepareInput) -> Plan:
        return await self._run(prepare.run, input)

    @activity.defn(name="parse_group")
    async def parse_group(self, input: GroupInput) -> GroupRef:
        return await self._run(parse.run_group, input)

    @activity.defn(name="assemble")
    async def assemble(self, input: AssembleInput) -> Registered:
        return await self._run(parse.run_assemble, input)

    @activity.defn(name="inventory")
    async def inventory(self, input: InventoryInput) -> Registered:
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
        return [
            self.prepare, self.parse_group, self.assemble, self.inventory, self.finalize,
            self.register_failure, self.report,
        ]  # fmt: skip


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


async def make_worker(client: Client, ports: Ports, runtime: Runtime, tier: str) -> Worker:
    """The CPU pool worker of one tier: the workflow and every Activity of #131."""
    await check_write_once(ports.store)
    return Worker(
        client,
        task_queue=task_queue("cpu", "low" if tier == "bulk" else "normal"),
        workflows=[PaperPdfWorkflow],
        activities=Activities(ports, runtime).all(),
    )
