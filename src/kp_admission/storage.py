"""Admission's object store operations on the custody bucket (admission spec §10, ADR-0012). So
far only `head`, which finalization asks (§6.2 step 3). The S3 adapter and the fake both pass
tests/admission/test_storage_contract.py."""

import asyncio
import os
from typing import Any, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


class StorageUnavailable(Exception):
    """Storage could not say whether the object exists."""


class ObjectStore(Protocol):
    bucket: str

    async def head(self, key: str) -> bool:
        """Whether the object exists; StorageUnavailable when storage cannot say."""
        ...


def source_key(document_uid: str, batch_id: str, index: int, sha256: str) -> str:
    """The key of a source file uploaded by one batch item (§10)."""
    return f"documents/{document_uid}/files/{batch_id}/{index}/{sha256}"


class FakeObjectStore:
    """In-process fake for tests: `keys` exist; nothing answers while `down`."""

    def __init__(self, bucket: str = "kp-custody") -> None:
        self.bucket = bucket
        self.keys: set[str] = set()
        self.down = False

    async def head(self, key: str) -> bool:
        if self.down:
            raise StorageUnavailable(key)
        return key in self.keys


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

    async def head(self, key: str) -> bool:
        try:
            await asyncio.to_thread(self.client.head_object, Bucket=self.bucket, Key=key)
            return True
        except ClientError as error:
            if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            raise StorageUnavailable(key) from error
        except BotoCoreError as error:  # no connection, timeout
            raise StorageUnavailable(key) from error
