"""ObjectStore port over the S3 API (#129 物件儲存與登錄). One real adapter (S3) and an
in-process fake; both must pass tests/ports/test_object_store_contract.py."""

import asyncio
import os
from typing import Any, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


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
        if key in self.objects:
            return False
        self.objects[key] = data
        return True

    async def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        try:
            return self.objects[key]
        except KeyError as exc:
            raise ObjectNotFound(key) from exc

    async def head(self, key: str) -> int | None:
        data = self.objects.get(key)
        return None if data is None else len(data)

    async def list_prefix(self, prefix: str) -> list[str]:
        return sorted(key for key in self.objects if key.startswith(prefix))


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
        client = boto3.client(
            "s3",
            endpoint_url=os.environ["KP_S3_ENDPOINT"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            config=Config(s3={"addressing_style": "path"}),
        )
        return cls(client, os.environ["KP_S3_BUCKET"])

    async def put_if_absent(self, key: str, data: bytes) -> bool:
        retries = 0
        while True:
            try:
                await asyncio.to_thread(
                    self.client.put_object,
                    Bucket=self.bucket,
                    Key=key,
                    Body=data,
                    IfNoneMatch="*",
                )
                return True
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if code in {"412", "PreconditionFailed"} or status == 412:
                    return False
                if (
                    code not in {"409", "ConditionalRequestConflict"} and status != 409
                ) or retries == 5:
                    raise
                await asyncio.sleep(0.1 * 2**retries)
                retries += 1

    async def put(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(self.client.put_object, Bucket=self.bucket, Key=key, Body=data)

    async def get(self, key: str) -> bytes:
        def read() -> bytes:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"]
            try:
                return body.read()
            finally:
                body.close()

        try:
            return await asyncio.to_thread(read)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
                raise ObjectNotFound(key) from exc
            raise

    async def head(self, key: str) -> int | None:
        try:
            response = await asyncio.to_thread(self.client.head_object, Bucket=self.bucket, Key=key)
            return response["ContentLength"]
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
                return None
            raise

    async def list_prefix(self, prefix: str) -> list[str]:
        def list_keys() -> list[str]:
            pages = self.client.get_paginator("list_objects_v2").paginate(
                Bucket=self.bucket, Prefix=prefix
            )
            return sorted(item["Key"] for page in pages for item in page.get("Contents", []))

        return await asyncio.to_thread(list_keys)
