"""The reference projection's query side (#279): keyword search over the store of its serving
Build, limited to the Resources the user may read (#87 C2) and answering with the result
contract of canonical consumption DR E4. A second role: it never runs in the reader's process
(DR A7), and it only reads the store.

- **The user** comes from the bearer token, by its SHA-256 in `users`; a user id the caller
  names is never taken (authorization guide §5.1). An agent application that asks for the user
  names itself in `X-Actor-Id`, sent on as `actor` (§5.9).
- **The pre-filter** is every page of `list_resources`, read for each query and never cached
  (§5.4, §5.8). Without a decision (§5.6) the answer is `503` with no content. The stored
  `resource_id` is compared as an opaque string; nothing asks the platform about a Document at
  query time: removal is the reader's cleanup (ADR-0014).
- **The search** is PostgreSQL full-text search of each entry's whole Markdown; ranking is not a
  goal (`search` is the one place to change it).
- **A result** carries `document_uid`, `resource_id`, the served Source and Canonical Revisions,
  the Source Revision's time, `stale` and a snippet. `stale` is what this projection knows at
  query time: the reader has queued an event of the Document that no run has finished, such
  as a newer revision being written. An event the reader has not read yet does not show.
  `latest_only` leaves stale results out.
- **The snippet** quotes the entry's `cited` text, which withholds every block a `disputed`
  enrichment targets (LaTeX of a formula, a table's values); the search still matches them.

The query is in a POST body, so no access log holds it. Log lines carry the user id, counts,
status codes, reason codes and trace ids; never the query or content. The metric
`kp_projection_queries_total{outcome}` counts queries `served`, `unauthenticated` and
`no_decision`; latency and status codes are the mesh's.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

from kp_sdk import PlatformError
from kp_sdk.projection import ProjectionClient

log = logging.getLogger(__name__)

FORWARDED = ("traceparent", "x-request-id")
queries = Counter("kp_projection_queries", "search queries by outcome", ["outcome"])


class Search(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    latest_only: bool = False
    limit: int = Field(default=10, ge=1, le=100)


class Hit(BaseModel):
    document_uid: str
    resource_id: str
    source_revision_id: str
    source_revision_created_at: datetime | None  # null until the platform's state gives it (#268)
    canonical_revision_id: str
    # E4 leaves the name to #76; this projection's meaning is in the module docstring.
    stale: bool
    snippet: str


class Results(BaseModel):
    results: list[Hit]


def app(sdk: ProjectionClient, pool: AsyncConnectionPool[Any], users: dict[str, str]) -> FastAPI:
    """The query API over the store in `pool`, asking the authz API through `sdk`; `users` maps
    the SHA-256 hex of each user's bearer token to the user id."""
    api = FastAPI(title="Reference projection query")

    @api.post("/v1/entries:search", response_model=Results)
    async def search_entries(body: Search, request: Request) -> Results | JSONResponse:
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        user = users.get(hashlib.sha256(token.encode()).hexdigest()) if token else None
        if user is None:
            queries.labels("unauthenticated").inc()
            return _error(401, "UNAUTHENTICATED", "A registered bearer token is required.")
        forwarded = {name: value for name in FORWARDED if (value := request.headers.get(name))}
        try:
            readable = await sdk.readable(user, request.headers.get("x-actor-id"), forwarded)
        except PlatformError as error:
            queries.labels("no_decision").inc()
            log.warning(
                "no decision: user=%s status=%s reason=%s trace_id=%s",
                user,
                error.status,
                error.reason,
                error.trace_id,
            )
            return _error(503, "UNAVAILABLE", "No decision could be made.")
        hits = await search(pool, body.query, readable, body.latest_only, body.limit)
        queries.labels("served").inc()
        log.info("search served: user=%s resources=%s hits=%s", user, len(readable), len(hits))
        return Results(results=hits)

    return api


async def search(
    pool: AsyncConnectionPool[Any], text: str, readable: list[str], latest_only: bool, limit: int
) -> list[Hit]:
    """The entries of the serving Build in `readable` whose Markdown matches `text`."""
    # shortcut: the 'simple' configuration does not segment Chinese or Japanese text; add a
    # segmenting configuration if the pilot corpus has CJK documents.
    async with pool.connection() as conn:
        rows = await conn.execute(
            "SELECT e.document_uid, e.resource_id, e.source_revision_id,"
            " e.source_revision_created_at, e.canonical_revision_id, s.stale,"
            " ts_headline('simple', e.cited, q,"
            " 'StartSel=**, StopSel=**, MaxWords=30, MinWords=10, MaxFragments=2')"
            " FROM entry e JOIN build b ON b.build_id = e.build_id AND b.serving,"
            " websearch_to_tsquery('simple', %(text)s) q,"
            # A registration of a newer write always has its work row: a run ends either.
            " LATERAL (SELECT EXISTS (SELECT 1 FROM work w WHERE w.document_uid = e.document_uid)"
            " AS stale) s"
            " WHERE e.markdown IS NOT NULL AND e.resource_id = ANY(%(readable)s)"
            " AND to_tsvector('simple', e.markdown) @@ q AND NOT (%(latest_only)s AND s.stale)"
            " ORDER BY ts_rank(to_tsvector('simple', e.markdown), q) DESC, e.document_uid"
            " LIMIT %(limit)s",
            {"text": text, "readable": readable, "latest_only": latest_only, "limit": limit},
        )
        fields = list(Hit.model_fields)
        return [Hit(**dict(zip(fields, row, strict=True))) for row in await rows.fetchall()]


def _error(code: int, status: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "status": status, "message": message}}, code)
