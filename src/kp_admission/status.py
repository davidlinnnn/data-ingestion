"""Status queries (#97, admission spec §5.5–§5.7, §7): a Source's requests and Documents, with
each Document's readiness, serving and attention, from the serving-fact mirror (#252)."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from kp_admission import feed
from kp_admission import serving as mirror
from kp_admission.reports import Pipeline, details
from kp_admission.resources import source_and_key

Readiness = Literal["deleted", "withdrawn", "not_ready", "ready_stale", "ready"]
# A platform failure's message can be an exception's text, which a Source does not see.
PLATFORM_FAILURE = "Processing failed for a platform reason; the platform owner is alerted."
PAGE = 500  # Documents per page of a refresh fan-out

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
       d.deleted_at, d.readiness_since, s.source_revision_id, s.source_version, s.outcome,
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


async def document(
    conn: AsyncConnection,
    tenant_id: str,
    source_id: str,
    document_id: str,
    pipelines: Mapping[str, Pipeline],
) -> dict[str, Any] | None:
    """The Source's Document (§5.6): its current generation, else the one deleted last.
    `pipelines` are the registered ones by track."""
    tail = "d.document_id = %(document_id)s ORDER BY d.deleted_at IS NOT NULL, d.deleted_at DESC"
    params = {"tenant_id": tenant_id, "source_id": source_id, "document_id": document_id}
    rows = await _rows(conn, tail + " LIMIT 1", params)
    if not rows:
        return None
    row, uid = rows[0], rows[0]["document_uid"]
    required = await mirror.required(conn, tenant_id, source_id)
    served = (await mirror.served(conn, [uid])).get(uid, {})
    projected = _projected(
        row,
        required,
        served,
        (await mirror.attempts(conn, [uid])).get(uid, {}),
        await mirror.serving_builds(conn),
        pipelines,
        datetime.now(UTC),
    )
    return _view(row, required, served, pipelines.get("canonical"), projected)


async def documents(
    conn: AsyncConnection,
    tenant_id: str,
    source_id: str,
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
    required = await mirror.required(conn, tenant_id, source_id)
    served = await mirror.served(conn, [row["document_uid"] for row in rows])
    entries = []
    for row in rows:
        view = _view(row, required, served.get(row["document_uid"], {}), None)
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


_STORED = """
SELECT d.tenant_id, d.source_id, d.deleted_at IS NOT NULL, d.latest_source_revision_id,
       d.readiness
FROM document d WHERE d.document_uid = %s FOR UPDATE
"""


async def refresh(conn: AsyncConnection, uids: Sequence[str]) -> None:
    """Records each Document's readiness and, when it changed, the moment: `since` (§5.6). Each
    in a transaction of its own, so a large fan-out holds no long transaction, and with the
    Document locked, so two refreshes of it record in the order they read. A report or state
    change that can move a Document's readiness calls it after its own transaction."""
    for uid in uids:
        async with conn.transaction():
            row = await (await conn.execute(_STORED, (uid,))).fetchone()
            if row is None:
                continue
            tenant_id, source_id, deleted, latest, stored = row
            required = await mirror.required(conn, tenant_id, source_id)
            served = (await mirror.served(conn, [uid])).get(uid, {})
            state = _readiness(deleted, required, served, latest)
            if state != stored:
                await conn.execute(
                    "UPDATE document SET readiness = %s, readiness_since = now()"
                    " WHERE document_uid = %s",
                    (state, uid),
                )


async def refresh_builds(conn: AsyncConnection, projection: str, builds: Sequence[str]) -> None:
    """refresh, in pages, for every Document the projection's Builds hold a fact of."""
    after = ""
    while page := await mirror.documents(conn, projection, builds, after, PAGE):
        await refresh(conn, page)
        after = page[-1]


async def refresh_source(conn: AsyncConnection, source_id: str) -> None:
    """refresh, in pages, for every Document of the Source not deleted: after its Knowledge
    Profile changed or a projection reported its backfill."""
    after = None
    while page := await feed.list_documents(conn, source_id, after, PAGE):
        await refresh(conn, page)
        after = page[-1]


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
                {"kind": "progress_stalled", "action_owner": "platform", "track": "canonical",
                 "source_version": version,
                 "message": "Canonical processing has not reported within its deadline.",
                 "since": _json(deadline)}
            )  # fmt: skip
    return found


def _projected(
    row: Mapping[str, Any],
    required: Mapping[str, bool],
    served: Mapping[str, mirror.Served],
    attempts: Mapping[str, mirror.Attempt],
    live: Mapping[str, datetime],
    pipelines: Mapping[str, Pipeline],
    now: datetime,
) -> list[dict[str, Any]]:
    """§7.2 from the required projections (#252). Of each, only the serving Build's attempt for
    the Document's current Canonical Revision counts (DR C4): failed or skipped for the latest
    Source Revision while that is not served, or past its deadline; and the serving Build without
    liveness, no report within the pipeline's update interval, is status_unverified."""
    latest, version = row["source_revision_id"], row["source_version"]
    found: list[dict[str, Any]] = []
    for projection in required:
        pipeline = pipelines.get(projection)
        attempt = attempts.get(projection)
        base = {"action_owner": "platform", "track": projection, "source_version": version}
        if attempt and pipeline:
            last, at = attempt.last_report, attempt.reported_at
            open_ = attempt.source_revision_id == latest and (
                projection not in served or served[projection].source_revision_id != latest
            )
            error = last["error"] or {}
            if last["state"] == "failed" and open_:
                found.append(
                    base | {"kind": "processing_failed", "message": PLATFORM_FAILURE,
                            "since": _json(at)}
                )  # fmt: skip
            elif last["state"] == "skipped" and open_:
                by_source = (error.get("metadata") or {}).get("cause") == "source"
                found.append(
                    base | {"kind": "skipped", "since": _json(at),
                            "action_owner": "source" if by_source else "platform",
                            "message": error["message"] if by_source else PLATFORM_FAILURE}
                )  # fmt: skip
            elif last["state"] in ("pending", "running"):
                wait = pipeline.start_deadline_s if last["state"] == "pending" else None
                deadline = at + timedelta(seconds=wait or pipeline.update_interval_s)
                if deadline < now:
                    found.append(
                        base | {"kind": "progress_stalled",
                                "message": "The projection has not reported within its deadline.",
                                "since": _json(deadline)}
                    )  # fmt: skip
        if pipeline and projection in live:
            deadline = live[projection] + timedelta(seconds=pipeline.update_interval_s)
            if deadline < now:
                found.append(
                    base | {"kind": "status_unverified",
                            "message": "The projection's serving Build has stopped reporting.",
                            "since": _json(deadline)}
                )  # fmt: skip
    return found


def _readiness(
    deleted: bool, required: Mapping[str, bool], served: Mapping[str, mirror.Served], latest: Any
) -> Readiness:
    """§7.1 over the projections that count (DR B1)."""
    counted = [p for p, counts in required.items() if counts]
    by_revision = {p: s.source_revision_id for p, s in served.items()}
    return readiness(deleted, counted, by_revision, latest)


def _serving(
    required: Mapping[str, bool], served: Mapping[str, mirror.Served], latest: Any
) -> list[dict[str, Any]]:
    """A row per required projection that serves the Document (DR B1): `building` while its
    backfill does not count, else `ready` when it serves the latest Source Revision, `stale`."""
    rows = []
    for projection, counts in required.items():
        if (s := served.get(projection)) is None:
            continue
        state = "building" if not counts else "ready" if s.source_revision_id == latest else "stale"
        rows.append(
            {"projection": projection, "state": state,
             "source_revision_id": s.source_revision_id, "source_version": s.source_version}
        )  # fmt: skip
    return rows


def _view(
    row: dict[str, Any],
    required: Mapping[str, bool],
    served: Mapping[str, mirror.Served],
    canonical: Pipeline | None,
    projected: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """The Document's view (§5.6). A list (§5.7) shows no attention and passes none."""
    latest = row["source_revision_id"]
    state = _readiness(row["deleted_at"] is not None, required, served, latest)
    since = row["deleted_at"] or row["readiness_since"]
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
        "serving": _serving(required, served, latest),
        "attention": []
        if state == "deleted"
        else [*attention(row, canonical, datetime.now(UTC)), *projected],
        "deleted_at": _json(row["deleted_at"]),
    }


def _json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return value
