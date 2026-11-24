"""The scan (#98, admission spec §9): each rule of the scan table and each row of the limit
table, the rollback by a withdrawn version, pacing, and the scan beside a Source's resend."""

from datetime import UTC, datetime
from typing import Any

import pytest
from prometheus_client import REGISTRY

from kp_admission import adoption, gauges, scan
from kp_admission.dispatcher import dispatch_due
from kp_admission.requests import record_outcome
from tests.admission.support import candidate, request
from tests.admission.test_deletion import started
from tests.admission.test_serving import revised
from tests.admission.test_status import PLATFORM, REJECTED, document

pytestmark = pytest.mark.docker

PDF = "application/pdf"
FINAL = PLATFORM | {"reason": "METHOD_ERROR", "retryable": False}


async def adopt(conn, version: str, refresh: Any = "none") -> tuple[str, int]:
    return version, await adoption.adopt(
        conn, tenant_id="t1", media_type=PDF, version=version, refresh=refresh
    )


async def withdraw(conn, version: str) -> None:
    await conn.execute(
        "INSERT INTO withdrawn_version (tenant_id, media_type, version) VALUES ('t1', %s, %s)",
        (PDF, version),
    )


async def ran(
    conn, uid: str, srv: str, adopted: tuple[str, int], outcome: str, ago: float = 0, **error: Any
) -> str:
    """A request of `srv` under `adopted` that ended `ago` minutes ago: accepted, no_candidate,
    retryable, final (not retryable) or rejected."""
    request_id, _ = await request(
        conn, uid, srv, adopted_version=adopted[0], adoption_sequence=adopted[1]
    )
    if outcome in ("accepted", "no_candidate"):
        own = candidate(uid, request_id) if outcome == "accepted" else None
        assert await record_outcome(conn, request_id, "succeeded", None, None, own)
    else:
        failure = {"retryable": PLATFORM, "final": FINAL, "rejected": REJECTED}[outcome]
        assert await record_outcome(conn, request_id, "failed", failure | error, None)
    await conn.execute(
        "UPDATE request SET created_at = now() - %s * interval '1 minute',"
        " terminal_at = now() - %s * interval '1 minute' WHERE request_id = %s",
        (ago, ago, request_id),
    )
    # It ran: its row left the outbox queue when the dispatcher started it.
    await conn.execute(
        "UPDATE outbox SET dispatched_at = now() WHERE request_id = %s", (request_id,)
    )
    return request_id


async def run(conn, **kwargs: Any):
    return await scan.run(conn, datetime.now(UTC), **kwargs)


async def opened(conn) -> list[tuple]:
    """The queued requests: (document_uid, source_revision_id, initiator, priority, version,
    adoption_sequence)."""
    cursor = await conn.execute(
        "SELECT document_uid, source_revision_id, initiator, priority, adopted_version,"
        " adoption_sequence FROM request WHERE state = 'queued' ORDER BY created_at"
    )
    return await cursor.fetchall()


async def accept_opened(conn) -> None:
    for request_id, uid in await (
        await conn.execute("SELECT request_id, document_uid FROM request WHERE state = 'queued'")
    ).fetchall():
        assert await record_outcome(
            conn, request_id, "succeeded", None, None, candidate(uid, request_id)
        )


async def test_rule_1_a_current_revision_the_adopted_version_made_is_left(conn):
    one = await adopt(conn, "paper-pdf@1")
    uid, srv = await document(conn)
    await ran(conn, uid, srv, one, "accepted")

    assert await run(conn) == {} and await opened(conn) == []


@pytest.mark.parametrize(
    ("scope", "refreshed"),
    [
        ("none", False),
        ("all", True),
        ({"made_by": ["paper-pdf@1"]}, True),
        ({"made_by": ["paper-pdf@3"]}, False),
    ],
)
async def test_rule_2_a_current_revision_another_version_made_is_refreshed_in_scope(
    conn, scope, refreshed
):
    one = await adopt(conn, "paper-pdf@1")
    uid, srv = await document(conn)
    await ran(conn, uid, srv, one, "accepted")
    two = await adopt(conn, "paper-pdf@2", scope)

    counts = await run(conn)

    expected = [(uid, srv, "platform", "low", *two)] if refreshed else []
    assert await opened(conn) == expected
    assert counts == ({"refresh": 1} if refreshed else {})


async def test_rule_2_a_withdrawn_version_s_revision_is_redone_whatever_the_scope(conn):
    two = await adopt(conn, "paper-pdf@2")
    uid, srv = await document(conn)
    await ran(conn, uid, srv, two, "accepted")
    one = await adopt(conn, "paper-pdf@1")  # scope none: the rollback
    await withdraw(conn, "paper-pdf@2")

    assert await run(conn) == {"redo": 1}
    assert await opened(conn) == [(uid, srv, "platform", "low", *one)]


async def test_rule_3_content_never_accepted_is_rerun_whatever_the_scope(conn):
    one = await adopt(conn, "paper-pdf@1")  # scope none
    uid, srv = await document(conn)
    await ran(conn, uid, srv, one, "retryable", ago=11)

    assert await run(conn) == {"rerun": 1}
    assert await opened(conn) == [(uid, srv, "operator", "normal", *one)]


@pytest.mark.parametrize("latest", ["rejected", "final"])
async def test_rule_4_a_withdrawn_version_s_current_revision_is_redone_when_the_latest_cannot_be(
    conn, latest
):
    two = await adopt(conn, "paper-pdf@2")
    uid, first = await document(conn)
    await ran(conn, uid, first, two, "accepted")
    one = await adopt(conn, "paper-pdf@1")
    await withdraw(conn, "paper-pdf@2")
    await revised(conn, uid, "srv_2")
    await ran(conn, uid, "srv_2", one, latest)

    assert await run(conn) == {"redo": 1}
    assert await opened(conn) == [(uid, first, "platform", "low", *one)]
    await accept_opened(conn)
    state = await (
        await conn.execute(
            "SELECT current_source_revision_id, current_adopted_version FROM document"
        )
    ).fetchone()
    assert state == (first, "paper-pdf@1")  # served by the adopted version again


async def test_rule_5_nothing_when_the_latest_cannot_be_reopened_and_the_current_is_kept(conn):
    one = await adopt(conn, "paper-pdf@1")
    uid, first = await document(conn)
    await ran(conn, uid, first, one, "accepted")
    await revised(conn, uid, "srv_2")
    await ran(conn, uid, "srv_2", one, "final")

    assert await run(conn) == {} and await opened(conn) == []


async def test_no_request_without_an_adopted_version_for_a_deleted_or_an_active_document(conn):
    uid, srv = await document(conn)  # no adoption yet
    assert await run(conn) == {}
    one = await adopt(conn, "paper-pdf@1")
    active, _ = await document(conn, "B")
    await request(conn, active, "srv_s1_B", adopted_version=one[0], adoption_sequence=one[1])
    deleted, _ = await document(conn, "C")
    await conn.execute("UPDATE document SET deleted_at = now() WHERE document_uid = %s", (deleted,))

    assert await run(conn) == {"rerun": 1}  # A only
    assert [row[0] for row in await opened(conn)] == [active, uid]


async def test_no_request_while_the_adopted_version_is_itself_withdrawn(conn):
    await adopt(conn, "paper-pdf@1")
    await withdraw(conn, "paper-pdf@1")
    await document(conn)

    assert await run(conn) == {}


@pytest.mark.parametrize(
    ("failures", "minutes", "due"),
    [(1, 9, False), (1, 11, True), (2, 19, False), (2, 21, True), (3, 39, False),
     (3, 41, True), (4, 59, False), (4, 61, True), (8, 59, False), (8, 61, True)],
)  # fmt: skip
async def test_a_retryable_failure_is_rerun_at_intervals_that_double_up_to_an_hour(
    conn, failures, minutes, due
):
    one = await adopt(conn, "paper-pdf@1")
    uid, srv = await document(conn)
    for k in range(failures, 0, -1):  # the oldest first
        await ran(conn, uid, srv, one, "retryable", ago=minutes + 100 * (k - 1))

    assert await run(conn) == ({"rerun": 1} if due else {})


async def test_retryable_failures_past_the_warning_count_are_measured_by_reason_and_still_rerun(
    conn,
):
    one = await adopt(conn, "paper-pdf@1")
    for name, reason, failures in (("A", "PLATFORM_ERROR", 5), ("B", "ENRICHMENT_INCOMPLETE", 5),
                                   ("C", "PLATFORM_ERROR", 4)):  # fmt: skip
        uid, srv = await document(conn, name)
        for k in range(failures, 0, -1):
            await ran(conn, uid, srv, one, "retryable", ago=61 + 100 * (k - 1), reason=reason)

    counts = await run(conn)
    await gauges.observe(conn)
    await accept_opened(conn)  # the service is back: the reruns are accepted

    def warned(reason: str) -> float | None:
        return REGISTRY.get_sample_value("kp_admission_reruns_retrying", {"reason": reason})

    assert counts == {"rerun": 3}
    assert (warned("PLATFORM_ERROR"), warned("ENRICHMENT_INCOMPLETE")) == (1, 1)
    cursor = await conn.execute("SELECT count(*) FROM document WHERE current_adopted_version = %s",
                                (one[0],))  # fmt: skip
    assert await cursor.fetchone() == (3,)


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        ("final", "METHOD_ERROR"),
        ("rejected", "PASSWORD_REQUIRED"),
        ("no_candidate", "NO_CANDIDATE"),
    ],
)
async def test_a_stopped_revision_is_rerun_once_per_adoption(conn, outcome, reason):
    one = await adopt(conn, "paper-pdf@1")
    uid, srv = await document(conn)
    await ran(conn, uid, srv, one, outcome)

    same = await run(conn)
    await gauges.observe(conn)
    stopped = REGISTRY.get_sample_value("kp_admission_reruns_stopped", {"reason": reason})
    two = await adopt(conn, "paper-pdf@2")
    next_adoption = await run(conn)
    [(request_id, *_)] = await (
        await conn.execute("SELECT request_id FROM request WHERE state = 'queued'")
    ).fetchall()
    rerun = await opened(conn)
    error = {"final": FINAL, "rejected": REJECTED}.get(outcome)
    state = "failed" if error else "succeeded"
    assert await record_outcome(conn, request_id, state, error, None)

    assert same == {} and stopped == 1
    assert next_adoption == {"rerun": 1} and rerun == [(uid, srv, "operator", "normal", *two)]
    assert await run(conn) == {}


async def test_a_refresh_that_fails_for_good_is_not_opened_again_under_the_adoption(conn):
    one = await adopt(conn, "paper-pdf@1")
    uid, srv = await document(conn)
    await ran(conn, uid, srv, one, "accepted")
    await adopt(conn, "paper-pdf@2", "all")
    assert await run(conn) == {"refresh": 1}
    [(request_id,)] = await (
        await conn.execute("SELECT request_id FROM request WHERE state = 'queued'")
    ).fetchall()
    assert await record_outcome(conn, request_id, "failed", FINAL, None)

    assert await run(conn) == {}


async def test_a_withdrawn_version_s_queued_request_ends_and_is_rerun_under_the_adopted_one(conn):
    two = await adopt(conn, "paper-pdf@2")
    uid, srv = await document(conn)
    await request(conn, uid, srv, adopted_version=two[0], adoption_sequence=two[1])
    await withdraw(conn, "paper-pdf@2")
    one = await adopt(conn, "paper-pdf@1")

    assert await dispatch_due(conn, started) == 0
    assert await run(conn) == {"rerun": 1}
    assert await opened(conn) == [(uid, srv, "operator", "normal", *one)]


async def test_a_rollback_is_finished_even_when_a_later_adoption_declares_no_refresh(conn):
    two = await adopt(conn, "paper-pdf@2")
    docs = [await document(conn, name) for name in ("A", "B")]
    for uid, srv in docs:
        await ran(conn, uid, srv, two, "accepted")
    await adopt(conn, "paper-pdf@1")
    await withdraw(conn, "paper-pdf@2")

    assert await run(conn, pace=1) == {"redo": 1}  # halfway
    await accept_opened(conn)
    three = await adopt(conn, "paper-pdf@3")  # scope none
    assert await run(conn) == {"redo": 1}

    assert await opened(conn) == [(docs[1][0], docs[1][1], "platform", "low", *three)]
    await accept_opened(conn)
    await run(conn)
    await gauges.observe(conn)
    left = REGISTRY.get_sample_value("kp_admission_documents_on_withdrawn", {"version": two[0]})
    assert left is None  # no Document is served by the withdrawn version


async def test_the_pace_opens_reruns_then_redos_then_refreshes(conn):
    two = await adopt(conn, "paper-pdf@2")
    refresh, redo, rerun = [await document(conn, name) for name in ("A", "B", "C")]
    await ran(conn, *refresh, two, "accepted")
    await ran(conn, *redo, await adopt(conn, "paper-pdf@3"), "accepted")
    await withdraw(conn, "paper-pdf@3")
    await adopt(conn, "paper-pdf@4", {"made_by": ["paper-pdf@2"]})

    order = []
    for _ in range(3):
        assert len(await run(conn, pace=1)) == 1
        order.append((await opened(conn))[-1][0])
        assert await dispatch_due(conn, started) == 1  # dispatched: no longer waiting

    assert order == [rerun[0], redo[0], refresh[0]]


async def test_the_documents_and_requests_gauges(conn):
    two = await adopt(conn, "paper-pdf@2")
    on_withdrawn, srv = await document(conn, "A")
    await ran(conn, on_withdrawn, srv, two, "accepted")
    await withdraw(conn, "paper-pdf@2")
    await adopt(conn, "paper-pdf@1")
    late, _ = await document(conn, "B")
    await conn.execute(
        "UPDATE document SET created_at = now() - interval '2 hours' WHERE document_uid = %s",
        (late,),
    )
    await run(conn)
    await dispatch_due(conn, started)
    await conn.execute("UPDATE outbox SET dispatched_at = now() - interval '2 hours'")
    await run(conn)
    await gauges.observe(conn)

    def value(name: str, **labels: str) -> float | None:
        return REGISTRY.get_sample_value(name, labels)

    assert value("kp_admission_documents_on_withdrawn", version="paper-pdf@2") == 1
    assert value("kp_admission_documents_without_current", source_id="s1") == 1
    assert value("kp_admission_requests_overdue", adopted_version="paper-pdf@1") == 2
    assert value("kp_admission_job_last_run_timestamp_seconds", job="scan")
