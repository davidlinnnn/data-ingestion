# Independent review — WeKnora fit research

**Date:** 2026-10-05. **Scope:** research issue [#73](https://github.com/davidlinnnn/data-ingestion/issues/73), independently reviewed from the background report author. No product, architecture, implementation, deployment or runtime qualification approval follows.

**Report:** [WeKnora fit for the Knowledge Platform](../research/weknora-knowledge-platform-fit-2026-10-05.md).

**Initial reviewed SHA-256:** `5fa056a5a197aa78111aefcb6ab9a5348128b2d5364b77c12fe4c4510fd8c1cd`.

**Final reviewed SHA-256:** `d8e4d764fc9a6b1bb8256b1dd5443093c77385212c3827e55e9fd73a6e0ad7ba` (59,760 bytes, 270 lines).

**Final outcome:** pass for the stated research scope; no blocking findings remain.

## Initial outcome

No blocking finding in the capability conclusions, target-contract comparison, adoption-path fairness or acceptance coverage. One narrow executable-evidence wording correction was requested before publication; additional source anchors and test links were suggested to make decisive claims easier to audit.

| Finding | Basis | Disposition |
|---|---|---|
| F1 — License script scope must name `go.mod`/`go.sum`, rather than imply scanning Go implementation files | The report's section 8 said the executed script checked removal of named converters from “current Go files/module manifests.” [The script](https://github.com/Tencent/WeKnora/blob/bccb4b151bae403508da77fbb174efc79dc47c1a/scripts/check-license-bundle.sh#L12-L16) searches only `go.mod` and `go.sum`. Its other checks validate source-pin versions/checksum shape and nonempty notice files; archive integrity is conditional on an unprovided `source_dir`. | Resolved. Final section 8 names `go.mod`/`go.sum` exactly and retains the no-archive/SBOM/model-clearance limitation. It does not change the licensing or adoption conclusions. |
| N1 — Add decisive source anchors and local test-code links | The initial draft's 58 upstream blob/tree links all resolved in the pinned checkout, but none had line anchors. Suggested deletion, shared-read and edit-hydration tests substantiate local safeguards and must remain explicitly source-inspected. | Resolved. Eight source/test anchors now point to valid frozen lines; all three suggested direct tests are included with narrow S/test-code language. The optional move-path test was not required. |
| F2 — Escape the legacy reference example's Markdown table delimiter (root documentation QA) | Root QA found a literal pipe in the Wiki-current-page row's inline example, which creates an extra GFM table column. | Resolved. The pipe is escaped; reviewer checked the final line and hash. Formatting only, with no capability or contract change. |

No wording-preference finding was treated as a blocker.

## Acceptance and authority coverage

| Required review area | Result |
|---|---|
| Frozen identities and evidence method | Main `bccb4b151bae403508da77fbb174efc79dc47c1a` is the source baseline. Release `v0.8.2`/`3e8b0bf` is documented metadata, without behavior parity or package qualification. Platform baseline, qualified PDF core, merged Docling report and design checkpoint are separately pinned. D/S/T/U boundaries are explicit. |
| Current accepted versus unresolved owner decisions | Matches the complete current #52/#73 and relevant #31/#32/#53/#54/#55/#56/#57/#58/#72 snapshots. Q1–Q13 and unified lifecycle/status-query scope are accepted; Q14, concrete pilot/coexistence, detailed enforcement/storage/publication mechanisms and implementation phasing remain unresolved. |
| Requirement/evidence/gap comparison | Covers product outcomes, representation/lifecycle, processing/admission reliability, governance/custody, quality/operations/licensing. Product resemblance is kept distinct from contract equivalence. |
| Shared product case and lifecycle | Uses an explicitly illustrative PDF/Markdown/PPTX topic and shared source inputs. Walks initial ingestion, source update, method-only reprocessing, independent projection failure/rebuild, withdrawal with late work and rollback/restore. |
| Adoption paths and handoffs | Direct adoption, product-layer integration, component reuse and design borrowing each have benefit, seam/change scope, maintenance/operations/licensing cost and smallest remaining experiment. Ranked retain/adopt-candidate/defer/reject findings remain proposals with current owners. |
| Qualification and scope | No inferred feature/product adoption, new prerequisite, owner decision closure, full deployment, numerical SLA or unrun test claim. Qualified PDF-core evidence is retained within its original scope. Issue/map publication remains the research owner's action, rather than an adopted platform contract. |

## Independent source checks

The reviewer followed decisive positive and negative claims into the frozen implementation and relevant test code. In particular:

- File replacement keeps the knowledge UUID, mutates current file fields, reparses and normally removes the old file after successful scheduling. This supports the retained-source-version gap, without claiming a reproduced update/restore run.
- Wiki snapshots omit source/chunk-reference fields; revert restores historical content into a new current page while keeping current references. These are content-history semantics, not exact historical input reconstruction.
- Current postprocessing counts the durable per-document Wiki operation despite an older migration comment; finalizing counters drain on terminal outcomes. Source inspection supports the required-success/acceptance distinction and early Retrieval visibility.
- Wiki citation fallback skips the chunk-classification pass; insufficient text is skipped, truncation is explicit, and rendered short citation handles are stripped while refs remain. Stored citations do not establish source truth.
- Chunk edits clear invalid locators; the inspected edit test asserts that behavior. Retrieval hydration rejects processing/failed index edits and excludes `wiki_page` from the allowlist; page writes do not synthesize Retrieval chunks.
- Deletion writes tombstone/pending-retraction safeguards, while a shared page can have refs removed without immediate rewriting of its generated text. The report correctly describes the local race safeguards and leaves global stop-disclosure/purge unverified.
- Local KB access uses caller-scoped permissions, with tests for grant revocation on a subsequent request. This is useful local authorization evidence, without establishing externally authoritative Source policy, mixed-source narrowing or global revocation.

Suggested local test links were inspected, not executed: [shared-page deletion refs](https://github.com/Tencent/WeKnora/blob/bccb4b151bae403508da77fbb174efc79dc47c1a/internal/application/service/knowledge_cleanup_regression_test.go#L35-L68), [KB permission recheck](https://github.com/Tencent/WeKnora/blob/bccb4b151bae403508da77fbb174efc79dc47c1a/internal/application/service/knowledge_shared_access_test.go#L191-L208), [edit hydration](https://github.com/Tencent/WeKnora/blob/bccb4b151bae403508da77fbb174efc79dc47c1a/internal/application/service/knowledgebase_search_results_edit_test.go#L9-L35), and [durable retraction-before-ref-removal on the move cleanup path](https://github.com/Tencent/WeKnora/blob/bccb4b151bae403508da77fbb174efc79dc47c1a/internal/application/service/knowledge_move_wiki_test.go#L346-L373).

## Evidence limits

The reviewer made read-only source, schema, test-code and authority checks and checked pinned local source-path existence. No upstream Go/Python test suite, model inference, API round trip, deployment, fault injection, benchmark or restore was run by this reviewer. The report's sole actual upstream run is the research owner's narrow license-bundle consistency script, exit 0; it is not legal clearance, SBOM validation or production qualification. Release metadata was independently verified by the research owner; the release source object was not present in the reviewer's shallow checkout, so implementation conclusions remain bound to the reviewed main commit.

## Final recheck

The final bytes match SHA-256 `d8e4d764fc9a6b1bb8256b1dd5443093c77385212c3827e55e9fd73a6e0ad7ba`. F1, N1 and F2 are resolved. The substantive correction/anchor revision was first rechecked at `3ade176984aac2762114aa236218da815d2ecb360139413cdf5c19a2c94ed441`; the final change escapes one table delimiter and does not alter that source audit. The report now has 66 upstream blob/tree links, all with existing pinned paths; all eight supplied line anchors are within the frozen files and support the cited local behavior. Added deletion and shared-access test descriptions explicitly exclude global enforcement/current-Source-policy qualification; edit-hydration assertions remain inspected test code. The added Redis append-only/persistent-volume statement matches the Helm template and does not claim outage or HA qualification. The publication-unit wording preserves projection ownership.

No blocking findings remain. This pass binds the research report's evidence and acceptance coverage; it does not authorize adoption or establish runtime guarantees.
