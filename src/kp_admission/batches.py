"""Batches: declaration, finalization, the batch's status and its expiry (admission spec §5.1,
§5.3, §5.4, §6, §11; #96).

Placement checks and storage are asked before a transaction takes its connection, so a
declaration or finalization never holds a locked row while it waits on either. Finalization and
re-declaration lock the document row (§3); a document created at finalization is guarded by the
`document_live_id` index instead.
"""

import asyncio
import hashlib
import json
import math
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import quote

import psycopg
from prometheus_client import Counter
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

from kp_admission import adoption
from kp_admission.authz import Authorizer, Decision, Ref
from kp_admission.errors import Refused
from kp_admission.requests import create_process_request
from kp_admission.resources import resource_id
from kp_admission.status import refresh
from kp_admission.storage import ObjectStore, StorageUnavailable, source_key

MAX_ITEMS = 50  # per declaration (§11, provisional)
QUOTA_ITEMS, QUOTA_PER_S = 50, 50 / 60  # each Source's bucket and refill (§11, provisional)
OPEN_FOR = timedelta(hours=24)
IDEMPOTENCY_FOR = timedelta(hours=24)
MAX_FILE_SIZE = 50 * 2**20

items_decided = Counter(
    "kp_admission_items", "batch items decided", ["operation", "status", "reason"]
)

_DOCUMENT_ID = re.compile(r"[A-Za-z0-9\-_.~:]{1,256}")
_METADATA_KEY = re.compile(r"[A-Za-z0-9_.\-]{1,64}")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})")

_MESSAGES = {
    "INVALID_ARGUMENT": "The item is malformed.",
    "FILE_TOO_LARGE": "A file is larger than the maximum file size.",
    "UNSUPPORTED_FORMAT": "No Processing Profile version is adopted for the main file's format.",
    "SOURCE_VERSION_REQUIRED": "The Source orders by source_version; the item has none.",
    "BINDING_CONFLICT": "The document is bound to another Resource.",
    "RESOURCE_NOT_FOUND": "The Source registered no Resource with this key.",
    "RESOURCE_REQUIRED": "A new document needs a Resource and the Source has no default.",
    "STALE_SOURCE_VERSION": "A higher source_version is already admitted.",
    "VERSION_CONFLICT": "This source_version is already admitted with other content.",
    "DOCUMENT_DELETED": "The document was deleted after the declaration.",
    "STALE_DECLARATION": "Another batch created the document after the declaration; declare again.",
    "FILES_MISSING": "A file to upload is not in place.",
}


class SourceSettings(BaseModel, frozen=True, extra="forbid"):
    """What admission reads of a Source's registration besides its credentials (§2)."""

    ordering: Literal["source_version", "arrival"] = "source_version"
    default_resource_id: str | None = Field(default=None, min_length=1)  # one of its own keys


@dataclass(frozen=True)
class Intake:
    """The deployment's settings of the batch API. Declarations pause while at least
    `pause_backlog` normal-priority process requests are queued (§9), never without it: a
    platform refresh's low-priority backlog never pauses intake. `public_url` is the origin
    Sources call, which every upload URL names (§5.1); without it, the URL the request reached."""

    store: ObjectStore
    sources: Mapping[str, SourceSettings] = field(default_factory=dict)
    max_file_size: int = MAX_FILE_SIZE
    pause_backlog: int | None = None
    public_url: str | None = None


class DeclaredFile(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    role: str
    sha256: str
    size: int = Field(ge=0)
    media_type: str = Field(min_length=1, max_length=255)


class DeclaredItem(BaseModel):
    document_id: str
    source_version: str | None = None
    title: str | None = None
    source_url: str | None = None
    resources: list[str] | None = Field(
        default=None, description="The Source's own Resource key, exactly one"
    )
    uploaded_by: str | None = None
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Source Metadata: replaces the whole map, omitted keeps it, {} clears it."
        " Everyone who can read the document can see it.",
    )
    files: list[DeclaredFile]


@dataclass
class Caller:
    tenant_id: str
    source_id: str
    trace_id: str


@dataclass
class _Document:
    uid: str
    resource_id: str
    latest: dict[str, Any] | None  # source_revision_id, source_version, files, outcome


@dataclass
class _Outcome:
    status: str
    reason: str | None = None
    request_id: str | None = None
    source_revision_id: str | None = None

    @classmethod
    def rejected(cls, reason: str) -> "_Outcome":
        return cls("rejected", reason)


class _Again(Exception):
    """Something changed between the reads and the transaction: start over."""


def body_sha256(items: list[DeclaredItem]) -> str:
    canonical = json.dumps([i.model_dump(mode="json") for i in items], sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


# --- Data access: one operation, one function. ---


async def _replay(
    conn: AsyncConnection, caller: Caller, key: str, digest: str
) -> tuple[int, dict] | None:
    row = await (
        await conn.execute(
            "SELECT body_sha256, status, response, created_at > now() - %s FROM idempotency_key"
            " WHERE tenant_id = %s AND source_id = %s AND key = %s",
            (IDEMPOTENCY_FOR, caller.tenant_id, caller.source_id, key),
        )
    ).fetchone()
    if row is None:
        return None
    if not row[3]:  # expired: the key is free again
        await conn.execute(
            "DELETE FROM idempotency_key WHERE tenant_id = %s AND source_id = %s AND key = %s",
            (caller.tenant_id, caller.source_id, key),
        )
        return None
    if row[0] != digest:
        raise Refused(
            422,
            "FAILED_PRECONDITION",
            "IDEMPOTENCY_KEY_REUSED",
            "The Idempotency-Key was used with another body.",
        )
    return row[1], row[2]


async def _remember(
    conn: AsyncConnection, caller: Caller, key: str, digest: str, status: int, body: dict
) -> bool:
    """False when a concurrent declaration with the same key committed first."""
    cursor = await conn.execute(
        "INSERT INTO idempotency_key (tenant_id, source_id, key, body_sha256, status, response)"
        " VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (caller.tenant_id, caller.source_id, key, digest, status, Jsonb(body)),
    )
    return cursor.rowcount == 1


async def _backlog(conn: AsyncConnection) -> int:
    row = await (
        await conn.execute(
            "SELECT count(*) FROM request"
            " WHERE kind = 'process' AND state = 'queued' AND priority = 'normal'"
        )
    ).fetchone()
    return row[0] if row else 0


async def _take_quota(conn: AsyncConnection, caller: Caller, items: int) -> float:
    """Takes `items` tokens from the Source's bucket and returns 0, or takes none and returns the
    seconds until there are enough. The row stays locked until the transaction ends."""
    await conn.execute(
        "INSERT INTO intake_quota (tenant_id, source_id, tokens, refilled_at)"
        " VALUES (%s, %s, %s, now()) ON CONFLICT DO NOTHING",
        (caller.tenant_id, caller.source_id, QUOTA_ITEMS),
    )
    row = await (
        await conn.execute(
            "SELECT tokens, refilled_at, now() FROM intake_quota"
            " WHERE tenant_id = %s AND source_id = %s FOR UPDATE",
            (caller.tenant_id, caller.source_id),
        )
    ).fetchone()
    assert row
    at = max(row[1], row[2])  # now() is this transaction's start, which may precede the last take
    tokens = min(QUOTA_ITEMS, row[0] + (at - row[1]).total_seconds() * QUOTA_PER_S)
    if tokens < items:
        return (items - tokens) / QUOTA_PER_S
    await conn.execute(
        "UPDATE intake_quota SET tokens = %s, refilled_at = %s"
        " WHERE tenant_id = %s AND source_id = %s",
        (tokens - items, at, caller.tenant_id, caller.source_id),
    )
    return 0.0


_DOCUMENT = """
SELECT d.document_uid, d.resource_id, r.source_revision_id, r.source_version, r.files, r.outcome,
       d.deleted_at IS NOT NULL
FROM document d LEFT JOIN source_revision r ON r.source_revision_id = d.latest_source_revision_id
WHERE {where}
"""


def _document_of(row: tuple | None) -> _Document | None:
    if row is None:
        return None
    latest: dict[str, Any] | None = None
    if row[2]:
        latest = dict(
            zip(("source_revision_id", "source_version", "files", "outcome"), row[2:6], strict=True)
        )
    return _Document(row[0], row[1], latest)


async def _locked(conn: AsyncConnection, where: str, params: tuple) -> None:
    # A statement of its own: one that waits for the lock reads rows as they were when it began.
    await conn.execute(f"SELECT 1 FROM document d WHERE {where} FOR UPDATE", params)  # type: ignore[arg-type]


async def _live_document(
    conn: AsyncConnection, caller: Caller, document_id: str, lock: bool
) -> _Document | None:
    where = "d.tenant_id = %s AND d.source_id = %s AND d.document_id = %s AND d.deleted_at IS NULL"
    params = (caller.tenant_id, caller.source_id, document_id)
    if lock:
        await _locked(conn, where, params)
    query = _DOCUMENT.format(where=where)
    return _document_of(await (await conn.execute(query, params)).fetchone())  # type: ignore[arg-type]


async def _document_by_uid(conn: AsyncConnection, uid: str) -> tuple[_Document, bool] | None:
    """The document with this uid, locked, and whether it is deleted."""
    await _locked(conn, "d.document_uid = %s", (uid,))
    query = _DOCUMENT.format(where="d.document_uid = %s")
    row = await (await conn.execute(query, (uid,))).fetchone()  # type: ignore[arg-type]
    document = _document_of(row)
    return None if row is None or document is None else (document, row[6])


async def _active_request(conn: AsyncConnection, uid: str, srv: str) -> str | None:
    row = await (
        await conn.execute(
            "SELECT request_id FROM request WHERE document_uid = %s AND source_revision_id = %s"
            " AND kind = 'process' AND state IN ('queued', 'processing')",
            (uid, srv),
        )
    ).fetchone()
    return row[0] if row else None


async def _last_failed_request(conn: AsyncConnection, uid: str, srv: str) -> str | None:
    row = await (
        await conn.execute(
            "SELECT request_id FROM request WHERE document_uid = %s AND source_revision_id = %s"
            " AND kind = 'process' AND state = 'failed' ORDER BY created_at DESC LIMIT 1",
            (uid, srv),
        )
    ).fetchone()
    return row[0] if row else None


async def _apply_catalog(conn: AsyncConnection, uid: str, item: dict[str, Any]) -> None:
    """§6.5: a submitted title or source_url replaces the value; metadata replaces the map."""
    metadata = item.get("metadata")
    await conn.execute(
        "UPDATE document SET title = coalesce(%s, title), source_url = coalesce(%s, source_url),"
        " metadata = coalesce(%s, metadata) WHERE document_uid = %s",
        (
            item.get("title"),
            item.get("source_url"),
            None if metadata is None else Jsonb(metadata),
            uid,
        ),
    )


async def _record_version(conn: AsyncConnection, srv: str, version: str) -> None:
    """§6.4: a higher source_version of the same content becomes its Source Revision's."""
    await conn.execute(
        "UPDATE source_revision SET source_version = %s WHERE source_revision_id = %s",
        (version, srv),
    )


async def _lock_resource(conn: AsyncConnection, full_id: str) -> bool:
    """Locks the Resource's row against its deletion, which locks it FOR UPDATE, so a document is
    never left bound to a deleted Resource (#114, authorization guide §4.6); shared, so bindings
    into one Resource do not wait on each other. False when it does not exist."""
    row = await (
        await conn.execute(
            "SELECT 1 FROM authz.resource WHERE resource_id = %s FOR SHARE", (full_id,)
        )
    ).fetchone()
    return row is not None


async def _create_document(
    conn: AsyncConnection, caller: Caller, uid: str, item: dict[str, Any]
) -> bool:
    """False when another document with the same document_id was created meanwhile."""
    try:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO document (document_uid, tenant_id, source_id, document_id,"
                " resource_id) VALUES (%s, %s, %s, %s, %s)",
                (uid, caller.tenant_id, caller.source_id, item["document_id"], item["resource_id"]),
            )
        return True
    except psycopg.errors.UniqueViolation:
        return False


async def _create_revision(
    conn: AsyncConnection, caller: Caller, uid: str, item: dict[str, Any], files: list[dict]
) -> str:
    srv = f"srv_{uuid.uuid4().hex}"
    # Under the Document's lock, so no two Source Revisions of it count the same sequence.
    await conn.execute(
        "INSERT INTO source_revision (source_revision_id, tenant_id, document_uid, source_version,"
        " files, sequence) SELECT %s, %s, %s, %s, %s, coalesce(max(sequence), 0) + 1"
        " FROM source_revision WHERE document_uid = %s",
        (srv, caller.tenant_id, uid, item.get("source_version"), Jsonb(files), uid),
    )
    await conn.execute(
        "UPDATE document SET latest_source_revision_id = %s WHERE document_uid = %s", (srv, uid)
    )
    return srv


async def _insert_batch(conn: AsyncConnection, caller: Caller, batch_id: str) -> datetime:
    row = await (
        await conn.execute(
            "INSERT INTO batch (batch_id, tenant_id, source_id, state, expires_at)"
            " VALUES (%s, %s, %s, 'open', now() + %s) RETURNING expires_at",
            (batch_id, caller.tenant_id, caller.source_id, OPEN_FOR),
        )
    ).fetchone()
    assert row
    return row[0]


async def _insert_item(
    conn: AsyncConnection,
    caller: Caller,
    batch_id: str,
    index: int,
    item: dict[str, Any],
    uid: str | None,
    outcome: _Outcome,
    placement: dict | None,
) -> None:
    await conn.execute(
        "INSERT INTO batch_item (batch_id, index, tenant_id, document_id, document_uid, status,"
        " request_id, source_revision_id, error, declared, placement)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            batch_id,
            index,
            caller.tenant_id,
            str(item.get("document_id", "")),
            uid,
            outcome.status,
            outcome.request_id,
            outcome.source_revision_id,
            _error(outcome) and Jsonb(_error(outcome)),
            Jsonb(item),
            placement and Jsonb(placement),
        ),
    )


async def _update_item(
    conn: AsyncConnection, batch_id: str, index: int, outcome: _Outcome, placement: dict | None
) -> None:
    await conn.execute(
        "UPDATE batch_item SET status = %s, request_id = %s, source_revision_id = %s, error = %s,"
        " placement = %s WHERE batch_id = %s AND index = %s",
        (
            outcome.status,
            outcome.request_id,
            outcome.source_revision_id,
            _error(outcome) and Jsonb(_error(outcome)),
            placement and Jsonb(placement),
            batch_id,
            index,
        ),
    )


@dataclass
class _Batch:
    state: str
    overdue: bool  # open, past expires_at, not yet marked expired
    created_at: datetime
    expires_at: datetime
    finalized_at: datetime | None


async def _batch(
    conn: AsyncConnection, caller: Caller, batch_id: str, lock: bool = False
) -> _Batch | None:
    """The Source's batch; None for another Source's."""
    row = await (
        await conn.execute(
            "SELECT state, state = 'open' AND expires_at <= now(), created_at, expires_at,"
            " finalized_at FROM batch WHERE batch_id = %s AND tenant_id = %s AND source_id = %s"
            + (" FOR UPDATE" if lock else ""),
            (batch_id, caller.tenant_id, caller.source_id),
        )
    ).fetchone()
    return None if row is None else _Batch(*row)


async def _delete_batch(conn: AsyncConnection, batch_id: str) -> None:
    await conn.execute("DELETE FROM batch WHERE batch_id = %s", (batch_id,))


async def _mark_finalized(conn: AsyncConnection, batch_id: str) -> None:
    await conn.execute(
        "UPDATE batch SET state = 'finalized', finalized_at = now() WHERE batch_id = %s",
        (batch_id,),
    )


async def _declared_items(
    conn: AsyncConnection, batch_id: str
) -> list[tuple[int, str, dict, dict]]:
    """(index, document_uid, the item as declared, its placement record) of each declared item."""
    rows = await (
        await conn.execute(
            "SELECT index, document_uid, declared, placement FROM batch_item"
            " WHERE batch_id = %s AND status = 'declared' ORDER BY index",
            (batch_id,),
        )
    ).fetchall()
    return [(row[0], row[1], row[2], row[3]) for row in rows]


async def _items(conn: AsyncConnection, batch_id: str) -> list[tuple]:
    return await (
        await conn.execute(
            "SELECT i.index, i.document_id, i.document_uid, i.status, i.request_id,"
            " i.source_revision_id, i.error, r.state FROM batch_item i"
            " LEFT JOIN request r ON r.request_id = i.request_id"
            " WHERE i.batch_id = %s ORDER BY i.index",
            (batch_id,),
        )
    ).fetchall()


async def expire(conn: AsyncConnection, batch_id: str | None = None) -> int:
    """Marks every open batch 24 hours old as expired, or only `batch_id`, with its declared items
    (§11), and returns how many. The hourly CronJob runs it for all."""
    only = "" if batch_id is None else " AND batch_id = %(batch_id)s"
    params = {"batch_id": batch_id}
    async with conn.transaction():
        rows = await (
            await conn.execute(
                "SELECT batch_id FROM batch WHERE state = 'open' AND expires_at <= now()"
                + only
                + " ORDER BY batch_id FOR UPDATE",
                params,
            )
        ).fetchall()
        ids = [row[0] for row in rows]
        for expiring in ids:
            await conn.execute(
                "UPDATE batch_item SET status = 'expired'"
                " WHERE batch_id = %s AND status = 'declared'",
                (expiring,),
            )
            await conn.execute(
                "UPDATE batch SET state = 'expired' WHERE batch_id = %s", (expiring,)
            )
    return len(ids)


# --- The rules (§6). ---


def _at(at: datetime) -> str:
    return at.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _error(outcome: _Outcome) -> dict | None:
    if outcome.reason is None:
        return None
    return {"reason": outcome.reason, "message": _MESSAGES[outcome.reason]}


def _version(value: str) -> int | datetime | None:
    """An integer or an RFC 3339 time with its offset (§6.3); None for anything else."""
    if re.fullmatch(r"[0-9]{1,18}", value):
        return int(value)
    if not _RFC3339.fullmatch(value):
        return None
    try:
        at = datetime.fromisoformat(value)
    except ValueError:
        return None
    return at if at.tzinfo else None


def _structure(item: DeclaredItem, max_file_size: int) -> str | None:
    """§6.1 rule 1."""
    paths = [f.path for f in item.files]
    if (
        not _DOCUMENT_ID.fullmatch(item.document_id)
        or [f.role for f in item.files].count("main") != 1
        or any(f.role not in ("main", "attachment") for f in item.files)
        or len(set(paths)) != len(paths)
        or any(p.startswith("/") or ".." in p.split("/") or "" in p.split("/") for p in paths)
        or any(not _SHA256.fullmatch(f.sha256) for f in item.files)
        or (item.resources is not None and (len(item.resources) != 1 or not item.resources[0]))
        or (item.source_version is not None and _version(item.source_version) is None)
        or not _valid_metadata(item.metadata)
    ):
        return "INVALID_ARGUMENT"
    if any(f.size > max_file_size for f in item.files):
        return "FILE_TOO_LARGE"
    return None


def _valid_metadata(metadata: dict[str, Any] | None) -> bool:
    if metadata is None:
        return True
    return (
        len(metadata) <= 50
        and all(_METADATA_KEY.fullmatch(k) for k in metadata)
        and all(isinstance(v, str) and len(v) <= 512 for v in metadata.values())
        and len(json.dumps(metadata, ensure_ascii=False).encode()) <= 8192
    )


def _main(item: dict[str, Any]) -> dict[str, Any]:
    return next(f for f in item["files"] if f["role"] == "main")


def _content(files: list[dict]) -> set[tuple[str, str]]:
    return {(f["path"], f["sha256"]) for f in files}


def _order(item: dict[str, Any], latest: dict | None, ordering: str) -> str | None:
    """§6.3 against the latest Source Revision: a rejection reason, "same" or "newer" (a higher
    source_version) for §6.4, or None when the item makes a new Source Revision."""
    if latest is None:
        return None
    same = _content(item["files"]) == _content(latest["files"])
    if ordering == "arrival" or latest["source_version"] is None:
        return "same" if same else None
    new, old = _version(item["source_version"]), _version(latest["source_version"])
    if type(new) is not type(old):
        return "INVALID_ARGUMENT"  # one kind of source_version per Source
    assert new is not None and old is not None
    if new < old:  # type: ignore[operator]
        return "STALE_SOURCE_VERSION"
    if same:
        return "same" if new == old else "newer"
    if new == old:
        return None if latest["outcome"] == "rejected" else "VERSION_CONFLICT"
    return None


async def _same_content(
    conn: AsyncConnection,
    caller: Caller,
    document: _Document,
    item: dict[str, Any],
    batch_id: str,
    adopted: tuple[str, int],
    order: str,
) -> _Outcome:
    """§6.4, with the catalog fields and a higher source_version recorded in every case."""
    latest = document.latest
    assert latest
    srv = latest["source_revision_id"]
    await _apply_catalog(conn, document.uid, item)
    if order == "newer":
        await _record_version(conn, srv, item["source_version"])
    if active := await _active_request(conn, document.uid, srv):
        return _Outcome("queued", request_id=active, source_revision_id=srv)
    if latest["outcome"] == "failed":
        request_id, _ = await create_process_request(
            conn,
            tenant_id=caller.tenant_id,
            document_uid=document.uid,
            source_revision_id=srv,
            initiator="source",
            priority="normal",
            adopted_version=adopted[0],
            adoption_sequence=adopted[1],
            trace_id=caller.trace_id,
            batch_id=batch_id,
            retry_of=await _last_failed_request(conn, document.uid, srv),
        )
        return _Outcome("queued", request_id=request_id, source_revision_id=srv)
    return _Outcome("unchanged", source_revision_id=srv)


def _record(decision: Decision) -> dict[str, Any]:
    record: dict[str, Any] = {
        "decision_id": decision.decision_id,
        "evaluated_at": decision.evaluated_at.isoformat(),
    }
    return record | ({"reason": decision.reason} if decision.reason else {})


async def _place(authorizer: Authorizer, caller: Caller, full_ids: set[str]) -> dict[str, Decision]:
    """The placement decision for each Resource; 503 AUTHZ_UNAVAILABLE when one is unavailable."""
    ordered = sorted(full_ids)
    subject = Ref(type="source", id=caller.source_id)
    made = await asyncio.gather(
        *(authorizer.check(subject, "place", rid, trace_id=caller.trace_id) for rid in ordered)
    )
    if any(d.outcome == "unavailable" for d in made):
        raise Refused(503, "UNAVAILABLE", "AUTHZ_UNAVAILABLE", "No decision could be made.")
    return dict(zip(ordered, made, strict=True))


def _resource(
    item: DeclaredItem, document: _Document | None, settings: SourceSettings, source_id: str
) -> str | None:
    """The full identifier the item is placed into (§6.1 rules 4 and 5)."""
    if item.resources:
        return resource_id(source_id, item.resources[0])
    if document:
        return document.resource_id
    if settings.default_resource_id:
        return resource_id(source_id, settings.default_resource_id)
    return None


def _upload_url(base: str, batch_id: str, index: int, path: str) -> str:
    return f"{base.rstrip('/')}/v1/batches/{batch_id}/items/{index}/files/{quote(path)}"


async def declare(
    pool: AsyncConnectionPool,
    authorizer: Authorizer,
    intake: Intake,
    caller: Caller,
    items: list[DeclaredItem],
    idempotency_key: str | None,
    base_url: str,
) -> tuple[int, dict[str, Any]]:
    """§5.1 and §6.1: (201, the batch) or (422, ALL_ITEMS_REJECTED's body); Refused for the
    other whole-request outcomes."""
    if len(items) > MAX_ITEMS:
        raise Refused(400, "INVALID_ARGUMENT", "TOO_MANY_ITEMS", f"At most {MAX_ITEMS} items.")
    digest = body_sha256(items)
    settings = intake.sources.get(caller.source_id, SourceSettings())
    while True:
        try:
            return await _declare_once(
                pool, authorizer, intake, settings, caller, items, idempotency_key, digest, base_url
            )
        except _Again:
            continue
        except Refused as refused:
            # The same key may have committed since the first look: its response wins.
            if refused.code in (429, 503) and idempotency_key:
                async with pool.connection() as conn:
                    if replayed := await _replay(conn, caller, idempotency_key, digest):
                        return replayed
            raise


async def _declare_once(
    pool: AsyncConnectionPool,
    authorizer: Authorizer,
    intake: Intake,
    settings: SourceSettings,
    caller: Caller,
    items: list[DeclaredItem],
    key: str | None,
    digest: str,
    base_url: str,
) -> tuple[int, dict[str, Any]]:
    async with pool.connection() as conn:
        if key and (replayed := await _replay(conn, caller, key, digest)):
            return replayed
        if intake.pause_backlog is not None and await _backlog(conn) >= intake.pause_backlog:
            raise Refused(503, "UNAVAILABLE", "ADMISSION_PAUSED", "Admission is paused.")
        known = {
            i.document_id: await _live_document(conn, caller, i.document_id, False) for i in items
        }
    resources = {
        rid
        for i in items
        if (rid := _resource(i, known[i.document_id], settings, caller.source_id))
    }
    decisions = await _place(authorizer, caller, resources)

    batch_id = f"bat_{uuid.uuid4().hex}"
    async with pool.connection() as conn, conn.transaction():
        # Taken first, so every declaration locks the quota row before any document row.
        if wait_s := await _take_quota(conn, caller, len(items)):
            raise Refused(
                429,
                "RESOURCE_EXHAUSTED",
                "RATE_LIMITED",
                f"At most {QUOTA_ITEMS} declared items per minute.",
                retry_after=max(1, math.ceil(wait_s)),
            )
        expires_at = await _insert_batch(conn, caller, batch_id)
        seen: set[str] = set()
        rows: list[tuple[dict, str | None, _Outcome, dict | None, dict]] = []
        # Locks follow document_id order, so concurrent declarations cannot deadlock.
        for index in sorted(range(len(items)), key=lambda k: items[k].document_id):
            item = items[index]
            stored: dict[str, Any] = item.model_dump(mode="json") | {"index": index}
            for f in stored["files"]:
                f["sha256"] = f["sha256"].lower()
            response: dict[str, Any] = {"index": index, "document_id": item.document_id}
            uid, placement = None, None
            # One item per document in a declaration.
            duplicate = item.document_id in seen
            reason = "INVALID_ARGUMENT" if duplicate else _structure(item, intake.max_file_size)
            seen.add(item.document_id)
            adopted = None
            if not reason:
                adopted = await adoption.current(conn, _main(stored)["media_type"])
                if adopted is None:
                    reason = "UNSUPPORTED_FORMAT"
            if not reason and settings.ordering == "source_version" and item.source_version is None:
                reason = "SOURCE_VERSION_REQUIRED"
            document = None
            if not reason:
                document = await _live_document(conn, caller, item.document_id, True)
                full_id = _resource(item, document, settings, caller.source_id)
                if document and item.resources and full_id != document.resource_id:
                    reason = "BINDING_CONFLICT"
                elif full_id is None:
                    reason = "RESOURCE_REQUIRED"
                elif full_id not in decisions:
                    raise _Again  # the document appeared or moved after the reads
                else:
                    placement = {"declaration": _record(decisions[full_id])}
                    stored["resource_id"] = full_id
                    if decisions[full_id].outcome == "deny":
                        reason = "RESOURCE_NOT_FOUND"
            if reason:
                outcome = _Outcome.rejected(reason)
            else:
                assert adopted
                latest = document.latest if document else None
                order = _order(stored, latest, settings.ordering)
                if order in ("same", "newer"):
                    assert document
                    outcome = await _same_content(
                        conn, caller, document, stored, batch_id, adopted, order
                    )
                    uid = document.uid
                elif order:
                    outcome = _Outcome.rejected(order)
                else:
                    uid = document.uid if document else f"doc_{uuid.uuid4().hex}"
                    stored["new"] = document is None
                    previous = {
                        (f["path"], f["sha256"]): f for f in (latest or {}).get("files", [])
                    }
                    carried = [f for f in stored["files"] if (f["path"], f["sha256"]) in previous]
                    stored["carried"] = {
                        f["path"]: previous[(f["path"], f["sha256"])]["custody_ref"]
                        for f in carried
                    }
                    response["uploads"] = [
                        {
                            "path": f["path"],
                            "method": "PUT",
                            "url": _upload_url(base_url, batch_id, index, f["path"]),
                        }
                        for f in stored["files"]
                        if f["path"] not in stored["carried"]
                    ]
                    response["carried_over"] = [f["path"] for f in carried]
                    outcome = _Outcome("declared")
            items_decided.labels("declare", outcome.status, outcome.reason or "").inc()
            response |= {"document_uid": uid, "status": outcome.status}
            response |= {"request_id": outcome.request_id, "error": _error(outcome)}
            rows.append((stored, uid, outcome, placement, response))

        rows.sort(key=lambda row: row[0]["index"])
        listed = [{k: v for k, v in row[4].items() if v is not None} for row in rows]
        if all(row[2].status == "rejected" for row in rows):
            await _delete_batch(conn, batch_id)
            status, body = 422, _all_rejected(listed)
        else:
            for stored, uid, outcome, placement, _ in rows:
                await _insert_item(
                    conn, caller, batch_id, stored["index"], stored, uid, outcome, placement
                )
            state = "open"
            if not any(row[2].status == "declared" for row in rows):
                state = "finalized"  # §5.1: nothing to upload
                await _mark_finalized(conn, batch_id)
            status = 201
            body = {
                "batch_id": batch_id,
                "state": state,
                "expires_at": _at(expires_at),
                "items": listed,
            }
        if key and not await _remember(conn, caller, key, digest, status, body):
            raise _Again  # the same key committed first: replay it
    return status, body


def _all_rejected(items: list[dict]) -> dict[str, Any]:
    return {"reason": "ALL_ITEMS_REJECTED", "message": "Every item is rejected.", "items": items}


async def finalize(
    pool: AsyncConnectionPool,
    authorizer: Authorizer,
    intake: Intake,
    caller: Caller,
    batch_id: str,
) -> tuple[int, dict[str, Any]]:
    """§5.3 and §6.2: (202, the batch) or (422, ALL_ITEMS_REJECTED's body); repeating it
    returns the batch as it stands. Refused for 404, 409 BATCH_EXPIRED and the 503s."""
    settings = intake.sources.get(caller.source_id, SourceSettings())
    async with pool.connection() as conn:
        found = await _batch(conn, caller, batch_id)
        if found is None:
            raise _not_found()
        if found.overdue:
            await expire(conn, batch_id)
        if found.state == "expired" or found.overdue:
            raise _expired()
        declared = await _declared_items(conn, batch_id) if found.state == "open" else []
    decisions = await _place(authorizer, caller, {d[2]["resource_id"] for d in declared})
    keys = {
        (index, f["path"]): source_key(uid, batch_id, index, f["sha256"])
        for index, uid, item, _ in declared
        for f in item["files"]
        if f["path"] not in item["carried"]
    }
    try:
        present = await asyncio.gather(*(intake.store.head(k) for k in keys.values()))
    except StorageUnavailable:
        raise Refused(
            503, "UNAVAILABLE", "UNAVAILABLE", "Storage cannot say whether the files are in place."
        ) from None
    in_place = dict(zip(keys, present, strict=True))

    expired = False
    async with pool.connection() as conn:
        async with conn.transaction():
            found = await _batch(conn, caller, batch_id, lock=True)
            assert found
            if found.overdue:
                expired = True
            elif found.state == "open":
                for index, uid, item, placement in sorted(
                    declared, key=lambda d: d[2]["document_id"]
                ):
                    decision = decisions[item["resource_id"]]
                    outcome = await _finalize_item(
                        conn,
                        caller,
                        settings,
                        intake,
                        batch_id,
                        index,
                        uid,
                        item,
                        decision,
                        in_place,
                    )
                    items_decided.labels("finalize", outcome.status, outcome.reason or "").inc()
                    record = placement | {"finalization": _record(decision)}
                    await _update_item(conn, batch_id, index, outcome, record)
                await _mark_finalized(conn, batch_id)
        if expired:
            await expire(conn, batch_id)
            raise _expired()
        if found.state == "expired":
            raise _expired()
        view = await _view(conn, caller, batch_id)
        # A new latest Source Revision can make a served Document ready_stale (§7.1); on every
        # call, so a retry after a crash before this line still records the change.
        await refresh(
            conn, sorted({i["document_uid"] for i in view["items"] if "document_uid" in i})
        )
    if all(item["status"] == "rejected" for item in view["items"]):
        return 422, _all_rejected(view["items"])
    return 202, view


async def _finalize_item(
    conn: AsyncConnection,
    caller: Caller,
    settings: SourceSettings,
    intake: Intake,
    batch_id: str,
    index: int,
    uid: str,
    item: dict[str, Any],
    decision: Decision,
    in_place: dict[tuple[int, str], bool],
) -> _Outcome:
    """§6.2 for one declared item, first failure wins."""
    found = await _document_by_uid(conn, uid)
    if (found and found[1]) or (not found and not item["new"]):
        return _Outcome.rejected("DOCUMENT_DELETED")
    if not found and await _live_document(conn, caller, item["document_id"], True):
        return _Outcome.rejected("STALE_DECLARATION")
    if (
        decision.outcome == "deny"
        or not found
        and not await _lock_resource(conn, item["resource_id"])
    ):
        return _Outcome.rejected("RESOURCE_NOT_FOUND")
    if not all(present for (i, _), present in in_place.items() if i == index):
        return _Outcome.rejected("FILES_MISSING")
    adopted = await adoption.current(conn, _main(item)["media_type"])
    if adopted is None:
        return _Outcome.rejected("UNSUPPORTED_FORMAT")
    document = found[0] if found else None
    order = _order(item, document.latest if document else None, settings.ordering)
    if order in ("same", "newer"):
        assert document
        return await _same_content(conn, caller, document, item, batch_id, adopted, order)
    if order:
        return _Outcome.rejected(order)
    if document is None and not await _create_document(conn, caller, uid, item):
        return _Outcome.rejected("STALE_DECLARATION")
    files = [
        f
        | {
            "custody_ref": item["carried"].get(f["path"])
            or f"s3://{intake.store.bucket}/{source_key(uid, batch_id, index, f['sha256'])}"
        }
        for f in item["files"]
    ]
    srv = await _create_revision(conn, caller, uid, item, files)
    await _apply_catalog(conn, uid, item)
    request_id, _ = await create_process_request(
        conn,
        tenant_id=caller.tenant_id,
        document_uid=uid,
        source_revision_id=srv,
        initiator="source",
        priority="normal",
        adopted_version=adopted[0],
        adoption_sequence=adopted[1],
        trace_id=caller.trace_id,
        batch_id=batch_id,
    )
    return _Outcome("queued", request_id=request_id, source_revision_id=srv)


async def view(pool: AsyncConnectionPool, caller: Caller, batch_id: str) -> dict[str, Any]:
    """§5.4: the batch, each item's status following its request; 404 when the Source has no
    such batch."""
    async with pool.connection() as conn:
        return await _view(conn, caller, batch_id)


async def _view(conn: AsyncConnection, caller: Caller, batch_id: str) -> dict[str, Any]:
    found = await _batch(conn, caller, batch_id)
    if found is None:
        raise _not_found()
    expired = found.overdue
    items, counts = [], {}
    for index, document_id, uid, status, request_id, srv, error, request_state in await _items(
        conn, batch_id
    ):
        if request_state and status == "queued":
            status = request_state
        if status == "declared" and (expired or found.state == "expired"):
            status = "expired"
        counts[status] = counts.get(status, 0) + 1
        entry = {
            "index": index,
            "document_id": document_id,
            "document_uid": uid,
            "status": status,
            "request_id": request_id,
            "source_revision_id": srv,
            "error": error,
        }
        items.append({k: v for k, v in entry.items() if v is not None})
    body = {
        "batch_id": batch_id,
        "state": "expired" if expired else found.state,
        "created_at": _at(found.created_at),
        "expires_at": _at(found.expires_at),
        "finalized_at": found.finalized_at and _at(found.finalized_at),
        "counts": counts,
        "items": items,
        "next_page_token": "",  # shortcut: a batch holds at most MAX_ITEMS, one page
    }
    return {k: v for k, v in body.items() if v is not None}


def _not_found() -> Refused:
    return Refused(404, "NOT_FOUND", "NOT_FOUND", "The Source has no such batch.")


def _expired() -> Refused:
    return Refused(409, "FAILED_PRECONDITION", "BATCH_EXPIRED", "The batch expired.")
