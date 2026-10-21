# Keep accepted Canonical Revisions fixed while selection follows explicit rules

Accepted Canonical content, structure/relationships, source/evidence mappings and
producing-method attribution remain fixed; a changed result becomes a new candidate
requiring acceptance so that Wiki and Retrieval references keep their original
meaning. Default selection may move under declared source/method applicability,
compatibility and current governance/lifecycle rules, automatically where
determinable, without treating the last completed result as the winner.
Catalog display information and present eligibility remain separate from fixed
content; immutability does not grant permanent access or retention.

The [Q15 decision](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6039615616) confirmed on 2026-10-07
binds references to a location within an exact revision. Initially there is no
guarantee of automatic cross-revision component matching; a reused local label
must not redirect historical references to new content.

Confirmed on 2026-10-07 in the [Q7/Q8 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035081526).
See the [canonical design checkpoint](../design/knowledge-platform-canonical-design.md#q7-accepted-revision-contents-remain-fixed)
for examples, the [Q9 invalidation principle](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035318528),
and remaining selection and lifecycle details.

The [Q11 decision](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035858969) confirmed on 2026-10-07
extends the rule to adopted Enrichment methods: automatically reprocess the declared
affected scope using retained eligible inputs, without Source Owner re-upload or
per-document approval. Acceptance and selection still gate replacement; ordinary
compatible updates remain automatic and major breaking production migrations retain
the existing authorized release decision.

The [Q24 decision](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6076049015) confirmed on 2026-10-09
keeps redelivery of the same candidate's same acceptance result on the same revision.
Distinct reprocessing candidates may be accepted as distinct revisions without
mandatory cross-run content comparison or merging. Without a clear replacement
basis, retain an existing selection only while it remains eligible; otherwise
expose unresolved selection instead of choosing by completion order. This avoids
both duplicate versions from redelivery and an unnecessary global deduplication mechanism.
