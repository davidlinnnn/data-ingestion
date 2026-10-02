# Cloud practices for captured-source attachment handoff

Date: 2026-10-02. Status: research evidence and **unconfirmed recommendation**, not a selected storage product or accepted API contract. Related discussion: [Define captured-source identity and authorization handoff](https://github.com/davidlinnnn/data-ingestion/issues/53).

Question: how can many independent Source Owners deliver document images or larger media without embedding bytes in the ingestion API or requiring Knowledge Platform operators to configure every owner's endpoint and long-lived token?

## Verified practices

### 1. Platform-issued direct-upload grant

AWS S3 supports presigned upload URLs: the destination owner authorizes a specific upload without giving the uploader AWS credentials. The bytes go directly to the destination bucket. Uploading to an existing key can replace its contents. [AWS: presigned uploads](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html)

For large objects, S3 multipart upload separates initiation, independent part uploads, and completion. Failed parts can be retried separately; unfinished uploads need completion or abort/cleanup. [AWS: multipart upload](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)

Google Cloud Storage supports signed URLs for temporary object access. Its resumable upload session can be initiated by a server and delegated to another client using the returned session URI. That URI authorizes subsequent uploads without further authentication; it is sensitive and should be shared over HTTPS. Resumable upload supports recovery after transfer interruptions. [GCS: signed URLs](https://docs.cloud.google.com/storage/docs/access-control/signed-urls), [GCS: resumable uploads](https://docs.cloud.google.com/storage/docs/resumable-uploads)

**Architecture implication:** Knowledge Platform can issue a limited upload grant after checking its own submitter authority. The provider uploads directly into platform-managed staging storage and submits/finalizes a manifest. This requires the platform's destination storage configuration, but no per-provider source-storage secret. The provider remains responsible for obtaining its source files legitimately. Multipart/resumable upload is a data-transfer choice, not a reason to stream media through the ingestion API.

### 2. Provider-issued download grant for a bounded import

A source can issue a signed GET URL for the platform to retrieve an object. S3 signed URLs use the signer's authority, can be reused until expiration, and may expire earlier when underlying temporary credentials expire. Network-path restrictions still apply. [AWS: presigned access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)

**Architecture implication:** a supported, reachable, per-submission download grant can avoid storing the source's static secret. It does not make arbitrary private MinIO endpoints reachable or create an ongoing connector. Import needs explicit bounds on locations, redirects/network destinations, object count/size, and credential handling. A failed or expired grant requires a renewed grant for the same declared input, or explicit failure; it must not silently fetch whatever is latest. The capture stage obtains governed custody before processing admission, rather than making long-running processing depend on an expiring download URL.

### 3. Federated access for recurring connectors

AWS STS AssumeRole returns temporary credentials. Cross-account access still requires a role trust policy and appropriate permissions. In a multi-customer third-party service, AWS documents a service-controlled, customer-specific ExternalId condition to prevent one customer tricking the service into using another customer's role. [AWS: AssumeRole](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html), [AWS: confused deputy protection](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html)

GCP Workload Identity Federation exchanges external identity credentials for short-lived access. Access requires configured identity trust plus resource IAM grants, either directly to the external principal or through service account impersonation. Federation does not authorize every resource by itself. [GCP: Workload Identity Federation](https://docs.cloud.google.com/iam/docs/workload-identity-federation)

**Architecture implication:** use federation for repeated source reads when a real connector justifies onboarding. Owners can establish scoped trust using a documented self-service process rather than sharing permanent access keys with platform operators. This removes static-secret handling, not the need for authorization, reachable networks, or connection metadata. It need not be mandatory for one-off delivery.

## Version and acceptance boundary

S3 GetObject can target a specific `versionId`; absent it, it normally returns the current version. GCS identifies object contents by bucket, object name, and generation; replacement produces a new generation. Version identity does not itself guarantee retention or future permission. [AWS: GetObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html), [GCS: objects and generations](https://docs.cloud.google.com/storage/docs/objects)

**Recommended invariant:** upload/import completion must verify all required artifacts, bind the exact retained artifact versions and integrity evidence, and freeze the Capture Package before normal processing admission. Signed grants are not inherently single-use; do not treat a successful upload to a mutable key as permanent input identity. Subsequent writes must not change what a finalized submission references. The exact finalization endpoint, state machine, integrity mechanism, and custody implementation remain design work.

## Proposed direction for Knowledge Platform

Make **platform-issued direct upload** the general delivery default. Keep **provider-issued download grants** as a bounded optional import path when evidence justifies it. Use **federated source access** for recurring connectors with an actual need; do not build all three immediately.

Retain governed Source registration, delegated submitter authority, and reader-policy accountability. These are separate from configuring a different storage endpoint and static token for each provider. An upload capability permits delivery; it does not grant employees permission to read the resulting knowledge.

This revises the earlier pending recommendation that a preregistered source-storage connection should be the general default. It preserves the confirmed capture-before-processing boundary. API shape, supported import transports, quotas, video processing support, and cloud/storage selection are still open. The proposed delivery mechanism does not expand the first slice into general live connectors.
