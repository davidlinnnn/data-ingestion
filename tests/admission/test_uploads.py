"""The upload endpoint (#194, admission spec §5.2): over the platform API with a real database, the
pilot's allow-all provider and the object store's fake. The per-outcome cases of §5.2 are #99's;
these are #194's acceptance criteria and the order of upload and finalization."""

import asyncio
import hashlib
import itertools
import os
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from psycopg_pool import AsyncConnectionPool

from kp_admission import adoption, storage
from kp_admission.api import SourceCredential, app
from kp_admission.authz import AllowAll
from kp_admission.batches import Intake, expire
from kp_admission.storage import FakeObjectStore, ObjectStore, S3ObjectStore, source_key
from kp_admission.uploads import PART, clean

pytestmark = pytest.mark.docker

PDF = b"%PDF-1.7\n" + os.urandom(2000)
PNG = b"\x89PNG\r\n\x1a\n" + os.urandom(2000)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


CREDENTIALS = {
    sha(b"hr-km"): SourceCredential.model_validate(
        {
            "credential_id": "hr-1",
            "tenant_id": "t1",
            "source_id": "hr-km",
            "scopes": ["submit", "manage_relations"],
        }
    )
}


def item(document_id: str, content: bytes, media_type: str = "application/pdf") -> dict[str, Any]:
    declared = {"path": "files/main.pdf", "role": "main", "sha256": sha(content)}
    declared |= {"size": len(content), "media_type": media_type}
    return {
        "document_id": document_id,
        "source_version": "1",
        "resources": ["hr-all"],
        "files": [declared],
    }


@pytest.fixture
async def pool(dsn):
    async with AsyncConnectionPool(dsn, kwargs={"autocommit": True}) as pool:
        yield pool


@pytest.fixture
def store() -> FakeObjectStore:
    return FakeObjectStore()


@pytest.fixture
async def hr(pool, store, conn):
    """hr-km's client, with its Resource hr-all registered and PDF adopted."""
    application = app(AllowAll(pool), {}, CREDENTIALS, pool, Intake(store))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(application),
        base_url="http://api",
        headers={"authorization": "Bearer hr-km"},
    ) as client:
        assert (await client.put("/v1/resources/hr-all")).status_code == 201
        await adoption.adopt(conn, tenant_id="t1", media_type="application/pdf", version="p@1")
        yield client


async def declare(client: httpx.AsyncClient, *items: dict) -> dict:
    declared = await client.post("/v1/batches", json={"items": list(items)})
    assert declared.status_code == 201, declared.text
    return declared.json()


def key_of(batch: dict, index: int, content: bytes) -> str:
    return source_key(batch["items"][index]["document_uid"], batch["batch_id"], index, sha(content))


async def chunks(data: bytes, size: int = 64 * 2**10) -> AsyncIterator[bytes]:
    for start in range(0, len(data), size):
        yield data[start : start + size]


async def put(client: httpx.AsyncClient, url: str, data: bytes) -> httpx.Response:
    headers = {"content-length": str(len(data)), "content-type": "application/octet-stream"}
    return await client.put(url, content=chunks(data), headers=headers)


async def test_an_uploaded_file_is_admitted_at_its_custody_key(hr, store):
    batch = await declare(hr, item("A", PDF))
    url = batch["items"][0]["uploads"][0]["url"]

    assert (await put(hr, url, PDF)).status_code == 204
    assert (await put(hr, url, PDF)).status_code == 204  # a repeat changes nothing
    finalized = await hr.post(f"/v1/batches/{batch['batch_id']}/finalize")

    assert finalized.status_code == 202
    assert finalized.json()["items"][0]["status"] == "queued"
    assert store.content[key_of(batch, 0, PDF)] == PDF


@pytest.mark.parametrize(
    ("declared", "status", "reason"),
    [
        (
            item("A", PDF) | {"files": [item("A", PDF)["files"][0] | {"sha256": sha(b"other")}]},
            422,
            "DIGEST_MISMATCH",
        ),
        (item("A", PNG), 422, "MEDIA_TYPE_MISMATCH"),
    ],
)
async def test_a_file_that_differs_from_its_declaration_is_not_staged(
    hr, store, declared, status, reason
):
    batch = await declare(hr, declared)
    content = PDF if reason == "DIGEST_MISMATCH" else PNG
    sent = await put(hr, batch["items"][0]["uploads"][0]["url"], content)

    assert (sent.status_code, sent.json()["error"]["details"][0]["reason"]) == (status, reason)
    key = source_key(
        batch["items"][0]["document_uid"], batch["batch_id"], 0, declared["files"][0]["sha256"]
    )
    assert await store.head(key) is False
    assert await store.incomplete_uploads(key) == []


async def test_a_size_other_than_declared_is_refused_before_any_byte_is_stored(hr, store):
    batch = await declare(hr, item("A", PDF))
    sent = await put(hr, batch["items"][0]["uploads"][0]["url"], PDF + b"x")

    assert sent.json()["error"]["details"][0]["reason"] == "SIZE_MISMATCH"
    assert store.parts == []


async def test_a_50_mb_file_is_stored_in_parts_of_8_mib(hr, store):
    content = b"%PDF-1.7\n" + os.urandom(50 * 10**6)
    batch = await declare(hr, item("A", content))

    assert (await put(hr, batch["items"][0]["uploads"][0]["url"], content)).status_code == 204
    assert store.parts[:-1] == [PART] * (len(content) // PART)
    assert 0 < store.parts[-1] <= PART
    assert store.content[key_of(batch, 0, content)] == content


async def test_an_upload_that_ends_after_finalization_is_refused_and_leaves_nothing(hr, store):
    batch = await declare(hr, item("A", PDF))
    finalized: list[int] = []

    async def finalized_midway() -> AsyncIterator[bytes]:
        yield PDF[:1000]
        finalized.append((await hr.post(f"/v1/batches/{batch['batch_id']}/finalize")).status_code)
        yield PDF[1000:]

    sent = await hr.put(
        batch["items"][0]["uploads"][0]["url"],
        content=finalized_midway(),
        headers={"content-length": str(len(PDF))},
    )

    assert finalized == [422]  # its only item is FILES_MISSING
    assert sent.json()["error"]["details"][0]["reason"] == "BATCH_FINALIZED"
    assert await store.head(key_of(batch, 0, PDF)) is False
    assert await store.incomplete_uploads(key_of(batch, 0, PDF)) == []


async def test_upload_urls_name_the_public_origin_whatever_url_the_request_reached(hr, pool, store):
    intake = Intake(store, public_url="https://kp.example")
    behind_the_ingress = app(AllowAll(pool), {}, CREDENTIALS, pool, intake)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(behind_the_ingress),
        base_url="http://10.0.0.7:8080",
        headers={"authorization": "Bearer hr-km"},
    ) as internal:
        batch = await declare(internal, item("A", PDF))

    url = batch["items"][0]["uploads"][0]["url"]
    assert url == f"https://kp.example/v1/batches/{batch['batch_id']}/items/0/files/files/main.pdf"


def attachment(content: bytes) -> dict[str, Any]:
    return {
        "path": "files/figure.png",
        "role": "attachment",
        "sha256": sha(content),
        "size": len(content),
        "media_type": "image/png",
    }


async def stage(client: httpx.AsyncClient, batch: dict, index: int, content: bytes) -> None:
    """Uploads `content` as the main file of the batch's item `index`."""
    url = f"/v1/batches/{batch['batch_id']}/items/{index}/files/files/main.pdf"
    assert (await put(client, url, content)).status_code == 204


async def test_the_cleanup_removes_what_no_source_revision_holds_and_repeats_as_a_no_op(
    hr, store, conn
):
    v2 = b"%PDF-1.7 v2" + os.urandom(100)
    first = await declare(hr, item("A", PDF))
    await stage(hr, first, 0, PDF)
    assert (await hr.post(f"/v1/batches/{first['batch_id']}/finalize")).status_code == 202
    await conn.execute("UPDATE request SET state = 'succeeded'")  # processed (#97)
    await conn.execute("UPDATE source_revision SET outcome = 'accepted'")

    # A's v2 twice: the batch finalized second resolves it by §6.4. B misses its figure.
    a2 = item("A", v2) | {"source_version": "2"}
    b = item("B", PDF) | {"files": [item("B", PDF)["files"][0], attachment(PNG)]}
    admitting, repeating, expiring = (
        await declare(hr, a2, b),
        await declare(hr, a2),
        await declare(hr, item("C", PDF)),
    )
    for batch, index, content in [
        (admitting, 0, v2),
        (admitting, 1, PDF),
        (repeating, 0, v2),
        (expiring, 0, PDF),
    ]:
        await stage(hr, batch, index, content)
    a2_key, b_key = key_of(admitting, 0, v2), key_of(admitting, 1, PDF)
    for interrupted in (a2_key, b_key):  # as an api pod killed during a transfer leaves them
        await store.create_upload(interrupted)
    admitted = (await hr.post(f"/v1/batches/{admitting['batch_id']}/finalize")).json()["items"]
    assert [i["status"] for i in admitted] == ["queued", "rejected"]
    repeated = (await hr.post(f"/v1/batches/{repeating['batch_id']}/finalize")).json()["items"]
    assert repeated[0]["source_revision_id"] == admitted[0]["source_revision_id"]  # §6.4
    repeated_key, expired_key = key_of(repeating, 0, v2), key_of(expiring, 0, PDF)
    held = {key_of(first, 0, PDF), a2_key}

    assert await clean(conn, store) == 0  # every batch ended under an hour ago
    assert {b_key, repeated_key, expired_key} <= store.keys

    await conn.execute(
        "UPDATE batch SET finalized_at = finalized_at - interval '1 hour',"
        " expires_at = expires_at - interval '25 hours'"
    )
    assert await expire(conn) == 1
    assert await clean(conn, store) == 4
    assert await clean(conn, store) == 0

    assert store.keys == held
    assert {k: store.content[k] for k in held} == {key_of(first, 0, PDF): PDF, a2_key: v2}
    for key in (a2_key, b_key):
        assert await store.incomplete_uploads(key) == []


class SlowS3:
    """A boto3 S3 client whose every part takes `PART_S` to store, blocking its thread."""

    PART_S = 0.3

    def create_multipart_upload(self, **_: Any) -> dict:
        return {"UploadId": "u1"}

    def upload_part(self, **_: Any) -> dict:
        time.sleep(self.PART_S)
        return {"ETag": "e"}

    def complete_multipart_upload(self, **_: Any) -> dict:
        return {}

    def abort_multipart_upload(self, **_: Any) -> dict:
        return {}


async def health_while_uploading(pool, conn, store: ObjectStore) -> list[float]:
    """The seconds between consecutive /healthz answers, asked every 20 ms while a 3-part file
    uploads: a stalled event loop shows as a long gap."""
    application = app(AllowAll(pool), {}, CREDENTIALS, pool, Intake(store))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(application),
        base_url="http://api",
        headers={"authorization": "Bearer hr-km"},
    ) as client:
        assert (await client.put("/v1/resources/hr-all")).status_code == 201
        await adoption.adopt(conn, tenant_id="t1", media_type="application/pdf", version="p@1")
        content = b"%PDF-1.7\n" + os.urandom(2 * PART)
        batch = await declare(client, item("A", content))
        uploading = asyncio.create_task(
            put(client, batch["items"][0]["uploads"][0]["url"], content)
        )
        answered = [time.monotonic()]
        while not uploading.done():
            assert (await client.get("/healthz")).status_code == 200
            answered.append(time.monotonic())
            await asyncio.sleep(0.02)
        assert (await uploading).status_code == 204
    return [later - earlier for earlier, later in itertools.pairwise(answered)]


async def test_light_requests_are_answered_while_a_file_uploads(pool, conn):
    gaps = await health_while_uploading(pool, conn, S3ObjectStore(SlowS3(), "kp-custody"))

    assert len(gaps) >= 10  # the upload took at least 3 parts of 0.3 s
    assert 0 <= max(gaps) <= 0.1


async def test_control_a_storage_call_on_the_event_loop_delays_them(pool, conn, monkeypatch):
    async def inline(call, /, *args, **kwargs):
        return call(*args, **kwargs)

    monkeypatch.setattr(storage.asyncio, "to_thread", inline)
    gaps = await health_while_uploading(pool, conn, S3ObjectStore(SlowS3(), "kp-custody"))

    assert max(gaps) >= SlowS3.PART_S
