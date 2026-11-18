"""Resource records (#114, authorization design §6.1, ADR-0013): a Source registers its own keys.

Within a tenant a Resource is its Source and that Source's key. The full identifier names both;
the decision interface, a Document's binding and a reader's copy carry it, and a Source's own
calls carry the key alone. It carries no tenant: one deployment serves one tenant (authorization
design Q7).
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import quote, unquote

from psycopg import AsyncConnection
from pydantic import AfterValidator, BaseModel
from pydantic.json_schema import SkipJsonSchema


def resource_id(source_id: str, key: str) -> str:
    """The full identifier: the Source, percent-encoded so it holds no `/`, then `/` and the key
    as it is. `km` and `hr-all` give `km/hr-all`."""
    return f"{quote(source_id, safe='')}/{key}"


def source_and_key(full_id: str) -> tuple[str, str]:
    """The Source and the key that resource_id() made `full_id` from; ValueError for a string
    it cannot have made."""
    encoded, _, key = full_id.partition("/")
    source_id = unquote(encoded)
    if not (source_id and key) or resource_id(source_id, key) != full_id:
        raise ValueError(f"not a Resource identifier: {full_id!r}")
    return source_id, key


class Resource(BaseModel, frozen=True):
    """A Resource as its Source sees it: by its key."""

    key: str
    name: str | SkipJsonSchema[None] = None
    created_at: Annotated[datetime, AfterValidator(lambda at: at.astimezone(UTC))]


_INSERT = """
INSERT INTO authz.resource (resource_id, tenant_id, name, created_by_source)
VALUES (%s, %s, %s, %s)
ON CONFLICT (resource_id) DO NOTHING
RETURNING name, created_at
"""

_CHANGE = """
INSERT INTO authz.relation_change (change_id, tenant_id, resource_id, op, actor_source_id,
                                   actor_credential_id)
VALUES (%s, %s, %s, %s, %s, %s)
"""


async def _change(
    conn: AsyncConnection, op: str, full_id: str, tenant_id: str, source_id: str, credential_id: str
) -> str:
    change_id = f"chg_{uuid.uuid4().hex}"
    await conn.execute(_CHANGE, (change_id, tenant_id, full_id, op, source_id, credential_id))
    return change_id


async def register(
    conn: AsyncConnection,
    *,
    tenant_id: str,
    source_id: str,
    key: str,
    name: str | None,
    credential_id: str,
) -> tuple[Resource, str | None]:
    """Registers the Source's key and returns (the Resource, the change_id of the
    `create_resource` change it records). A key the Source registered before gets no change and
    returns (that Resource, None); a `name` given replaces its display name."""
    full_id = resource_id(source_id, key)
    async with conn.transaction():
        while True:
            if row := await (
                await conn.execute(_INSERT, (full_id, tenant_id, name, source_id))
            ).fetchone():
                change_id = await _change(
                    conn, "create_resource", full_id, tenant_id, source_id, credential_id
                )
                return Resource(key=key, name=row[0], created_at=row[1]), change_id
            if row := await (
                await conn.execute(
                    "UPDATE authz.resource SET name = coalesce(%s, name) WHERE resource_id = %s"
                    " RETURNING name, created_at",
                    (name, full_id),
                )
            ).fetchone():
                return Resource(key=key, name=row[0], created_at=row[1]), None
            # Deleted between the two statements: insert again.


async def get(conn: AsyncConnection, *, source_id: str, key: str) -> Resource | None:
    row = await (
        await conn.execute(
            "SELECT name, created_at FROM authz.resource WHERE resource_id = %s",
            (resource_id(source_id, key),),
        )
    ).fetchone()
    return None if row is None else Resource(key=key, name=row[0], created_at=row[1])


async def list_page(
    conn: AsyncConnection, *, source_id: str, after: str | None, limit: int
) -> list[Resource]:
    """At most `limit` of the Source's Resources, in one fixed order, from the one after the key
    `after` (from the first without it)."""
    rows = await (
        await conn.execute(
            "SELECT resource_id, name, created_at FROM authz.resource"
            " WHERE created_by_source = %s AND resource_id > %s ORDER BY resource_id LIMIT %s",
            (source_id, "" if after is None else resource_id(source_id, after), limit),
        )
    ).fetchall()
    return [Resource(key=source_and_key(row[0])[1], name=row[1], created_at=row[2]) for row in rows]


async def delete(
    conn: AsyncConnection, *, tenant_id: str, source_id: str, key: str, credential_id: str
) -> Literal["deleted", "not_found", "not_empty"]:
    """Deletes the Resource and records a `delete_resource` change, unless a Document without
    Source Deletion applied is bound to it. A Document bound in a transaction that locked the
    Resource's row first (#96, #205) is never left bound to a deleted Resource."""
    full_id = resource_id(source_id, key)
    async with conn.transaction():
        if not await (
            await conn.execute(
                "SELECT 1 FROM authz.resource WHERE resource_id = %s FOR UPDATE", (full_id,)
            )
        ).fetchone():
            return "not_found"
        if await (
            await conn.execute(
                "SELECT 1 FROM document WHERE resource_id = %s AND deleted_at IS NULL LIMIT 1",
                (full_id,),
            )
        ).fetchone():
            return "not_empty"
        await conn.execute("DELETE FROM authz.resource WHERE resource_id = %s", (full_id,))
        await _change(conn, "delete_resource", full_id, tenant_id, source_id, credential_id)
        return "deleted"
