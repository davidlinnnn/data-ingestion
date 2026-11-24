"""Canonical Acceptance on PostgreSQL (#251, admission spec §3): which Canonical Revision a
successful process request records, and which one becomes the Document's current one."""

import asyncio

import psycopg
import pytest
from prometheus_client import REGISTRY

from kp_admission import adoption, feed, reports, status
from kp_admission.requests import Candidate, record_outcome
from tests.admission.support import candidate, request, revision
from tests.admission.test_status import PIPELINE, dispatched, document, report

pytestmark = pytest.mark.docker


@pytest.fixture(autouse=True)
async def accepted_iff_recorded(conn):
    """After every test: a Source Revision is accepted exactly when it has a Canonical Revision."""
    yield
    cursor = await conn.execute(
        "SELECT source_revision_id FROM source_revision s WHERE (outcome = 'accepted') <>"
        " EXISTS (SELECT 1 FROM canonical_revision c"
        "         WHERE c.source_revision_id = s.source_revision_id)"
    )
    assert await cursor.fetchall() == []


async def newer(conn, uid: str, srv: str) -> str:
    """A newer Source Revision of the Document, as finalization numbers it."""
    await conn.execute(
        "INSERT INTO source_revision (source_revision_id, tenant_id, document_uid, source_version,"
        " files, sequence) SELECT %s, 't1', document_uid, '2', files, sequence + 1"
        " FROM source_revision WHERE source_revision_id = %s",
        (f"{srv}_2", srv),
    )
    return f"{srv}_2"


OWN = Candidate(ref="own", sha256="c" * 64, size=0)  # stands for the request's own candidate


async def succeed(conn, request_id: str, given: Candidate | None = OWN) -> bool:
    if given is OWN:
        [(uid,)] = await (
            await conn.execute(
                "SELECT document_uid FROM request WHERE request_id = %s", (request_id,)
            )
        ).fetchall()
        given = candidate(uid, request_id)
    return await record_outcome(conn, request_id, "succeeded", None, None, given)


async def run(conn, uid: str, srv: str, **fields) -> str:
    """A process request of `srv` that succeeds with the candidate."""
    request_id, _ = await request(conn, uid, srv, **fields)
    assert await succeed(conn, request_id)
    return request_id


def crv(request_id: str) -> str:
    return "crv_" + request_id.removeprefix("req_")


async def current(conn, uid: str) -> str | None:
    state = await feed.document_state(conn, uid, None)
    assert state
    return state.current and state.current.canonical_revision_id


async def events(conn, start: str) -> list[tuple[str, str | None, str]]:
    found, _ = await feed.read(conn, start, limit=10)
    return [(e.kind, e.document_uid, e.priority) for e in found]


async def recorded(conn, srv: str) -> list[str]:
    cursor = await conn.execute(
        "SELECT canonical_revision_id FROM canonical_revision WHERE source_revision_id = %s"
        " ORDER BY canonical_revision_id",
        (srv,),
    )
    return [row[0] for row in await cursor.fetchall()]


async def outcomes(conn, request_id: str) -> tuple[str, str]:
    """(the request's state, its Source Revision's outcome)."""
    cursor = await conn.execute(
        "SELECT r.state, s.outcome FROM request r JOIN source_revision s USING"
        " (source_revision_id) WHERE request_id = %s",
        (request_id,),
    )
    row = await cursor.fetchone()
    assert row
    return row


def not_accepted(reason: str) -> float:
    return REGISTRY.get_sample_value("kp_admission_not_accepted_total", {"reason": reason}) or 0.0


async def withdraw(conn, version: str) -> None:
    await conn.execute(
        "INSERT INTO withdrawn_version (tenant_id, media_type, version)"
        " VALUES ('t1', 'application/pdf', %s)",
        (version,),
    )


async def test_an_acceptance_makes_the_revision_current_with_one_event(conn):
    uid, srv = await revision(conn)
    start = await feed.head(conn)

    request_id = await run(conn, uid, srv)

    assert await outcomes(conn, request_id) == ("succeeded", "accepted")
    state = await feed.document_state(conn, uid, None)
    assert state and state.current and state.current.source_revision_created_at
    assert state == feed.State(
        resource_id="res_1",
        current=feed.Current(
            source_revision_id=srv,
            canonical_revision_id=crv(request_id),
            source_revision_created_at=state.current.source_revision_created_at,
        ),
        status="active",
    )
    assert await events(conn, start) == [("current_revision_changed", uid, "normal")]
    cursor = await conn.execute(
        "SELECT tenant_id, document_uid, request_id, adopted_version, adoption_sequence,"
        " content_ref, content_sha256, content_size FROM canonical_revision"
    )
    assert await cursor.fetchall() == [
        (
            "t1",
            uid,
            request_id,
            "paper-pdf@1",
            7,
            f"documents/{uid}/revisions/{crv(request_id)}.json",
            "c" * 64,
            2048,
        )
    ]


async def test_when_the_event_fails_to_append_nothing_of_the_acceptance_remains(conn):
    uid, srv = await revision(conn)
    request_id, _ = await request(conn, uid, srv)
    await conn.execute(
        "CREATE FUNCTION refuse() RETURNS trigger LANGUAGE plpgsql AS"
        " $$ BEGIN RAISE EXCEPTION 'injected'; END $$;"
        " CREATE TRIGGER refuse BEFORE INSERT ON change_feed"
        " FOR EACH ROW EXECUTE FUNCTION refuse()"
    )

    with pytest.raises(psycopg.errors.RaiseException):
        await succeed(conn, request_id)

    assert await outcomes(conn, request_id) == ("queued", "pending")
    assert await recorded(conn, srv) == []
    assert await current(conn, uid) is None


async def test_when_the_transaction_fails_after_the_acceptance_there_is_no_event(conn):
    uid, srv = await revision(conn)
    request_id, _ = await request(conn, uid, srv)
    start = await feed.head(conn)

    with pytest.raises(ZeroDivisionError):
        async with conn.transaction():
            assert await succeed(conn, request_id)
            raise ZeroDivisionError

    assert await outcomes(conn, request_id) == ("queued", "pending")
    assert await recorded(conn, srv) == []
    assert await current(conn, uid) is None
    assert await events(conn, start) == []


async def test_a_resent_acceptance_changes_nothing(conn):
    uid, srv = await revision(conn)
    request_id = await run(conn, uid, srv)
    start = await feed.head(conn)

    assert not await succeed(conn, request_id)

    assert await recorded(conn, srv) == [crv(request_id)]
    assert await current(conn, uid) == crv(request_id)
    assert await events(conn, start) == []


@pytest.mark.parametrize("newer_first", [False, True])
async def test_the_newer_source_revision_is_current_whichever_result_arrives_first(
    conn, newer_first: bool
):
    uid, old = await revision(conn)
    new = await newer(conn, uid, old)
    runs = {srv: (await request(conn, uid, srv))[0] for srv in (old, new)}
    order = [new, old] if newer_first else [old, new]
    seen = []

    for srv in order:
        start = await feed.head(conn)
        assert await succeed(conn, runs[srv])
        seen.append(await events(conn, start))

    assert await current(conn, uid) == crv(runs[new])
    assert await recorded(conn, old) == [crv(runs[old])]  # the late older one is still recorded
    assert [len(e) for e in seen] == ([1, 0] if newer_first else [1, 1])


async def test_of_one_source_revision_the_higher_adoption_sequence_wins_and_a_tie_keeps(conn):
    uid, srv = await revision(conn)
    first = await run(conn, uid, srv, adoption_sequence=7)
    start = await feed.head(conn)

    higher = await run(conn, uid, srv, adoption_sequence=8)
    after_higher = await events(conn, start)
    start = await feed.head(conn)
    tie = await run(conn, uid, srv, adoption_sequence=8)
    lower = await run(conn, uid, srv, adoption_sequence=6)

    assert after_higher == [("current_revision_changed", uid, "normal")]
    assert await current(conn, uid) == crv(higher)
    assert await events(conn, start) == []
    assert await recorded(conn, srv) == sorted(crv(r) for r in (first, higher, tie, lower))


async def test_a_late_success_of_a_deleted_document_forms_no_acceptance(conn):
    uid, srv = await revision(conn)
    request_id, _ = await request(conn, uid, srv)
    await conn.execute("UPDATE document SET deleted_at = now() WHERE document_uid = %s", (uid,))
    start, before = await feed.head(conn), not_accepted("document_deleted")

    assert await succeed(conn, request_id)

    assert await outcomes(conn, request_id) == ("succeeded", "pending")
    assert await recorded(conn, srv) == []
    state = await feed.document_state(conn, uid, None)
    assert state and state.status == "deleted"
    assert await events(conn, start) == []
    assert not_accepted("document_deleted") == before + 1


async def test_a_success_without_a_candidate_forms_no_acceptance(conn):
    uid, srv = await revision(conn)
    request_id, _ = await request(conn, uid, srv)
    start, before = await feed.head(conn), not_accepted("no_candidate")

    assert await succeed(conn, request_id, None)

    assert await outcomes(conn, request_id) == ("succeeded", "pending")
    assert await recorded(conn, srv) == []
    assert await current(conn, uid) is None
    assert await events(conn, start) == []
    assert not_accepted("no_candidate") == before + 1


@pytest.mark.parametrize("names", ["another document", "another revision"])
async def test_a_candidate_whose_ref_is_not_its_revision_s_key_forms_no_acceptance(
    conn, names: str
):
    uid, srv = await revision(conn)
    other, _ = await revision(conn)
    request_id, _ = await request(conn, uid, srv)
    own = candidate(uid, request_id)
    wrong = {
        "another document": candidate(other, request_id),
        "another revision": candidate(uid, "req_" + "0" * 32),
    }[names]
    start, before = await feed.head(conn), not_accepted("ref_mismatch")

    assert await succeed(conn, request_id, wrong)

    assert wrong.ref != own.ref
    assert await outcomes(conn, request_id) == ("succeeded", "pending")
    assert await recorded(conn, srv) == []
    assert await current(conn, uid) is None
    assert await events(conn, start) == []
    assert not_accepted("ref_mismatch") == before + 1


async def test_a_success_after_its_version_is_withdrawn_forms_no_acceptance(conn):
    uid, srv = await revision(conn)
    earlier = await run(conn, uid, srv, adopted_version="paper-pdf@2", adoption_sequence=8)
    late, _ = await request(conn, uid, srv, adopted_version="paper-pdf@2", adoption_sequence=9)
    await withdraw(conn, "paper-pdf@2")
    start, before = await feed.head(conn), not_accepted("version_withdrawn")

    assert await succeed(conn, late)

    assert (await outcomes(conn, late))[0] == "succeeded"
    assert await recorded(conn, srv) == [crv(earlier)]
    assert await current(conn, uid) == crv(earlier)  # withdrawal moves no current revision
    assert await events(conn, start) == []
    assert not_accepted("version_withdrawn") == before + 1


async def test_a_platform_refresh_is_background_unless_it_replaces_a_withdrawn_version(conn):
    refreshed, srv_r = await revision(conn)
    rolled_back, srv_b = await revision(conn)
    await run(conn, refreshed, srv_r, adopted_version="paper-pdf@1", adoption_sequence=7)
    await run(conn, rolled_back, srv_b, adopted_version="paper-pdf@2", adoption_sequence=8)
    await withdraw(conn, "paper-pdf@2")
    start = await feed.head(conn)

    for uid, srv in ((refreshed, srv_r), (rolled_back, srv_b)):
        await run(
            conn, uid, srv, initiator="platform", adopted_version="paper-pdf@3", adoption_sequence=9
        )

    assert await events(conn, start) == [
        ("current_revision_changed", refreshed, "background"),
        ("current_revision_changed", rolled_back, "normal"),
    ]


async def test_the_document_shows_a_method_version_lag_of_its_current_revision(conn):
    uid, srv = await document(conn)
    await adoption.adopt(conn, tenant_id="t1", media_type="application/pdf", version="paper-pdf@1")
    request_id = await run(conn, uid, srv)
    view = await status.document(conn, "t1", "s1", "A", {})
    assert view and view["details"] is None

    await adoption.adopt(conn, tenant_id="t1", media_type="application/pdf", version="paper-pdf@2")
    lagging = await status.document(conn, "t1", "s1", "A", {})

    assert lagging and lagging["details"] == {
        "method_version_lag": {
            "canonical_revision_id": crv(request_id),
            "processing_profile_version": "paper-pdf@1",
            "adopted_version": "paper-pdf@2",
        }
    }


@pytest.mark.parametrize("path", ["report", "reconciler"])
async def test_ending_a_request_locks_the_document_before_the_request(conn, dsn, path: str):
    """The order every transaction that ends a request takes its locks in (spec §3); the
    reconciler ends one through record_outcome."""
    uid, srv = await revision(conn)
    request_id = await dispatched(conn, uid, srv)
    last = reports.Report.model_validate(
        report(
            request_id,
            1,
            "finalize",
            "succeeded",
            candidate=candidate(uid, request_id).model_dump(),
        )
    )
    end = reports.take(conn, PIPELINE, last) if path == "report" else succeed(conn, request_id)

    async with (
        await psycopg.AsyncConnection.connect(dsn) as holder,
        await psycopg.AsyncConnection.connect(dsn) as other,
    ):
        async with holder.transaction():
            await holder.execute(
                "SELECT 1 FROM document WHERE document_uid = %s FOR UPDATE", (uid,)
            )
            ending = asyncio.create_task(end)
            await asyncio.sleep(0.5)
            assert not ending.done()
            async with other.transaction():  # the request is free while it waits
                await other.execute(
                    "SELECT 1 FROM request WHERE request_id = %s FOR UPDATE NOWAIT", (request_id,)
                )
        await ending

    assert await current(conn, uid) == crv(request_id)
