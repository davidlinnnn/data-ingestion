"""The platform API (#113, authorization design Q12, §4.3), with its OpenAPI document at
/openapi.json and a health route at /healthz. So far the internal authz API: the Authorizer for
the PEPs outside this process, open only to registered PEP service identities; under /v1/, open
only to registered credentials (§7), the Resource registration of a Source (#114, authorization
design §6.1) and its batches: declare, finalize and get_batch (#96, admission spec §5.1, §5.3,
§5.4), and its requests and Documents with their status (#97, admission spec §5.5–§5.7); under
/read/v1/ the governed read API (#126, canonical consumption DR §3): the Change Feed, cursors,
Document state and bootstrap listings that kp_admission.feed describes, open only to the same
registered service identities as the authz API; and under /report/v1/ the status report intake
(#97, admission spec §7.3) and the projections' reports (#252, §7.4) with their repair views
(#260), open only to the registered
pipelines. Both have their own prefix
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
- `kp_api_calls_total` (count) of the /v1/, /read/v1/ and /report/v1/ calls that reached an
  operation, by `operation` (its route's name, such as register_resource) and `status`, the HTTP
  status code: for report_status 202 recorded, 200 a repeat, 409 out of order or another attempt,
  503 an attempt not recorded yet.
- `kp_admission_items_total` (count) of the batch items decided, by `operation` (declare,
  finalize), `status` (declared, unchanged, queued, rejected) and `reason`, a rejection's reason
  code (admission spec §12), empty otherwise.
- kp_admission.feed's gauges, and kp_admission.serving's counters, histogram and gauge (#252,
  #260).
"""

import hashlib
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Mapping
from contextvars import ContextVar
from types import MappingProxyType
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

from kp_admission import batches, feed, reports, resources, serving, status, uploads
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
REPORT = "/report/"  # status reports, for the registered pipelines
RETRY_AFTER_S = 1

# Keyed by log field (trace_id, x_request_id, pep, source_id or client_id, credential_id):
# RequestLog writes it onto each line as it is.
_request: ContextVar[dict[str, str]] = ContextVar("request")
# W3C Trace Context §3.2: version 00 has exactly these fields; a later one may append more (§3.2.4).
_FILE_PATH = re.compile(r"^(/v1/batches/[^/]+/items/[^/]+/files/).+")
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


class DocumentEntry(BaseModel):
    document_id: str
    document_uid: str
    latest: dict[str, str | None]  # source_version
    readiness: str
    metadata: dict[str, Any] | None


class DocumentList(BaseModel):
    documents: list[DocumentEntry]
    next_page_token: str = ""  # empty on the last page (AIP-158)


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
_BuildId = Annotated[str, Path(min_length=1, max_length=128)]  # the owner's choice

Key = Annotated[
    str, Path(min_length=1, max_length=200, description="The Source's own key, URL-encoded")
]


def trace_id() -> str:
    """The trace id of the request being served; a handler records this one."""
    return _request.get()["trace_id"]


class RequestLog(logging.Filter):
    """Adds the trace_id of the request being served, and its x_request_id and pep when known, to
    each record logged while it is served, as the `correlation` extra JsonFormatter writes; and
    leaves the file path out of an upload's access line."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.__dict__["correlation"] = _request.get({}) | getattr(record, "correlation", {})
        # uvicorn's access line is (client, method, path, version, status); a file path stays out.
        if record.name == "uvicorn.access" and isinstance(record.args, tuple):
            record.args = tuple(
                _FILE_PATH.sub(r"\1…", a) if i == 2 and isinstance(a, str) else a
                for i, a in enumerate(record.args)
            )
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


class ServiceOnly:
    """Answers 401 to a call under one of `prefixes` that carries none of the registered service
    credentials `identities` maps to a service identity, before anything reads its body, and
    records the identity of the others on the request under `field`: `pep` for the PEPs under
    /authz/ and /read/, `pipeline` for the reporters under /report/."""

    def __init__(
        self, app: ASGIApp, identities: Mapping[str, str], prefixes: tuple[str, ...], field: str
    ) -> None:
        self._app, self._identities, self._prefixes, self._field = app, identities, prefixes, field

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(self._prefixes):
            identity = self._identities.get(_bearer_digest(scope))
            if identity is None:
                log.warning("call without a registered %s credential from %s", self._field,
                            _peer(scope))  # fmt: skip
                rejected = _error(
                    401,
                    "UNAUTHENTICATED",
                    "A registered service credential is required.",
                    domain=_domain(scope["path"]),
                )
                await rejected(scope, receive, send)
                return
            _request.set(_request.get() | {self._field: identity})
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
    """Counts each call under /v1/, /read/ or /report/ that reached a route, by the route's name
    and status code."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith((V1, READ, REPORT)):
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
    pipelines: Mapping[str, reports.Pipeline] = MappingProxyType({}),
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

    Under /read/v1/ a registered PEP reads the Change Feed and reports only its own cursor.

    `pipelines` maps that of each reporter's service credential to its registration (#97); under
    /report/v1/ only those reach a route. The `canonical` one reports a request's status, and
    every other one, a projection named by its track, its Builds (#252, admission spec §7.4)."""
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

    @v1.get("/requests/{request_id}")
    async def get_request(request_id: Annotated[str, Path(max_length=64)]) -> JSONResponse:
        """The request (admission spec §5.5); 404 for another Source's, or 30 days after its
        terminal outcome."""
        source = _source("submit")
        async with pool.connection() as conn:
            found = await status.request(conn, source.tenant_id, source.source_id, request_id)
        if found is None:
            raise Refused(404, "NOT_FOUND", "NOT_FOUND", "The Source has no such request.")
        return JSONResponse(found)

    by_track = {p.track: p for p in pipelines.values()}

    @v1.get("/documents/{document_id}")
    async def get_document(document_id: Annotated[str, Path(max_length=256)]) -> JSONResponse:
        """The Document's current generation, else the one deleted last (admission spec
        §5.6); 404 for another Source's."""
        source = _source("submit")
        async with pool.connection() as conn:
            found = await status.document(
                conn, source.tenant_id, source.source_id, document_id, by_track
            )
        if found is None:
            raise Refused(404, "NOT_FOUND", "NOT_FOUND", "The Source has no such document.")
        return JSONResponse(found)

    @v1.get("/documents", response_model=DocumentList)
    async def list_documents_of_source(
        resource_id: str | None = None,
        readiness: status.Readiness | None = None,
        projection: str | None = None,
        page_size: Annotated[int, Query(ge=0)] = 0,
        page_token: str | None = None,
    ) -> DocumentList:
        """The Source's Documents, deleted ones within retention included (admission spec §5.7),
        in AIP-158 pages: a page_size of 0 or above 1000 is 1000. The filters apply after paging,
        so a page may hold fewer entries, none even, with more to follow: read until
        next_page_token is empty. `projection` keeps the Documents whose serving lists it."""
        source = _source("submit")
        async with pool.connection() as conn:
            try:
                entries, token = await status.documents(
                    conn,
                    source.tenant_id,
                    source.source_id,
                    page_size=min(page_size or PAGE_SIZE, PAGE_SIZE),
                    page_token=page_token,
                    resource_id=resource_id
                    and resources.resource_id(source.source_id, resource_id),
                    readiness=readiness,
                    projection=projection,
                )
            except ValueError:
                raise _invalid("page_token: not a token this list returned") from None
        return DocumentList.model_validate({"documents": entries, "next_page_token": token})

    report = APIRouter(
        prefix="/report/v1",
        dependencies=declared,
        responses={
            "200": traced | {"description": "A repeat of the last report: nothing changed"},
            "4XX": error | {"description": "400, 401, 403 or 404"},
            "409": traced
            | {"model": reports.Position, "description": "Out of order: the position"},
            "503": error | {"description": "ATTEMPT_NOT_RECORDED or UNAVAILABLE: retry"},
        },
    )
    pipeline_of = {p.pipeline_id: p for p in pipelines.values()}

    @report.post("/requests/{request_id}/status-reports", status_code=202)
    async def report_status(
        request_id: Annotated[str, Path(max_length=64)], body: reports.Report
    ) -> Response:
        """Takes a status report of the request's current attempt (admission spec §7.3)."""
        pipeline = pipeline_of[_request.get()["pipeline"]]
        if pipeline.track != "canonical":
            raise Refused(
                403, "PERMISSION_DENIED", "PERMISSION_DENIED", "Only canonical processing reports."
            )
        if body.request_id != request_id:
            raise _invalid("request_id: not the request of the path")
        async with pool.connection() as conn:
            taken = await reports.take(conn, pipeline, body)
        match taken.result:
            case "recorded":
                return Response(status_code=202)
            case "repeated":
                return Response(status_code=200)
            case "not_found":
                raise Refused(404, "NOT_FOUND", "NOT_FOUND", "No such process request.")
            case "bad_stage":
                raise _invalid("stage: not a stage the pipeline registered")
            case "no_attempt":
                raise Refused(
                    503, "UNAVAILABLE", "ATTEMPT_NOT_RECORDED", "The attempt is not recorded yet."
                )
        assert taken.position
        return JSONResponse(taken.position.model_dump(), 409)

    def calling_projection() -> str:
        """The calling projection: its pipeline's track (admission spec §7.4)."""
        track = pipeline_of[_request.get()["pipeline"]].track
        if track == "canonical":
            raise Refused(
                403, "PERMISSION_DENIED", "PERMISSION_DENIED", "Only projections report Builds."
            )
        return track

    @report.put("/builds/{build_id}", response_model=serving.BuildAnswer)
    async def report_build_state(build_id: _BuildId, body: serving.BuildReport) -> JSONResponse:
        """A Build's state (DR §4, D2); a switch failing a gate is 409 GATE_FAILED."""
        name = calling_projection()
        async with pool.connection() as conn:
            answer, changed = await serving.report_build(conn, name, build_id, body)
            # shortcut: a switch, or a resent one, refreshes every Document of both Builds inside
            # the request, move the fan-out to a worker when #99 measures it near a call's timeout.
            await status.refresh_builds(conn, name, changed)
        return JSONResponse(answer.model_dump(mode="json"))

    @report.put("/sources/{source_id}/backfill", status_code=204, response_class=Response)
    async def report_backfill(
        source_id: Annotated[str, Path(max_length=64)], body: serving.Backfill
    ) -> None:
        """The projection's backfill of the Source is complete at profile_seq (DR B1)."""
        name = calling_projection()
        async with pool.connection() as conn:
            await serving.report_backfill(conn, name, source_id, body.profile_seq)
            # shortcut: refreshes every Document of the Source inside the request, move the
            # fan-out to a worker when #99 measures it near a call's timeout.
            await status.refresh_source(conn, source_id)

    @report.post("/builds/{build_id}/registrations", response_model=serving.Answer)
    async def register_facts(build_id: _BuildId, body: serving.Registrations) -> JSONResponse:
        """`pending` facts before a store write, all or none, after the B5 check (DR §5.2);
        409 SUPERSEDED: drop the result, do not write."""
        name = calling_projection()
        async with pool.connection() as conn:
            answer = await serving.register(conn, name, build_id, body.facts)
        return JSONResponse(answer.model_dump(mode="json"))

    @report.post("/builds/{build_id}/heartbeats", response_model=serving.Answer)
    async def report_heartbeat(build_id: _BuildId, body: serving.Heartbeat) -> JSONResponse:
        """The Build's count and digest (DR §5.5); a mismatch asks for a repair view."""
        name = calling_projection()
        async with pool.connection() as conn:
            answer = await serving.heartbeat(conn, name, build_id, body)
        return JSONResponse(answer.model_dump(mode="json"))

    @report.put(
        "/builds/{build_id}/repair-views/{view_id}/pages/{page}", response_model=serving.ViewAnswer
    )
    async def report_repair_view(
        build_id: _BuildId,
        view_id: Annotated[str, Path(min_length=1, max_length=64)],
        page: Annotated[int, Path(ge=1)],
        body: serving.ViewPage,
    ) -> JSONResponse:
        """A page of the Build's repair view (DR §5.4); the last one to arrive replaces the
        mirror. 409 VIEW_DISCARDED: capture a fresh view, unless `superseded`."""
        name = calling_projection()
        async with pool.connection() as conn:
            answer, installed = await serving.repair_view(conn, name, build_id, view_id, page, body)
            if installed:
                # shortcut: refreshes every Document of the Build inside the request, move the
                # fan-out to a worker when #99 measures it near a call's timeout.
                await status.refresh_builds(conn, name, [build_id])
        return JSONResponse(answer.model_dump(mode="json"))

    @report.post("/builds/{build_id}/status-reports", status_code=202)
    async def report_projection_status(build_id: _BuildId, body: serving.AttemptReport) -> Response:
        """A status report of the projection's attempt for a Document's Canonical Revision in
        the Build (admission spec §7.4): 409 with the current position when out of order."""
        name = calling_projection()
        async with pool.connection() as conn:
            taken = await serving.take_attempt(conn, by_track[name], build_id, body)
        if isinstance(taken, serving.AttemptPosition):
            return JSONResponse(taken.model_dump(), 409)
        return Response(status_code=202 if taken == "recorded" else 200)

    @report.post("/builds/{build_id}/facts", response_model=serving.FactsAnswer)
    async def report_serving_facts(build_id: _BuildId, body: serving.ServingFacts) -> JSONResponse:
        """`included` and `removed` facts (DR §5.1); a fenced one is listed and not taken."""
        name = calling_projection()
        async with pool.connection() as conn:
            answer = await serving.report_facts(conn, name, build_id, body.facts)
            await status.refresh(conn, sorted({f.document_uid for f in body.facts}))
        return JSONResponse(answer.model_dump(mode="json"))

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
    api.include_router(report)
    api.add_middleware(Counted)
    api.add_middleware(Credentialed, credentials=credentials)
    api.add_middleware(ServiceOnly, identities=peps, prefixes=("/authz/", READ), field="pep")
    reporters = {credential: p.pipeline_id for credential, p in pipelines.items()}
    api.add_middleware(ServiceOnly, identities=reporters, prefixes=(REPORT,), field="pipeline")
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
