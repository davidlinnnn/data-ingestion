"""Admission's object store, one contract for the fake and the S3 adapter. The S3 run needs the
stand-in from tests/s3/compose.yaml and KP_S3_* set (see that file); it is skipped otherwise."""

import os
import uuid

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError

from kp_admission.storage import (
    CHUNK,
    FakeObjectStore,
    ObjectMissing,
    S3ObjectStore,
    StorageUnavailable,
    source_key,
)


@pytest.fixture(params=["fake", pytest.param("s3", marks=pytest.mark.s3)])
def kind(request) -> str:
    if request.param == "s3" and not os.environ.get("KP_S3_ENDPOINT"):
        pytest.skip("KP_S3_ENDPOINT not set; start tests/s3/compose.yaml")
    return request.param


@pytest.fixture
def store(kind):
    if kind == "fake":
        return FakeObjectStore()
    store = S3ObjectStore.from_env()
    try:
        store.client.head_bucket(Bucket=store.bucket)
    except ClientError:
        store.client.create_bucket(Bucket=store.bucket)
    return store


def place(store, key: str, body: bytes = b"%PDF-1.7") -> None:
    if isinstance(store, FakeObjectStore):
        store.keys.add(key)
        store.content[key] = body
    else:
        store.client.put_object(Bucket=store.bucket, Key=key, Body=body)


def unreachable(store):
    if isinstance(store, FakeObjectStore):
        store.down = True
        return store
    client = boto3.client(
        "s3",
        endpoint_url="http://127.0.0.1:9",  # discard port: nothing listens
        aws_access_key_id="x",
        aws_secret_access_key="x",
        region_name="us-east-1",
        config=Config(connect_timeout=1, retries={"max_attempts": 1}),
    )
    return S3ObjectStore(client, store.bucket)


def key() -> str:
    return source_key(f"doc_{uuid.uuid4().hex}", "bat_1", 0, "ab" * 32)


async def test_head_finds_a_placed_object_and_not_an_absent_one(store):
    placed, absent = key(), key()
    place(store, placed)

    assert await store.head(placed) is True
    assert await store.head(absent) is False


async def test_head_raises_when_storage_cannot_answer(store):
    with pytest.raises(StorageUnavailable):
        await unreachable(store).head(key())


async def test_open_streams_a_placed_object_in_chunks_of_at_most_the_chunk_size(store):
    placed, body = key(), os.urandom(CHUNK + 5)
    place(store, placed, body)

    chunks = [chunk async for chunk in await store.open(placed)]

    assert b"".join(chunks) == body
    assert 0 < max(map(len, chunks)) <= CHUNK


async def test_open_tells_an_absent_object_from_storage_that_cannot_answer(store):
    with pytest.raises(ObjectMissing):
        await store.open(key())
    with pytest.raises(StorageUnavailable) as unavailable:
        await unreachable(store).open(key())
    assert not isinstance(unavailable.value, ObjectMissing)


@pytest.mark.s3
async def test_a_bucket_that_does_not_exist_is_unavailable_not_a_missing_object(kind):
    if kind == "fake":
        pytest.skip("only S3 has buckets")
    store = S3ObjectStore.from_env()
    elsewhere = S3ObjectStore(store.client, f"kp-absent-{uuid.uuid4().hex[:8]}")

    with pytest.raises(StorageUnavailable) as unavailable:
        await elsewhere.open(key())
    assert not isinstance(unavailable.value, ObjectMissing)


def stored(store, key: str) -> bytes | None:
    """The object's bytes, None when there is none."""
    if isinstance(store, FakeObjectStore):
        return store.content.get(key)
    try:
        return store.client.get_object(Bucket=store.bucket, Key=key)["Body"].read()
    except ClientError:
        return None


PART = 5 * 2**20  # S3's smallest part but the last


async def test_an_upload_appears_only_once_completed(store):
    target = key()
    upload_id = await store.create_upload(target)
    etags = [
        await store.upload_part(target, upload_id, 1, b"a" * PART),
        await store.upload_part(target, upload_id, 2, b"b"),
    ]

    assert await store.head(target) is False
    await store.complete_upload(target, upload_id, etags)
    assert stored(store, target) == b"a" * PART + b"b"


async def test_an_empty_file_is_one_empty_part(store):
    target = key()
    upload_id = await store.create_upload(target)
    await store.complete_upload(
        target, upload_id, [await store.upload_part(target, upload_id, 1, b"")]
    )

    assert stored(store, target) == b""


async def test_incomplete_uploads_are_listed_by_their_full_key_only(store):
    target, other = key(), key()
    upload_id = await store.create_upload(target)
    await store.create_upload(other)

    assert await store.incomplete_uploads(target) == [upload_id]


async def test_an_aborted_upload_leaves_nothing_and_cannot_complete(store):
    target = key()
    upload_id = await store.create_upload(target)
    etag = await store.upload_part(target, upload_id, 1, b"x")
    await store.abort_upload(target, upload_id)

    assert await store.incomplete_uploads(target) == []
    with pytest.raises(StorageUnavailable):
        await store.complete_upload(target, upload_id, [etag])
    assert await store.head(target) is False


async def test_delete_removes_the_object_and_succeeds_for_an_absent_one(store):
    placed, absent = key(), key()
    place(store, placed)

    await store.delete(placed)
    await store.delete(absent)
    assert await store.head(placed) is False


async def test_every_operation_raises_when_storage_cannot_answer(store):
    down = unreachable(store)
    for call in (
        down.create_upload(key()),
        down.upload_part(key(), "u", 1, b""),
        down.complete_upload(key(), "u", ["e"]),
        down.abort_upload(key(), "u"),
        down.incomplete_uploads(key()),
        down.delete(key()),
    ):
        with pytest.raises(StorageUnavailable):
            await call


def test_the_key_names_the_document_batch_item_and_digest():
    assert source_key("doc_7f3", "bat_01J", 2, "9f2c") == "documents/doc_7f3/files/bat_01J/2/9f2c"
