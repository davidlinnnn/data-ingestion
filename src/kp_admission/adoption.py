"""The adoption record (admission spec §3): which Processing Profile version a new process request
runs, by the media type of its main file, and the adoption sequence it carries (§10).

One sequence counts every adoption of the deployment, so it rises for every Source at each
adoption: in the pilot no Source pins a version, and current-revision selection compares the
sequences of one document only. Adopting a version supersedes the one adopted before for that
media type; cancelling the adopted version leaves none, with no fall back to an earlier one.
Neither opens a refresh request (#98 does).
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal

import psycopg
import pydantic
from prometheus_client import Gauge
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

log = logging.getLogger(__name__)

_LATEST = """
SELECT adopted_version, sequence, cancelled_at IS NULL FROM adoption
WHERE media_type = %s ORDER BY sequence DESC LIMIT 1 FOR SHARE
"""


async def current(conn: AsyncConnection, media_type: str) -> tuple[str, int] | None:
    """(adopted_version, adoption_sequence) for `media_type`, or None when none is adopted. In a
    transaction its row stays locked until the end, so a cancel waits for the requests made under
    it and none is made under a version after its cancel returns."""
    while True:
        row = await (await conn.execute(_LATEST, (media_type,))).fetchone()
        newest = await (
            await conn.execute(
                "SELECT max(sequence) FROM adoption WHERE media_type = %s", (media_type,)
            )
        ).fetchone()
        # A read that waited on a declared adoption's lock returns the record it superseded.
        if not row or not newest or newest[0] == row[1]:
            return (row[0], row[1]) if row and row[2] else None


async def adopt(
    conn: AsyncConnection, *, tenant_id: str, media_type: str, version: str, refresh: Any = "none"
) -> int:
    """Adopts `version` for `media_type` with the refresh scope `refresh` (#98) and returns its
    adoption sequence. The version adopted already, with that scope, keeps its sequence."""
    while True:
        if (found := await current(conn, media_type)) and found[0] == version:
            if await refresh_scope(conn, media_type) == refresh:
                return found[1]
        try:
            row = await (
                await conn.execute(
                    "INSERT INTO adoption (sequence, tenant_id, media_type, adopted_version,"
                    " refresh) SELECT coalesce(max(sequence), 0) + 1, %s, %s, %s, %s"
                    " FROM adoption RETURNING sequence",
                    (tenant_id, media_type, version, Jsonb(refresh)),
                )
            ).fetchone()
            assert row
            return row[0]
        except psycopg.errors.UniqueViolation:
            pass  # a concurrent adoption took the sequence: count again


async def cancel(conn: AsyncConnection, *, media_type: str, version: str) -> bool:
    """Cancels the adoption of `version` for `media_type` when it is the adopted one; False when
    it is not."""
    cursor = await conn.execute(
        "UPDATE adoption SET cancelled_at = now() WHERE sequence = ("
        " SELECT max(sequence) FROM adoption WHERE media_type = %s)"
        " AND adopted_version = %s AND cancelled_at IS NULL",
        (media_type, version),
    )
    return cursor.rowcount == 1


async def withdrawn(conn: AsyncConnection, media_type: str) -> set[str]:
    """The Processing Profile versions withdrawn for `media_type` (#57 B6), as the transaction
    reads them now."""
    cursor = await conn.execute(
        "SELECT version FROM withdrawn_version WHERE media_type = %s", (media_type,)
    )
    return {version for (version,) in await cursor.fetchall()}


async def adopted_for(conn: AsyncConnection, version: str) -> str | None:
    """The version adopted now for the media type `version` was adopted for, or None when it has
    none: a version names one profile, so one media type (§3)."""
    row = await (
        await conn.execute(
            "SELECT adopted_version, cancelled_at IS NULL FROM adoption WHERE media_type ="
            " (SELECT media_type FROM adoption WHERE adopted_version = %s LIMIT 1)"
            " ORDER BY sequence DESC LIMIT 1",
            (version,),
        )
    ).fetchone()
    return row[0] if row and row[1] else None


# Declarative adoption (#261): the deployment values' entries, applied by a CronJob after a gate.

NONE = "none"  # the version of a declared cancellation
CHECK_PREFIX = "chk_"  # the gate's test workflow IDs; admission keeps no request for them
Version = Annotated[str, pydantic.StringConstraints(pattern=r"^[a-z0-9-]+@[1-9][0-9]*$")]


class MadeBy(pydantic.BaseModel, extra="forbid"):
    made_by: list[Version] = pydantic.Field(min_length=1)


Refresh = Literal["none", "all"] | MadeBy  # which documents #98 refreshes after an adoption


class Declared(pydantic.BaseModel, extra="forbid"):
    """One media type's entry of the deployment values' `adoption` mapping."""

    declaration: pydantic.StrictInt = pydantic.Field(ge=1)
    version: Version | Literal["none"]
    refresh: Refresh  # required: no default scope (#57 B8)
    withdrawn: list[Version] = []
    kept: list[Version] = []

    @pydantic.model_validator(mode="after")
    def _cancel_refreshes_nothing(self) -> "Declared":
        if self.version == NONE and self.refresh != "none":
            raise ValueError("a cancellation refreshes nothing")
        return self


@dataclass(frozen=True)
class Applied:
    """What one run did with one media type's declaration: `applied`, `skipped` (applied
    already), `waiting` (at the gate) or `refused`, with a reason code."""

    media_type: str
    declaration: int | None
    version: str | None
    result: Literal["applied", "skipped", "waiting", "refused"]
    reason: str = ""
    sequence: int | None = None


Gate = Callable[[str, str, bool], Awaitable[tuple[bool, str]]]
"""(media_type, version, adopted before) -> (passed, reason): whether the version may be adopted
now, and a reason code for waiting or for passing on a fallback."""


async def apply(
    conn: AsyncConnection, tenant_id: str, declared: dict[str, Any], gate: Gate
) -> list[Applied]:
    """Applies each media type's declaration on an autocommit connection, in a transaction of its
    own, once it passes the rules and `gate`, and logs one line for each. A media type that has an
    adoption record but no declaration is refused; so is a declaration that fails the rules, and
    then nothing of it is written. A gate that raises leaves its media type `waiting` with reason
    `gate_unavailable`."""
    rows = await conn.execute("SELECT DISTINCT media_type FROM adoption")
    results = []
    for media_type in sorted({m for (m,) in await rows.fetchall()} | set(declared)):
        result = await _apply_one(conn, tenant_id, media_type, declared.get(media_type), gate)
        log.log(
            logging.WARNING if result.result == "refused" else logging.INFO,
            "adoption %s: %s",
            result.result,
            result.reason or "-",
            extra={"correlation": {"media_type": result.media_type,
                                   "declaration": result.declaration, "version": result.version,
                                   "result": result.result, "reason": result.reason}},
        )  # fmt: skip
        await _record(conn, tenant_id, result)
        results.append(result)
    return results


async def _record(conn: AsyncConnection, tenant_id: str, result: "Applied") -> None:
    values = (tenant_id, result.media_type, result.result, result.reason)
    await conn.execute(
        "INSERT INTO adoption_run (tenant_id, media_type, result, reason, runs)"
        " VALUES (%s, %s, %s, %s, 1) ON CONFLICT (media_type, result, reason)"
        " DO UPDATE SET runs = adoption_run.runs + 1",
        values,
    )
    await conn.execute(
        "INSERT INTO adoption_status (tenant_id, media_type, result, reason, since)"
        " VALUES (%s, %s, %s, %s, now()) ON CONFLICT (media_type) DO UPDATE SET"
        " result = EXCLUDED.result, reason = EXCLUDED.reason, since = CASE"
        " WHEN adoption_status.result = EXCLUDED.result THEN adoption_status.since ELSE now() END",
        values,
    )


runs = Gauge(
    "kp_admission_adoption_runs",
    "apply-adoption runs by media type, result and reason; it only rises",
    ["media_type", "result", "reason"],
)
status = Gauge(
    "kp_admission_adoption_status",
    "1 for each media type's result and reason in the latest apply-adoption run",
    ["media_type", "result", "reason"],
)
status_age = Gauge(
    "kp_admission_adoption_status_seconds",
    "how long each media type has had its latest result, such as waiting at the gate",
    ["media_type"],
)


async def observe(conn: AsyncConnection) -> None:
    """Sets the adoption gauges from apply-adoption's records (the api measures them)."""
    counted = await (
        await conn.execute("SELECT media_type, result, reason, runs FROM adoption_run")
    ).fetchall()
    latest = await (
        await conn.execute(
            "SELECT media_type, result, reason,"
            " extract(epoch FROM now() - since)::float FROM adoption_status"
        )
    ).fetchall()
    runs.clear()
    for media_type, result, reason, n in counted:
        runs.labels(media_type, result, reason).set(n)
    status.clear()
    status_age.clear()
    for media_type, result, reason, age in latest:
        status.labels(media_type, result, reason).set(1)
        status_age.labels(media_type).set(age)


async def _apply_one(
    conn: AsyncConnection, tenant_id: str, media_type: str, raw: Any, gate: Gate
) -> Applied:
    if raw is None:
        return Applied(media_type, None, None, "refused", "media_type_missing")
    try:
        entry = Declared.model_validate(raw)
    except pydantic.ValidationError:
        number = raw.get("declaration") if isinstance(raw, dict) else None
        return Applied(media_type, number if isinstance(number, int) else None, None, "refused",
                       "bad_declaration")  # fmt: skip
    if verdict := await _verdict(conn, media_type, entry):
        return verdict
    passed, reason = (True, "")
    if entry.version != NONE:
        # Adopted through the gate before: the local adopt command's rows do not count.
        adopted = await conn.execute(
            "SELECT 1 FROM adoption WHERE media_type = %s AND adopted_version = %s"
            " AND declaration IS NOT NULL",
            (media_type, entry.version),
        )
        before = bool(await adopted.fetchone())
        try:
            passed, reason = await gate(media_type, entry.version, before)
        except Exception:
            log.warning("adoption gate of %s failed", media_type, exc_info=True)
            passed, reason = False, "gate_unavailable"
    if not passed:
        return Applied(media_type, entry.declaration, entry.version, "waiting", reason)
    async with conn.transaction():
        # Waits for the declarations that read the adopted version, as cancel does.
        await conn.execute(
            "SELECT 1 FROM adoption WHERE media_type = %s ORDER BY sequence DESC LIMIT 1"
            " FOR UPDATE",
            (media_type,),
        )
        while True:
            # Again inside the lock: a pod that waited at the gate must not apply a stale entry.
            if verdict := await _verdict(conn, media_type, entry):
                return verdict
            try:
                async with conn.transaction():
                    sequence = await _write(conn, tenant_id, media_type, entry)
                return Applied(
                    media_type, entry.declaration, entry.version, "applied", reason, sequence
                )
            except psycopg.errors.UniqueViolation:
                pass  # another adoption took the sequence, or another pod this declaration


async def _verdict(conn: AsyncConnection, media_type: str, entry: Declared) -> Applied | None:
    """The run's result when `entry` is not to be applied; None when it is."""

    def refused(reason: str) -> Applied:
        return Applied(media_type, entry.declaration, entry.version, "refused", reason)

    state = await (await conn.execute(_STATE, {"media_type": media_type})).fetchone()
    assert state
    highest, version, refresh, withdrawn = state
    if highest is not None and entry.declaration <= highest:
        # Compared with the record in effect, so values reverted whole are refused, not skipped.
        same = (version or NONE, refresh, set(withdrawn)) == (
            entry.version,
            _dump(entry.refresh),
            set(entry.withdrawn),
        )
        if same:
            return Applied(media_type, entry.declaration, entry.version, "skipped")
        return refused("declaration_not_raised")
    if entry.version in {*withdrawn, *entry.withdrawn}:
        return refused("version_withdrawn")
    if not set(withdrawn) <= set(entry.withdrawn):
        return refused("withdrawn_removed")
    if entry.version != NONE:
        # A downgrade states what becomes of each higher version's documents (#57 B6).
        name, number = entry.version.split("@")
        rows = await conn.execute(
            "SELECT DISTINCT adopted_version FROM adoption"
            " WHERE media_type = %s AND adopted_version LIKE %s",
            (media_type, f"{name}@%"),
        )
        higher = {v for (v,) in await rows.fetchall() if int(v.split("@")[1]) > int(number)}
        if higher - {*entry.withdrawn, *entry.kept}:
            return refused("downgrade_undeclared")
    return None


# The highest declaration applied, then the record in effect and the withdrawn versions.
_STATE = """
SELECT (SELECT max(declaration) FROM adoption WHERE media_type = %(media_type)s),
       CASE WHEN a.cancelled_at IS NULL THEN a.adopted_version END, a.refresh,
       ARRAY(SELECT version FROM withdrawn_version WHERE media_type = %(media_type)s)
FROM (SELECT 1) one
LEFT JOIN LATERAL (
    SELECT * FROM adoption WHERE media_type = %(media_type)s ORDER BY sequence DESC LIMIT 1
) a ON true
"""


async def refresh_scope(conn: AsyncConnection, media_type: str) -> Any:
    """The refresh scope of `media_type`'s latest adoption (#98): "none", "all" or {"made_by":
    [version, ...]}; None when it has no adoption record."""
    row = await (
        await conn.execute(
            "SELECT refresh FROM adoption WHERE media_type = %s ORDER BY sequence DESC LIMIT 1",
            (media_type,),
        )
    ).fetchone()
    return row[0] if row else None


async def _write(conn: AsyncConnection, tenant_id: str, media_type: str, entry: Declared) -> int:
    version = None if entry.version == NONE else entry.version
    row = await (
        await conn.execute(
            "INSERT INTO adoption (sequence, tenant_id, media_type, adopted_version,"
            " cancelled_at, declaration, refresh)"
            " SELECT coalesce(max(sequence), 0) + 1, %s, %s, %s,"
            " CASE WHEN %s THEN now() END, %s, %s FROM adoption RETURNING sequence",
            (
                tenant_id,
                media_type,
                version,
                version is None,
                entry.declaration,
                Jsonb(_dump(entry.refresh)),
            ),
        )  # fmt: skip
    ).fetchone()
    assert row
    await conn.execute(
        "INSERT INTO withdrawn_version (tenant_id, media_type, version)"
        " SELECT %s, %s, unnest(%s::text[]) ON CONFLICT DO NOTHING",
        (tenant_id, media_type, entry.withdrawn),
    )
    return row[0]


def _dump(refresh: str | MadeBy) -> Any:
    return refresh if isinstance(refresh, str) else refresh.model_dump()
