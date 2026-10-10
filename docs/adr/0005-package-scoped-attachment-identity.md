# Keep attachment identity within its Capture Package

Attachment identity belongs to its Capture Package/document-version scope; equal
bytes, hashes or source URLs do not merge identity, authority or lifecycle across
documents. The first slice omits a global shared-attachment catalog, shared update
feature and automatic cross-document deduplication because the confirmed
simplification requires a concrete shared-management need or measured storage cost
before revisiting them. Logical separation still permits eligible physical reuse
under the applicable custody obligations and does not require duplicate uploads.

Originally confirmed on 2026-10-05 in
[revised source-handoff Q14](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5992838620),
which replaced the earlier unconfirmed shared-attachment proposal.
Retrospectively recorded on 2026-10-09; no new design decision is made here.
[Canonical Q20](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6074671955)
subsequently preserves each within-document occurrence and its context while
referencing one fixed package artifact.
