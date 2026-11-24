"""Exact-revision reads of Canonical content (#268, admission spec §5.9): the content object of one
Canonical Revision, and one artifact its manifest lists (content spec §4), for any Document's
revision, current or not (ADR-0003).

Each read takes one revision record, with its Document's state and its Source Revision's time, and
resolves every object key from that record, never from the caller's uid. A purged revision
answers CONTENT_NOT_RETAINED and a deleted Document DOCUMENT_DELETED, before any storage read.

Metrics:
- `kp_canonical_reads_total` (count) by `kind` (content, artifact) and `result`: served,
  not_found, deleted, not_retained, missing (the record names an object storage says is absent:
  lost data, #57 scope 7), unavailable (storage did not answer) or interrupted (the stream
  stopped before its end).
- `kp_canonical_read_bytes_total` (count) of the bytes sent, by `kind`.
"""

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from prometheus_client import Counter
from psycopg_pool import AsyncConnectionPool

from kp_admission.errors import Refused
from kp_admission.storage import ObjectMissing, ObjectStore, StorageUnavailable

Kind = Literal["content", "artifact"]

# Content spec §4: no bucket, no prefix, no `.` or `..` segment.
REFERENCE = re.compile(r"[0-9a-f]{64}(/[A-Za-z0-9_-][A-Za-z0-9._-]*)+")
MISSING_RETRY_S = 3600  # nothing repairs a lost object in the pilot: the Source resends

reads = Counter("kp_canonical_reads", "exact-revision content reads", ["kind", "result"])
sent = Counter("kp_canonical_read_bytes", "bytes the content reads sent", ["kind"])
log = logging.getLogger(__name__)

_REVISION = """
SELECT c.document_uid, c.content_ref, c.content_sha256, c.content_size, c.purged_at,
       d.deleted_at, s.created_at
FROM canonical_revision c
JOIN document d ON d.document_uid = c.document_uid
JOIN source_revision s ON s.source_revision_id = c.source_revision_id
WHERE c.canonical_revision_id = %s AND c.document_uid = %s
"""


@dataclass(frozen=True)
class Served:
    """An object to send: its bytes stream from storage after the response starts."""

    media_type: str
    sha256: str
    size: int
    source_revision_created_at: datetime
    body: AsyncIterator[bytes]


@dataclass(frozen=True)
class _Read:
    kind: Kind
    document_uid: str
    canonical_revision_id: str

    def done(self, result: str, count: int = 0) -> None:
        reads.labels(self.kind, result).inc()
        correlation = {
            "document_uid": self.document_uid,
            "canonical_revision_id": self.canonical_revision_id,
            "kind": self.kind,
            "bytes": count,
            "result": result,
        }
        log.info("canonical read %s", result, extra={"correlation": correlation})

    def refuse(self, result: str, refused: Refused) -> Refused:
        self.done(result)
        return refused


async def read_content(
    pool: AsyncConnectionPool[Any], store: ObjectStore, document_uid: str, crv: str
) -> Served:
    """The revision's content object, as accepted."""
    read = _Read("content", document_uid, crv)
    record = await _record(pool, read)
    body = await _open(store, read, record["content_ref"])
    return Served(
        "application/json",
        record["content_sha256"],
        record["content_size"],
        record["created_at"],
        _counted(read, body),
    )


async def read_artifact(
    pool: AsyncConnectionPool[Any], store: ObjectStore, document_uid: str, crv: str, reference: str
) -> Served:
    """One artifact the revision's manifest lists, with the manifest's media type and digest."""
    read = _Read("artifact", document_uid, crv)
    if not REFERENCE.fullmatch(reference):
        raise read.refuse("not_found", _NO_ARTIFACT)
    record = await _record(pool, read)
    # shortcut: every artifact read reads and parses the whole content object (up to 1.1 MB in
    # #81's corpus); cache manifests by revision if #99 measures it costly.
    content = await _whole(read, await _open(store, read, record["content_ref"]))
    manifest = await asyncio.to_thread(_manifest, content)
    if (entry := manifest.get(reference)) is None:
        raise read.refuse("not_found", _NO_ARTIFACT)
    body = await _open(store, read, f"documents/{record['document_uid']}/items/{reference}")
    return Served(
        entry["media_type"],
        entry["sha256"],
        entry["size"],
        record["created_at"],
        _counted(read, body),
    )


async def _record(pool: AsyncConnectionPool[Any], read: _Read) -> dict[str, Any]:
    async with pool.connection() as conn:
        cursor = await conn.execute(_REVISION, (read.canonical_revision_id, read.document_uid))
        row = await cursor.fetchone()
        names = [column.name for column in cursor.description or []]
    if row is None:
        raise read.refuse(
            "not_found",
            Refused(404, "NOT_FOUND", "REVISION_NOT_FOUND", "The Document has no such revision."),
        )
    record = dict(zip(names, row, strict=True))
    if record["purged_at"] is not None:  # first: a purged Document is a deleted one too
        raise read.refuse(
            "not_retained",
            Refused(
                410,
                "FAILED_PRECONDITION",
                "CONTENT_NOT_RETAINED",
                "The revision's content is no longer retained.",
            ),
        )
    if record["deleted_at"] is not None:
        raise read.refuse(
            "deleted",
            Refused(410, "FAILED_PRECONDITION", "DOCUMENT_DELETED", "The Document is deleted."),
        )
    return record


async def _open(store: ObjectStore, read: _Read, key: str) -> AsyncIterator[bytes]:
    try:
        return await store.open(key)
    except ObjectMissing:
        raise read.refuse("missing", _MISSING) from None
    except StorageUnavailable:
        raise read.refuse("unavailable", _UNAVAILABLE) from None


async def _whole(read: _Read, body: AsyncIterator[bytes]) -> bytes:
    try:
        return b"".join([chunk async for chunk in body])
    except StorageUnavailable:
        raise read.refuse("unavailable", _UNAVAILABLE) from None


def _manifest(content: bytes) -> dict[str, dict[str, Any]]:
    return {entry["ref"]: entry for entry in json.loads(content)["artifacts"]}


async def _counted(read: _Read, body: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """`body`, counting what it sends; logs once when the stream ends or stops."""
    count, result = 0, "interrupted"
    try:
        async for chunk in body:
            count += len(chunk)
            sent.labels(read.kind).inc(len(chunk))
            yield chunk
        result = "served"
    finally:
        read.done(result, count)


_MISSING = Refused(
    503,
    "UNAVAILABLE",
    "CONTENT_MISSING",
    "Storage no longer holds an object the revision records.",
    retry_after=MISSING_RETRY_S,
)
_NO_ARTIFACT = Refused(
    404, "NOT_FOUND", "ARTIFACT_NOT_FOUND", "The revision's manifest lists no such artifact."
)
_UNAVAILABLE = Refused(503, "UNAVAILABLE", "STORAGE_UNAVAILABLE", "Storage did not answer; retry.")
