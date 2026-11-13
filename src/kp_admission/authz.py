"""The authorization decision interface and the pilot's allow-all provider (#113, authorization
design §4 and its 2026-11-13 note)."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal, LiteralString, Protocol

from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

Action = Literal["read", "place", "manage"]
Outcome = Literal["allow", "deny", "unavailable"]
Reason = Literal["resource_not_found", "no_relation"]

TIMEOUT_S = 0.5  # authz_timeout (§8)
PAGE_SIZE = 1000  # list_resources (§8)

log = logging.getLogger(__name__)


class Ref(BaseModel, frozen=True):
    """A subject (user, source, client), an actor (client) or a Resource (resource)."""

    type: Literal["user", "source", "client", "resource"]
    id: str = Field(min_length=1)


class Decision(BaseModel, frozen=True):
    """One decision; the provider keeps no record of it (Q2). `reason` is set on a deny only and
    is for operators, never for a PEP's caller (E4). A `list_resources` decision has no
    `resource`, and has `resource_ids` unless it is unavailable."""

    decision_id: str
    outcome: Outcome
    evaluated_at: datetime
    valid_until: datetime  # equal to evaluated_at: no reuse (§8)
    decided_by: str
    subject: Ref
    actor: Ref | None
    actor_verified: bool = False  # identity stage P0: the actor is recorded, not evaluated
    action: Action
    resource: Ref | None
    trace_id: str
    reason: Reason | None = None
    resource_ids: list[str] | None = None
    next_cursor: str | None = None


class Authorizer(Protocol):
    """The PDP (§4.1). Neither call raises: a decision that cannot be made is `unavailable`."""

    async def check(
        self,
        subject: Ref,
        action: Action,
        resource_id: str,
        *,
        actor: Ref | None = None,
        trace_id: str,
    ) -> Decision: ...

    async def list_resources(
        self,
        subject: Ref,
        action: Action,
        *,
        actor: Ref | None = None,
        cursor: str | None = None,
        trace_id: str,
    ) -> Decision:
        """The Resources on which `subject` may take `action`, PAGE_SIZE at a time; `next_cursor`
        asks for the next page and is None on the last. Pages share no snapshot (§4.1)."""
        ...


def new_decision(
    outcome: Outcome,
    decided_by: str,
    subject: Ref,
    action: Action,
    resource_id: str | None,
    actor: Ref | None,
    trace_id: str,
    **fields,
) -> Decision:
    now = datetime.now(UTC)
    return Decision(
        decision_id=f"dec_{uuid.uuid4().hex}",
        outcome=outcome,
        evaluated_at=now,
        valid_until=now,
        decided_by=decided_by,
        subject=subject,
        actor=actor,
        action=action,
        resource=None if resource_id is None else Ref(type="resource", id=resource_id),
        trace_id=trace_id,
        **fields,
    )


class AllowAll:
    """The pilot provider: every subject may take every action on every Resource that exists.
    Selectable only in pilot configuration (#113)."""

    decided_by = "allow-all/model-1"

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool
        self._cancelled: set[asyncio.Task] = set()

    async def check(
        self,
        subject: Ref,
        action: Action,
        resource_id: str,
        *,
        actor: Ref | None = None,
        trace_id: str,
    ) -> Decision:
        args = (self.decided_by, subject, action, resource_id, actor, trace_id)
        found = await self._fetch(
            "SELECT 1 FROM authz.resource WHERE resource_id = %s", (resource_id,)
        )
        if found is None:
            return new_decision("unavailable", *args)
        if found:
            return new_decision("allow", *args)
        return new_decision("deny", *args, reason="resource_not_found")

    async def list_resources(
        self,
        subject: Ref,
        action: Action,
        *,
        actor: Ref | None = None,
        cursor: str | None = None,
        trace_id: str,
    ) -> Decision:
        args = (self.decided_by, subject, action, None, actor, trace_id)
        # One tenant per deployment (Q7), so every row is the tenant's.
        rows = await self._fetch(
            "SELECT resource_id FROM authz.resource WHERE resource_id > %s"
            " ORDER BY resource_id LIMIT %s",
            (cursor or "", PAGE_SIZE + 1),
        )
        if rows is None:
            return new_decision("unavailable", *args)
        ids = [row[0] for row in rows[:PAGE_SIZE]]
        more = len(rows) > PAGE_SIZE
        return new_decision("allow", *args, resource_ids=ids, next_cursor=ids[-1] if more else None)

    async def _fetch(self, query: LiteralString, params: tuple) -> list[tuple] | None:
        """The rows of `query`, or None when it fails or outlasts TIMEOUT_S. It does not wait for
        the cancelled query to end: psycopg waits up to 10 s for a server that stopped answering."""

        async def fetch() -> list[tuple]:
            async with self._pool.connection() as conn:
                return await (await conn.execute(query, params)).fetchall()

        task = asyncio.create_task(fetch())
        try:
            async with asyncio.timeout(TIMEOUT_S):
                return await asyncio.shield(task)
        except Exception as error:
            log.warning("authz lookup failed: %s", type(error).__name__)
            return None
        finally:
            if not task.done():
                task.cancel()
                self._cancelled.add(task)  # held until it ends, as asyncio asks of its caller
                task.add_done_callback(self._cancelled.discard)
