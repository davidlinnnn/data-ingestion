"""Storage behaviour the #184 upload design relies on, probed against one S3 endpoint.

    env KP_S3_ENDPOINT=http://127.0.0.1:9100 KP_S3_BUCKET=kp-dev \
        AWS_ACCESS_KEY_ID=kpdev AWS_SECRET_ACCESS_KEY=kpdev-secret \
        .venv/bin/python docs/validation/184/storage_probe.py

Works under the key prefix probe184/{random}/ of the bucket and deletes what it wrote.
Exits 1 when a required behaviour is missing. The results of 2026-11-11 are in the file
upload design, section 6.7.
"""

import sys
import uuid
from collections.abc import Callable
from typing import Any

from botocore.exceptions import ClientError

from kp_canonicalization.ports.object_store import S3ObjectStore

PART = b"A" * 6 * 2**20  # above the 5 MiB minimum part size


def status(call: Callable[..., Any], **kwargs: Any) -> int:
    try:
        call(**kwargs)
        return 200
    except ClientError as exc:
        return exc.response["ResponseMetadata"]["HTTPStatusCode"]


def main() -> int:
    store = S3ObjectStore.from_env()
    s3, bucket = store.client, store.bucket
    folder = f"probe184/{uuid.uuid4().hex[:8]}/"
    key, other = folder + "item/a", folder + "item/b"
    failed = False

    def begin(body: bytes) -> tuple[str, dict[str, Any]]:
        upload = s3.create_multipart_upload(Bucket=bucket, Key=key)["UploadId"]
        etag = s3.upload_part(Bucket=bucket, Key=key, UploadId=upload, PartNumber=1, Body=body)
        return upload, {"Parts": [{"PartNumber": 1, "ETag": etag["ETag"]}]}

    def uploads(prefix: str) -> int:
        listed = s3.list_multipart_uploads(Bucket=bucket, Prefix=prefix)
        return len(listed.get("Uploads", []))

    def report(required: bool, name: str, ok: bool, seen: object) -> None:
        nonlocal failed
        failed |= required and not ok
        label = "ok" if ok else ("MISSING" if required else "no")
        print(f"{'required' if required else 'optional'}  {label:8} {name}: {seen}")

    upload, parts = begin(PART)
    seen = (
        status(s3.head_object, Bucket=bucket, Key=key),
        s3.list_objects_v2(Bucket=bucket, Prefix=folder)["KeyCount"],
    )
    report(True, "an upload in parts is invisible until completed", seen == (404, 0), seen)
    report(True, "incomplete uploads are listed by the exact key", uploads(key) == 1, uploads(key))
    report(False, "incomplete uploads are listed by a folder prefix", uploads(folder) == 1, "")
    s3.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload)
    done = status(
        s3.complete_multipart_upload,
        Bucket=bucket,
        Key=key,
        UploadId=upload,
        MultipartUpload=parts,
    )
    seen = (done, status(s3.head_object, Bucket=bucket, Key=key), uploads(key))
    report(True, "an aborted upload cannot complete and leaves nothing", seen == (404, 404, 0), seen)
    deleted = status(s3.delete_object, Bucket=bucket, Key=key)
    report(True, "deleting an absent key succeeds", deleted in (200, 204), deleted)

    upload, parts = begin(PART)
    s3.complete_multipart_upload(Bucket=bucket, Key=key, UploadId=upload, MultipartUpload=parts)
    upload, parts = begin(b"B" * len(PART))
    done = status(
        s3.complete_multipart_upload,
        Bucket=bucket,
        Key=key,
        UploadId=upload,
        MultipartUpload=parts,
        IfNoneMatch="*",
    )
    report(False, "completing onto an existing key with If-None-Match: * is refused", done == 412, done)
    if done == 412:
        s3.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload)

    s3.put_object(Bucket=bucket, Key=other, Body=b"other")
    source = {"Bucket": bucket, "Key": other}
    copied = status(s3.copy_object, Bucket=bucket, Key=key, CopySource=source, IfNoneMatch="*")
    kept = s3.get_object(Bucket=bucket, Key=key, Range="bytes=0-0")["Body"].read() == b"A"
    seen = f"{copied}, existing object {'kept' if kept else 'OVERWRITTEN'}"
    report(False, "copying onto an existing key with If-None-Match: * is refused", kept, seen)

    for name in (key, other):
        s3.delete_object(Bucket=bucket, Key=name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
