"""Exact-revision content reads over HTTP (#268, admission spec §5.9): the content object of a
Canonical Revision and the artifacts its manifest lists, for registered service identities, with
a real database and the object store's fake for fault injection."""

import asyncio
import hashlib
import itertools
import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from prometheus_client import REGISTRY
from psycopg_pool import AsyncConnectionPool

from kp_admission import storage
from kp_admission.api import app
from kp_admission.batches import Intake
from kp_admission.requests import Candidate, record_outcome
from kp_admission.storage import FakeObjectStore, ObjectStore, S3ObjectStore
from kp_sdk.projection import ProjectionClient
from tests.admission.authz_fake import FakeAuthorizer
from tests.admission.support import request, revision
from tests.admission.test_api import PEPS, TOKEN

pytestmark = pytest.mark.docker

CANARY = "canary-6f1d2c"  # in content and artifact bytes; never in a log line
PNG = b"\x89PNG\r\n\x1a\n" + CANARY.encode() + os.urandom(500)
PAGE = ("a" * 64 + "/pages/1.png", "page_image", "image/png", PNG)
CROP = ("b" * 64 + "/crop.json", "evidence", "application/json", b'{"bbox": [1, 2, 3, 4]}')
RAW = "b" * 64 + "/provider/raw.json"  # a registered object the content does not reference


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Store(FakeObjectStore):
    """The fake, recording every key opened."""

    def __init__(self) -> None:
        super().__init__()
        self.opened: list[str] = []

    async def open(self, key: str):
        self.opened.append(key)
        return await super().open(key)

    def put(self, key: str, data: bytes) -> None:
        self.keys.add(key)
        self.content[key] = data


@pytest.fixture
async def pool(dsn):
    # Not UTC, so a time the database gives in its session zone shows unless converted.
    kwargs = {"autocommit": True, "options": "-c TimeZone=Asia/Taipei"}
    async with AsyncConnectionPool(dsn, kwargs=kwargs) as connections:
        yield connections


@pytest.fixture
def store() -> Store:
    return Store()


def client(pool, store: ObjectStore, token: str = TOKEN) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app(FakeAuthorizer(), PEPS, {}, pool, Intake(store)))
    headers = {"authorization": f"Bearer {token}"}
    return httpx.AsyncClient(transport=transport, base_url="http://api/read", headers=headers)


async def accept(conn, store: Store, uid: str, srv: str, artifacts=(PAGE, CROP), **fields) -> str:
    """A run of `srv` accepted with a content object whose manifest lists `artifacts`, all placed
    in the store; returns its canonical_revision_id."""
    request_id, _ = await request(conn, uid, srv, **fields)
    crv = "crv_" + request_id.removeprefix("req_")
    manifest = [
        {"ref": ref, "kind": kind, "media_type": media_type, "sha256": sha(data), "size": len(data)}
        for ref, kind, media_type, data in sorted(artifacts)
    ]
    content = {
        "schema": "canonical-content/v1",
        "revision": {"canonical_revision_id": crv, "document_uid": uid},
        "blocks": [{"ref": "#/texts/0", "kind": "text", "text": CANARY}],
        "artifacts": manifest,
    }
    body = json.dumps(content).encode()
    key = f"documents/{uid}/revisions/{crv}.json"
    store.put(key, body)
    for ref, _, _, data in artifacts:
        store.put(f"documents/{uid}/items/{ref}", data)
    candidate = Candidate(ref=key, sha256=sha(body), size=len(body))
    assert await record_outcome(conn, request_id, "succeeded", None, None, candidate)
    return crv


async def newer(conn, uid: str, srv: str) -> str:
    await conn.execute(
        "INSERT INTO source_revision (source_revision_id, tenant_id, document_uid, source_version,"
        " files, sequence) SELECT %s, 't1', document_uid, '2', files, sequence + 1"
        " FROM source_revision WHERE source_revision_id = %s",
        (f"{srv}_2", srv),
    )
    return f"{srv}_2"


def reason(response: httpx.Response) -> str:
    return response.json()["error"]["details"][0]["reason"]


def reads(kind: str, result: str) -> float:
    labels = {"kind": kind, "result": result}
    return REGISTRY.get_sample_value("kp_canonical_reads_total", labels) or 0.0


async def test_the_content_read_returns_the_recorded_bytes_with_sha256_size_and_time(
    conn, pool, store
):
    start = datetime.now(UTC)
    uid, srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    async with client(pool, store) as api:
        read = await api.get(f"/v1/documents/{uid}/revisions/{crv}")
        state = await api.get(f"/v1/documents/{uid}/state")

    [(recorded_sha, recorded_size)] = await (
        await conn.execute(
            "SELECT content_sha256, content_size FROM canonical_revision"
            " WHERE canonical_revision_id = %s",
            (crv,),
        )
    ).fetchall()
    assert read.status_code == 200
    assert read.headers["content-type"] == "application/json"
    assert sha(read.content) == recorded_sha == read.headers["x-content-sha256"]
    assert len(read.content) == recorded_size == int(read.headers["content-length"])
    created = read.headers["x-source-revision-created-at"]
    assert created == state.json()["current"]["source_revision_created_at"]
    assert created.endswith("Z")  # RFC 3339 UTC (spec §4)
    assert start - timedelta(seconds=1) <= datetime.fromisoformat(created) <= datetime.now(UTC)


async def test_an_artifact_the_manifest_lists_is_served_with_its_media_type(conn, pool, store):
    uid, srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    async with client(pool, store) as api:
        page = await api.get(f"/v1/documents/{uid}/revisions/{crv}/artifacts/{PAGE[0]}")
        crop = await api.get(f"/v1/documents/{uid}/revisions/{crv}/artifacts/{CROP[0]}")

    assert (page.status_code, page.content, page.headers["content-type"]) == (200, PNG, "image/png")
    assert page.headers["x-content-sha256"] == sha(PNG)
    assert (crop.status_code, crop.headers["content-type"]) == (200, "application/json")


async def test_a_reference_sent_as_one_encoded_segment_is_the_same_artifact(conn, pool, store):
    """The SDK sends a reference's `/` as `%2F` (#127)."""
    uid, srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    encoded = PAGE[0].replace("/", "%2F")
    async with client(pool, store) as api:
        page = await api.get(f"/v1/documents/{uid}/revisions/{crv}/artifacts/{encoded}")

    assert (page.status_code, page.content) == (200, PNG)


async def test_the_sdk_reads_both_through_the_real_routes(conn, pool, store):
    uid, srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    transport = httpx.ASGITransport(app(FakeAuthorizer(), PEPS, {}, pool, Intake(store)))
    sdk = ProjectionClient("http://api", TOKEN, "retrieval", transport=transport)
    try:
        content = json.loads(await sdk.content(uid, crv))
        page = await sdk.artifact(uid, crv, PAGE[0])
    finally:
        await sdk.aclose()

    assert content["revision"]["canonical_revision_id"] == crv
    assert page == PNG


async def test_objects_are_found_at_the_location_the_record_holds(conn, pool, store):
    """Not at a key built from the path's uid: a copy's revision (#120) lives under another
    Document's prefix."""
    uid, srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    elsewhere = f"documents/doc_original/revisions/{crv}.json"
    store.put(elsewhere, store.content.pop(f"documents/{uid}/revisions/{crv}.json"))
    store.keys.discard(f"documents/{uid}/revisions/{crv}.json")
    await conn.execute(
        "UPDATE canonical_revision SET content_ref = %s WHERE canonical_revision_id = %s",
        (elsewhere, crv),
    )
    async with client(pool, store) as api:
        read = await api.get(f"/v1/documents/{uid}/revisions/{crv}")
        page = await api.get(f"/v1/documents/{uid}/revisions/{crv}/artifacts/{PAGE[0]}")

    assert (read.status_code, page.status_code) == (200, 200)
    assert store.opened == [elsewhere, elsewhere, f"documents/{uid}/items/{PAGE[0]}"]


async def test_an_object_of_the_document_the_manifest_does_not_list_is_404_and_never_read(
    conn, pool, store
):
    uid, srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    store.put(f"documents/{uid}/items/{RAW}", b'{"raw": "provider output"}')
    async with client(pool, store) as api:
        unlisted = await api.get(f"/v1/documents/{uid}/revisions/{crv}/artifacts/{RAW}")

    assert (unlisted.status_code, reason(unlisted)) == (404, "ARTIFACT_NOT_FOUND")
    assert f"documents/{uid}/items/{RAW}" not in store.opened


@pytest.mark.parametrize(
    "reference",
    [
        "a" * 64 + "/%2E%2E/%2E%2E/revisions/x.json",
        "a" * 64 + "/pages/%2E%2E",
        "documents/doc_1/items/" + PAGE[0],
        "s3:/kp-custody/documents/doc_1/items/" + PAGE[0],
        "a" * 64,
    ],
)
async def test_a_reference_not_of_the_reference_form_is_404_without_a_storage_read(
    conn, pool, store, reference
):
    uid, srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    async with client(pool, store) as api:
        answer = await api.get(f"/v1/documents/{uid}/revisions/{crv}/artifacts/{reference}")

    assert (answer.status_code, reason(answer)) == (404, "ARTIFACT_NOT_FOUND")
    assert store.opened == []


async def test_another_document_s_revision_or_an_unknown_id_is_404(conn, pool, store):
    uid, srv = await revision(conn)
    other, other_srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    await accept(conn, store, other, other_srv)
    async with client(pool, store) as api:
        answers = [
            await api.get(f"/v1/documents/{other}/revisions/{crv}"),
            await api.get(f"/v1/documents/{other}/revisions/{crv}/artifacts/{PAGE[0]}"),
            await api.get(f"/v1/documents/{uid}/revisions/crv_{uuid.uuid4().hex}"),
            await api.get(f"/v1/documents/doc_unknown/revisions/{crv}"),
        ]

    assert [(a.status_code, reason(a)) for a in answers] == [(404, "REVISION_NOT_FOUND")] * 4
    assert store.opened == []


async def test_a_replaced_revision_and_a_losing_candidate_stay_readable(conn, pool, store):
    uid, srv = await revision(conn)
    replaced = await accept(conn, store, uid, srv, adoption_sequence=7)
    current = await accept(conn, store, uid, await newer(conn, uid, srv), adoption_sequence=7)
    losing = await accept(conn, store, uid, srv, adoption_sequence=5)  # older: recorded only
    async with client(pool, store) as api:
        state = (await api.get(f"/v1/documents/{uid}/state")).json()
        answers = [
            await api.get(f"/v1/documents/{uid}/revisions/{crv}") for crv in (replaced, losing)
        ]
        picture = await api.get(f"/v1/documents/{uid}/revisions/{replaced}/artifacts/{PAGE[0]}")

    assert state["current"]["canonical_revision_id"] == current
    assert [a.status_code for a in answers] == [200, 200]
    assert picture.status_code == 200


async def test_a_deleted_document_is_refused_and_a_purged_one_is_no_longer_retained(
    conn, pool, store
):
    deleted, deleted_srv = await revision(conn)
    purged, purged_srv = await revision(conn)
    live, live_srv = await revision(conn)
    crvs = {
        uid: await accept(conn, store, uid, srv)
        for uid, srv in ((deleted, deleted_srv), (purged, purged_srv), (live, live_srv))
    }
    await conn.execute(
        "UPDATE document SET deleted_at = now() WHERE document_uid IN (%s, %s)", (deleted, purged)
    )
    # A purge of a deleted Document (#267), and of a replaced revision past retention (#269).
    await conn.execute(
        "UPDATE canonical_revision SET purged_at = now() WHERE document_uid IN (%s, %s)",
        (purged, live),
    )
    async with client(pool, store) as api:
        answers = {
            uid: [
                await api.get(f"/v1/documents/{uid}/revisions/{crvs[uid]}"),
                await api.get(f"/v1/documents/{uid}/revisions/{crvs[uid]}/artifacts/{PAGE[0]}"),
            ]
            for uid in crvs
        }

    def seen(uid: str) -> list[tuple[int, str]]:
        return [(a.status_code, reason(a)) for a in answers[uid]]

    assert seen(deleted) == [(410, "DOCUMENT_DELETED")] * 2
    assert seen(purged) == [(410, "CONTENT_NOT_RETAINED")] * 2
    assert seen(live) == [(410, "CONTENT_NOT_RETAINED")] * 2
    assert store.opened == []


async def test_a_recorded_object_storage_says_is_absent_is_503_content_missing_and_counted(
    conn, pool, store
):
    uid, srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    store.keys.discard(f"documents/{uid}/items/{PAGE[0]}")  # storage lost the page image
    before = reads("artifact", "missing")
    async with client(pool, store) as api:
        lost = await api.get(f"/v1/documents/{uid}/revisions/{crv}/artifacts/{PAGE[0]}")
        store.keys.discard(f"documents/{uid}/revisions/{crv}.json")  # and then the content
        lost_content = await api.get(f"/v1/documents/{uid}/revisions/{crv}")

    assert (lost.status_code, reason(lost)) == (503, "CONTENT_MISSING")
    assert (lost_content.status_code, reason(lost_content)) == (503, "CONTENT_MISSING")
    assert int(lost.headers["retry-after"]) >= 3600  # nothing repairs it in the pilot
    assert reads("artifact", "missing") - before == 1
    assert "documents/" not in lost.text  # no object key in the answer


async def test_storage_that_cannot_answer_is_503_storage_unavailable_and_not_counted_as_missing(
    conn, pool, store
):
    uid, srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    store.down = True
    missing = reads("content", "missing"), reads("artifact", "missing")
    async with client(pool, store) as api:
        answers = [
            await api.get(f"/v1/documents/{uid}/revisions/{crv}"),
            await api.get(f"/v1/documents/{uid}/revisions/{crv}/artifacts/{PAGE[0]}"),
        ]

    assert [(a.status_code, reason(a)) for a in answers] == [(503, "STORAGE_UNAVAILABLE")] * 2
    assert (reads("content", "missing"), reads("artifact", "missing")) == missing


async def test_every_read_logs_its_ids_kind_bytes_and_result_and_never_the_content(
    conn, pool, store, caplog
):
    uid, srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    served = reads("content", "served"), reads("artifact", "served")
    sent = REGISTRY.get_sample_value("kp_canonical_read_bytes_total", {"kind": "artifact"}) or 0.0
    with caplog.at_level(logging.DEBUG):
        async with client(pool, store) as api:
            content = await api.get(f"/v1/documents/{uid}/revisions/{crv}")
            await api.get(f"/v1/documents/{uid}/revisions/{crv}/artifacts/{PAGE[0]}")
            store.keys.discard(f"documents/{uid}/items/{CROP[0]}")
            await api.get(f"/v1/documents/{uid}/revisions/{crv}/artifacts/{CROP[0]}")

    lines = [r for r in caplog.records if r.name == "kp_admission.content"]
    assert [r.correlation for r in lines] == [  # type: ignore[attr-defined]
        {"document_uid": uid, "canonical_revision_id": crv, "kind": "content",
         "bytes": len(content.content), "result": "served"},
        {"document_uid": uid, "canonical_revision_id": crv, "kind": "artifact",
         "bytes": len(PNG), "result": "served"},
        {"document_uid": uid, "canonical_revision_id": crv, "kind": "artifact",
         "bytes": 0, "result": "missing"},
    ]  # fmt: skip
    assert CANARY in content.text  # the control: the canary is in what was read
    assert all(CANARY not in f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert (reads("content", "served"), reads("artifact", "served")) == (
        served[0] + 1,
        served[1] + 1,
    )
    after = REGISTRY.get_sample_value("kp_canonical_read_bytes_total", {"kind": "artifact"})
    assert (after or 0.0) - sent == len(PNG)


class Breaking(Store):
    """Storage whose reads fail after the first chunk."""

    async def open(self, key: str):
        chunks = await super().open(key)

        async def broken():
            yield await anext(chunks)
            raise storage.StorageUnavailable(key)

        return broken()


async def test_a_stream_storage_breaks_off_is_counted_and_logged_as_interrupted(conn, pool, caplog):
    store = Breaking()
    uid, srv = await revision(conn)
    crv = await accept(conn, store, uid, srv)
    before = reads("content", "interrupted")
    with caplog.at_level(logging.INFO, logger="kp_admission.content"):
        async with client(pool, store) as api:
            with pytest.raises(storage.StorageUnavailable):  # the response cannot end well
                await api.get(f"/v1/documents/{uid}/revisions/{crv}")

    assert reads("content", "interrupted") - before == 1
    [line] = [r for r in caplog.records if r.name == "kp_admission.content"]
    assert line.correlation["result"] == "interrupted"  # type: ignore[attr-defined]
    assert line.correlation["bytes"] > 0  # type: ignore[attr-defined]


async def test_the_openapi_document_has_both_reads_with_their_media_types(pool, store):
    async with client(pool, store) as api:
        paths = (await api.get("http://api/openapi.json")).json()["paths"]

    content = paths["/read/v1/documents/{document_uid}/revisions/{canonical_revision_id}"]["get"]
    artifact = paths[
        "/read/v1/documents/{document_uid}/revisions/{canonical_revision_id}/artifacts/{reference}"
    ]["get"]
    assert "application/json" in content["responses"]["200"]["content"]
    assert "x-content-sha256" in {h.lower() for h in content["responses"]["200"]["headers"]}
    assert "application/octet-stream" in artifact["responses"]["200"]["content"]
    for operation in (content, artifact):
        assert {"200", "4XX", "404", "410", "503"} <= set(operation["responses"])
        assert "REVISION_NOT_FOUND" in operation["responses"]["404"]["description"]
        assert "CONTENT_NOT_RETAINED" in operation["responses"]["410"]["description"]
        assert "CONTENT_MISSING" in operation["responses"]["503"]["description"]
    assert "ARTIFACT_NOT_FOUND" in artifact["responses"]["404"]["description"]


class SlowS3:
    """A boto3 S3 client whose object body yields CHUNK bytes per `READ_S`, blocking its thread."""

    READ_S = 0.3

    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def get_object(self, *, Key: str, **_: Any) -> dict:
        data = self.objects[Key]
        reads = iter(range(0, len(data), storage.CHUNK))

        class Body:
            def read(self, size: int) -> bytes:
                start = next(reads, None)
                if start is None:
                    return b""
                if start:  # the first read answers at once, as get_object's headers do
                    time.sleep(SlowS3.READ_S)
                return data[start : start + size]

            def close(self) -> None:
                pass

        return {"Body": Body()}


async def health_while_reading(conn, pool) -> list[float]:
    """The seconds between consecutive /healthz answers, asked every 20 ms while a 3 MiB content
    object streams: a stalled event loop shows as a long gap."""
    fake = Store()
    uid, srv = await revision(conn)
    crv = await accept(conn, fake, uid, srv, artifacts=())
    key = f"documents/{uid}/revisions/{crv}.json"
    big = os.urandom(3 * storage.CHUNK + 1)
    await conn.execute(
        "UPDATE canonical_revision SET content_sha256 = %s, content_size = %s"
        " WHERE canonical_revision_id = %s",
        (sha(big), len(big), crv),
    )
    slow = S3ObjectStore(SlowS3({key: big}), "kp-custody")
    async with client(pool, slow) as api:
        reading = asyncio.create_task(api.get(f"/v1/documents/{uid}/revisions/{crv}"))
        answered = [time.monotonic()]
        while not reading.done():
            assert (await api.get("http://api/healthz")).status_code == 200
            answered.append(time.monotonic())
            await asyncio.sleep(0.02)
        answered.append(time.monotonic())  # a stall inside the last sleep counts too
        read = await reading
    assert (read.status_code, len(read.content)) == (200, len(big))
    return [later - earlier for earlier, later in itertools.pairwise(answered)]


async def test_light_requests_are_answered_while_a_large_object_streams(conn, pool):
    gaps = await health_while_reading(conn, pool)

    assert len(gaps) >= 10  # the read took at least 3 chunks of 0.3 s
    # The first gap also holds the read's own start (its database query); a stall is >= 0.3 s.
    assert 0 <= max(gaps) <= 0.2


async def test_control_a_body_read_on_the_event_loop_delays_them(conn, pool, monkeypatch):
    async def inline(call, /, *args, **kwargs):
        return call(*args, **kwargs)

    monkeypatch.setattr(storage.asyncio, "to_thread", inline)
    gaps = await health_while_reading(conn, pool)

    assert max(gaps) >= SlowS3.READ_S
