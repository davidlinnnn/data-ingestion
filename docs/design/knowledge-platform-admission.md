# Knowledge Platform admission design notes

Active design for [Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31),
within the existing Knowledge Platform wayfinder map. Confirmed choices below
are inputs to the continuing design; the admission contract remains open.

## Confirmed delivery direction on 2026-10-18

The user reaffirmed platform-issued **direct upload** and requested that future
design-principle documentation explain the **Valet Key pattern**: the platform
first establishes the submitter's authority, then delegates access to specific
storage resources for limited operations and a limited period.

The client transfers file bytes to platform-designated storage. The platform
retains responsibility for the delivery authorization, capture verification,
durable processing admission and governed use of retained data. Source Owner
accountability and source authorization ceilings remain in force.

The user emphasized enterprise Authentication and Authorization (AA) for the
handoff of sensitive data, together with a bounded implementation that reuses
existing capabilities. This confirmation selects neither a storage product nor
a presigned URL, SAS, token format, endpoint, grant lifetime or revocation policy.

## Client clarification on 2026-10-18

The user clarified that the intended integration client is the Data Owner's
system calling the platform API. The document's Resource binding would be
provided during submission, with GAM or compatible authorization governing
subsequent data access. A human may trigger the source system; this alone does
not establish that the platform must authorize the operation as that human.

The existing source-handoff contract supports delegated programs and workload
identities. Submission authority and authority to establish a document's
Resource binding must both be trustworthy; merely supplying a Resource ID does
not establish permission to use that binding or broaden the source audience.

The pilot decision below establishes platform-managed service-account tokens.
The existing controlled manual pilot client does not require a separate
per-person submission permission system.

The user subsequently identified an existing company mechanism called PAT for
system identity, distinct from tSSO for people, while noting that its details are
uncertain. The company PAT's expansion, protocol, token lifetime, validation and
revocation capabilities have not been verified. Integration with that mechanism
is deferred by the pilot decision below. See the
[CSP authentication and operations investigation](../research/service-client-authentication-csp-practices-2026-10-18.md).

## Confirmed pilot service-account authentication on 2026-10-18

The user selected a bounded pilot approach: Knowledge Platform configuration
manages the client service accounts and the platform issues a fixed service-account
token to each Data Owner system. In this pilot discussion, PAT refers to that
platform-managed credential; it does not claim compatibility or integration with
the existing company PAT service. Exact token encoding and lifetime are not
selected by this decision.

The purpose is to make system submission usable with low operating effort while
prioritizing data access control. Company PAT integration, OAuth token exchange,
managed identity and federation remain follow-up topics rather than prerequisites
for the pilot. The research is retained for that revisit. This is not a selection
of the production authentication mechanism.

Keep the pilot's submission boundary small:

- Identify each client service account separately and limit its submission
  authority to the configured Sources and permitted operations. A valid token
  does not grant permission to read all data or manage authorization policy.
- Establish trustworthy document-to-Resource bindings within delegated authority;
  arbitrary caller-supplied Resource IDs cannot broaden the source audience.
- Retain an operator path to disable or replace a client's credential through
  configuration, with credential values protected from source control and logs.
  A credential-management UI, self-service issuer and automatic rotation service
  are not required by this pilot decision. Configuration propagation and any
  effect on previously issued upload grants remain admission-design details.

Data access control retains first priority and remains owned by
[Define governance enforcement across canonical data and published views](https://github.com/davidlinnnn/data-ingestion/issues/56).
Admission consumes and enforces its applicable
contract, including the trusted Resource binding; it does not create a second
reader-authorization system or waive governed access for the pilot.

Platform API authentication and the temporary storage grant used for direct
upload retain distinct purposes. The confirmed direct-upload / Valet Key
direction remains in force; this decision does not choose presigned URL versus
another storage mechanism. The remaining admission contract is still open.

## Confirmed single and batch submission contract on 2026-10-18

The user confirmed one shared submission contract accepting `items[1..N]`;
a single-document submission contains one item. Batch supplies grouping and
aggregate progress while every document retains its own identity, governance
relationships and result. Corpus membership and Resource bindings belong to the
individual document's governed relationships, not to its incidental batch.

This selects the common contract, not separate single/bulk processing pipelines.
The numeric maximum, exact routes and fields, batch/item operation identifiers,
cross-Source or cross-authorization-scope admission rules, and persistence remain
open. An item represents a complete captured document package, which can include
required attachments rather than exactly one file.

The user has not yet decided partial-admission/atomicity: the example with 19
valid items and one invalid item at admission remains unanswered. Independent
outcomes after admission remain required. Neither this agreement nor the batch
research chooses inline bytes, external-location import, the finalization trigger
or the storage-grant mechanism.

## Principle for later architecture documentation

Authorize delivery before delegating data transfer. Use the Valet Key pattern
to grant the client narrowly scoped, time-limited access to the required storage
resources. Establish complete, fixed and governed captured inputs before durable
processing admission. Delivery permission, processing authority and permission
to read published knowledge remain distinct.

Direct upload describes the path of file bytes. Presigned URLs, SAS and other
supported capabilities describe how storage authorizes that transfer; they are
mechanism choices within the delivery direction.

## AA mechanism under discussion

The existing company direction uses tSSO for user identity and GAM or
GAM-compatible authorization. Submission authority, reader access and
policy-management authority have separate meanings. The confirmed requirements
leave detailed token integration, check locations, validity and revocation
behavior to the owning design decisions. For the pilot, the service-account
credential issuer is Knowledge Platform as confirmed above; the company PAT
integration and protocol remain deferred.

A candidate minimal implementation authorizes a grant through the platform,
issues a temporary capability for a designated upload target, and checks current
submission authority and capture readiness at finalization/admission. It would
correlate the grant recipient, Source/Asset context, target and admission outcome
for audit. This check schedule and mechanism are proposals awaiting discussion.

Presigned URLs are bearer capabilities: possession can permit use within their
scope and validity. Grant-issuance attribution alone does not prove who actually
sent every byte. The design must settle whether the company accepts that bounded
delegation or needs identity-bound storage access, and when withdrawal must stop
already-authorized uploads. Retained versions must remain stable after admission;
expired grants, incomplete uploads and staged data need defined handling.

## References

- [Inline content and storage-reference ingestion](../research/document-inline-reference-ingestion-2026-10-18.md) — delivery trade-offs and Bedrock evidence; no additional input mode selected.
- [Single and multiple-document admission: CSP API investigation](../research/document-batch-admission-csp-practices-2026-10-18.md) — evidence for the confirmed shared `items[1..N]` contract; detailed routes, scope and partial-admission behavior remain open.
- [Valet Key pattern, Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/valet-key)
- [Confirmed source delivery and finalization direction](https://github.com/davidlinnnn/data-ingestion/blob/9be8021a25a39545c28af8f420c3750a7ce21859/docs/design/knowledge-platform-source-handoff.md#L157)
- [Original cloud-practice investigation and decision history](https://github.com/davidlinnnn/data-ingestion/blob/9be8021a25a39545c28af8f420c3750a7ce21859/docs/research/attachment-handoff-cloud-practices-2026-10-02.md)
- [Confirmed company AA requirements](https://github.com/davidlinnnn/data-ingestion/issues/56#issuecomment-6230755901)
- [Source authorization and enforcement-boundary handoff](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5991845520)
- [S3 presigned URL scope, bearer semantics and reuse](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)
