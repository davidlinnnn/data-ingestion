"""The governed read API over HTTP (#126, canonical consumption DR §3): the Change Feed, cursors,
Document state and bootstrap listings, for registered service identities (#113)."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from prometheus_client import REGISTRY
from psycopg_pool import AsyncConnectionPool

from kp_admission import feed
from kp_admission.api import app
from tests.admission.authz_fake import FakeAuthorizer
from tests.admission.support import INTAKE, revision
from tests.admission.test_api import PEPS, TOKEN

pytestmark = pytest.mark.docker


@pytest.fixture
async def pool(dsn):
    async with AsyncConnectionPool(dsn, kwargs={"autocommit": True}) as connections:
        yield connections


def client(pool: AsyncConnectionPool, token: str | None = TOKEN) -> httpx.AsyncClient:
    headers = {"authorization": f"Bearer {token}"} if token else {}
    transport = httpx.ASGITransport(app(FakeAuthorizer(), PEPS, {}, pool, INTAKE))
    return httpx.AsyncClient(transport=transport, base_url="http://api/read", headers=headers)


async def delete(conn, uid: str) -> None:
    """The deletion as #98 will record it."""
    async with conn.transaction():
        await conn.execute("UPDATE document SET deleted_at = now() WHERE document_uid = %s", (uid,))
        await feed.append(
            conn,
            "document_deleted",
            tenant_id="t1",
            source_id="s1",
            document_uid=uid,
            priority="narrowing",
        )


class ReferenceProjection:
    """The platform side of a projection's reader (#127 builds the real one): it keeps the uids of
    the Documents it would serve."""

    def __init__(self, api: httpx.AsyncClient) -> None:
        self.api, self.stored, self.cursor = api, set[str](), ""

    async def reconcile(self, uid: str, at_least: str | None = None) -> None:
        params = {"at_least": at_least} if at_least else {}
        response = await self.api.get(f"/v1/documents/{uid}/state", params=params)
        response.raise_for_status()
        if response.json()["status"] == "active":
            self.stored.add(uid)
        else:
            self.stored.discard(uid)

    async def follow(self) -> int:
        """Reads the feed to its end and reports the cursor; returns the status of the read."""
        while True:
            response = await self.api.get("/v1/feed", params={"cursor": self.cursor})
            if response.status_code != 200:
                return response.status_code
            page = response.json()
            for event in page["events"]:
                await self.reconcile(event["document_uid"], event["position"])
            self.cursor = page["next_cursor"]
            put = await self.api.put("/v1/consumers/retrieval/cursor", json={"cursor": self.cursor})
            assert put.status_code == 204
            if not page["events"]:
                return 200

    async def bootstrap(self) -> None:
        """Fixes the starting point, then enumerates every Source's Documents and reconciles
        those it stores that the enumeration did not return (A4 R-a)."""
        self.cursor = (await self.api.get("/v1/feed")).json()["next_cursor"]
        listed: set[str] = set()
        for source_id in (await self.api.get("/v1/sources")).json()["source_ids"]:
            after = None
            while True:
                params = {"limit": 2} | ({"after": after} if after else {})
                page = await self.api.get(f"/v1/sources/{source_id}/documents", params=params)
                listed |= set(page.json()["document_uids"])
                if not (after := page.json()["next_after"]):
                    break
        for uid in listed | self.stored:
            await self.reconcile(uid)
        put = await self.api.put("/v1/consumers/retrieval/cursor", json={"cursor": self.cursor})
        assert put.status_code == 204


async def test_a_projection_paused_beyond_retention_is_consistent_again_after_bootstrap(conn, pool):
    """SC16, the platform side: a Document deleted while the projection was paused, in a month
    that retention then dropped, leaves the store at bootstrap."""
    await feed.set_profile(conn, tenant_id="t1", source_id="s1", projections=["retrieval"])
    kept, gone = (await revision(conn))[0], (await revision(conn))[0]
    async with client(pool) as api:
        projection = ReferenceProjection(api)
        await projection.bootstrap()
        assert projection.stored == {kept, gone}

        await delete(conn, gone)  # while the projection is paused
        added = (await revision(conn))[0]
        now = datetime.now(UTC)
        await feed.retain(conn, now + timedelta(days=200))
        await feed.retain(conn, now)

        assert await projection.follow() == 410
        expired = await api.get("/v1/feed", params={"cursor": projection.cursor})
        await projection.bootstrap()
        await delete(conn, kept)
        assert await projection.follow() == 200

    assert expired.json()["error"]["details"][0]["reason"] == "CURSOR_EXPIRED"
    assert projection.stored == {added}


async def test_every_governed_read_refuses_a_caller_without_a_registered_identity(pool):
    calls = [
        ("GET", "/v1/feed"),
        ("PUT", "/v1/consumers/retrieval/cursor"),
        ("GET", "/v1/documents/doc_1/state"),
        ("GET", "/v1/sources"),
        ("GET", "/v1/sources/s1/profile"),
        ("GET", "/v1/sources/s1/documents"),
        ("GET", "/v1/documents/doc_1/revisions/crv_1"),
        ("GET", f"/v1/documents/doc_1/revisions/crv_1/artifacts/{'a' * 64}/pages/1.png"),
    ]
    async with client(pool, token="another-credential") as api:
        responses = [await api.request(method, path, json={}) for method, path in calls]

    assert [r.status_code for r in responses] == [401] * len(calls)


async def test_a_cursor_report_that_steps_back_gets_409_with_the_platform_position(conn, pool):
    uid, _ = await revision(conn)
    async with client(pool) as api:
        start = (await api.get("/v1/feed")).json()["next_cursor"]
        await delete(conn, uid)
        end = (await api.get("/v1/feed", params={"cursor": start})).json()["next_cursor"]

        ahead = await api.put("/v1/consumers/retrieval/cursor", json={"cursor": end})
        back = await api.put("/v1/consumers/retrieval/cursor", json={"cursor": start})
        other = await api.put("/v1/consumers/wiki/cursor", json={"cursor": end})
        invalid = await api.put("/v1/consumers/retrieval/cursor", json={"cursor": "c1f"})

    assert ahead.status_code == 204
    assert back.status_code == 409
    [detail] = back.json()["error"]["details"]
    assert (detail["reason"], detail["metadata"]) == ("CURSOR_BACKWARDS", {"cursor": end})
    assert other.status_code == 403  # another projection's cursor
    assert invalid.status_code == 400


async def test_document_state_answers_its_fields_404_for_an_unknown_uid_and_503_when_behind(
    conn, pool
):
    start = datetime.now(UTC)
    uid, srv = await revision(conn)
    created = datetime.now(UTC)
    await conn.execute(
        "UPDATE document SET current_source_revision_id = %s,"
        " current_canonical_revision_id = 'crv_1' WHERE document_uid = %s",
        (srv, uid),
    )
    async with client(pool) as api, conn.transaction():
        behind = await feed.append(
            conn,
            "current_revision_changed",
            tenant_id="t1",
            source_id="s1",
            document_uid=uid,
            priority="normal",
        )
        state = await api.get(f"/v1/documents/{uid}/state")
        unknown = await api.get("/v1/documents/doc_unknown/state")
        waiting = await api.get(f"/v1/documents/{uid}/state", params={"at_least": behind})

    assert state.status_code == 200
    answer = state.json()
    at = datetime.fromisoformat(answer["current"].pop("source_revision_created_at"))
    assert start - timedelta(seconds=1) <= at <= created + timedelta(seconds=1)  # clock skew
    assert answer == {
        "resource_id": "res_1",
        "current": {"source_revision_id": srv, "canonical_revision_id": "crv_1"},
        "status": "active",
        "copy_of": None,
    }
    assert unknown.status_code == 404
    assert waiting.status_code == 503


async def test_a_feed_page_carries_identities_only_and_each_read_is_counted(conn, pool):
    await feed.set_profile(conn, tenant_id="t1", source_id="s1", projections=["retrieval"])
    uid, _ = await revision(conn)
    labels = {"operation": "read_feed", "status": "200"}
    before = REGISTRY.get_sample_value("kp_api_calls_total", labels) or 0.0
    async with client(pool) as api:
        start = (await api.get("/v1/feed")).json()["next_cursor"]
        await delete(conn, uid)
        await feed.set_profile(conn, tenant_id="t1", source_id="s1", projections=["wiki"])
        page = (await api.get("/v1/feed", params={"cursor": start, "limit": 1})).json()
        rest = (await api.get("/v1/feed", params={"cursor": page["next_cursor"]})).json()
        profile = (await api.get("/v1/sources/s1/profile")).json()

    [deleted], [changed] = page["events"], rest["events"]
    assert set(deleted) == {
        "position",
        "kind",
        "document_uid",
        "source_id",
        "priority",
        "occurred_at",
    }
    assert (deleted["kind"], deleted["document_uid"], deleted["priority"]) == (
        "document_deleted",
        uid,
        "narrowing",
    )
    assert "document_uid" not in changed
    assert profile == {
        "source_id": "s1",
        "projections": ["wiki"],
        "profile_seq": changed["position"],
    }
    assert (REGISTRY.get_sample_value("kp_api_calls_total", labels) or 0.0) - before == 3
