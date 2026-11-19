"""Status queries (#97, admission spec §5.5–§5.7, §7): a Source's requests and Documents, with
each Document's readiness and attention."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from kp_admission.reports import Pipeline, details
from kp_admission.resources import source_and_key

Readiness = Literal["deleted", "withdrawn", "not_ready", "ready_stale", "ready"]
# A platform failure's message can be an exception's text, which a Source does not see.
PLATFORM_FAILURE = "Processing failed for a platform reason; the platform owner is alerted."

_REQUEST = """
SELECT r.request_id, r.kind, r.state, d.document_id, r.document_uid, r.source_revision_id,
       r.initiator, r.retry_of, r.batch_id, r.created_at, r.updated_at, r.terminal_at, r.error,
       r.trace_id, r.last_report
FROM request r JOIN document d ON d.document_uid = r.document_uid
WHERE r.request_id = %s AND d.tenant_id = %s AND d.source_id = %s
  AND (r.terminal_at IS NULL OR r.terminal_at > now() - interval '30 days')
"""


async def request(
    conn: AsyncConnection, tenant_id: str, source_id: str, request_id: str
) -> dict[str, Any] | None:
    """The request (§5.5) when it is of one of the Source's Documents, until 30 days after its
    terminal outcome (§11); an active request never expires."""
    cursor = conn.cursor(row_factory=dict_row)
    row = await (await cursor.execute(_REQUEST, (request_id, tenant_id, source_id))).fetchone()
    if row is None:
        return None
    row["details"] = details(row.pop("last_report"))
    row["error"] = _shown(row["error"])
    return {k: _json(v) for k, v in row.items()}


def _shown(error: dict[str, Any] | None) -> dict[str, Any] | None:
    """The error block as a Source sees it: a failure whose cause is not the source carries
    PLATFORM_FAILURE as its message."""
    if error is None or (error.get("metadata") or {}).get("cause") == "source":
        return error
    return error | {"message": PLATFORM_FAILURE}


# The latest Source Revision and its newest request that is not a platform refresh, which never
# affects readiness or attention (§7.2).
_DOCUMENTS = """
SELECT d.document_uid, d.document_id, d.resource_id, d.title, d.source_url, d.metadata,
       d.deleted_at, d.created_at, s.source_revision_id, s.source_version, s.outcome,
       r.request_id, r.state, r.error, r.terminal_at, r.reported_at, o.dispatched_at
FROM document d
LEFT JOIN source_revision s ON s.source_revision_id = d.latest_source_revision_id
LEFT JOIN LATERAL (
    SELECT request_id, state, error, terminal_at, reported_at FROM request
    WHERE document_uid = d.document_uid AND source_revision_id = s.source_revision_id
      AND kind = 'process' AND initiator <> 'platform'
    ORDER BY created_at DESC, request_id DESC LIMIT 1
) r ON true
LEFT JOIN outbox o ON o.request_id = r.request_id
WHERE d.tenant_id = %(tenant_id)s AND d.source_id = %(source_id)s AND {tail}
"""

_PROJECTIONS = "SELECT projections FROM source WHERE tenant_id = %s AND source_id = %s"


async def document(
    conn: AsyncConnection,
    tenant_id: str,
    source_id: str,
    document_id: str,
    canonical: Pipeline | None,
) -> dict[str, Any] | None:
    """The Source's Document (§5.6): its current generation, else the one deleted last."""
    tail = "d.document_id = %(document_id)s ORDER BY d.deleted_at IS NOT NULL, d.deleted_at DESC"
    params = {"tenant_id": tenant_id, "source_id": source_id, "document_id": document_id}
    rows = await _rows(conn, tail + " LIMIT 1", params)
    if not rows:
        return None
    return _view(rows[0], await _projections(conn, tenant_id, source_id), canonical)


async def documents(
    conn: AsyncConnection,
    tenant_id: str,
    source_id: str,
    canonical: Pipeline | None,
    *,
    page_size: int,
    page_token: str | None = None,
    resource_id: str | None = None,
    readiness: str | None = None,
    projection: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """One page of the Source's Documents (§5.7), deleted ones within retention included, in
    (document_id, document_uid) order, and the next page's token, empty on the last page. It
    reads page_size Documents after page_token, in Resource `resource_id` (the full identifier)
    when given, then keeps those of `readiness` and whose serving lists `projection`, so a page
    may hold fewer. ValueError for a page_token this list did not return."""
    tail = "(d.deleted_at IS NULL OR d.deleted_at > now() - interval '30 days')"
    params: dict[str, Any] = {"tenant_id": tenant_id, "source_id": source_id}
    if resource_id is not None:
        tail += " AND d.resource_id = %(resource_id)s"
        params["resource_id"] = resource_id
    if page_token:
        document_id, _, uid = page_token.partition("/")  # a document_id holds no "/"
        if not (document_id and uid):
            raise ValueError(f"not a page token: {page_token!r}")
        tail += " AND (d.document_id, d.document_uid) > (%(after_id)s, %(after_uid)s)"
        params["after_id"], params["after_uid"] = document_id, uid
    params["limit"] = page_size + 1
    rows = await _rows(
        conn, tail + " ORDER BY d.document_id, d.document_uid LIMIT %(limit)s", params
    )
    more, rows = len(rows) > page_size, rows[:page_size]
    required = await _projections(conn, tenant_id, source_id)
    entries = []
    for row in rows:
        view = _view(row, required, canonical)
        if readiness not in (None, view["readiness"]) or (
            projection is not None and all(s["projection"] != projection for s in view["serving"])
        ):
            continue
        entries.append(
            {k: view[k] for k in ("document_id", "document_uid", "readiness", "metadata")}
            | {"latest": {"source_version": view["latest"]["source_version"]}}
        )
    token = f"{rows[-1]['document_id']}/{rows[-1]['document_uid']}" if more else ""
    return entries, token


async def _rows(conn: AsyncConnection, tail: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """The rows of _DOCUMENTS with `tail` after its own conditions: more, and the order."""
    cursor = conn.cursor(row_factory=dict_row)
    return await (await cursor.execute(_DOCUMENTS.format(tail=tail), params)).fetchall()  # type: ignore[arg-type]


async def _projections(conn: AsyncConnection, tenant_id: str, source_id: str) -> list[str]:
    row = await (await conn.execute(_PROJECTIONS, (tenant_id, source_id))).fetchone()
    return row[0] if row else []


def readiness(
    deleted: bool, required: Sequence[str], serving: Mapping[str, str], latest: str | None
) -> Readiness:
    """§7.1, first match, given which Source Revision each projection serves. withdrawn has no
    source in the pilot (#56). A Document with no required projection is not_ready: nothing
    serves it."""
    if deleted:
        return "deleted"
    if not required or any(p not in serving for p in required):
        return "not_ready"
    if any(serving[p] != latest for p in required):
        return "ready_stale"
    return "ready"


def attention(row: Mapping[str, Any], canonical: Pipeline | None, now: datetime) -> list[dict]:
    """§7.2 from canonical processing: the latest Source Revision rejected, failed with no active
    request, or its active request past the pipeline's deadline."""
    version, error, outcome = row["source_version"], row["error"] or {}, row["outcome"]
    active = row["state"] in ("queued", "processing")
    found: list[dict[str, Any]] = []
    if outcome == "rejected":
        found.append(
            {"kind": "source_revision_rejected", "action_owner": "source",
             "source_version": version, "message": error.get("message", ""),
             "since": _json(row["terminal_at"])}
        )  # fmt: skip
    if outcome == "failed" and not active:
        found.append(
            {"kind": "processing_failed", "action_owner": "platform", "track": "canonical",
             "source_version": version, "message": PLATFORM_FAILURE,
             "since": _json(row["terminal_at"])}
        )  # fmt: skip
    if active and canonical:
        if row["reported_at"]:
            deadline = row["reported_at"] + timedelta(seconds=canonical.update_interval_s)
        elif row["dispatched_at"]:
            deadline = row["dispatched_at"] + timedelta(seconds=canonical.start_deadline_s)
        else:
            deadline = None  # not dispatched yet: admission's own backlog
        if deadline and deadline < now:
            found.append(
                {"kind": "progress_stalled", "action_owner": "platform", "source_version": version,
                 "message": "Canonical processing has not reported within its deadline.",
                 "since": _json(deadline)}
            )  # fmt: skip
    return found


def _view(row: dict[str, Any], required: list[str], canonical: Pipeline | None) -> dict[str, Any]:
    serving: dict[str, str] = {}  # serving facts arrive with #252
    state = readiness(row["deleted_at"] is not None, required, serving, row["source_revision_id"])
    # shortcut: since holds while nothing serves the Document; #252 records when readiness changes.
    since = row["deleted_at"] or row["created_at"]
    return {
        "document_id": row["document_id"],
        "document_uid": row["document_uid"],
        "resource_id": source_and_key(row["resource_id"])[1],
        "title": row["title"],
        "source_url": row["source_url"],
        "metadata": row["metadata"],
        "readiness": state,
        "since": _json(since),
        "latest": {
            "source_revision_id": row["source_revision_id"],
            "source_version": row["source_version"],
            "request_id": row["request_id"],
        },
        "serving": [],
        "attention": attention(row, canonical, datetime.now(UTC)) if state != "deleted" else [],
        "deleted_at": _json(row["deleted_at"]),
    }


def _json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return value
