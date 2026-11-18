"""The Change Feed on PostgreSQL (#126, ADR-0009, canonical consumption DR §2 A1–A6).

What the feed promises its readers: every committed change appears, changes of one Document in
commit order, within a bounded delay. The tests do not check an order across Documents."""

import asyncio
import random
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from prometheus_client import REGISTRY

from kp_admission import feed
from tests.admission.conftest import TEMPLATE
from tests.admission.support import revision

pytestmark = pytest.mark.docker


async def test_concurrent_writes_reach_the_feed_once_each_where_a_sequence_cursor_skips_some(
    conn, dsn
):
    """1,000 transactions write a fact, then its event, and commit after a random wait. A reader
    that follows the feed during the writes sees each committed event exactly once; a
    sequence-only cursor (the negative control, ADR-0009 round 1) skips some."""
    uids = [(await revision(conn))[0] for _ in range(20)]
    committed: list[str] = []
    writing = True
    rng = random.Random(126)

    async def writer(worker: int) -> None:
        async with await psycopg.AsyncConnection.connect(dsn) as own:
            for i in range(50):
                uid = uids[(worker + i) % len(uids)]
                rollback = rng.random() < 0.05
                async with own.transaction() as tx:
                    await own.execute(
                        "UPDATE document SET title = %s WHERE document_uid = %s", (str(i), uid)
                    )
                    await asyncio.sleep(rng.uniform(0, 0.01))
                    position = await feed.append(
                        own,
                        "current_revision_changed",
                        tenant_id="t1",
                        source_id="s1",
                        document_uid=uid,
                        priority="normal",
                    )
                    await asyncio.sleep(rng.uniform(0, 0.03))
                    if rollback:
                        raise psycopg.Rollback(tx)
                if not rollback:
                    committed.append(position)

    async def follow() -> list[str]:
        seen: list[str] = []
        async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as own:
            cursor = await feed.head(own)
            while True:
                done = not writing
                page, cursor = await feed.read(own, cursor, limit=100)
                seen += [event.position for event in page]
                if done and not page:
                    return seen
                await asyncio.sleep(0.005)

    async def follow_sequence() -> set[int]:
        seen: set[int] = set()
        last = 0
        while True:
            done = not writing
            rows = await (
                await conn.execute(
                    "SELECT seq FROM change_feed WHERE seq > %s"
                    " AND xid < pg_snapshot_xmin(pg_current_snapshot()) ORDER BY seq LIMIT 100",
                    (last,),
                )
            ).fetchall()
            for (seq,) in rows:
                seen.add(seq)
                last = seq
            if done and not rows:
                return seen
            await asyncio.sleep(0.005)

    readers = asyncio.gather(follow(), follow_sequence())
    await asyncio.gather(*(writer(w) for w in range(20)))
    writing = False
    seen, by_sequence = await readers

    assert 900 < len(committed) < 1000
    assert sorted(seen) == sorted(committed)
    every = {seq for (seq,) in await (await conn.execute("SELECT seq FROM change_feed")).fetchall()}
    assert len(every) == len(committed)
    assert len(every - by_sequence) > 0  # the sequence-only cursor skipped committed events


async def next_revision(conn, uid: str) -> tuple[str, int]:
    """Status intake's write as #97 will make it: the next current Canonical Revision and its
    event in one transaction. Returns (position, revision number)."""
    async with conn.transaction():
        cursor = await conn.execute(
            "UPDATE document SET current_canonical_revision_id ="
            " (coalesce(current_canonical_revision_id::int, 0) + 1)::text"
            " WHERE document_uid = %s RETURNING current_canonical_revision_id::int, source_id",
            (uid,),
        )
        number, source_id = await cursor.fetchone() or (0, "")
        await asyncio.sleep(random.uniform(0, 0.01))
        position = await feed.append(
            conn,
            "current_revision_changed",
            tenant_id="t1",
            source_id=source_id,
            document_uid=uid,
            priority="normal",
        )
        await asyncio.sleep(random.uniform(0, 0.01))
    return position, number


async def test_a_state_read_after_a_feed_position_is_never_older_than_that_position(conn, dsn):
    """Read-your-feed (A6) under concurrent writes: each event's state read, made with that event's
    position as at_least, shows that revision or a newer one."""
    uids = [(await revision(conn))[0] for _ in range(5)]
    written: dict[str, int] = {}
    writing = True

    async def writer(worker: int) -> None:
        async with await psycopg.AsyncConnection.connect(dsn) as own:
            for i in range(40):
                position, number = await next_revision(own, uids[(worker + i) % len(uids)])
                written[position] = number

    async def follow() -> list[tuple[int, int]]:
        checked: list[tuple[int, str]] = []
        cursor = await feed.head(conn)
        while True:
            done = not writing
            page, cursor = await feed.read(conn, cursor, limit=20)
            for event in page:
                state = await feed.document_state(conn, event.document_uid or "", event.position)
                assert state and state.current
                checked.append((int(state.current.canonical_revision_id), event.position))
            if done and not page:
                return [(seen, written[position]) for seen, position in checked]
            await asyncio.sleep(0.002)

    reader = asyncio.create_task(follow())
    await asyncio.gather(*(writer(w) for w in range(10)))
    writing = False
    checked = await reader

    assert len(checked) == 400
    assert all(seen >= number for seen, number in checked)
    assert any(seen > number for seen, number in checked)  # the state was newer than some events


async def test_a_state_read_past_what_has_committed_is_refused(conn, dsn):
    uid, _ = await revision(conn)
    async with await psycopg.AsyncConnection.connect(dsn) as writer, writer.transaction():
        position = await feed.append(
            writer,
            "current_revision_changed",
            tenant_id="t1",
            source_id="s1",
            document_uid=uid,
            priority="normal",
        )

        with pytest.raises(feed.Behind):
            await feed.document_state(conn, uid, position)

    assert await feed.document_state(conn, uid, position)


async def test_a_deleted_document_reads_as_deleted_and_an_unknown_one_as_none(conn):
    uid, _ = await revision(conn)
    await conn.execute("UPDATE document SET deleted_at = now() WHERE document_uid = %s", (uid,))

    state = await feed.document_state(conn, uid, None)

    assert state
    assert (state.status, state.current, state.resource_id) == ("deleted", None, "res_1")
    assert state.copy_of is None
    assert await feed.document_state(conn, "doc_unknown", None) is None


async def write_fact(conn, kind: feed.Kind, uid: str) -> None:
    """The fact behind each event, as its owner writes it (#97, #98, #205, this ticket), with
    the event in the same transaction."""
    if kind == "source_profile_changed":
        await feed.set_profile(conn, tenant_id="t1", source_id="s1", projections=["retrieval"])
        return
    fact = {
        "current_revision_changed": "current_canonical_revision_id = 'crv_2'",
        "document_deleted": "deleted_at = now()",
        "inclusion_changed": "resource_id = 'res_2'",
    }[kind]
    await conn.execute(f"UPDATE document SET {fact} WHERE document_uid = %s", (uid,))
    await feed.append(
        conn, kind, tenant_id="t1", source_id="s1", document_uid=uid, priority="narrowing"
    )


async def facts(conn, uid: str) -> tuple:
    return (await feed.document_state(conn, uid, None), await feed.profile(conn, "s1"))


KINDS: list[feed.Kind] = [
    "current_revision_changed",
    "document_deleted",
    "inclusion_changed",
    "source_profile_changed",
]


@pytest.mark.parametrize("kind", KINDS)
async def test_when_the_fact_fails_to_commit_there_is_no_event(conn, kind: feed.Kind):
    uid, _ = await revision(conn)
    start, before = await feed.head(conn), await facts(conn, uid)

    with pytest.raises(ZeroDivisionError):
        async with conn.transaction():
            await write_fact(conn, kind, uid)
            raise ZeroDivisionError  # the owner's transaction fails after both writes

    assert await facts(conn, uid) == before
    assert await feed.read(conn, start, limit=10) == ([], start)


@pytest.mark.parametrize("kind", KINDS)
async def test_when_the_event_fails_to_append_the_fact_rolls_back(conn, kind: feed.Kind):
    uid, _ = await revision(conn)
    before = await facts(conn, uid)
    await conn.execute(
        "CREATE FUNCTION refuse() RETURNS trigger LANGUAGE plpgsql AS"
        " $$ BEGIN RAISE EXCEPTION 'injected'; END $$;"
        " CREATE TRIGGER refuse BEFORE INSERT ON change_feed"
        " FOR EACH ROW EXECUTE FUNCTION refuse()"
    )

    with pytest.raises(psycopg.errors.RaiseException):
        async with conn.transaction():
            await write_fact(conn, kind, uid)

    assert await facts(conn, uid) == before


async def test_an_event_outside_a_transaction_is_refused(conn):
    uid, _ = await revision(conn)
    with pytest.raises(RuntimeError):
        await feed.append(
            conn,
            "document_deleted",
            tenant_id="t1",
            source_id="s1",
            document_uid=uid,
            priority="narrowing",
        )


async def test_a_profile_change_is_an_event_whose_position_is_the_profile_seq(conn):
    start = await feed.head(conn)

    first = await feed.set_profile(conn, tenant_id="t1", source_id="s1", projections=["retrieval"])
    same = await feed.set_profile(conn, tenant_id="t1", source_id="s1", projections=["retrieval"])
    wider = await feed.set_profile(
        conn, tenant_id="t1", source_id="s1", projections=["retrieval", "wiki"]
    )

    events, _ = await feed.read(conn, start, limit=10)
    assert [(e.kind, e.source_id, e.document_uid, e.priority) for e in events] == [
        ("source_profile_changed", "s1", None, "background")
    ] * 2
    assert same == first
    assert [e.position for e in events] == [first, wider]
    assert await feed.profile(conn, "s1") == feed.Profile(
        source_id="s1", projections=["retrieval", "wiki"], profile_seq=wider
    )
    assert await feed.profile(conn, "s2") is None


async def test_a_cursor_moves_forward_or_stays_and_a_step_back_returns_the_platform_position(
    conn,
):
    uid, _ = await revision(conn)
    start = await feed.head(conn)
    async with conn.transaction():
        await write_fact(conn, "document_deleted", uid)
    [event], end = await feed.read(conn, start, limit=10)

    await feed.report_cursor(conn, "retrieval", start)
    await feed.report_cursor(conn, "retrieval", end)
    await feed.report_cursor(conn, "retrieval", end)  # a repeated report is no step back
    with pytest.raises(feed.Backwards) as backwards:
        await feed.report_cursor(conn, "retrieval", start)
    await feed.report_cursor(conn, "wiki", start)  # each projection has its own

    assert backwards.value.position == end == event.position


async def test_a_cursor_ahead_of_the_feed_is_refused(conn, dsn):
    uid, _ = await revision(conn)
    async with await psycopg.AsyncConnection.connect(dsn) as writer, writer.transaction():
        uncommitted = await feed.append(
            writer,
            "document_deleted",
            tenant_id="t1",
            source_id="s1",
            document_uid=uid,
            priority="narrowing",
        )
        with pytest.raises(ValueError):
            await feed.report_cursor(conn, "retrieval", uncommitted)
    with pytest.raises(ValueError):
        await feed.report_cursor(conn, "retrieval", "not-a-position")


async def test_bootstrap_lists_the_sources_and_pages_each_one_s_live_documents_by_key(conn):
    await feed.set_profile(conn, tenant_id="t1", source_id="s1", projections=["retrieval"])
    await feed.set_profile(conn, tenant_id="t1", source_id="s2", projections=["wiki"])
    live = sorted([(await revision(conn))[0] for _ in range(5)])
    gone, _ = await revision(conn)
    await revision(conn, source_id="s2")
    await conn.execute("UPDATE document SET deleted_at = now() WHERE document_uid = %s", (gone,))

    pages, after = [], None
    while True:
        page = await feed.list_documents(conn, "s1", after, limit=2)
        pages.append(page)
        if len(page) < 2:
            break
        after = page[-1]

    assert await feed.list_sources(conn) == ["s1", "s2"]
    assert pages == [live[:2], live[2:4], live[4:]]


async def test_retention_drops_months_past_90_days_and_expires_the_cursors_they_held(conn):
    uid, _ = await revision(conn)
    before = await feed.head(conn)
    async with conn.transaction():
        await write_fact(conn, "current_revision_changed", uid)
    _, last = await feed.read(conn, before, limit=10)
    now = datetime.now(UTC)

    kept = await feed.retain(conn, now)
    later = await feed.retain(conn, now + timedelta(days=200))
    await feed.retain(conn, now)  # the months of the real clock again, for the writes below

    assert kept == {"created": [], "dropped": []}
    assert len(later["created"]) == 2
    assert f"change_feed_{now:%Y%m}" in later["dropped"]
    with pytest.raises(feed.CursorExpired):
        await feed.read(conn, before, limit=10)
    assert await feed.read(conn, last, limit=10) == ([], last)  # it missed nothing
    async with conn.transaction():
        await write_fact(conn, "document_deleted", uid)
    [deleted], _ = await feed.read(conn, last, limit=10)
    assert deleted.kind == "document_deleted"


async def test_a_long_transaction_and_a_lagging_consumer_show_in_the_metrics(conn, dsn):
    uid, _ = await revision(conn)
    start = await feed.head(conn)
    await feed.report_cursor(conn, "retrieval", start)
    await feed.report_cursor(conn, "wiki", start)
    async with conn.transaction():
        await write_fact(conn, "document_deleted", uid)
    _, end = await feed.read(conn, start, limit=10)
    await feed.report_cursor(conn, "wiki", end)
    quiet = await feed.observe(conn)

    async with await psycopg.AsyncConnection.connect(dsn) as holder, holder.transaction():
        await holder.execute("SELECT pg_current_xact_id()")  # holds the snapshot xmin
        await asyncio.sleep(1.2)
        held = await feed.observe(conn)

    assert 0 <= quiet.oldest_xmin_age_s < 1
    assert 1.2 <= held.oldest_xmin_age_s < 10
    assert REGISTRY.get_sample_value("kp_feed_oldest_xmin_age_seconds") == held.oldest_xmin_age_s
    assert held.lag_s["wiki"] == 0
    assert 1.2 <= held.lag_s["retrieval"] < 10
    assert (
        REGISTRY.get_sample_value("kp_feed_consumer_lag_seconds", {"projection": "retrieval"})
        == held.lag_s["retrieval"]
    )


async def test_the_schema_sets_the_long_transaction_timeouts_on_its_database(postgres):
    async with await psycopg.AsyncConnection.connect(postgres) as base:
        cursor = await base.execute(
            "SELECT setconfig FROM pg_db_role_setting s JOIN pg_database d ON d.oid = s.setdatabase"
            " WHERE d.datname = %s AND s.setrole = 0",
            (TEMPLATE,),
        )
        [(settings,)] = await cursor.fetchall()

    assert set(settings) == {"transaction_timeout=60s", "idle_in_transaction_session_timeout=30s"}
