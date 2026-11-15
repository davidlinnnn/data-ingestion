"""The decision obligations every Authorizer meets, for each outcome (#113, authorization design
§4.1, Q2): the allow-all provider on PostgreSQL and the PEP tests' fake."""

import pytest
from psycopg_pool import AsyncConnectionPool

from kp_admission.authz import AllowAll, Ref
from tests.admission.authz_fake import FakeAuthorizer
from tests.admission.conftest import fresh_database
from tests.admission.support import resource

ALICE = Ref(type="user", id="alice")
AGENT = Ref(type="client", id="research-agent")
CASES = [
    pytest.param((provider, outcome), id=f"{provider}-{outcome}", marks=marks)
    for provider, outcome, marks in [
        ("allow-all", "allow", pytest.mark.docker),
        ("allow-all", "deny", pytest.mark.docker),
        ("allow-all", "unavailable", ()),
        ("fake", "allow", ()),
        ("fake", "deny", ()),
        ("fake", "unavailable", ()),
    ]
]


@pytest.fixture(params=CASES)
async def case(request):
    """(an Authorizer whose check on res_01 has the case's outcome, that outcome)."""
    provider, outcome = request.param
    if provider == "fake":
        yield FakeAuthorizer(outcome), outcome
        return
    if outcome == "unavailable":
        dsn = "host=127.0.0.1 port=9"
    else:  # only these cases start the PostgreSQL container
        dsn = await fresh_database(request.getfixturevalue("postgres"))
    async with AsyncConnectionPool(dsn, kwargs={"autocommit": True}, open=False) as pool:
        if outcome == "allow":
            async with pool.connection() as conn:
                await resource(conn)
        yield AllowAll(pool), outcome


async def test_check_returns_a_decision_with_the_request_and_no_reuse(case):
    authorizer, outcome = case

    first, second = [
        await authorizer.check(ALICE, "read", "res_01", actor=AGENT, trace_id="4bf92f3577b34da6")
        for _ in range(2)
    ]

    assert first.outcome == outcome
    assert first.decision_id.startswith("dec_") and first.decision_id != second.decision_id
    assert first.valid_until == first.evaluated_at
    assert (first.subject, first.actor, first.actor_verified) == (ALICE, AGENT, False)
    assert (first.action, first.resource) == ("read", Ref(type="resource", id="res_01"))
    assert first.trace_id == "4bf92f3577b34da6"
    assert (first.reason is not None) == (outcome == "deny")
    assert (first.resource_ids, first.next_cursor) == (None, None)


async def test_list_resources_returns_ids_unless_unavailable(case):
    authorizer, outcome = case

    page = await authorizer.list_resources(ALICE, "read", actor=AGENT, trace_id="t")

    assert page.outcome == ("unavailable" if outcome == "unavailable" else "allow")
    assert (page.resource is None, page.reason, page.actor_verified) == (True, None, False)
    assert (page.resource_ids is None) == (outcome == "unavailable")
    assert page.valid_until == page.evaluated_at
