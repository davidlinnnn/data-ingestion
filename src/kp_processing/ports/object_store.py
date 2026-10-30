"""ObjectStore port over the S3 API (#129 物件儲存與登錄). One real adapter (S3) and an
in-process fake; both must pass tests/ports/test_object_store_contract.py."""

from typing import Any, Protocol


class ObjectNotFound(KeyError):
    pass


class ObjectStore(Protocol):
    async def put_if_absent(self, key: str, data: bytes) -> bool:
        """Write once. True when this call created the object; False when the key already
        existed (the existing object is left untouched). Of concurrent calls on one key,
        exactly one returns True."""
        ...

    async def put(self, key: str, data: bytes) -> None:
        """Create or overwrite."""
        ...

    async def get(self, key: str) -> bytes:
        """Raises ObjectNotFound."""
        ...

    async def head(self, key: str) -> int | None:
        """Size in bytes, or None when absent."""
        ...

    async def list_prefix(self, prefix: str) -> list[str]:
        """Every key starting with prefix, sorted; no pagination limit."""
        ...


class DictObjectStore:
    """In-process fake for tests."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put_if_absent(self, key: str, data: bytes) -> bool:
        raise NotImplementedError

    async def put(self, key: str, data: bytes) -> None:
        raise NotImplementedError

    async def get(self, key: str) -> bytes:
        raise NotImplementedError

    async def head(self, key: str) -> int | None:
        raise NotImplementedError

    async def list_prefix(self, prefix: str) -> list[str]:
        raise NotImplementedError


class S3ObjectStore:
    """S3 API adapter (boto3; calls run in a worker thread). put_if_absent uses a
    conditional put (If-None-Match: *); 412 PreconditionFailed means another writer won.
    A 409 ConditionalRequestConflict (a concurrent conditional write in flight) is retried.
    Tested only against MinIO, never against a mocked boto3."""

    def __init__(self, client: Any, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    @classmethod
    def from_env(cls) -> "S3ObjectStore":
        """KP_S3_ENDPOINT (URL), KP_S3_BUCKET, and the standard AWS_ACCESS_KEY_ID /
        AWS_SECRET_ACCESS_KEY / AWS_REGION (default us-east-1). Path-style addressing."""
        raise NotImplementedError

    async def put_if_absent(self, key: str, data: bytes) -> bool:
        raise NotImplementedError

    async def put(self, key: str, data: bytes) -> None:
        raise NotImplementedError

    async def get(self, key: str) -> bytes:
        raise NotImplementedError

    async def head(self, key: str) -> int | None:
        raise NotImplementedError

    async def list_prefix(self, prefix: str) -> list[str]:
        raise NotImplementedError
