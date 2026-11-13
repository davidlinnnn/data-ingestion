"""The platform API's HTTP routes. So far the internal authz API (#113, authorization design Q12,
§4.3): the Authorizer for the PEPs outside this process, open only to registered PEP service
identities."""

import hashlib
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

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


def app(authorizer: Authorizer, peps: Mapping[str, str]) -> Starlette:
    """`peps` maps the SHA-256 hex digest of each registered PEP credential to the PEP's service
    identity. A call without a registered credential gets 401, an invalid body 400, and every
    decision 200 whatever its outcome, without the fields that do not apply."""

    def endpoint[T: BaseModel](
        model: type[T], decide: Callable[[T], Awaitable[Decision]]
    ) -> Callable[[Request], Awaitable[JSONResponse]]:
        async def handle(request: Request) -> JSONResponse:
            scheme, _, token = request.headers.get("authorization", "").partition(" ")
            if scheme.lower() != "bearer" or _digest(token) not in peps:
                peer = request.client.host if request.client else None
                log.warning("authz API call without a registered PEP credential from %s", peer)
                return _error(401, "UNAUTHENTICATED", "A registered PEP credential is required.")
            try:
                body = model.model_validate_json(await request.body())
            except ValidationError as error:
                first = error.errors()[0]
                where = ".".join(map(str, first["loc"]))
                return _error(400, "INVALID_ARGUMENT", f"{where}: {first['msg']}")
            return JSONResponse((await decide(body)).model_dump(mode="json", exclude_none=True))

        return handle

    async def check(body: CheckRequest) -> Decision:
        return await authorizer.check(
            body.subject, body.action, body.resource.id, actor=body.actor, trace_id=body.trace_id
        )

    async def list_resources(body: ListRequest) -> Decision:
        return await authorizer.list_resources(
            body.subject, body.action, actor=body.actor, cursor=body.cursor, trace_id=body.trace_id
        )

    return Starlette(
        routes=[
            Route("/authz/v1/check", endpoint(CheckRequest, check), methods=["POST"]),
            Route(
                "/authz/v1/list_resources",
                endpoint(ListRequest, list_resources),
                methods=["POST"],
            ),
        ]
    )


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _error(code: int, status: str, message: str) -> JSONResponse:
    """An AIP-193 error, as admission's (admission spec §4)."""
    info = {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": status,
        "domain": "authz.knowledge-platform",
    }
    body = {"error": {"code": code, "status": status, "message": message, "details": [info]}}
    return JSONResponse(body, status_code=code)
