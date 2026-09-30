# Captured-source identity and authorization handoff

[Design index](README.md) · [Confirmed overall logical baseline](knowledge-platform-logical-design.md)

**Status:** Q1–Q7 confirmed on 2026-09-30; the complete source-handoff design
remains open. This document assembles the implications of the
[Q1–Q3 decision record](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5909819124) and
[Q6/Q7 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5911948945), and
[Q4 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912631142), and
[Q5 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912982133) in
[Define captured-source identity and authorization handoff](https://github.com/davidlinnnn/data-ingestion/issues/53).
Issue records remain authoritative. Question numbers here belong to this ticket,
not the earlier overall-design interview.

## Confirmed decisions

### Q1 — Source authority and delegated submission

Register the governed Source and explicitly delegate submission on its behalf.
Distinguish original Source Owner accountability, capture/submission responsibility,
and authority to provide or confirm source-access policy. Roles may be co-located;
this does not prescribe separate services or a management UI. Upload authority
does not grant authority to broaden the source audience. A delegated llmwiki client
does not become the original Source Owner simply by forwarding files.

Q7 below selects the initial team/collection direction and responsible roles;
actual identities and delegation grants must be bound during adoption.

### Q2 — Stable logical Asset identity

Within a Source, use a trustworthy stable native identity to resolve an Asset when
available. Otherwise allocate an identity on explicit creation and require explicit
reuse for updates. Names, paths, URLs, storage locations and content digests do not
automatically define logical identity. Renaming, relocation and content updates can
preserve an Asset. Equal bytes across Sources do not automatically merge Assets;
physical byte deduplication remains a separate storage choice. Corpus membership
reuses the Asset identity and does not expand access.

Q4 below distinguishes source-version identity from processing requests. Detailed
metadata-only changes, observation ordering and reuse rules remain open.

### Q3 — Capture readiness and custody before admission

Before durable processing admission returns `202`, captured inputs must have fixed
immutable versions, integrity information, and accountable custody supporting
retrieval through the agreed queueing, suspension and retry period. Workers still
verify integrity on access. Platform custody or an explicitly approved equivalent
arrangement can satisfy this without necessarily copying bytes again.

A short-lived URL can be a renewable access mechanism over a durable object
identity and custody arrangement. An arbitrary local path, an unprotected expiring
URL, or fetching latest only when execution begins does not establish that guarantee.
The boundary does not require synchronous parsing/OCR and does not mean Canonical
Acceptance. Exact custody duration/release and withdrawal/purge handling remain open.

### Q4 — Source Revision versus processing request

An Asset identifies a logical document; its Source Revision identifies a captured
source version/observation. A processing request is a work order over selected
captured inputs and methods. Redelivery preserves the Source Revision. Admission
request deduplication applies; workflow/activity retries do not by themselves
create a new source version or deliberate processing request.

Method-only reprocessing retains the Source Revision and uses a new request. An
explicitly new source version/observation can have a new Source Revision even when
bytes are equal; ordinary re-upload alone does not establish a new source version.
An existing observation identity cannot be silently rebound to conflicting content.
Use reliable native source-version identity where available, otherwise an explicit
capture identity reusable on redelivery. Digests support integrity and possible
reuse, not source-version identity by themselves.

New source observations do not inherently require repeating all expensive work;
reuse requires compatible inputs/methods. Exact identity representation, ordering,
metadata-only changes, reuse rules and retained-identity lifetime remain open.

### Q5 — Trusted reader policy before normal admission

Normal ingestion admission requires a trustworthy, explicit reader policy whose
meaning the platform supports. Verify submitter identity and Source-scoped
authority separately from the document's permitted audience. Reader policies may
identify employee accounts or groups; exact directory mappings remain detailed
work. Upload authority does not permit broadening the source-authorized audience.

Carry attributable policy evidence or reference an explicitly authorized registered
Source default. Establish its responsible authority and applicability rather than
accept an arbitrary uploader assertion. Missing, untrustworthy or unsupported
required policy/authority causes normal admission to be rejected until corrected
and resubmitted. Valid inputs proceed automatically, without per-document human
approval. Current governance continues to apply after capture; the captured policy
is not a permanent access grant.

Policy representations, version/observation fields, change delivery, ordering and
freshness remain detailed work. This does not select an identity provider, protocol,
policy engine, quarantine service or approval queue.

### Q6 — Finite capture packages

A Capture Package comprises the main document and explicitly declared dependencies
required to interpret it. All included artifacts have fixed versions and integrity
information under the Q3 custody guarantee. A self-contained PDF/PPTX may be one
file; Markdown with required relative images includes those images. Ordinary
hyperlinks remain references, without automatic recursive acquisition. Package
representation, missing-dependency outcomes and shared-attachment lifecycle remain
open.

### Q7 — Initial team and document collection

Start with the engineering team responsible for the Knowledge Platform and a
controlled collection of technical/operations documents it maintains and is
allowed to ingest. The document-owning role retains content/publication
accountability. Capture/submission is delegated to an authorized program or
operating role. The designated data-access role supplies/confirms source policy;
platform operation alone does not confer that authority. This selects the pilot
boundary and roles, not named-person assignments or already-provisioned grants.

Make the document inventory and concrete identity/delegation bindings explicit
for adoption. Numeric workload, concurrency and resource targets remain with
[Set the first-adoption workload and operating envelope](https://github.com/davidlinnnn/data-ingestion/issues/54).

## Next frontier — proposed, not confirmed

The [Q5 confirmation and next-round record](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912982133) distinguishes the accepted
trust rule from the following recommendations. Await user answers before adopting
them or proceeding into dependent details.

| Question | Decision to resolve |
|---|---|
| Q8 | Explicit controlled-source delivery of content, catalog metadata, policy, confirmed deletion and withdrawal changes, with appropriate operation authority |
| Q9 | Required-package dependency failures, admission timing and whether to support partial source packages in the first slice |
| Q10 | Retaining captured input for applicable reprocessing/evidence obligations after initial processing, distinct from intermediate cleanup |

Subsequent branches include change ordering and policy freshness, custody release,
concrete package validation, and reviewed PDF, Markdown and PPTX examples. Format
design does not expand the PDF core's qualified support.

## Integration and ownership

The [wayfinder map](https://github.com/davidlinnnn/data-ingestion/issues/52) makes
confirmed target contracts authoritative. Workflow/API differences become versioned
implementation migration or integration work, with validation at the map's existing
follow-through checkpoints. Measured resource configurations inform the operating
envelope within their qualified scope.

[Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31)
owns transport, public request/status semantics and admission persistence/atomicity.
[Design canonical schema and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32)
owns the canonical representation and lifecycle contract. This source-boundary
decision supplies their identity, capture and authorization prerequisites.
