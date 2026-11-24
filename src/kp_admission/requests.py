"""Process requests, their outbox rows, their outcomes and Canonical Acceptance (admission spec
§3, §9)."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from prometheus_client import Counter
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, StrictInt

from kp_admission import adoption, feed

_INSERT = """
INSERT INTO request (request_id, tenant_id, kind, document_uid, source_revision_id, state,
                     initiator, retry_of, batch_id, priority, adopted_version, adoption_sequence,
                     trace_id)
VALUES (%(request_id)s, %(tenant_id)s, 'process', %(document_uid)s, %(source_revision_id)s,
        'queued', %(initiator)s, %(retry_of)s, %(batch_id)s, %(priority)s, %(adopted_version)s,
        %(adoption_sequence)s, %(trace_id)s)
ON CONFLICT (document_uid, source_revision_id)
    WHERE kind = 'process' AND state IN ('queued', 'processing') DO NOTHING
RETURNING request_id
"""

_ACTIVE = """
SELECT request_id FROM request
WHERE document_uid = %(document_uid)s AND source_revision_id = %(source_revision_id)s
  AND kind = 'process' AND state IN ('queued', 'processing')
"""


async def create_process_request(
    conn: AsyncConnection,
    *,
    tenant_id: str,
    document_uid: str,
    source_revision_id: str,
    initiator: Literal["source", "operator", "platform"],
    priority: Literal["normal", "low"],
    adopted_version: str,
    adoption_sequence: int,
    trace_id: str,
    batch_id: str | None = None,
    retry_of: str | None = None,
) -> tuple[str, bool]:
    """Creates a queued process request and its outbox row in one transaction, or in a savepoint
    when the caller has one open, and returns (request_id, True). When the Source Revision already
    has a queued or processing request, it creates nothing and returns (that request_id, False)."""
    params = {
        "tenant_id": tenant_id,
        "document_uid": document_uid,
        "source_revision_id": source_revision_id,
        "initiator": initiator,
        "priority": priority,
        "adopted_version": adopted_version,
        "adoption_sequence": adoption_sequence,
        "trace_id": trace_id,
        "batch_id": batch_id,
        "retry_of": retry_of,
    }
    async with conn.transaction():
        while True:
            params["request_id"] = f"req_{uuid.uuid4().hex}"
            if await (await conn.execute(_INSERT, params)).fetchone():
                await conn.execute(
                    "INSERT INTO outbox (request_id, tenant_id) VALUES (%s, %s)",
                    (params["request_id"], tenant_id),
                )
                return params["request_id"], True
            if active := await (await conn.execute(_ACTIVE, params)).fetchone():
                return active[0], False
            # The active request ended between the two statements: insert again.


_END = """
UPDATE request SET state = %s, terminal_at = %s, error = %s, updated_at = now()
WHERE request_id = %s AND kind = 'process' AND state IN ('queued', 'processing')
RETURNING initiator, source_revision_id, document_uid, adopted_version, adoption_sequence
"""

# An accepted revision stays accepted: a later run that fails does not undo the acceptance.
_OUTCOME = """
UPDATE source_revision SET outcome = %s WHERE source_revision_id = %s AND outcome <> 'accepted'
"""

# Every success writes the Document, accepted or not: the conflict a concurrent deletion meets on
# MongoDB.
_DOCUMENT = """
UPDATE document SET acceptance_version = acceptance_version + 1 WHERE document_uid = %s
RETURNING tenant_id, source_id, deleted_at IS NOT NULL, current_source_revision_sequence,
          current_adoption_sequence, current_adopted_version
"""

_REVISION = """
INSERT INTO canonical_revision (canonical_revision_id, tenant_id, document_uid, source_revision_id,
                                request_id, adopted_version, adoption_sequence, content_ref,
                                content_sha256, content_size)
VALUES (%(crv)s, %(tenant_id)s, %(uid)s, %(srv)s, %(request_id)s, %(adopted_version)s,
        %(adoption_sequence)s, %(ref)s, %(sha256)s, %(size)s)
"""

_CURRENT = """
UPDATE document SET current_source_revision_id = %(srv)s, current_canonical_revision_id = %(crv)s,
                    current_source_revision_sequence = %(sequence)s,
                    current_adoption_sequence = %(adoption_sequence)s,
                    current_adopted_version = %(adopted_version)s
WHERE document_uid = %(uid)s
"""

ERROR_DOMAIN = "admission.knowledge-platform"

# A request of a version withdrawn before it ended (#57 B6): no run of it is accepted, so it ends
# and the scan reruns its revision under the adopted version at once.
VERSION_WITHDRAWN = {
    "domain": ERROR_DOMAIN,
    "reason": "VERSION_WITHDRAWN",
    "message": "The Processing Profile version was withdrawn before the request ended.",
    "retryable": True,
    "metadata": {"cause": "platform"},
}

not_accepted = Counter(
    "kp_admission_not_accepted", "successful process requests that formed no acceptance", ["reason"]
)
log = logging.getLogger(__name__)


class Candidate(BaseModel, frozen=True, extra="forbid"):
    """The Canonical content object a successful run hands over (spec §7.3)."""

    ref: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: StrictInt = Field(ge=0)


async def lock_document(conn: AsyncConnection, request_id: str) -> None:
    """Locks the request's Document: the first lock of a transaction that ends a request, before
    the request's own (spec §3)."""
    await conn.execute(
        "SELECT 1 FROM document WHERE document_uid ="
        " (SELECT document_uid FROM request WHERE request_id = %s) FOR UPDATE",
        (request_id,),
    )


async def record_outcome(
    conn: AsyncConnection,
    request_id: str,
    state: Literal["succeeded", "failed"],
    error: dict[str, Any] | None,
    terminal_at: datetime | None,
    candidate: Candidate | None = None,
) -> bool:
    """Ends a queued or processing process request with `state` and `error`, the status report's or
    the workflow's error block, in one transaction, and returns whether it did; an ended request
    keeps its outcome. Unless the request is a platform refresh (§3), its Source Revision's outcome
    follows: succeeded makes it pending; failed with error.metadata.cause "source" makes it
    rejected, any other failure failed. An accepted revision keeps its outcome.

    A success with `candidate` is Canonical Acceptance (§3), unless the Document is deleted, the
    candidate's ref is not the revision's own key, or the request's version is withdrawn for its
    media type: the Canonical Revision is recorded, its
    Source Revision becomes accepted, and it becomes the Document's current one, with a
    current_revision_changed event, when it is of a newer Source Revision or, of the same one,
    under a higher adoption sequence."""
    async with conn.transaction():
        await lock_document(conn, request_id)
        ended = await (
            await conn.execute(_END, (state, terminal_at, error and Jsonb(error), request_id))
        ).fetchone()
        if ended is None:
            return False
        initiator, srv, uid, adopted_version, adoption_sequence = ended
        # A withdrawal says nothing of the revision, as a discarded result does not (#251).
        if initiator != "platform" and not _withdrawn(error):
            await conn.execute(_OUTCOME, (revision_outcome(state, error), srv))
        if state == "succeeded":
            await _accept(
                conn, request_id, initiator, srv, uid, adopted_version, adoption_sequence, candidate
            )
    return True


async def _accept(
    conn: AsyncConnection,
    request_id: str,
    initiator: str,
    srv: str,
    uid: str,
    adopted_version: str,
    adoption_sequence: int,
    candidate: Candidate | None,
) -> None:
    document = await (await conn.execute(_DOCUMENT, (uid,))).fetchone()
    assert document
    tenant_id, source_id, deleted, current_sequence, current_adoption, current_version = document
    revision = await (
        await conn.execute(
            "SELECT sequence, files FROM source_revision WHERE source_revision_id = %s", (srv,)
        )
    ).fetchone()
    assert revision
    sequence, files = revision
    main = next(f for f in files if f["role"] == "main")
    withdrawn = await adoption.withdrawn(conn, main["media_type"])
    crv = f"crv_{request_id.removeprefix('req_')}"
    reason = None
    if deleted:  # a late result does not bring a deleted Document back (§8)
        reason = "document_deleted"
    elif candidate is None:
        reason = "no_candidate"
    elif candidate.ref != f"documents/{uid}/revisions/{crv}.json":
        reason = "ref_mismatch"  # reads follow ref: it must not name another Document's object
    elif adopted_version in withdrawn:
        reason = "version_withdrawn"
    if reason or candidate is None:
        not_accepted.labels(reason).inc()
        log.warning(
            "no canonical acceptance: %s",
            reason,
            extra={"correlation": {"request_id": request_id, "document_uid": uid,
                                   "adopted_version": adopted_version, "reason": reason}},
        )  # fmt: skip
        return
    params = {
        "crv": crv,
        "tenant_id": tenant_id,
        "uid": uid,
        "srv": srv,
        "request_id": request_id,
        "sequence": sequence,
        "adopted_version": adopted_version,
        "adoption_sequence": adoption_sequence,
    } | candidate.model_dump()
    await conn.execute(_REVISION, params)
    await conn.execute(
        "UPDATE source_revision SET outcome = 'accepted' WHERE source_revision_id = %s", (srv,)
    )
    if current_sequence is not None and (sequence, adoption_sequence) <= (
        current_sequence,
        current_adoption,
    ):
        return  # an older or equal candidate: recorded, the current one stays
    await conn.execute(_CURRENT, params)
    # Replacing a withdrawn version's revision is a canonical rollback (DR §3), not a refresh.
    rollback = current_version in withdrawn
    await feed.append(
        conn,
        "current_revision_changed",
        tenant_id=tenant_id,
        source_id=source_id,
        document_uid=uid,
        priority="background" if initiator == "platform" and not rollback else "normal",
    )


def _withdrawn(error: dict[str, Any] | None) -> bool:
    return bool(error) and (error["domain"], error["reason"]) == (ERROR_DOMAIN, "VERSION_WITHDRAWN")


async def end_withdrawn(conn: AsyncConnection, request_id: str) -> bool:
    """Ends a queued or processing request whose version is withdrawn, failed with
    VERSION_WITHDRAWN, leaving its Source Revision's outcome; False when it had ended."""
    error = VERSION_WITHDRAWN | {
        "occurred_at": datetime.now(UTC).isoformat().replace("+00:00", "Z")
    }
    return await record_outcome(conn, request_id, "failed", error, datetime.now(UTC))


def revision_outcome(state: str, error: dict[str, Any] | None) -> str:
    if state == "succeeded":
        return "pending"
    cause = ((error or {}).get("metadata") or {}).get("cause")
    return "rejected" if cause == "source" else "failed"
