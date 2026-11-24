"""Admission's object store operations on the custody bucket (admission spec §10, ADR-0012):
`head` for finalization (§6.2 step 3), multipart uploads for the upload endpoint (§5.2),
delete and abort for the upload cleanup (§6.2), and `open` for the content reads (§5.9). They
rely only on the behaviours the document submission guide §6.7 marks required. The S3 adapter
and the fake both pass tests/admission/test_storage_contract.py."""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

CHUNK = 2**20  # the most bytes `open` yields at once


class StorageUnavailable(Exception):
    """Storage did not perform the operation, or could not say whether the object exists."""


class ObjectMissing(Exception):
    """Storage answered that the object does not exist."""


class ObjectStore(Protocol):
    """Every operation raises StorageUnavailable when storage does not perform it."""

    bucket: str

    async def head(self, key: str) -> bool:
        """Whether the object exists."""
        ...

    async def open(self, key: str) -> AsyncIterator[bytes]:
        """The object's bytes, in chunks of at most CHUNK. Raises ObjectMissing when storage
        answers that it does not exist, before any chunk; a failure while reading raises
        StorageUnavailable from the iterator."""
        ...

    async def create_upload(self, key: str) -> str:
        """Starts a multipart upload to `key` and returns its upload id. Nothing appears at `key`
        until it completes."""
        ...

    async def upload_part(
        self, key: str, upload_id: str, number: int, data: bytes | bytearray
    ) -> str:
        """Stores part `number` (from 1) and returns its ETag. Every part but the last holds at
        least 5 MiB."""
        ...

    async def complete_upload(self, key: str, upload_id: str, etags: list[str]) -> None:
        """Makes the parts, in order, the object at `key`; an aborted upload cannot complete."""
        ...

    async def abort_upload(self, key: str, upload_id: str) -> None:
        """Discards the upload and its parts."""
        ...

    async def incomplete_uploads(self, key: str) -> list[str]:
        """The upload ids of the uploads to exactly `key` that neither completed nor aborted."""
        ...

    async def delete(self, key: str) -> None:
        """Removes the object; an absent one is no error."""
        ...


def source_key(document_uid: str, batch_id: str, index: int, sha256: str) -> str:
    """The key of a source file uploaded by one batch item (§10)."""
    return f"documents/{document_uid}/files/{batch_id}/{index}/{sha256}"


class FakeObjectStore:
    """In-process fake for tests: `keys` exist, those completed through an upload with their
    `content`; `parts` records the size of every part stored; nothing answers while `down`."""

    def __init__(self, bucket: str = "kp-custody") -> None:
        self.bucket = bucket
        self.keys: set[str] = set()
        self.content: dict[str, bytes] = {}
        self.parts: list[int] = []
        self.down = False
        self._uploads: dict[str, tuple[str, dict[int, bytes]]] = {}

    def _raise_if_down(self, key: str) -> None:
        if self.down:
            raise StorageUnavailable(key)

    async def head(self, key: str) -> bool:
        self._raise_if_down(key)
        return key in self.keys

    async def open(self, key: str) -> AsyncIterator[bytes]:
        self._raise_if_down(key)
        if key not in self.keys:
            raise ObjectMissing(key)
        return _chunks(self.content.get(key, b""))

    async def create_upload(self, key: str) -> str:
        self._raise_if_down(key)
        upload_id = uuid.uuid4().hex
        self._uploads[upload_id] = (key, {})
        return upload_id

    async def upload_part(
        self, key: str, upload_id: str, number: int, data: bytes | bytearray
    ) -> str:
        self._raise_if_down(key)
        if upload_id not in self._uploads:
            raise StorageUnavailable(key)
        self._uploads[upload_id][1][number] = bytes(data)
        self.parts.append(len(data))
        return str(number)

    async def complete_upload(self, key: str, upload_id: str, etags: list[str]) -> None:
        self._raise_if_down(key)
        if upload_id not in self._uploads:
            raise StorageUnavailable(key)
        _, parts = self._uploads.pop(upload_id)
        self.content[key] = b"".join(parts[int(etag)] for etag in etags)
        self.keys.add(key)

    async def abort_upload(self, key: str, upload_id: str) -> None:
        self._raise_if_down(key)
        self._uploads.pop(upload_id, None)

    async def incomplete_uploads(self, key: str) -> list[str]:
        self._raise_if_down(key)
        return [upload_id for upload_id, (k, _) in self._uploads.items() if k == key]

    async def delete(self, key: str) -> None:
        self._raise_if_down(key)
        self.keys.discard(key)
        self.content.pop(key, None)


class S3ObjectStore:
    """The S3 API through boto3, each call in a thread (CODING_STANDARDS § Platform API)."""

    def __init__(self, client: Any, bucket: str) -> None:
        self.client, self.bucket = client, bucket

    @classmethod
    def from_env(cls) -> "S3ObjectStore":
        """KP_S3_ENDPOINT (URL), KP_S3_BUCKET, and the standard AWS_ACCESS_KEY_ID /
        AWS_SECRET_ACCESS_KEY / AWS_REGION (default us-east-1), as the processing workers read
        them: source files and processing results share the bucket (§10)."""
        client = boto3.client(
            "s3",
            endpoint_url=os.environ["KP_S3_ENDPOINT"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 2}),
        )
        return cls(client, os.environ["KP_S3_BUCKET"])

    async def _call(self, operation: Callable[..., Any], key: str, **params: Any) -> Any:
        try:
            return await asyncio.to_thread(operation, Bucket=self.bucket, Key=key, **params)
        except (ClientError, BotoCoreError) as error:  # BotoCoreError: no connection, timeout
            raise StorageUnavailable(key) from error

    async def head(self, key: str) -> bool:
        try:
            await self._call(self.client.head_object, key)
            return True
        except StorageUnavailable as unavailable:
            error = unavailable.__cause__
            if isinstance(error, ClientError) and _status(error) == 404:
                return False
            raise

    async def open(self, key: str) -> AsyncIterator[bytes]:
        try:
            answer = await self._call(self.client.get_object, key)
        except StorageUnavailable as unavailable:
            error = unavailable.__cause__
            # By code: a bucket that does not exist is a 404 too, and it is no lost object.
            if isinstance(error, ClientError) and error.response["Error"]["Code"] == "NoSuchKey":
                raise ObjectMissing(key) from error
            raise
        return _body(answer["Body"], key)

    async def create_upload(self, key: str) -> str:
        return (await self._call(self.client.create_multipart_upload, key))["UploadId"]

    async def upload_part(
        self, key: str, upload_id: str, number: int, data: bytes | bytearray
    ) -> str:
        answer = await self._call(
            self.client.upload_part, key, UploadId=upload_id, PartNumber=number, Body=data
        )
        return answer["ETag"]

    async def complete_upload(self, key: str, upload_id: str, etags: list[str]) -> None:
        parts = [{"ETag": etag, "PartNumber": n} for n, etag in enumerate(etags, 1)]
        await self._call(
            self.client.complete_multipart_upload,
            key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

    async def abort_upload(self, key: str, upload_id: str) -> None:
        await self._call(self.client.abort_multipart_upload, key, UploadId=upload_id)

    async def incomplete_uploads(self, key: str) -> list[str]:
        # By full key: AIStor lists incomplete uploads by object name only (guide §6.7).
        try:
            answer = await asyncio.to_thread(
                self.client.list_multipart_uploads, Bucket=self.bucket, Prefix=key
            )
        except (ClientError, BotoCoreError) as error:
            raise StorageUnavailable(key) from error
        return [u["UploadId"] for u in answer.get("Uploads", []) if u["Key"] == key]

    async def delete(self, key: str) -> None:
        await self._call(self.client.delete_object, key)


def _status(error: ClientError) -> int | None:
    return error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")


async def _chunks(data: bytes) -> AsyncIterator[bytes]:
    for start in range(0, len(data), CHUNK):
        yield data[start : start + CHUNK]


async def _body(body: Any, key: str) -> AsyncIterator[bytes]:
    """A boto3 streaming body, each read in a thread."""
    try:
        while chunk := await asyncio.to_thread(body.read, CHUNK):
            yield chunk
    except (ClientError, BotoCoreError) as error:
        raise StorageUnavailable(key) from error
    finally:
        body.close()
