"""The platform API (#113, authorization design Q12, §4.3), with its OpenAPI document at
/openapi.json. So far the internal authz API: the Authorizer for the PEPs outside this process,
open only to registered PEP service identities."""

import hashlib
import logging
from collections.abc import Mapping
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

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


class ErrorInfo(BaseModel):
    type: str = Field(default="type.googleapis.com/google.rpc.ErrorInfo", alias="@type")
    reason: str
    domain: str = "authz.knowledge-platform"


class Status(BaseModel):
    code: int
    status: str
    message: str
    details: list[ErrorInfo]


class Error(BaseModel):
    """An AIP-193 error, as admission's (admission spec §4)."""

    error: Status


class Rejected(Exception):
    def __init__(self, code: int, status: str, message: str) -> None:
        self.code, self.status, self.message = code, status, message


def app(authorizer: Authorizer, peps: Mapping[str, str]) -> FastAPI:
    """`peps` maps the SHA-256 hex digest of each registered PEP credential to the PEP's service
    identity. A call without a registered credential gets 401, an invalid body 400, and every
    decision 200 whatever its outcome, without the fields that do not apply."""

    async def registered_pep(
        request: Request,
        credentials: Annotated[
            HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))
        ],
    ) -> None:
        if credentials is None or _digest(credentials.credentials) not in peps:
            peer = request.client.host if request.client else None
            log.warning("authz API call without a registered PEP credential from %s", peer)
            raise Rejected(401, "UNAUTHENTICATED", "A registered PEP credential is required.")

    errors = {"model": Error, "description": "400 INVALID_ARGUMENT or 401 UNAUTHENTICATED"}
    authz = APIRouter(
        prefix="/authz/v1", dependencies=[Depends(registered_pep)], responses={"4XX": errors}
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

    api = FastAPI(title="Knowledge Platform API", version="1")
    api.include_router(authz)

    @api.exception_handler(Rejected)
    async def rejected(request: Request, error: Rejected) -> JSONResponse:
        return _error(error.code, error.status, error.message)

    @api.exception_handler(RequestValidationError)
    async def invalid(request: Request, error: RequestValidationError) -> JSONResponse:
        first = error.errors()[0]
        where = ".".join(map(str, first["loc"]))
        return _error(400, "INVALID_ARGUMENT", f"{where}: {first['msg']}")

    return api


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _error(code: int, status: str, message: str) -> JSONResponse:
    details = [ErrorInfo(reason=status)]
    body = Error(error=Status(code=code, status=status, message=message, details=details))
    return JSONResponse(body.model_dump(by_alias=True), status_code=code)
