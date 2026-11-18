"""Admission's object store, one contract for the fake and the S3 adapter. The S3 run needs the
stand-in from tests/s3/compose.yaml and KP_S3_* set (see that file); it is skipped otherwise."""

import os
import uuid

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError

from kp_admission.storage import FakeObjectStore, S3ObjectStore, StorageUnavailable, source_key


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


def place(store, key: str) -> None:
    if isinstance(store, FakeObjectStore):
        store.keys.add(key)
    else:
        store.client.put_object(Bucket=store.bucket, Key=key, Body=b"%PDF-1.7")


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


def test_the_key_names_the_document_batch_item_and_digest():
    assert source_key("doc_7f3", "bat_01J", 2, "9f2c") == "documents/doc_7f3/files/bat_01J/2/9f2c"
