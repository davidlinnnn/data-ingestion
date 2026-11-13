"""The platform API (#113, authorization design Q12, §4.3), with its OpenAPI document at
/openapi.json. So far the internal authz API: the Authorizer for the PEPs outside this process,
open only to registered PEP service identities."""

import hashlib
import logging
from collections.abc import Mapping
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from kp_admission.authz import Action, Authorizer, Decision, Ref

log = logging.getLogger(__name__)


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
    trace_id: str = Field(min_length=1)


class ListRequest(BaseModel):
    subject: Subject
    actor: Actor | None = None
    action: Action
    cursor: str | None = None
    trace_id: str = Field(min_length=1)


ErrorReason = Literal["INVALID_ARGUMENT", "UNAUTHENTICATED"]


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


class PepOnly:
    """Answers 401 to a call under /authz/ that carries no registered PEP credential, before
    anything reads its body."""

    def __init__(self, app: ASGIApp, peps: Mapping[str, str]) -> None:
        self._app, self._peps = app, peps

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/authz/"):
            scheme, _, token = Headers(scope=scope).get("authorization", "").partition(" ")
            if scheme.lower() != "bearer" or _digest(token) not in self._peps:
                peer = scope["client"][0] if scope.get("client") else None
                log.warning("authz API call without a registered PEP credential from %s", peer)
                rejected = _error(
                    401, "UNAUTHENTICATED", "A registered PEP credential is required."
                )
                await rejected(scope, receive, send)
                return
        await self._app(scope, receive, send)


def app(authorizer: Authorizer, peps: Mapping[str, str]) -> FastAPI:
    """`peps` maps the SHA-256 hex digest of each registered PEP credential to the PEP's service
    identity. A call under /authz/ without a registered credential gets 401 whatever else it
    carries; a body that is not the JSON the operation takes, sent as application/json, gets 400;
    every decision is 200 whatever its outcome, without the fields that do not apply."""
    errors = {"model": ErrorResponse, "description": "400 INVALID_ARGUMENT or 401 UNAUTHENTICATED"}
    # HTTPBearer only names the scheme in the OpenAPI document; PepOnly enforces it.
    authz = APIRouter(
        prefix="/authz/v1",
        dependencies=[Depends(HTTPBearer(auto_error=False))],
        responses={"4XX": errors},
    )

    @authz.post("/check", response_model_exclude_none=True)
    async def check(body: CheckRequest) -> Decision:
        return await authorizer.check(
            body.subject, body.action, body.resource.id, actor=body.actor, trace_id=body.trace_id
        )

    @authz.post("/list_resources", response_model_exclude_none=True)
    async def list_resources(body: ListRequest) -> Decision:
        return await authorizer.list_resources(
            body.subject, body.action, actor=body.actor, cursor=body.cursor, trace_id=body.trace_id
        )

    # No /docs or /redoc: those pages load their scripts from another site.
    api = FastAPI(title="Knowledge Platform API", version="1", docs_url=None, redoc_url=None)
    api.include_router(authz)
    api.add_middleware(PepOnly, peps=peps)

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


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _error(code: int, status: ErrorReason, message: str) -> JSONResponse:
    details = [ErrorInfo(reason=status)]
    body = ErrorResponse(
        error=ErrorBody(code=code, status=status, message=message, details=details)
    )
    return JSONResponse(body.model_dump(by_alias=True), status_code=code)
