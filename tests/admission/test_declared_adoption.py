"""Declarative adoption (#261, admission spec §3): the rules a declaration passes, the gate it
waits on and the one transaction that applies it. The gate is a stand-in here; the Temporal gate
has its own tests."""

import asyncio

import psycopg
import pytest

from kp_admission import adoption

pytestmark = pytest.mark.docker

PDF = "application/pdf"


class Gate:
    """Passes, or waits with `waiting`; records each call."""

    def __init__(self, waiting: str = "") -> None:
        self.waiting = waiting
        self.calls: list[tuple[str, str, bool]] = []

    async def __call__(self, media_type: str, version: str, adopted_before: bool):
        self.calls.append((media_type, version, adopted_before))
        return (False, self.waiting) if self.waiting else (True, "")


def entry(declaration: int, version: str = "paper-pdf@1", **fields):
    return {"declaration": declaration, "version": version, "refresh": "none"} | fields


async def test_a_first_declaration_is_adopted_after_the_gate(conn):
    gate = Gate()

    [result] = await adoption.apply(conn, "t1", {PDF: entry(1)}, gate)

    assert (result.result, result.reason) == ("applied", "")
    assert gate.calls == [(PDF, "paper-pdf@1", False)]
    assert await adoption.current(conn, PDF) == ("paper-pdf@1", result.sequence)


async def test_a_declaration_not_raised_is_skipped_when_it_matches_the_one_in_effect(conn):
    await adoption.apply(conn, "t1", {PDF: entry(1)}, Gate())
    gate = Gate()

    [result] = await adoption.apply(conn, "t1", {PDF: entry(1)}, gate)

    assert (result.result, result.reason, gate.calls) == ("skipped", "", [])


async def test_a_changed_declaration_not_raised_is_refused_and_changes_nothing(conn):
    [first] = await adoption.apply(conn, "t1", {PDF: entry(1)}, Gate())

    [result] = await adoption.apply(conn, "t1", {PDF: entry(1, "paper-pdf@2")}, Gate())

    assert (result.result, result.reason) == ("refused", "declaration_not_raised")
    assert await adoption.current(conn, PDF) == ("paper-pdf@1", first.sequence)


async def test_values_reverted_whole_to_an_older_declaration_are_refused(conn):
    await adoption.apply(conn, "t1", {PDF: entry(1)}, Gate())
    [second] = await adoption.apply(conn, "t1", {PDF: entry(2, "paper-pdf@2")}, Gate())

    [result] = await adoption.apply(conn, "t1", {PDF: entry(1)}, Gate())

    assert (result.result, result.reason) == ("refused", "declaration_not_raised")
    assert await adoption.current(conn, PDF) == ("paper-pdf@2", second.sequence)


async def test_a_raised_declaration_that_only_changes_the_refresh_is_a_new_adoption(conn):
    [first] = await adoption.apply(conn, "t1", {PDF: entry(1)}, Gate())

    [second] = await adoption.apply(conn, "t1", {PDF: entry(2, refresh="all")}, Gate())

    assert second.result == "applied" and second.sequence == (first.sequence or 0) + 1
    assert await adoption.current(conn, PDF) == ("paper-pdf@1", second.sequence)
    assert await adoption.refresh_scope(conn, PDF) == "all"


async def state(conn):
    """Every adoption record and withdrawn version, to show a refusal wrote nothing."""
    rows = await conn.execute("SELECT * FROM adoption ORDER BY sequence")
    withdrawn = await conn.execute("SELECT media_type, version FROM withdrawn_version")
    return await rows.fetchall(), await withdrawn.fetchall()


async def adopted(conn, *versions: str):
    """Declarations 1, 2, … adopting each version in turn."""
    for n, version in enumerate(versions, 1):
        [result] = await adoption.apply(conn, "t1", {PDF: entry(n, version)}, Gate())
        assert result.result == "applied"


@pytest.mark.parametrize(
    ("declared", "reason"),
    [
        (entry(3, "paper-pdf@2", withdrawn=["paper-pdf@2"]), "version_withdrawn"),
        (entry(3, "paper-pdf@1"), "downgrade_undeclared"),
        (entry(3, "paper-pdf@1", kept=["paper-pdf@3"]), "downgrade_undeclared"),
        ({"declaration": 3, "version": "paper-pdf@2"}, "bad_declaration"),
        (entry(3, refresh="some"), "bad_declaration"),
        (entry(3, refresh={"made_by": []}), "bad_declaration"),
        (entry(3, version="paper-pdf@2 "), "bad_declaration"),
        (entry(3, version="none", refresh="all"), "bad_declaration"),
    ],
)
async def test_a_declaration_against_the_rules_is_refused_and_writes_nothing(
    conn, declared, reason
):
    await adopted(conn, "paper-pdf@1", "paper-pdf@2")
    before = await state(conn)

    [result] = await adoption.apply(conn, "t1", {PDF: declared}, Gate())

    assert (result.result, result.reason) == ("refused", reason)
    assert await state(conn) == before


async def test_a_withdrawn_version_stays_withdrawn_and_is_never_adopted_again(conn):
    await adopted(conn, "paper-pdf@1", "paper-pdf@2")
    rollback = entry(
        3, "paper-pdf@1", withdrawn=["paper-pdf@2"], refresh={"made_by": ["paper-pdf@2"]}
    )
    [applied] = await adoption.apply(conn, "t1", {PDF: rollback}, Gate())
    before = await state(conn)

    [removed] = await adoption.apply(conn, "t1", {PDF: entry(4, "paper-pdf@1")}, Gate())
    [again] = await adoption.apply(
        conn, "t1", {PDF: entry(4, "paper-pdf@2", withdrawn=["paper-pdf@2"])}, Gate()
    )

    assert applied.result == "applied"
    assert await adoption.withdrawn(conn, PDF) == {"paper-pdf@2"}
    assert (removed.reason, again.reason) == ("withdrawn_removed", "version_withdrawn")
    assert await state(conn) == before


async def test_a_downgrade_that_keeps_the_higher_version_is_applied(conn):
    await adopted(conn, "paper-pdf@1", "paper-pdf@2")

    [result] = await adoption.apply(
        conn, "t1", {PDF: entry(3, "paper-pdf@1", kept=["paper-pdf@2"])}, Gate()
    )

    assert result.result == "applied" and await adoption.withdrawn(conn, PDF) == set()
    assert await adoption.current(conn, PDF) == ("paper-pdf@1", result.sequence)


async def test_a_downgrade_states_every_higher_version_adopted_before(conn):
    await adopted(conn, "paper-pdf@1", "paper-pdf@2", "paper-pdf@3")

    [partial] = await adoption.apply(
        conn, "t1", {PDF: entry(4, "paper-pdf@1", withdrawn=["paper-pdf@3"])}, Gate()
    )
    [whole] = await adoption.apply(
        conn,
        "t1",
        {PDF: entry(4, "paper-pdf@1", withdrawn=["paper-pdf@3"], kept=["paper-pdf@2"])},
        Gate(),
    )

    assert (partial.reason, whole.result) == ("downgrade_undeclared", "applied")


async def test_a_media_type_left_out_is_refused_while_the_others_apply(conn):
    await adopted(conn, "paper-pdf@1")
    before = await state(conn)

    results = await adoption.apply(conn, "t1", {"text/markdown": entry(1, "md@1")}, Gate())

    assert {(r.media_type, r.result, r.reason) for r in results} == {
        (PDF, "refused", "media_type_missing"),
        ("text/markdown", "applied", ""),
    }
    assert await state(conn) != before
    assert await adoption.current(conn, PDF) == ("paper-pdf@1", 1)


async def test_a_declaration_waiting_at_the_gate_writes_nothing(conn):
    await adopted(conn, "paper-pdf@1")
    before = await state(conn)

    [result] = await adoption.apply(
        conn, "t1", {PDF: entry(2, "paper-pdf@2")}, Gate(waiting="check_running")
    )

    assert (result.result, result.reason) == ("waiting", "check_running")
    assert await state(conn) == before


async def test_a_version_adopted_before_tells_the_gate_so(conn):
    await adopted(conn, "paper-pdf@1", "paper-pdf@2")
    gate = Gate()

    [result] = await adoption.apply(
        conn, "t1", {PDF: entry(3, "paper-pdf@1", withdrawn=["paper-pdf@2"])}, gate
    )

    assert result.result == "applied" and gate.calls == [(PDF, "paper-pdf@1", True)]


async def test_a_declared_cancellation_leaves_no_version_without_the_gate(conn):
    await adopted(conn, "paper-pdf@1")
    gate = Gate(waiting="not_deployed")

    [result] = await adoption.apply(conn, "t1", {PDF: entry(2, "none")}, gate)
    [again] = await adoption.apply(conn, "t1", {PDF: entry(2, "none")}, gate)

    assert (result.result, again.result, gate.calls) == ("applied", "skipped", [])
    assert await adoption.current(conn, PDF) is None


async def test_two_runs_applying_one_new_declaration_write_one_record(dsn):

    async def run():
        async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
            return await adoption.apply(conn, "t1", {PDF: entry(1)}, Gate())

    results = await asyncio.gather(*(run() for _ in range(4)))

    assert sorted(r.result for [r] in results) == ["applied", "skipped", "skipped", "skipped"]
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        assert len((await state(conn))[0]) == 1


async def test_a_run_that_waited_at_the_gate_does_not_apply_over_a_newer_declaration(dsn):

    newer_applied = asyncio.Event()

    async def slow_gate(media_type, version, adopted_before):
        await newer_applied.wait()  # an old pod, at the gate while the values move on
        return True, ""

    async with (
        await psycopg.AsyncConnection.connect(dsn, autocommit=True) as old,
        await psycopg.AsyncConnection.connect(dsn, autocommit=True) as new,
    ):
        stale = asyncio.create_task(adoption.apply(old, "t1", {PDF: entry(1)}, slow_gate))
        await asyncio.sleep(0.2)
        [newer] = await adoption.apply(new, "t1", {PDF: entry(2, "paper-pdf@2")}, Gate())
        newer_applied.set()
        [result] = await stale

        assert newer.result == "applied"
        assert (result.result, result.reason) == ("refused", "declaration_not_raised")
        assert await adoption.current(new, PDF) == ("paper-pdf@2", newer.sequence)


async def test_a_version_adopted_only_by_the_local_command_still_runs_the_gate_test(conn):
    """Only an adoption through the gate counts as passed before (#57 B6)."""
    await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@1")
    gate = Gate()

    [result] = await adoption.apply(conn, "t1", {PDF: entry(1)}, gate)

    assert result.result == "applied" and gate.calls == [(PDF, "paper-pdf@1", False)]


async def test_a_gate_that_raises_leaves_the_media_type_waiting_and_the_others_go_on(conn):
    async def broken(media_type, version, adopted_before):
        if media_type == PDF:
            raise RuntimeError("Temporal unreachable")
        return True, ""

    results = await adoption.apply(
        conn, "t1", {PDF: entry(1), "text/markdown": entry(1, "md@1")}, broken
    )

    assert {(r.media_type, r.result, r.reason) for r in results} == {
        (PDF, "waiting", "gate_unavailable"),
        ("text/markdown", "applied", ""),
    }


async def test_a_reader_waiting_on_a_declared_cancellation_sees_no_version(dsn, conn):
    """Spec §3: no request is made under a version after its cancellation commits, also for a
    batch declaration whose read waited on the cancellation's lock."""
    await adopted(conn, "paper-pdf@1")
    async with (
        await psycopg.AsyncConnection.connect(dsn) as writer,
        await psycopg.AsyncConnection.connect(dsn) as reader,
    ):
        # The cancellation's transaction, as _apply_one runs it: the lock, then the new record.
        await writer.execute(
            "SELECT 1 FROM adoption WHERE media_type = %s ORDER BY sequence DESC LIMIT 1"
            " FOR UPDATE",
            (PDF,),
        )
        await writer.execute(
            "INSERT INTO adoption (sequence, tenant_id, media_type, adopted_version,"
            " cancelled_at, declaration) VALUES (2, 't1', %s, NULL, now(), 2)",
            (PDF,),
        )
        waiting = asyncio.create_task(adoption.current(reader, PDF))
        await asyncio.sleep(0.3)
        assert not waiting.done()  # it waits on the lock
        await writer.commit()

        assert await waiting is None
