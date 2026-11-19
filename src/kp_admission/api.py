"""The platform API (#113, authorization design Q12, §4.3), with its OpenAPI document at
/openapi.json and a health route at /healthz. So far the internal authz API: the Authorizer for
the PEPs outside this process, open only to registered PEP service identities; under /v1/, open
only to registered credentials (§7), the Resource registration of a Source (#114, authorization
design §6.1) and its batches: declare, finalize and get_batch (#96, admission spec §5.1, §5.3,
§5.4); and under /read/v1/ the governed read API (#126, canonical consumption DR §3):
the Change Feed, cursors, Document state and bootstrap listings that kp_admission.feed describes,
open only to the same registered service identities as the authz API. It has its own prefix
because /v1/ is the Source-facing surface that an ingress exposes.

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
- `kp_api_calls_total` (count) of the /v1/ and /read/v1/ calls that reached an operation, by
  `operation` (its route's name, such as register_resource) and `status`, the HTTP status code.
- `kp_admission_items_total` (count) of the batch items decided, by `operation` (declare,
  finalize), `status` (declared, unchanged, queued, rejected) and `reason`, a rejection's reason
  code (admission spec §12), empty otherwise.
- kp_admission.feed's gauges.
"""

import hashlib
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Mapping
from contextvars import ContextVar
from typing import Annotated, Any, Literal

import psycopg
from fastapi import APIRouter, Depends, FastAPI, Header, Path, Query, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.security import HTTPBearer
from prometheus_client import Counter, Histogram
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field, TypeAdapter
from pydantic.json_schema import SkipJsonSchema
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kp_admission import batches, feed, resources, uploads
from kp_admission.authz import PAGE_SIZE, Action, Authorizer, Decision, Operation, Outcome, Ref
from kp_admission.errors import ErrorStatus, Refused
from kp_admission.resources import Resource

log = logging.getLogger(__name__)

decisions = Counter("kp_authz_decisions", "authz API decisions", ["operation", "outcome", "pep"])
decision_duration = Histogram(
    "kp_authz_decision_duration_seconds", "Authorizer time per authz API decision", ["operation"]
)
calls = Counter("kp_api_calls", "platform API /v1/ calls", ["operation", "status"])

AUTHZ = "authz.knowledge-platform"
ADMISSION = "admission.knowledge-platform"
V1 = "/v1/"  # the Source-facing routes
READ = "/read/"  # the governed reads, for projections
RETRY_AFTER_S = 1

# Keyed by log field (trace_id, x_request_id, pep, source_id or client_id, credential_id):
# RequestLog writes it onto each line as it is.
_request: ContextVar[dict[str, str]] = ContextVar("request")
# W3C Trace Context §3.2: version 00 has exactly these fields; a later one may append more (§3.2.4).
_TRACEPARENT = re.compile(
    r"(?!ff)([0-9a-f]{2})-(?!0{32})([0-9a-f]{32})-(?!0{16})[0-9a-f]{16}-[0-9a-f]{2}(-.*)?"
)


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


class ErrorInfo(BaseModel):
    type: str = Field(default="type.googleapis.com/google.rpc.ErrorInfo", alias="@type")
    reason: str
    domain: str
    metadata: dict[str, str] | SkipJsonSchema[None] = None


class ErrorBody(BaseModel):
    code: int
    status: ErrorStatus
    message: str
    details: list[ErrorInfo]


class ErrorResponse(BaseModel):
    """An AIP-193 error, as admission's (admission spec §4)."""

    error: ErrorBody
    trace_id: str
    items: list[dict[str, Any]] | SkipJsonSchema[None] = None  # ALL_ITEMS_REJECTED only


CredentialScope = Literal["submit", "manage_relations"]


class SourceCredential(BaseModel, frozen=True, extra="forbid"):
    """A Source's credential (§7, admission spec §2): every call made with it is the Source's,
    in its tenant."""

    credential_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    scopes: frozenset[CredentialScope] = Field(min_length=1)


class ClientCredential(BaseModel, frozen=True, extra="forbid"):
    """An agent or consumer client's credential, `client:<client_id>` in decisions (§7). The
    delegate flag, acting for users, has no effect before identity stage P1 (#87 F1)."""

    credential_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    delegate: bool = False


Credential = SourceCredential | ClientCredential
# The registered credentials, keyed by the SHA-256 hex digest of each.
CREDENTIALS = TypeAdapter(dict[str, Credential])

_credential: ContextVar[Credential] = ContextVar("credential")


class Registration(BaseModel):
    name: str | None = Field(default=None, max_length=200)


class Registered(Resource, frozen=True):
    change_id: str | SkipJsonSchema[None] = None  # on the first registration only


class ResourceList(BaseModel):
    resources: list[Resource]
    next_page_token: str = ""  # empty on the last page (AIP-158)


class Declaration(BaseModel):
    items: list[batches.DeclaredItem] = Field(min_length=1)


class Upload(BaseModel):
    path: str
    method: Literal["PUT"]
    url: str


class DeclaredOutcome(BaseModel):
    index: int
    document_id: str
    document_uid: str | SkipJsonSchema[None] = None
    status: Literal["declared", "unchanged", "queued", "rejected"]
    uploads: list[Upload] | SkipJsonSchema[None] = None
    carried_over: list[str] | SkipJsonSchema[None] = None
    request_id: str | SkipJsonSchema[None] = None
    error: dict[str, str] | SkipJsonSchema[None] = None


class Declared(BaseModel):
    batch_id: str
    state: Literal["open", "finalized"]
    expires_at: str
    items: list[DeclaredOutcome]


class BatchItem(BaseModel):
    index: int
    document_id: str
    document_uid: str | SkipJsonSchema[None] = None
    status: str = Field(description="The item's status, then its request's")
    request_id: str | SkipJsonSchema[None] = None
    source_revision_id: str | SkipJsonSchema[None] = None
    error: dict[str, str] | SkipJsonSchema[None] = None


class BatchView(BaseModel):
    batch_id: str
    state: Literal["open", "finalized", "expired"]
    created_at: str
    expires_at: str
    finalized_at: str | SkipJsonSchema[None] = None
    counts: dict[str, int]
    items: list[BatchItem]
    next_page_token: str = ""


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


_Limit = Annotated[int, Query(ge=1, le=1000)]

Key = Annotated[
    str, Path(min_length=1, max_length=200, description="The Source's own key, URL-encoded")
]


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


class PepOnly:
    """Answers 401 to a call under /authz/ or /read/ that carries no registered PEP credential,
    before anything reads its body, and records the PEP of the others as the request's `pep`."""

    def __init__(self, app: ASGIApp, peps: Mapping[str, str]) -> None:
        self._app, self._peps = app, peps

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(("/authz/", READ)):
            pep = self._peps.get(_bearer_digest(scope))
            if pep is None:
                log.warning("call without a registered PEP credential from %s", _peer(scope))
                rejected = _error(
                    401,
                    "UNAUTHENTICATED",
                    "A registered PEP credential is required.",
                    domain=_domain(scope["path"]),
                )
                await rejected(scope, receive, send)
                return
            _request.set(_request.get() | {"pep": pep})
        await self._app(scope, receive, send)


class Credentialed:
    """Answers 401 to a call under /v1/ that carries no registered credential, before anything
    reads its body, and records the Source or client and the credential_id of the others on the
    request."""

    def __init__(self, app: ASGIApp, credentials: Mapping[str, Credential]) -> None:
        self._app, self._credentials = app, credentials

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(V1):
            await self._app(scope, receive, send)
            return
        credential = self._credentials.get(_bearer_digest(scope))
        if credential is None:
            log.warning("API call without a registered credential from %s", _peer(scope))
            rejected = _error(
                401, "UNAUTHENTICATED", "A registered credential is required.", domain=ADMISSION
            )
            await rejected(scope, receive, send)
            return
        caller = (
            {"source_id": credential.source_id}
            if isinstance(credential, SourceCredential)
            else {"client_id": credential.client_id}
        )
        _request.set(_request.get() | caller | {"credential_id": credential.credential_id})
        token = _credential.set(credential)
        try:
            await self._app(scope, receive, send)
        finally:
            _credential.reset(token)


class Counted:
    """Counts each call under /v1/ or /read/ that reached a route, by the route's name and status
    code."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith((V1, READ)):
            await self._app(scope, receive, send)
            return
        status = 500  # unless a response starts

        async def counted(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self._app(scope, receive, counted)
        finally:
            if route := scope.get("route"):  # the router sets it on this scope when it matches
                calls.labels(route.name, str(status)).inc()


def app(
    authorizer: Authorizer,
    peps: Mapping[str, str],
    credentials: Mapping[str, Credential],
    pool: AsyncConnectionPool[Any],
    intake: batches.Intake,
) -> FastAPI:
    """`peps` maps the SHA-256 hex digest of each registered PEP credential to the PEP's service
    identity, `credentials` that of each Source and client credential to it. A call under /authz/
    without a registered PEP credential, or under /v1/ without a registered credential, gets 401
    whatever else it carries; a body that is not the JSON the operation takes, sent as
    application/json, gets 400. On /authz/ a decision is 200, without the fields that do not
    apply, and no decision is 503. /healthz answers 200 to anyone without reading the database.

    Under /v1/ a Source reaches only the keys it registered; `pool` holds them. A key it did not
    register is 404, a credential without the scope an operation needs 403, and a client
    credential holds none. A batch is the Source's own too: another Source's is 404.

    Under /read/v1/ a registered PEP reads the Change Feed and reports only its own cursor."""
    traced = {"headers": {"X-Trace-Id": {"description": "trace_id", "schema": {"type": "string"}}}}
    error = traced | {"model": ErrorResponse}
    errors = error | {"description": "400 INVALID_ARGUMENT or 401 UNAUTHENTICATED"}
    unavailable = error | {"description": "UNAVAILABLE: no decision could be made"}
    # Both only name what a caller sends in the OpenAPI document; the middleware reads them.
    declared = [Depends(HTTPBearer(auto_error=False)), Depends(_traceparent)]
    authz = APIRouter(
        prefix="/authz/v1",
        dependencies=declared,
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

    v1 = APIRouter(
        prefix="/v1",
        dependencies=declared,
        responses={
            "200": traced,
            "4XX": error | {"description": "400, 401, 403, 404, 409, 422 or 429"},
            "503": error | {"description": "AUTHZ_UNAVAILABLE, ADMISSION_PAUSED or UNAVAILABLE"},
        },
    )
    not_found = Refused(
        404, "NOT_FOUND", "RESOURCE_NOT_FOUND", "The Source registered no Resource with this key."
    )

    @v1.put(
        "/resources/{key:path}",
        response_model=Registered,
        response_model_exclude_none=True,
        responses={"201": traced | {"model": Registered, "description": "Registered now"}},
    )
    async def register_resource(
        key: Key, response: Response, body: Registration | None = None
    ) -> Registered:
        source = _source("manage_relations")
        async with pool.connection() as conn:
            resource, change_id = await resources.register(
                conn,
                tenant_id=source.tenant_id,
                source_id=source.source_id,
                key=key,
                name=body and body.name,
                credential_id=source.credential_id,
            )
        if change_id:
            response.status_code = 201
        return Registered(**resource.model_dump(), change_id=change_id)

    @v1.get("/resources", response_model=ResourceList, response_model_exclude_none=True)
    async def list_resources_of_source(
        page_size: Annotated[int, Query(ge=0)] = 0, page_token: str | None = None
    ) -> ResourceList:
        """AIP-158 paging: a page_size of 0 or above 1000 is 1000."""
        source = _source("submit", "manage_relations")
        size = min(page_size or PAGE_SIZE, PAGE_SIZE)
        async with pool.connection() as conn:
            page = await resources.list_page(
                conn, source_id=source.source_id, after=page_token or None, limit=size + 1
            )
        more = len(page) > size
        return ResourceList(
            resources=page[:size], next_page_token=page[size - 1].key if more else ""
        )

    @v1.get("/resources/{key:path}", response_model=Resource, response_model_exclude_none=True)
    async def get_resource(key: Key) -> Resource:
        source = _source("submit", "manage_relations")
        async with pool.connection() as conn:
            if found := await resources.get(conn, source_id=source.source_id, key=key):
                return found
        raise not_found

    @v1.delete("/resources/{key:path}", status_code=204, response_class=Response)
    async def delete_resource(key: Key) -> None:
        """409 RESOURCE_NOT_EMPTY while a Document without Source Deletion applied is bound."""
        source = _source("manage_relations")
        async with pool.connection() as conn:  # a key it did not register is 404, not a deny
            if not await resources.get(conn, source_id=source.source_id, key=key):
                raise not_found
        decision = await authorizer.check(
            Ref(type="source", id=source.source_id),
            "manage",
            resources.resource_id(source.source_id, key),
            trace_id=trace_id(),
        )
        if decision.outcome == "unavailable":
            raise Refused(503, "UNAVAILABLE", "AUTHZ_UNAVAILABLE", "No decision could be made.")
        if decision.outcome == "deny":
            raise Refused(
                403, "PERMISSION_DENIED", "PERMISSION_DENIED", "The Source may not manage it."
            )
        async with pool.connection() as conn:
            outcome = await resources.delete(
                conn,
                tenant_id=source.tenant_id,
                source_id=source.source_id,
                key=key,
                credential_id=source.credential_id,
            )
        if outcome == "not_found":
            raise not_found
        if outcome == "not_empty":
            raise Refused(
                409, "FAILED_PRECONDITION", "RESOURCE_NOT_EMPTY", "Documents are bound to it."
            )

    @v1.post(
        "/batches",
        status_code=201,
        responses={"201": traced | {"model": Declared, "description": "Declared"}},
    )
    async def declare(
        body: Declaration,
        request: Request,
        idempotency_key: Annotated[str | None, Header(max_length=255)] = None,
    ) -> JSONResponse:
        """Declares a batch (admission spec §5.1, §6.1)."""
        status, answer = await batches.declare(
            pool,
            authorizer,
            intake,
            _caller(),
            body.items,
            idempotency_key,
            intake.public_url or str(request.base_url),
        )
        return _answer(status, answer)

    @v1.post(
        "/batches/{batch_id}/finalize",
        status_code=202,
        responses={"202": traced | {"model": BatchView, "description": "Finalized"}},
    )
    async def finalize(batch_id: Annotated[str, Path(max_length=64)]) -> JSONResponse:
        """Finalizes a batch (admission spec §5.3, §6.2); repeating it returns the batch."""
        return _answer(*await batches.finalize(pool, authorizer, intake, _caller(), batch_id))

    @v1.put(
        "/batches/{batch_id}/items/{index}/files/{path:path}",
        status_code=204,
        response_class=Response,
        responses={"204": traced | {"description": "Staged"}},
    )
    async def upload_file(
        batch_id: Annotated[str, Path(max_length=64)],
        index: int,
        path: Annotated[str, Path(description="The declared file path")],
        request: Request,
    ) -> Response:
        """Stages one declared file; the body is its bytes (admission spec §5.2)."""
        try:
            await uploads.receive(
                pool,
                intake.store,
                _caller(),
                batch_id,
                index,
                path,
                request.headers.get("content-length"),
                request.stream(),
            )
        except ClientDisconnect:
            log.warning("upload interrupted", extra={"correlation": {"batch_id": batch_id}})
            return Response(status_code=499)  # never sent; counted as the interrupted upload
        return Response(status_code=204)

    @v1.get("/batches/{batch_id}", response_model=BatchView)
    async def get_batch(batch_id: Annotated[str, Path(max_length=64)]) -> JSONResponse:
        """The batch and each item's outcome (admission spec §5.4)."""
        return JSONResponse(await batches.view(pool, _caller(), batch_id))

    read = APIRouter(
        prefix="/read/v1",
        dependencies=declared,
        responses={
            "200": traced,
            "4XX": error | {"description": "400, 401, 403, 404, 409 or 410"},
            "503": error | {"description": "STATE_BEHIND or UNAVAILABLE: retry"},
        },
    )

    @read.get("/feed", response_model=FeedPage, response_model_exclude_none=True)
    async def read_feed(cursor: str | None = None, limit: _Limit = 100) -> FeedPage:
        """Without a cursor: no events and the position to start from before enumerating
        Documents (A4). An expired cursor is 410 CURSOR_EXPIRED: bootstrap again."""
        async with pool.connection() as conn:
            if cursor is None:
                return FeedPage(events=[], next_cursor=await feed.head(conn))
            try:
                events, next_cursor = await feed.read(conn, cursor, limit)
            except ValueError:
                raise _invalid("cursor: not a feed position") from None
            except feed.CursorExpired:
                raise Refused(
                    410,
                    "FAILED_PRECONDITION",
                    "CURSOR_EXPIRED",
                    "Retention dropped entries after this cursor.",
                ) from None
        return FeedPage(events=events, next_cursor=next_cursor)

    @read.put("/consumers/{projection}/cursor", status_code=204, response_class=Response)
    async def report_cursor(projection: str, body: CursorReport) -> None:
        """Only forward: a step back is 409 CURSOR_BACKWARDS with the platform's cursor, which
        wins (A3)."""
        if projection != _request.get()["pep"]:
            raise Refused(
                403,
                "PERMISSION_DENIED",
                "PERMISSION_DENIED",
                "A projection reports only its own cursor.",
            )
        async with pool.connection() as conn:
            try:
                await feed.report_cursor(conn, projection, body.cursor)
            except ValueError:
                raise _invalid("cursor: not a position of the feed") from None
            except feed.Backwards as backwards:
                raise Refused(
                    409,
                    "FAILED_PRECONDITION",
                    "CURSOR_BACKWARDS",
                    "The cursor only moves forward.",
                    {"cursor": backwards.position},
                ) from None

    @read.get("/documents/{document_uid}/state", response_model=feed.State)
    async def document_state(document_uid: str, at_least: str | None = None) -> feed.State:
        """At least as new as at_least, else 503 STATE_BEHIND to retry (A6); a deleted Document
        answers `deleted` (A4 R-a), a uid the platform never had 404."""
        async with pool.connection() as conn:
            try:
                state = await feed.document_state(conn, document_uid, at_least)
            except ValueError:
                raise _invalid("at_least: not a feed position") from None
            except feed.Behind:
                raise Refused(
                    503,
                    "UNAVAILABLE",
                    "STATE_BEHIND",
                    "The state does not include at_least yet; retry.",
                ) from None
        if state is None:
            raise Refused(404, "NOT_FOUND", "DOCUMENT_NOT_FOUND", "No such Document.")
        return state

    @read.get("/sources", response_model=SourceList)
    async def list_sources() -> SourceList:
        async with pool.connection() as conn:
            return SourceList(source_ids=await feed.list_sources(conn))

    @read.get("/sources/{source_id}/profile", response_model=feed.Profile)
    async def source_profile(source_id: str) -> feed.Profile:
        async with pool.connection() as conn:
            if found := await feed.profile(conn, source_id):
                return found
        raise Refused(404, "NOT_FOUND", "SOURCE_NOT_FOUND", "No such Source.")

    @read.get("/sources/{source_id}/documents", response_model=DocumentPage)
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
    api.include_router(v1)
    api.include_router(read)
    api.add_middleware(Counted)
    api.add_middleware(Credentialed, credentials=credentials)
    api.add_middleware(PepOnly, peps=peps)
    api.add_middleware(Traced)  # added last, so it runs first: a 401 carries the trace id too

    @api.get("/healthz")
    async def healthz() -> Response:
        return Response()

    @api.exception_handler(RequestValidationError)
    async def invalid(request: Request, error: RequestValidationError) -> JSONResponse:
        first = error.errors()[0]
        where = ".".join(map(str, first["loc"]))
        message = f"{where}: {first['msg']}"
        return _error(400, "INVALID_ARGUMENT", message, domain=_domain(request.url.path))

    @api.exception_handler(HTTPException)
    async def unreadable(request: Request, error: HTTPException) -> Response:
        if error.status_code == 400:  # FastAPI could not decode the body
            return _error(
                400, "INVALID_ARGUMENT", str(error.detail), domain=_domain(request.url.path)
            )
        return await http_exception_handler(request, error)

    @api.exception_handler(Refused)
    async def refused(request: Request, error: Refused) -> JSONResponse:
        return _error(
            error.code,
            error.status,
            error.message,
            error.reason,
            ADMISSION,
            error.metadata,
            error.retry_after,
            error.items,
        )

    @api.exception_handler(psycopg.OperationalError)  # PoolTimeout included
    async def database_down(request: Request, error: psycopg.OperationalError) -> JSONResponse:
        log.warning("database unavailable", extra={"correlation": {"error": type(error).__name__}})
        message = "The database is unavailable."
        return _error(503, "UNAVAILABLE", message, domain=_domain(request.url.path))

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


def _source(*scopes: CredentialScope) -> SourceCredential:
    """The caller's credential, when it is a Source's that holds one of `scopes`."""
    credential = _credential.get()
    if isinstance(credential, SourceCredential) and credential.scopes & set(scopes):
        return credential
    needed = " or ".join(scopes)
    raise Refused(403, "PERMISSION_DENIED", "PERMISSION_DENIED", f"The credential needs {needed}.")


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _bearer_digest(scope: Scope) -> str:
    """The digest of the request's bearer token; empty without one."""
    scheme, _, token = Headers(scope=scope).get("authorization", "").partition(" ")
    return _digest(token) if scheme.lower() == "bearer" else ""


def _peer(scope: Scope) -> str | None:
    return scope["client"][0] if scope.get("client") else None


def _domain(path: str) -> str:
    return AUTHZ if path.startswith("/authz/") else ADMISSION


def _invalid(message: str) -> Refused:
    return Refused(400, "INVALID_ARGUMENT", "INVALID_ARGUMENT", message)


def _error(
    code: int,
    status: ErrorStatus,
    message: str,
    reason: str | None = None,
    domain: str = AUTHZ,
    metadata: dict[str, str] | None = None,
    retry_after: int | None = None,
    items: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    details = [ErrorInfo(reason=reason or status, domain=domain, metadata=metadata)]
    # Every /v1/ and /read/v1/ 429 and 503 says when to retry (admission spec §5.1).
    if code == 503 and domain == ADMISSION:
        retry_after = retry_after or RETRY_AFTER_S
    retry = {"Retry-After": str(retry_after)} if retry_after else None
    body = ErrorResponse(
        error=ErrorBody(code=code, status=status, message=message, details=details),
        trace_id=trace_id(),
        items=items,
    )
    return JSONResponse(
        body.model_dump(by_alias=True, exclude_none=True), status_code=code, headers=retry
    )


def _caller() -> batches.Caller:
    source = _source("submit")
    return batches.Caller(source.tenant_id, source.source_id, trace_id())


def _answer(status: int, body: dict[str, Any]) -> JSONResponse:
    """A 2XX as it is; ALL_ITEMS_REJECTED as an AIP-193 error that lists every item."""
    if status >= 400:
        raise Refused(
            status, "FAILED_PRECONDITION", body["reason"], body["message"], items=body["items"]
        )
    return JSONResponse(body, status_code=status)
