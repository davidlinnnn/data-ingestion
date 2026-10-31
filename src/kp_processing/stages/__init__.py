"""Activity bodies of the paper-pdf workflow (#129, stage graph and Activities).

Each stage module exposes `async def run(input, ports, runtime)`, free of Temporal: the
Temporal wrappers in kp_processing.worker only add heartbeats, cancellation and the
runtime. Temporal payloads carry references (object keys) and digests only.

Object keys (#129, object storage and registration):

    documents/{document_uid}/items/{key}/...         registered, write-once, shared across requests
    requests/{request_id}/attempts/{run_id}/plan.json the frozen group plan of one attempt
    requests/{request_id}/attempts/{run_id}/receipts/{item_id}/{attempt}.json
                                                      external request receipts (#133)
    requests/{request_id}/attempts/{run_id}/outcomes/{key}/outcome.json
                                                      outcome records that must not be reused
    documents/{document_uid}/service-unavailable/{request_id}  redrive marker (empty)
    requests/{request_id}/result.json | failure.json  the Processing Result or failure report

Enrichment (#132): inventory lists one item per enrichment target; an enrichment Activity
registers one outcome record per item under documents/{document_uid}/items/{key}/, and
finalize applies the profile's status rule to the outcome records.
"""

import asyncio
import contextlib
import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from kp_processing.ports.clock import Clock, SystemClock
from kp_processing.ports.inference import InferenceTransport
from kp_processing.ports.object_store import ObjectNotFound, ObjectStore
from kp_processing.ports.status_reporter import StatusReporter
from kp_processing.profile import ProcessingProfile

Cause = Literal["source", "platform"]
# v2 §6: configuration, method and integrity fail the document even on one item; source
# means the Source Revision itself is unprocessable; platform covers the rest.
Category = Literal["source", "configuration", "method", "integrity", "platform"]
ERROR_DOMAIN = "kp-processing"


@dataclass(frozen=True)
class Ports:
    store: ObjectStore
    reporter: StatusReporter
    clock: Clock = SystemClock()
    heartbeat: Callable[[], None] = lambda: None  # called after each completed item
    vlm: InferenceTransport | None = None  # only the vlm worker has one


@dataclass(frozen=True)
class Runtime:
    profile: ProcessingProfile  # the worker's Processing Profile, loaded at start
    # The bucket ports.store reads; until #57 decides custody, custody_ref must name it.
    custody_bucket: str
    build_id: str  # the worker build, e.g. "1-r1"; recorded in runtime_identity


class ProcessingFailure(Exception):
    """A failure that ends the request with a failure report. `reason` is UPPER_SNAKE_CASE;
    `metadata` holds extra string facts (limit and actual values) for the AIP-193 block."""

    def __init__(
        self,
        cause: Cause,
        category: Category,
        reason: str,
        message: str,
        retryable: bool = False,
        metadata: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.cause = cause
        self.category = category
        self.reason = reason
        self.message = message
        self.retryable = retryable
        self.metadata = metadata or {}

    def details(self) -> dict[str, Any]:
        """JSON-safe form carried across Temporal; error_block() turns it into the AIP-193
        block."""
        return {
            "cause": self.cause,
            "category": self.category,
            "reason": self.reason,
            "message": self.message,
            "retryable": self.retryable,
            "metadata": self.metadata,
        }


def error_block(details: dict[str, Any], occurred_at: str, support_ref: str) -> dict[str, Any]:
    """AIP-193 error block for the failure report and the failed status report. The category
    goes into metadata."""
    return {
        "domain": ERROR_DOMAIN,
        "reason": details["reason"],
        "message": details["message"],
        "retryable": details["retryable"],
        "metadata": {"category": details["category"], **details["metadata"]},
        "support_ref": support_ref,
        "occurred_at": occurred_at,
    }


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class PrepareInput:
    start: Any  # admission may send anything; prepare validates
    run_id: str  # Temporal run ID; names the attempt's scratch prefix


@dataclass(frozen=True)
class Plan:
    source_key: str  # object key of the main file in custody
    source_sha256: str
    page_count: int
    groups: list[list[int]]  # [first, last], 1-based inclusive, in page order
    no_text_layer_pages: list[int]
    ref: str  # requests/{request_id}/attempts/{run_id}/plan.json
    # The profile's runtime section, frozen into workflow history by this Activity's result;
    # the workflow takes the later Activities' options from it.
    runtime: dict[str, Any]


@dataclass(frozen=True)
class GroupInput:
    document_uid: str
    source_key: str
    source_sha256: str
    pages: list[int]  # [first, last]


@dataclass(frozen=True)
class GroupRef:
    pages: list[int]  # [first, last]
    ref: str  # key of the registered group.json
    digest: str  # sha256 of its bytes
    reused: bool  # True when it was registered before this call


@dataclass(frozen=True)
class Registered:
    ref: str  # key of the registered object
    digest: str  # sha256 of its bytes
    reused: bool


async def registered(store: ObjectStore, ref: str) -> Registered | None:
    """The object already registered at ref (reused=True), or None."""
    if await store.head(ref) is None:
        return None
    return Registered(ref, sha256(await store.get(ref)), True)


async def register(store: ObjectStore, ref: str, body: bytes) -> Registered:
    """Write once. When another writer won, its object is returned with reused=True."""
    created = await store.put_if_absent(ref, body)
    if not created:
        body = await store.get(ref)
    return Registered(ref, sha256(body), not created)


def item_prefix(document_uid: str, key: str) -> str:
    """documents/{document_uid}/items/{key}: where one registered item's objects live."""
    return f"documents/{document_uid}/items/{key}"


async def register_item(
    store: ObjectStore, prefix: str, record: str, body: bytes, files: dict[str, bytes]
) -> Registered:
    """Put each file at {prefix}/{name} (first write wins), then register {prefix}/{record}
    write-once and last, so that the record's presence means the item is complete."""
    for name, data in files.items():
        await store.put_if_absent(f"{prefix}/{name}", data)
    return await register(store, f"{prefix}/{record}", body)


async def in_thread[T](function: Callable[..., T], *args: Any) -> T:
    """asyncio.to_thread that, when cancelled, waits for the thread to end before raising
    CancelledError: a thread cannot be stopped, and the worker must not free the slot of a
    parser that still runs."""
    future = asyncio.ensure_future(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        while not future.done():
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait({future})
        raise


async def read_verified(
    store: ObjectStore, ref: str, digest: str, failure: Callable[[], ProcessingFailure]
) -> bytes:
    """The object at ref; raises failure() when it is missing or its sha256 is not digest."""
    try:
        data = await store.get(ref)
    except ObjectNotFound as exc:
        raise failure() from exc
    if sha256(data) != digest:
        raise failure()
    return data


@dataclass(frozen=True)
class AssembleInput:
    document_uid: str
    source_key: str
    source_sha256: str
    groups: list[GroupRef]  # every group of the plan, in page order


@dataclass(frozen=True)
class InventoryInput:
    document_uid: str
    source_key: str
    source_sha256: str
    groups: list[GroupRef]  # every group of the plan, in page order (for page images)
    assembly: Registered


@dataclass(frozen=True)
class InventoryRef:
    ref: str  # key of the registered inventory.json
    digest: str
    reused: bool
    items: int  # number of enrichment items it lists


@dataclass(frozen=True)
class EnrichInput:
    document_uid: str
    inventory: InventoryRef
    request_id: str  # with run_id, names the attempt's scratch prefix (receipts)
    run_id: str


@dataclass(frozen=True)
class OutcomeRef:
    item_id: str  # the inventory item this outcome record answers
    ref: str  # key of the registered outcome.json
    digest: str  # sha256 of its bytes
    reused: bool  # True when it was registered before this call


@dataclass(frozen=True)
class FinalizeInput:
    start: dict[str, Any]
    plan: Plan
    groups: list[GroupRef]
    assembly: Registered
    inventory: InventoryRef
    outcomes: list[OutcomeRef]  # from every enrichment Activity, in any order


@dataclass(frozen=True)
class FailureInput:
    request_id: str  # the workflow ID; the start input may be too malformed to hold it
    start: Any  # admission may send anything; prepare validates
    stage: Literal["prepare", "parse", "enrich", "finalize"]
    cause: Cause
    error: dict[str, Any]  # error_block()
    inventory_ref: str | None
