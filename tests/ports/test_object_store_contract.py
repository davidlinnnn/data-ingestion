"""One contract, two implementations. The S3 run needs the MinIO from tests/minio/compose.yaml
and KP_S3_* set (see that file); it is skipped otherwise, e.g. inside the Codex sandbox."""

import asyncio
import os
import uuid

import pytest

from kp_processing.ports.object_store import (
    DictObjectStore,
    ObjectNotFound,
    ObjectStore,
    S3ObjectStore,
)


@pytest.fixture(params=["dict", pytest.param("s3", marks=pytest.mark.minio)])
def store(request) -> ObjectStore:
    if request.param == "dict":
        return DictObjectStore()
    if not os.environ.get("KP_S3_ENDPOINT"):
        pytest.skip("KP_S3_ENDPOINT not set; start tests/minio/compose.yaml")
    return S3ObjectStore.from_env()


@pytest.fixture
def prefix() -> str:
    return f"contract-test/{uuid.uuid4().hex}/"


async def test_put_if_absent_creates_once_and_keeps_the_first(store, prefix):
    key = prefix + "items/a.json"

    assert await store.put_if_absent(key, b"first") is True
    assert await store.put_if_absent(key, b"second") is False
    assert await store.get(key) == b"first"


async def test_concurrent_put_if_absent_has_exactly_one_winner(store, prefix):
    key = prefix + "items/race.json"
    payloads = [f"writer-{i}".encode() for i in range(8)]

    results = await asyncio.gather(*(store.put_if_absent(key, p) for p in payloads))

    assert results.count(True) == 1
    winner = payloads[results.index(True)]
    assert await store.get(key) == winner


async def test_put_overwrites(store, prefix):
    key = prefix + "result.json"
    await store.put(key, b"v1")
    await store.put(key, b"v2")

    assert await store.get(key) == b"v2"


async def test_get_of_a_missing_key_raises_object_not_found(store, prefix):
    with pytest.raises(ObjectNotFound):
        await store.get(prefix + "missing")


async def test_head_reports_size_or_none(store, prefix):
    await store.put(prefix + "five", b"12345")
    await store.put(prefix + "empty", b"")

    assert await store.head(prefix + "five") == 5
    assert await store.head(prefix + "empty") == 0
    assert await store.head(prefix + "missing") is None


async def test_list_prefix_returns_matching_keys_sorted(store, prefix):
    for name in ["b/2", "a/1", "b/1", "c"]:
        await store.put(prefix + "docs/" + name, b"x")
    await store.put(prefix + "docsX/other", b"x")

    assert await store.list_prefix(prefix + "docs/b/") == [prefix + "docs/b/1", prefix + "docs/b/2"]
    assert await store.list_prefix(prefix + "docs/") == [
        prefix + "docs/" + n for n in ["a/1", "b/1", "b/2", "c"]
    ]
    assert await store.list_prefix(prefix + "nothing/") == []


async def test_list_prefix_is_not_limited_to_one_page(store, prefix):
    keys = [f"{prefix}many/{i:04d}" for i in range(1005)]  # S3 pages at 1000
    await asyncio.gather(*(store.put(k, b"") for k in keys))

    assert await store.list_prefix(prefix + "many/") == keys
