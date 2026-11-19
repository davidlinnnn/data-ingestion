"""The upload endpoint (admission spec §5.2, ADR-0012; #194): one file of a declared batch item,
streamed into storage at its custody key (§10) in parts, and completed only once its size, SHA-256
and media type equal the declaration; and the upload cleanup (§6.2).

No lock spans the transfer or the completion. Finalization asks storage before its transaction
(§6.2 step 3), so an upload that completes after it is a missing file there and its object is the
cleanup's (§6.2). The batch is read again just before the upload completes, so one that is
finalized or expires during the transfer is refused and its parts discarded.
"""

import contextlib
import hashlib
import logging
from collections.abc import AsyncIterator, Callable
from datetime import timedelta
from typing import Any

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from kp_admission.batches import MAX_ITEMS, Caller
from kp_admission.errors import Refused
from kp_admission.storage import ObjectStore, StorageUnavailable, source_key

PART = 8 * 2**20  # every part but the last

log = logging.getLogger(__name__)

# The media types the platform detects (§5.2), by their leading bytes.
_SIGNATURES: dict[str, Callable[[bytes], bool]] = {
    "application/pdf": lambda head: head.startswith(b"%PDF-"),
    "image/png": lambda head: head.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda head: head.startswith(b"\xff\xd8\xff"),
    "image/gif": lambda head: head.startswith((b"GIF87a", b"GIF89a")),
    "image/webp": lambda head: head.startswith(b"RIFF") and head[8:12] == b"WEBP",
    "image/tiff": lambda head: head.startswith((b"II*\x00", b"MM\x00*")),
}
_HEAD = 1024


def matches(declared: str, head: bytes) -> bool:
    """Whether a file's first bytes fit its declared media type: a type the platform detects must
    be the one detected; any other stands unless the bytes show a type the platform detects."""
    declared = declared.lower()
    if declared == "application/pdf":  # its header may sit anywhere in the first 1024 bytes
        return b"%PDF-" in head[:_HEAD]
    found = next((t for t, shows in _SIGNATURES.items() if shows(head)), None)
    return found == declared or (found is None and declared not in _SIGNATURES)


async def receive(
    pool: AsyncConnectionPool[Any],
    store: ObjectStore,
    caller: Caller,
    batch_id: str,
    index: int,
    path: str,
    content_length: str | None,
    body: AsyncIterator[bytes],
) -> None:
    """§5.2: returns once the file is staged; Refused for every other outcome."""
    if content_length is None:
        raise Refused(411, "INVALID_ARGUMENT", "LENGTH_REQUIRED", "Content-Length is required.")
    declared, key = await _target(pool, caller, batch_id, index, path)
    if not content_length.isdecimal() or int(content_length) != declared["size"]:
        raise _size_mismatch()
    try:
        upload_id = await store.create_upload(key)
    except StorageUnavailable:
        raise _unavailable() from None
    try:
        etags = await _stream(store, key, upload_id, declared, body)
        await _target(pool, caller, batch_id, index, path)  # still open
        await store.complete_upload(key, upload_id, etags)
    except BaseException as error:
        with contextlib.suppress(StorageUnavailable):  # else the cleanup aborts it (§6.2)
            await store.abort_upload(key, upload_id)
        if isinstance(error, StorageUnavailable):
            raise _unavailable() from None
        raise


async def _stream(
    store: ObjectStore, key: str, upload_id: str, declared: dict, body: AsyncIterator[bytes]
) -> list[str]:
    """Stores the body in parts and returns their ETags once it equals the declaration."""
    digest, received, etags, head = hashlib.sha256(), 0, [], b""
    part = bytearray()

    async def store_part() -> None:
        nonlocal head, part
        if not etags:
            head = bytes(part[:_HEAD])
        etags.append(await store.upload_part(key, upload_id, len(etags) + 1, part))
        part = bytearray()

    async for chunk in body:
        received += len(chunk)
        if received > declared["size"]:
            raise _size_mismatch()
        digest.update(chunk)
        while chunk:
            taken = PART - len(part)
            part += chunk[:taken]
            chunk = chunk[taken:]
            if len(part) == PART:
                await store_part()
    if received != declared["size"]:
        raise _size_mismatch()
    if part or not etags:  # the last part; an empty file is one empty part
        await store_part()
    if digest.hexdigest() != declared["sha256"]:
        raise Refused(
            422, "INVALID_ARGUMENT", "DIGEST_MISMATCH", "The SHA-256 differs from the declaration."
        )
    if not matches(declared["media_type"], head):
        raise Refused(
            422,
            "INVALID_ARGUMENT",
            "MEDIA_TYPE_MISMATCH",
            "The detected media type differs from the declaration.",
        )
    return etags


async def _target(
    pool: AsyncConnectionPool[Any], caller: Caller, batch_id: str, index: int, path: str
) -> tuple[dict[str, Any], str]:
    """The declared file and its key, while the batch is open."""
    row = None
    if 0 <= index < MAX_ITEMS:
        async with pool.connection() as conn:
            row = await (
                await conn.execute(
                    "SELECT b.state, b.state = 'open' AND b.expires_at <= now(), i.document_uid,"
                    " i.declared FROM batch b LEFT JOIN batch_item i"
                    " ON i.batch_id = b.batch_id AND i.index = %s"
                    " WHERE b.batch_id = %s AND b.tenant_id = %s AND b.source_id = %s",
                    (index, batch_id, caller.tenant_id, caller.source_id),
                )
            ).fetchone()
    state, overdue, uid, item = row or (None, False, None, None)
    item = item or {}
    # Only a declared item has `carried`; its uploads are its other files (§5.1).
    uploads = {
        f["path"]: f
        for f in item.get("files", [])
        if "carried" in item and f["path"] not in item["carried"]
    }
    if path not in uploads:
        raise Refused(404, "NOT_FOUND", "NOT_FOUND", "The batch item has no such upload.")
    if state == "finalized":
        raise Refused(409, "FAILED_PRECONDITION", "BATCH_FINALIZED", "The batch is finalized.")
    if state == "expired" or overdue:
        raise Refused(409, "FAILED_PRECONDITION", "BATCH_EXPIRED", "The batch expired.")
    declared = uploads[path]
    assert uid  # given at declaration
    return declared, source_key(uid, batch_id, index, declared["sha256"])


CLEAN_AFTER = timedelta(hours=1)  # uploads in flight when a batch ends have ended by then (§6.2)


async def clean(conn: AsyncConnection, store: ObjectStore) -> tuple[int, int]:
    """§6.2: for each batch finalized or expired CLEAN_AFTER before and not yet cleaned, aborts
    every incomplete upload under its keys and deletes each uploaded object that no Source
    Revision of its document references, then marks the batch cleaned. The keys come from the
    records, never from listing a prefix (document submission guide §6.7). A batch that storage
    fails for is left to the next run, and the others go on. Returns (cleaned, left)."""
    cleaned, left = 0, 0
    for batch_id in await _ended(conn):
        try:
            await _clean_batch(conn, store, batch_id)
            cleaned += 1
        except StorageUnavailable as error:
            left += 1
            cause = type(error.__cause__).__name__
            log.warning(
                "upload cleanup left a batch",
                extra={"correlation": {"batch_id": batch_id, "error": cause}},
            )
    return cleaned, left


async def _clean_batch(conn: AsyncConnection, store: ObjectStore, batch_id: str) -> None:
    for index, uid, item in await _uploading_items(conn, batch_id):
        held = await _referenced(conn, uid)
        for f in item["files"]:
            if f["path"] in item["carried"]:
                continue
            key = source_key(uid, batch_id, index, f["sha256"])
            for upload_id in await store.incomplete_uploads(key):
                await store.abort_upload(key, upload_id)
            if f"s3://{store.bucket}/{key}" not in held:
                await store.delete(key)
    await _mark_cleaned(conn, batch_id)


async def _ended(conn: AsyncConnection) -> list[str]:
    rows = await (
        await conn.execute(
            "SELECT batch_id FROM batch WHERE cleaned_at IS NULL AND ("
            " (state = 'finalized' AND finalized_at <= now() - %(after)s)"
            " OR (state <> 'finalized' AND expires_at <= now() - %(after)s)) ORDER BY batch_id",
            {"after": CLEAN_AFTER},
        )
    ).fetchall()
    return [row[0] for row in rows]


async def _uploading_items(conn: AsyncConnection, batch_id: str) -> list[tuple[int, str, dict]]:
    """(index, document_uid, the item as declared) of each item that was declared, whatever its
    status now: only those had uploads (§5.1)."""
    rows = await (
        await conn.execute(
            "SELECT index, document_uid, declared FROM batch_item WHERE batch_id = %s"
            " ORDER BY index",
            (batch_id,),
        )
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows if "carried" in row[2]]


async def _referenced(conn: AsyncConnection, document_uid: str) -> set[str]:
    """The custody_ref of every file of every Source Revision of the document."""
    rows = await (
        await conn.execute(
            "SELECT files FROM source_revision WHERE document_uid = %s", (document_uid,)
        )
    ).fetchall()
    return {f["custody_ref"] for row in rows for f in row[0]}


async def _mark_cleaned(conn: AsyncConnection, batch_id: str) -> None:
    await conn.execute("UPDATE batch SET cleaned_at = now() WHERE batch_id = %s", (batch_id,))


def _size_mismatch() -> Refused:
    return Refused(
        400, "INVALID_ARGUMENT", "SIZE_MISMATCH", "The size differs from the declaration."
    )


def _unavailable() -> Refused:
    return Refused(503, "UNAVAILABLE", "UNAVAILABLE", "Storage is unavailable; repeat the upload.")
