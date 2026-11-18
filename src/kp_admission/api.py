"""The platform API (#113, authorization design Q12, §4.3), with its OpenAPI document at
/openapi.json and a health route at /healthz. So far two parts, both open only to registered
service identities (PEPs and projections): the internal authz API, the Authorizer for the PEPs
outside this process; and the governed read API (#126, canonical consumption DR §3), the Change
Feed, cursors, Document state and bootstrap listings, which kp_admission.feed describes.

Every request has a trace id (admission spec §4): the trace id of its `traceparent` header, or a
generated one when the header is absent or invalid. Every response returns it in X-Trace-Id and
every error in its body. A handler reads it with trace_id(); RequestLog adds it to each log line
written while the request is served.

Metrics, in the prometheus_client default registry; the names are provisional until #78's naming
conventions:
- `kp_authz_decisions_total` (count) by `operation` (check, list_resources), `outcome` (allow,
  deny, unavailable) and `pep`, the calling PEP's service identity.
- `kp_authz_decision_duration_seconds` (histogram, seconds), the Authorizer's time per decision, by
  `operation`.
- `kp_feed_requests_total` (count) of governed reads by `operation`, `outcome` (the status code)
  and `projection`, the caller's service identity; and kp_admission.feed's gauges.
"""

import hashlib
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from contextvars import ContextVar
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.routing import APIRoute
from fastapi.security import HTTPBearer
from prometheus_client import Counter, Histogram
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kp_admission import feed
from kp_admission.authz import Action, Authorizer, Decision, Operation, Outcome, Ref

log = logging.getLogger(__name__)

decisions = Counter("kp_authz_decisions", "authz API decisions", ["operation", "outcome", "pep"])
decision_duration = Histogram(
    "kp_authz_decision_duration_seconds", "Authorizer time per authz API decision", ["operation"]
)
feed_requests = Counter(
    "kp_feed_requests", "governed read API requests", ["operation", "outcome", "projection"]
)

# Keyed by log field (trace_id, x_request_id, pep): RequestLog writes it onto each line as it is.
_request: ContextVar[dict[str, str]] = ContextVar("request")
# W3C Trace Context §3.2: version 00 has exactly these fields; a later one may append more (§3.2.4).
_TRACEPARENT = re.compile(
    r"(?!ff)([0-9a-f]{2})-(?!0{32})([0-9a-f]{32})-(?!0{16})[0-9a-f]{16}-[0-9a-f]{2}(-.*)?"
)
_Limit = Annotated[int, Query(ge=1, le=1000)]
# The paths only a registered service identity may call.
_SERVICE_ONLY = re.compile(r"/authz/|/v1/(feed|consumers/|sources|documents/[^/]+/state)")


class Subject(Ref, frozen=True):
    type: Literal["user", "source", "client"]


class Actor(Ref, frozen=True):
    type: Literal["client"]


class ResourceRef(Ref, frozen=True):
    type: Literal["resource"]


class CheckRequest(BaseModel):
    subject: Subject
    actor: Actor | None = None
    action: Action
    resource: ResourceRef


class ListRequest(BaseModel):
    subject: Subject
    actor: Actor | None = None
    action: Action
    cursor: str | None = None


class CheckResponse(Decision, frozen=True):
    """A check decision as a 200 carries it."""

    outcome: Literal["allow", "deny"]


class ResourcePage(Decision, frozen=True):
    """A list_resources decision as a 200 carries it: the list is the answer, so no outcome."""

    outcome: SkipJsonSchema[Outcome] = Field(exclude=True)


ErrorStatus = Literal[
    "INVALID_ARGUMENT",
    "UNAUTHENTICATED",
    "PERMISSION_DENIED",
    "NOT_FOUND",
    "FAILED_PRECONDITION",
    "UNAVAILABLE",
]


class ErrorInfo(BaseModel):
    type: str = Field(default="type.googleapis.com/google.rpc.ErrorInfo", alias="@type")
    reason: str
    domain: str
    metadata: dict[str, str] | None = None


class ErrorBody(BaseModel):
    code: int
    status: ErrorStatus
    message: str
    details: list[ErrorInfo]


class ErrorResponse(BaseModel):
    """An AIP-193 error, as admission's (admission spec §4)."""

    error: ErrorBody
    trace_id: str


def trace_id() -> str:
    """The trace id of the request being served; a handler records this one."""
    return _request.get()["trace_id"]


class RequestLog(logging.Filter):
    """Adds the trace_id of the request being served, and its x_request_id and pep when known, to
    each record logged while it is served, as the `correlation` extra JsonFormatter writes."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.__dict__["correlation"] = _request.get({}) | getattr(record, "correlation", {})
        return True


class Traced:
    """Gives each request its trace id and returns it in X-Trace-Id on every response."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        match = _TRACEPARENT.fullmatch(headers.get("traceparent", ""))
        valid = match and not (match[1] == "00" and match[3])
        # A version-4 UUID is 32 lowercase hex characters and never all zeros.
        request = {"trace_id": match[2] if match and valid else uuid.uuid4().hex}
        if request_id := headers.get("x-request-id"):
            request["x_request_id"] = request_id[:128]  # the caller's text, on every log line
        token, started = _request.set(request), False

        async def traced(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                MutableHeaders(scope=message).append("X-Trace-Id", request["trace_id"])
            await send(message)

        try:
            await self._app(scope, receive, traced)
        except Exception:
            if started:
                raise
            # Starlette would answer outside this middleware, without the trace id.
            log.exception("unhandled error")
            await PlainTextResponse("Internal Server Error", 500)(scope, receive, traced)
        finally:
            _request.reset(token)


class CursorReport(BaseModel):
    cursor: str


class FeedPage(BaseModel):
    events: list[feed.Event]
    next_cursor: str


class SourceList(BaseModel):
    source_ids: list[str]


class DocumentPage(BaseModel):
    document_uids: list[str]
    next_after: str | None  # null on the last page


class Counted(APIRoute):
    """Counts each answer of a governed read by operation, status code and projection."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[None, None, Response]]:
        handler = super().get_route_handler()

        async def counted(request: Request) -> Response:
            response = await handler(request)
            feed_requests.labels(self.name, response.status_code, _request.get()["pep"]).inc()
            return response

        return counted


class PepOnly:
    """Answers 401 to a call of the authz API or the governed read API that carries no registered
    service credential, before anything reads its body, and records the identity of the others as
    the request's `pep`."""

    def __init__(self, app: ASGIApp, peps: Mapping[str, str]) -> None:
        self._app, self._peps = app, peps

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and _SERVICE_ONLY.match(scope["path"]):
            scheme, _, token = Headers(scope=scope).get("authorization", "").partition(" ")
            pep = self._peps.get(_digest(token)) if scheme.lower() == "bearer" else None
            if pep is None:
                peer = scope["client"][0] if scope.get("client") else None
                log.warning("call without a registered service credential from %s", peer)
                rejected = _error(
                    401,
                    "UNAUTHENTICATED",
                    "A registered service credential is required.",
                    path=scope["path"],
                )
                await rejected(scope, receive, send)
                return
            _request.set(_request.get() | {"pep": pep})
        await self._app(scope, receive, send)


def app(authorizer: Authorizer, peps: Mapping[str, str], pool: AsyncConnectionPool[Any]) -> FastAPI:
    """`peps` maps the SHA-256 hex digest of each registered service credential to its service
    identity, a PEP's or a projection's. A call of either API without a registered credential gets
    401 whatever else it carries; a body or parameter that is not what the operation takes gets
    400. An authz decision is 200, without the fields that do not apply, and no decision is 503.
    The governed reads use `pool`; a projection reports only its own cursor. /healthz answers 200
    to anyone without reading the database."""
    traced = {"headers": {"X-Trace-Id": {"description": "trace_id", "schema": {"type": "string"}}}}
    error = traced | {"model": ErrorResponse}
    errors = error | {"description": "400 INVALID_ARGUMENT or 401 UNAUTHENTICATED"}
    unavailable = error | {"description": "UNAVAILABLE: no decision could be made"}
    # Both only name what a caller sends in the OpenAPI document; PepOnly and Traced read it.
    authz = APIRouter(
        prefix="/authz/v1",
        dependencies=[Depends(HTTPBearer(auto_error=False)), Depends(_traceparent)],
        responses={"200": traced, "4XX": errors, "503": unavailable},
    )

    @authz.post("/check", response_model=CheckResponse, response_model_exclude_none=True)
    async def check(body: CheckRequest) -> Decision | JSONResponse:
        return await _decide(
            "check",
            authorizer.check(
                body.subject, body.action, body.resource.id, actor=body.actor, trace_id=trace_id()
            ),
        )

    @authz.post("/list_resources", response_model=ResourcePage, response_model_exclude_none=True)
    async def list_resources(body: ListRequest) -> Decision | JSONResponse:
        return await _decide(
            "list_resources",
            authorizer.list_resources(
                body.subject, body.action, actor=body.actor, cursor=body.cursor, trace_id=trace_id()
            ),
        )

    governed = APIRouter(
        prefix="/v1",
        dependencies=[Depends(HTTPBearer(auto_error=False)), Depends(_traceparent)],
        responses={"200": traced, "4XX": error, "503": error},
        route_class=Counted,
    )

    @governed.get("/feed", response_model=FeedPage, response_model_exclude_none=True)
    async def read_feed(cursor: str | None = None, limit: _Limit = 100) -> FeedPage | JSONResponse:
        """Without a cursor: no events and the position to start from before enumerating
        Documents (A4). An expired cursor is 410 CURSOR_EXPIRED: bootstrap again."""
        async with pool.connection() as conn:
            if cursor is None:
                return FeedPage(events=[], next_cursor=await feed.head(conn))
            try:
                events, next_cursor = await feed.read(conn, cursor, limit)
            except ValueError:
                return _fail(400, "INVALID_ARGUMENT", "cursor: not a feed position")
            except feed.CursorExpired:
                return _fail(
                    410,
                    "FAILED_PRECONDITION",
                    "Retention dropped entries after this cursor.",
                    reason="CURSOR_EXPIRED",
                )
        return FeedPage(events=events, next_cursor=next_cursor)

    @governed.put("/consumers/{projection}/cursor", status_code=204)
    async def report_cursor(projection: str, body: CursorReport) -> Response:
        """Only forward: a step back is 409 CURSOR_BACKWARDS with the platform's cursor, which
        wins (A3)."""
        if projection != _request.get()["pep"]:
            return _fail(403, "PERMISSION_DENIED", "A projection reports only its own cursor.")
        async with pool.connection() as conn:
            try:
                await feed.report_cursor(conn, projection, body.cursor)
            except ValueError:
                return _fail(400, "INVALID_ARGUMENT", "cursor: not a position of the feed")
            except feed.Backwards as backwards:
                return _fail(
                    409,
                    "FAILED_PRECONDITION",
                    "The cursor only moves forward.",
                    reason="CURSOR_BACKWARDS",
                    metadata={"cursor": backwards.position},
                )
        return Response(status_code=204)

    @governed.get("/documents/{document_uid}/state", response_model=feed.State)
    async def document_state(
        document_uid: str, at_least: str | None = None
    ) -> feed.State | JSONResponse:
        """At least as new as at_least, else 503 to retry (A6); a deleted Document answers
        `deleted` (A4 R-a), a uid the platform never had 404."""
        async with pool.connection() as conn:
            try:
                state = await feed.document_state(conn, document_uid, at_least)
            except ValueError:
                return _fail(400, "INVALID_ARGUMENT", "at_least: not a feed position")
            except feed.Behind:
                return _fail(
                    503,
                    "UNAVAILABLE",
                    "The state does not include at_least yet; retry.",
                    reason="STATE_BEHIND",
                )
        return state or _fail(404, "NOT_FOUND", "No such Document.")

    @governed.get("/sources", response_model=SourceList)
    async def list_sources() -> SourceList:
        async with pool.connection() as conn:
            return SourceList(source_ids=await feed.list_sources(conn))

    @governed.get("/sources/{source_id}/profile", response_model=feed.Profile)
    async def source_profile(source_id: str) -> feed.Profile | JSONResponse:
        async with pool.connection() as conn:
            found = await feed.profile(conn, source_id)
        return found or _fail(404, "NOT_FOUND", "No such Source.")

    @governed.get("/sources/{source_id}/documents", response_model=DocumentPage)
    async def list_documents(
        source_id: str, after: str | None = None, limit: _Limit = 100
    ) -> DocumentPage:
        """The Source's Documents that are not deleted, by uid after `after`."""
        async with pool.connection() as conn:
            uids = await feed.list_documents(conn, source_id, after, limit)
        return DocumentPage(document_uids=uids, next_after=uids[-1] if len(uids) == limit else None)

    # No /docs or /redoc: those pages load their scripts from another site.
    api = FastAPI(title="Knowledge Platform API", version="1", docs_url=None, redoc_url=None)
    api.include_router(authz)
    api.include_router(governed)
    api.add_middleware(PepOnly, peps=peps)
    api.add_middleware(Traced)  # added last, so it runs first: a 401 carries the trace id too

    @api.get("/healthz")
    async def healthz() -> Response:
        return Response()

    @api.exception_handler(RequestValidationError)
    async def invalid(request: Request, error: RequestValidationError) -> JSONResponse:
        first = error.errors()[0]
        where = ".".join(map(str, first["loc"]))
        return _error(400, "INVALID_ARGUMENT", f"{where}: {first['msg']}", path=request.url.path)

    @api.exception_handler(HTTPException)
    async def unreadable(request: Request, error: HTTPException) -> Response:
        if error.status_code == 400:  # FastAPI could not decode the body
            return _error(400, "INVALID_ARGUMENT", str(error.detail), path=request.url.path)
        return await http_exception_handler(request, error)

    return api


async def _traceparent(traceparent: Annotated[str | None, Header()] = None) -> None:
    pass


async def _decide(operation: Operation, decision: Awaitable[Decision]) -> Decision | JSONResponse:
    start = time.monotonic()
    made = await decision
    decision_duration.labels(operation).observe(time.monotonic() - start)
    decisions.labels(operation, made.outcome, _request.get()["pep"]).inc()
    if made.outcome == "unavailable":
        return _error(503, "UNAVAILABLE", "No decision could be made.")
    return made


def _fail(code: int, status: ErrorStatus, message: str, **details: Any) -> JSONResponse:
    """An error of the governed read API."""
    return _error(code, status, message, path="/v1/", **details)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _error(
    code: int,
    status: ErrorStatus,
    message: str,
    *,
    path: str = "/authz/",
    reason: str | None = None,
    metadata: dict[str, str] | None = None,
) -> JSONResponse:
    """An AIP-193 error of the API that `path` belongs to; its reason is the status unless one is
    given."""
    domain = "authz" if path.startswith("/authz/") else "admission"
    info = ErrorInfo(
        reason=reason or status, domain=f"{domain}.knowledge-platform", metadata=metadata
    )
    body = ErrorResponse(
        error=ErrorBody(code=code, status=status, message=message, details=[info]),
        trace_id=trace_id(),
    )
    return JSONResponse(body.model_dump(by_alias=True, exclude_none=True), status_code=code)
