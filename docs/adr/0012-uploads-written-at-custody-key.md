# Write uploads at their custody key; admit by a database commit alone

The upload endpoint writes each file once, after verifying its size, SHA-256 and
media type, to the object key that its `custody_ref` will name; finalization
writes nothing to storage and admits a document with one database transaction.
A separate staging store, copied into custody at finalization, was decided on
2026-10-20 for uploads through presigned URLs, where the client wrote storage
directly and bytes could not be verified before finalization. Since 2026-11-07
the platform receives and verifies every byte itself, so that reason no longer
holds, and the copy would put a storage write beside the database commit that
admits the document: every interruption between the two needs its own repair,
and a destination-side condition on a storage copy is not honoured by every
S3-compatible store (MinIO community RELEASE.2025-09-07 overwrites silently).

Confirmed on 2026-11-11 in
[#184](https://github.com/davidlinnnn/data-ingestion/issues/184).

## Consequences

- Files uploaded but not admitted sit in the custody bucket until admission
  deletes them, and processing workers' credentials can read them.
- Admission deletes inside the bucket that holds admitted source files. The
  object key names the batch item that uploaded the file, so the deletion of a
  rejected or expired item's files cannot reach another item's.
- Equal bytes uploaded by two batch items of one document are stored twice.
