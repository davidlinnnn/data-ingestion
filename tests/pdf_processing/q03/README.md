# Q03: four bounded algorithm structures and representation dispositions

Implements the local portion of #50 / specification #47, based on
`4571eea1c6492de7c097fe3fa6ce99494c34dbef`. K8s qualification is **NOT RUN** for
this producer. No #50, Q04 or #44 release acceptance follows from local tests.
See [runtime admission plan](RUNTIME-PLAN.md) and [source review](SOURCE-REVIEW.md).

## Interface contract

The outer evidence seam remains `typed-source-relationships-v2`, with the unchanged
`local-function-block-v1` derivation. An optional relationship-policy field opts
into `representation.version = source-reviewed-representation-v1`. Absence of
that field keeps Q02 behavior, including unresolved isolated combining marks.
Unknown versions, methods, fields and dispositions fail explicitly. A new frozen
profile, producer/release and request identity are required; accepted old plans
cannot be reinterpreted by the new worker.

The opt-in policy requires `selected_regions`, `unresolved: reject`, one required
relationship per selected region, and exactly one source review for each region.
The selected source identity, physical page and unique review/selection IDs must
agree. Reviews contain no algorithm names, expected edges, roles or member refs.
They enter only **after** independent method derivation; they cannot supply missing
structure, change roles, or resolve an ambiguous caption. Each relationship must
still have valid, ordered, nonempty header/body/caption membership.

Each review has `header_body` and `caption` comparison streams, with independently
reviewed source/extraction whitespace-compacted SHA-256 fingerprints. The complete
stream fingerprints prevent an allowance from masking surrounding loss, added
content or reordered text. Differences retain explicit half-open source/extracted
comparison ranges, exact differing characters, a kind and a disposition. Runtime
checks the extracted fingerprint, each difference and the declared source fingerprint
using the explicit difference record. This is review-consistency validation, not
source discovery, normalized equality or mathematical interpretation.

Supported reviewed occurrences are minus/hyphen, native U+0007/body absence, native
U+0002/caption absence, and separately preserved combining marks. There is no
global character-class allowance. Review authority is the frozen operator profile;
the implementation does not manufacture an independent reviewer attestation.
`reviewed-representation.json` is the separately documented, agent-reviewed Q03
qualification selection, not a production default or discovery answer table.

`retain_uninterpreted` allows delivery of exact extraction with its local source
context while explicitly retaining representation uncertainty. `release_gate`
records an unsettled decision and blocks completion. Unsupported dispositions
fail admission. The report keeps structural `resolved` status separate from each
representation disposition; `source_native_equal` remains false for the uncertain
cases, and `semantic_equivalence` is `not_claimed`.

`raw_extracted_ranges` index unchanged item text. `source_range` and
`extracted_range` in differences index **whitespace-compacted Unicode code points**;
they are not raw offsets. Absent extracted characters have an empty raw range list.
Isolated combining marks retain actual ref/type/range/zero-width provenance,
`order: null` and `position_in_body: null`. Full-page context avoids inventing a
symbol width, insertion position or attachment to a neighboring glyph.

## Durable boundary and evidence

The existing supervised evidence child writes the extended report. Finalization
rederives/validates the selected structures and reviews against the exact document,
source, parsed-result and assembly, checks all required work, then rejects any
release gate. The separate relationship registration adds `representation_evidence`
with each review's source-page artifact/digest and crop recipe. Page metadata must
match physical page/geometry and retained PNG bytes must be readable. Local
algorithm/caption source context and full-page isolated-symbol context are both
available through the same registered content evidence. Complete publication and
retry reads traverse this barrier. Raw source and historical outputs are unchanged.

Global `source_review.status: not_performed` continues to describe independent
structural review by the runtime. Representation annotations identify their
separate `profile_source_review_not_discovery` origin. The independent four-case
source oracle is test-only. Neither quality nor canonical acceptance is granted.

## Compatibility impact

Only `relationships.py` and `enrichment.py` change production bytes. The existing
stage dependency contract already fingerprints both; it is unchanged.

| Change | Group / assembly | Selection / OCR | Evidence / final |
| --- | --- | --- | --- |
| Actual Q01/Q02 producer to Q03 | Equal checked contracts | Invalidated conservatively by enrichment.py | Invalidated |
| Representation-policy-only change within Q03 | Equal | Equal | Invalidated |
| Accepted old request | Retained producer/profile required | Same | Same |

`test_q03_compatibility.py` compares the actual recorded Q01/Q02 runtime producer
with the current inventory. Equal operation contracts are local evidence only;
new-producer runtime reuse must still be demonstrated in the coordinated window.

## Local verification and support boundary

`run_suite.py` runs the existing PDF local suite plus Q03. The supporting checkpoint
seam qualifies all four reviewed source regions against the unchanged independent
Q02/P2 oracle and repeats them on corrected Q01 assembly. Final-publication tests
use real rendered source pages and the production Store/finalization code, with
only S3 transport in memory; upstream plan/assembly/OCR selection are seeded.
They are not actual Temporal, OCR engine or fresh native processing evidence.

Tests retain valid fragmentation and reject corrupt roles/order/captions, missing
recursive body or combining marks, wrong identities/ranges/evidence, unsupported
review policy, unreviewed content changes and each independently unsettled symbol
observation. Full source/output bytes stay in private storage. The committed
manifest links hashes, policy, producer, fixture and test versions for Q04.

Bounded support is BFS (original 101 / 3.11), uniform-cost (103 / 3.14), depth-limited
(107 / 3.17), and iterative-deepening (108 / 3.18), on the fixed contiguous AIMA
99–110 Source Revision. There is no universal discovery, AST, LaTeX enrichment,
mathematical reconstruction, new canonical schema or expanded layout/language claim.

Final local checks: **66 tests PASS**, typecheck **0 errors / 0 warnings**. Both
code-review axes have no remaining local findings after the PNG-decoding and
numeric-metadata fixes; see [review](REVIEW.md). These checks do not close the
explicit runtime gates above.

## Interrupted required evidence follow-up

The missing hook and procedure are now prepared: see [operation procedure](INTERRUPTION.md)
and [follow-up review](INTERRUPTION-REVIEW.md). The 22-case runtime matrix includes a
standalone interrupted-evidence case. Final local checks: **73 tests PASS** and
typecheck **0 errors / 0 warnings**. Seven hook tests cover actual child interruption,
recovery/replay, refusal/timeout, delayed stop and overlapping cancellation cleanup.
Production inventory is unchanged from the initial Q03 commit. Follow-up evidence
is bound by `evidence/interruption/manifest.json`; the original evidence remains
historical. Actual Temporal/shared-storage/K8s qualification is **NOT RUN** and
requires newly coordinated capacity.
