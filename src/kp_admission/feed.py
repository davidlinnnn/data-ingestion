"""The Change Feed and the governed reads behind it (#126, ADR-0009, canonical consumption DR §2
A1–A7, §3), one function per operation.

What a reader may rely on: every committed change appears in the feed within a bounded delay.
The events of one Document may arrive in any order, so each one means "re-read the current
state". A position is an opaque string. The state read may be newer than the event that led to
it, and a reader may see one change more than once.
On PostgreSQL each event is written in the transaction of its fact and the feed is read in
(transaction id, sequence) order below the snapshot xmin, which ADR-0009 explains.

shortcut: a Source is named by its source_id alone, as the pilot deployment holds one tenant; add
the tenant to these reads when a deployment holds two.
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from prometheus_client import Gauge
from psycopg import AsyncConnection, sql
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb
from pydantic import BaseModel

Kind = Literal[
    "current_revision_changed", "document_deleted", "inclusion_changed", "source_profile_changed"
]
Priority = Literal["narrowing", "normal", "background"]

_POSITION = re.compile(r"[0-9a-f]{32}")
RETENTION = timedelta(days=90)  # DR §2 A4

# Alert thresholds are #78's.
oldest_xmin_age = Gauge(
    "kp_feed_oldest_xmin_age_seconds",
    "age of the oldest open transaction with a transaction id, which holds back the whole feed",
)
consumer_lag = Gauge(
    "kp_feed_consumer_lag_seconds",
    "age of the first feed entry after the projection's cursor; 0 when it has read them all",
    ["projection"],
)


class Event(BaseModel, frozen=True):
    position: str
    kind: Kind
    document_uid: str | None = None  # absent from source_profile_changed
    source_id: str
    priority: Priority
    occurred_at: datetime


class Current(BaseModel, frozen=True):
    source_revision_id: str | None
    canonical_revision_id: str
    # When finalization created the Source Revision, not when it was accepted (#268).
    source_revision_created_at: datetime | None


class State(BaseModel, frozen=True):
    """A Document's current state (DR §3). resource_id is the Resource's full identifier
    (ADR-0013), opaque to readers."""

    resource_id: str
    current: Current | None
    # shortcut: never `withdrawn`: the pilot builds no withdrawal (#56, 2026-11-18); read its
    # record here when a release adds one.
    status: Literal["active", "deleted", "withdrawn"]
    copy_of: None = None  # copies are not in v1 (DR B3)


class Profile(BaseModel, frozen=True):
    """A Source's Knowledge Profile; profile_seq is the position of the event that set it (A2)."""

    source_id: str
    projections: list[str]
    profile_seq: str


class Observed(BaseModel, frozen=True):
    oldest_xmin_age_s: float
    lag_s: dict[str, float]


class CursorExpired(Exception):
    """Entries after the cursor were dropped by retention: bootstrap again (A4)."""


class Backwards(Exception):
    """The report would move the cursor back; the platform's position wins (A3)."""

    def __init__(self, position: str) -> None:
        super().__init__(position)
        self.position = position


class Behind(Exception):
    """The state read does not yet include the at_least position: retry (A6)."""


def _position(xid: str, seq: int) -> str:
    # Fixed-width hex, so positions compare as strings in feed order.
    return f"{int(xid):016x}{seq:016x}"


def _split(position: str) -> tuple[str, int]:
    """(xid, seq) of a position; ValueError when it is not one."""
    if not _POSITION.fullmatch(position):
        raise ValueError("not a feed position")
    return str(int(position[:16], 16)), int(position[16:], 16)


async def append(
    conn: AsyncConnection,
    kind: Kind,
    *,
    tenant_id: str,
    source_id: str,
    priority: Priority,
    document_uid: str | None = None,
) -> str:
    """Appends an event in the caller's open transaction, so it commits or rolls back with the
    fact it records, and returns its position. document_uid is required except for
    source_profile_changed, which has none."""
    if conn.info.transaction_status != TransactionStatus.INTRANS:
        raise RuntimeError("feed.append must run inside the transaction that writes the fact")
    cursor = await conn.execute(
        "INSERT INTO change_feed (tenant_id, kind, source_id, document_uid, priority)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING xid::text, seq",
        (tenant_id, kind, source_id, document_uid, priority),
    )
    xid, seq = await cursor.fetchone() or ("", 0)
    return _position(xid, seq)


async def head(conn: AsyncConnection) -> str:
    """A position no later entry can precede: a new reader's starting point (A4 bootstrap)."""
    cursor = await conn.execute("SELECT pg_snapshot_xmin(pg_current_snapshot())::text")
    [(xmin,)] = await cursor.fetchall()
    return _position(xmin, 0)


async def read(conn: AsyncConnection, cursor: str, limit: int) -> tuple[list[Event], str]:
    """Up to `limit` events after cursor and the cursor after them. Raises CursorExpired when
    retention dropped entries after it, ValueError when it is not a position."""
    xid, seq = _split(cursor)
    rows = await conn.execute(
        "SELECT xid::text, seq, kind, document_uid, source_id, priority, occurred_at"
        " FROM change_feed WHERE (xid, seq) > (%s::xid8, %s)"
        " AND xid < pg_snapshot_xmin(pg_current_snapshot())"
        # Qualified: a bare xid would sort by the text output column of the same name.
        " ORDER BY change_feed.xid, seq LIMIT %s",
        (xid, seq, limit),
    )
    events = [
        Event(
            position=_position(x, s),
            kind=kind,
            document_uid=uid,
            source_id=source,
            priority=priority,
            occurred_at=at,
        )
        for x, s, kind, uid, source, priority, at in await rows.fetchall()
    ]
    # After the read: a drop waits for the read above, and commits with its horizon.
    horizon = await conn.execute("SELECT position FROM change_feed_horizon")
    [(dropped,)] = await horizon.fetchall()
    if cursor < dropped:
        raise CursorExpired
    return events, events[-1].position if events else cursor


async def document_state(
    conn: AsyncConnection, document_uid: str, at_least: str | None
) -> State | None:
    """The Document's state, at least as new as the at_least position; None for a uid the platform
    never had. A deleted Document answers `deleted` (A4 R-a). Raises Behind when the state does not
    yet include at_least, ValueError when it is not a position."""
    if at_least is not None:
        _split(at_least)
    # One statement, so the xmin and the row come from one snapshot.
    cursor = await conn.execute(
        "SELECT pg_snapshot_xmin(pg_current_snapshot())::text, d.resource_id, d.deleted_at,"
        " d.current_source_revision_id, d.current_canonical_revision_id, s.created_at"
        " FROM (VALUES (1)) one LEFT JOIN document d ON d.document_uid = %s"
        " LEFT JOIN source_revision s ON s.source_revision_id = d.current_source_revision_id",
        (document_uid,),
    )
    [
        (xmin, resource_id, deleted_at, source_revision, canonical_revision, created_at)
    ] = await cursor.fetchall()
    if at_least is not None and at_least > _position(xmin, 0):
        raise Behind
    if resource_id is None:
        return None
    if deleted_at is not None:
        return State(resource_id=resource_id, current=None, status="deleted")
    current = (
        Current(
            source_revision_id=source_revision,
            canonical_revision_id=canonical_revision,
            source_revision_created_at=created_at,
        )
        if canonical_revision
        else None
    )
    return State(resource_id=resource_id, current=current, status="active")


async def set_profile(
    conn: AsyncConnection, *, tenant_id: str, source_id: str, projections: list[str]
) -> str:
    """Sets the Source's Knowledge Profile and appends source_profile_changed in one transaction,
    or in a savepoint when the caller has one open, and returns its profile_seq. An unchanged
    profile appends nothing and keeps its profile_seq. It records the profile_seq at which each
    projection joined; one of the Source's first profile joined at none (DR B1)."""
    async with conn.transaction():
        cursor = await conn.execute(
            "SELECT projections, profile_seq, added FROM source"
            " WHERE tenant_id = %s AND source_id = %s FOR UPDATE",
            (tenant_id, source_id),
        )
        if (row := await cursor.fetchone()) and row[0] == projections:
            return row[1]
        await conn.execute(
            "INSERT INTO source (tenant_id, source_id, projections, profile_seq)"
            " VALUES (%s, %s, %s, '') ON CONFLICT (tenant_id, source_id)"
            " DO UPDATE SET projections = excluded.projections",
            (tenant_id, source_id, projections),
        )
        seq = await append(
            conn,
            "source_profile_changed",
            tenant_id=tenant_id,
            source_id=source_id,
            priority="background",
        )
        before, added = (row[0], row[2]) if row else (projections, {})
        joined = {p: added.get(p, "") if p in before else seq for p in projections}
        await conn.execute(
            "UPDATE source SET profile_seq = %s, added = %s"
            " WHERE tenant_id = %s AND source_id = %s",
            (seq, Jsonb(joined), tenant_id, source_id),
        )
        return seq


async def profile(conn: AsyncConnection, source_id: str) -> Profile | None:
    """The Source's Knowledge Profile; None for a Source without one."""
    cursor = await conn.execute(
        "SELECT projections, profile_seq FROM source WHERE source_id = %s", (source_id,)
    )
    row = await cursor.fetchone()
    return Profile(source_id=source_id, projections=row[0], profile_seq=row[1]) if row else None


async def report_cursor(conn: AsyncConnection, projection: str, position: str) -> None:
    """Records the projection's position. Raises Backwards with the recorded position when this one
    is earlier, ValueError when it is not a position or is ahead of every committed entry."""
    _split(position)
    if position > await head(conn):  # the head only moves forward, so it holds for the write
        raise ValueError("position ahead of the feed")
    cursor = await conn.execute(
        "INSERT INTO consumer_cursor (projection, position) VALUES (%s, %s)"
        " ON CONFLICT (projection) DO UPDATE SET position = excluded.position, updated_at = now()"
        " WHERE consumer_cursor.position <= excluded.position RETURNING position",
        (projection, position),
    )
    if await cursor.fetchone() is None:
        recorded = await conn.execute(
            "SELECT position FROM consumer_cursor WHERE projection = %s", (projection,)
        )
        [(platform,)] = await recorded.fetchall()
        raise Backwards(platform)


async def lag_s(conn: AsyncConnection, position: str) -> float:
    """How long the oldest entry after the position has waited, in seconds; 0 when none follows.
    ValueError when it is not a position, or is one the feed has not reached."""
    cursor = await conn.execute(
        "SELECT pg_snapshot_xmin(pg_current_snapshot())::text,"
        " coalesce(extract(epoch FROM now() - (SELECT occurred_at FROM change_feed"
        " WHERE (xid, seq) > (%s::xid8, %s) ORDER BY xid, seq LIMIT 1)), 0)::float",
        _split(position),
    )
    [(xmin, lag)] = await cursor.fetchall()
    if position > _position(xmin, 0):  # as document_state: no read has answered it
        raise ValueError("ahead of the feed")
    return lag


async def list_sources(conn: AsyncConnection) -> list[str]:
    """Every Source with a Knowledge Profile, for bootstrap."""
    cursor = await conn.execute("SELECT source_id FROM source ORDER BY source_id")
    return [source_id for (source_id,) in await cursor.fetchall()]


async def list_documents(
    conn: AsyncConnection, source_id: str, after: str | None, limit: int
) -> list[str]:
    """Up to `limit` uids of the Source's Documents that are not deleted, in key order after
    `after`; a shorter page is the last."""
    cursor = await conn.execute(
        "SELECT document_uid FROM document WHERE source_id = %s AND deleted_at IS NULL"
        " AND document_uid > %s ORDER BY document_uid LIMIT %s",
        (source_id, after or "", limit),
    )
    return [uid for (uid,) in await cursor.fetchall()]


def _month(at: datetime, ahead: int = 0) -> datetime:
    months = at.year * 12 + at.month - 1 + ahead
    return datetime(months // 12, months % 12 + 1, 1, tzinfo=UTC)


async def retain(conn: AsyncConnection, now: datetime) -> dict[str, list[str]]:
    """Creates the partitions of now's month and the two after it, so a missed run stops no write
    for two months, and drops each month whose entries
    are all older than RETENTION, after recording its highest position as the horizon below which
    a cursor is expired. Returns the partitions it created and dropped."""
    now = now.astimezone(UTC)
    done: dict[str, list[str]] = {"created": [], "dropped": []}
    for ahead in (0, 1, 2):
        start = _month(now, ahead)
        name = f"change_feed_{start:%Y%m}"
        cursor = await conn.execute("SELECT to_regclass(%s)", (name,))
        if (await cursor.fetchone() or (None,))[0] is None:
            await conn.execute(
                sql.SQL(
                    "CREATE TABLE {} PARTITION OF change_feed FOR VALUES FROM ({}) TO ({})"
                ).format(sql.Identifier(name), sql.Literal(start), sql.Literal(_month(start, 1)))
            )
            done["created"].append(name)
    cursor = await conn.execute(
        "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid"
        " WHERE i.inhparent = 'change_feed'::regclass ORDER BY c.relname"
    )
    for (name,) in await cursor.fetchall():
        start = datetime.strptime(name.removeprefix("change_feed_"), "%Y%m").replace(tzinfo=UTC)
        if _month(start, 1) > now - RETENTION:
            continue
        async with conn.transaction():
            highest = await conn.execute(
                sql.SQL(
                    "SELECT xid::text, seq FROM {} p ORDER BY p.xid DESC, seq DESC LIMIT 1"
                ).format(sql.Identifier(name))
            )
            if row := await highest.fetchone():
                await conn.execute(
                    "UPDATE change_feed_horizon SET position = greatest(position, %s)",
                    (_position(*row),),
                )
            await conn.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(name)))
        done["dropped"].append(name)
    return done


async def observe(conn: AsyncConnection) -> Observed:
    """Measures the long-transaction guards (A5, G8) and sets their gauges. The xmin age counts
    every database of the instance, whose transaction ids hold back the snapshot xmin alike; the
    sessions of other roles count only when this role may see them (pg_read_all_stats)."""
    cursor = await conn.execute(
        "SELECT coalesce(extract(epoch FROM max(now() - xact_start)), 0)::float"
        " FROM pg_stat_activity WHERE backend_xid IS NOT NULL AND pid <> pg_backend_pid()"
    )
    [(age,)] = await cursor.fetchall()
    lags: dict[str, float] = {}
    cursors = await conn.execute("SELECT projection, position FROM consumer_cursor")
    for projection, position in await cursors.fetchall():
        lags[projection] = await lag_s(conn, position)
    observed = Observed(oldest_xmin_age_s=age, lag_s=lags)
    oldest_xmin_age.set(observed.oldest_xmin_age_s)
    consumer_lag.clear()
    for projection, lag in observed.lag_s.items():
        consumer_lag.labels(projection).set(lag)
    return observed
