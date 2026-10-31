"""Activity bodies of the paper-pdf workflow (#129, stage graph and Activities).

Each stage module exposes `async def run(input, ports, runtime)`, free of Temporal: the
Temporal wrappers in kp_processing.worker only add heartbeats, cancellation and the
runtime. Temporal payloads carry references (object keys) and digests only.

Object keys (#129, object storage and registration):

    documents/{document_uid}/items/{key}/...         registered, write-once, shared across requests
    requests/{request_id}/attempts/{run_id}/plan.json the frozen group plan of one attempt
    requests/{request_id}/result.json | failure.json  the Processing Result or failure report
"""

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

from kp_processing.ports.clock import Clock, SystemClock
from kp_processing.ports.object_store import ObjectStore
from kp_processing.ports.status_reporter import StatusReporter
from kp_processing.profile import Profile

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


@dataclass(frozen=True)
class Runtime:
    profile: Profile  # the worker's Processing Profile, loaded at start
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
    start: dict[str, Any]  # admission spec §10 start input, as received
    run_id: str  # Temporal run ID; names the attempt's scratch prefix


@dataclass(frozen=True)
class Plan:
    source_key: str  # object key of the main file in custody
    source_sha256: str
    page_count: int
    groups: list[list[int]]  # [first, last], 1-based inclusive, in page order
    no_text_layer_pages: list[int]
    ref: str  # requests/{request_id}/attempts/{run_id}/plan.json


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


@dataclass(frozen=True)
class AssembleInput:
    document_uid: str
    source_key: str
    source_sha256: str
    groups: list[GroupRef]  # every group of the plan, in page order


@dataclass(frozen=True)
class InventoryInput:
    document_uid: str
    assembly: Registered


@dataclass(frozen=True)
class FinalizeInput:
    start: dict[str, Any]
    plan: Plan
    groups: list[GroupRef]
    assembly: Registered
    inventory: Registered


@dataclass(frozen=True)
class FailureInput:
    request_id: str  # the workflow ID; the start input may be too malformed to hold it
    start: dict[str, Any]
    stage: Literal["prepare", "parse", "enrich", "finalize"]
    cause: Cause
    error: dict[str, Any]  # error_block()
    inventory_ref: str | None
