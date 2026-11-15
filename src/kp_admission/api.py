"""The platform API (#113, authorization design Q12, §4.3), with its OpenAPI document at
/openapi.json and a health route at /healthz. So far the internal authz API: the Authorizer for
the PEPs outside this process, open only to registered PEP service identities.

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
"""

import hashlib
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Mapping
from contextvars import ContextVar
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Header, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.security import HTTPBearer
from prometheus_client import Counter, Histogram
from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kp_admission.authz import Action, Authorizer, Decision, Operation, Outcome, Ref

log = logging.getLogger(__name__)

decisions = Counter("kp_authz_decisions", "authz API decisions", ["operation", "outcome", "pep"])
decision_duration = Histogram(
    "kp_authz_decision_duration_seconds", "Authorizer time per authz API decision", ["operation"]
)

# Keyed by log field (trace_id, x_request_id, pep): RequestLog writes it onto each line as it is.
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


ErrorReason = Literal["INVALID_ARGUMENT", "UNAUTHENTICATED", "UNAVAILABLE"]


class ErrorInfo(BaseModel):
    type: str = Field(default="type.googleapis.com/google.rpc.ErrorInfo", alias="@type")
    reason: ErrorReason
    domain: str = "authz.knowledge-platform"


class ErrorBody(BaseModel):
    code: int
    status: ErrorReason
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


class PepOnly:
    """Answers 401 to a call under /authz/ that carries no registered PEP credential, before
    anything reads its body, and records the PEP of the others as the request's `pep`."""

    def __init__(self, app: ASGIApp, peps: Mapping[str, str]) -> None:
        self._app, self._peps = app, peps

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/authz/"):
            scheme, _, token = Headers(scope=scope).get("authorization", "").partition(" ")
            pep = self._peps.get(_digest(token)) if scheme.lower() == "bearer" else None
            if pep is None:
                peer = scope["client"][0] if scope.get("client") else None
                log.warning("authz API call without a registered PEP credential from %s", peer)
                rejected = _error(
                    401, "UNAUTHENTICATED", "A registered PEP credential is required."
                )
                await rejected(scope, receive, send)
                return
            _request.set(_request.get() | {"pep": pep})
        await self._app(scope, receive, send)


def app(authorizer: Authorizer, peps: Mapping[str, str]) -> FastAPI:
    """`peps` maps the SHA-256 hex digest of each registered PEP credential to the PEP's service
    identity. A call under /authz/ without a registered credential gets 401 whatever else it
    carries; a body that is not the JSON the operation takes, sent as application/json, gets 400;
    a decision is 200, without the fields that do not apply, and no decision is 503. /healthz
    answers 200 to anyone without reading the database."""
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

    # No /docs or /redoc: those pages load their scripts from another site.
    api = FastAPI(title="Knowledge Platform API", version="1", docs_url=None, redoc_url=None)
    api.include_router(authz)
    api.add_middleware(PepOnly, peps=peps)
    api.add_middleware(Traced)  # added last, so it runs first: a 401 carries the trace id too

    @api.get("/healthz")
    async def healthz() -> Response:
        return Response()

    @api.exception_handler(RequestValidationError)
    async def invalid(request: Request, error: RequestValidationError) -> JSONResponse:
        first = error.errors()[0]
        where = ".".join(map(str, first["loc"]))
        return _error(400, "INVALID_ARGUMENT", f"{where}: {first['msg']}")

    @api.exception_handler(HTTPException)
    async def unreadable(request: Request, error: HTTPException) -> Response:
        if error.status_code == 400:  # FastAPI could not decode the body
            return _error(400, "INVALID_ARGUMENT", str(error.detail))
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


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _error(code: int, status: ErrorReason, message: str) -> JSONResponse:
    details = [ErrorInfo(reason=status)]
    body = ErrorResponse(
        error=ErrorBody(code=code, status=status, message=message, details=details),
        trace_id=trace_id(),
    )
    return JSONResponse(body.model_dump(by_alias=True), status_code=code)
