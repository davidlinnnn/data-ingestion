# Q04 continuation v2 offline result

Status: **reviewed exact v2 oracle candidate; no Q04 runtime acceptance**.

`src/pdf_processing/continuation.py` now declares
`column-edge-continuation-v2`, SHA-256
`8c5e68006af438e2c1a5d5f82614436c8e1e7e5fc7f6e0a1d77645c640b23305`.
The only policy change requires cross-page text endpoints to be adjacent in
Docling's predicted body reading order, ignoring page furniture and margin-sized
text. It runs **after** the existing ambiguous-owner/entrance checks. The old
`column-edge-continuation-v1` source is retained in Git at SHA-256
`791e2ebef036d6f2468fb607162a135eecb3c4eaa056d4e35b1a81bffde49772`;
its exact method binding is rejected by the new parser before processing.

The existing local `pdf-checkpoint-prototype:linux-v2` image ran with no network,
a 10 GiB container memory limit and four CPUs. Its method fields match AG's
native and Wiki06 methods exactly except for the versioned continuation entry.
The local captures and checkpoints are retained at
`/private/tmp/q04-local-native-v2/`; they are **not** Temporal/shared-storage
runtime evidence.

| Fixture | Source PDF SHA-256 | Retained reference SHA-256 | Local v2 document SHA-256 | Raw text nodes | Source-fragment result |
| --- | --- | --- | --- | --- | --- |
| native, 51 pages | `d58be5fc39608dc9aec45194c602436d793f2f2bf56f267d0e38d6258a9f7a9e` | `616f9e2a73f530de42e16f9b451356c7549d46f68563e5c9513a046c47bc6135` | `70673bdc5cb548d37c81efa91bb1c5460f71f94148bdb5d1218a319c6af9f152` | 1,119 → 1,151 | Exact multiset; 32 ordered one-to-two body-text splits and one unchanged duplicate `OPT` correspondence; no fragment-order mismatch within any changed component. |
| Wiki06, 28 pages | `65afc6e12f6f707483fe1b79a97ab67c03abf4b4992f82fde03eb7b8d9ad4a69` | `a936ed723ca31098e6104560759e2bc130c66d94d4dd3cb6b8471f0c9bc1d263` | `5f00af22b9264c32462f006f4debadff20fe52051424b38c8f06e5e28404cb68` | 490 → 496 | Exact multiset; six ordered one-to-two body-text splits. This document hash is the same as AG's Wiki06 result. |

Replaying the **same full native page checkpoints** through frozen v1 and v2
removed exactly six v1 edges and added none. They are the six invalid joins
across pages 12–13, 16–17 (two), 18–19, 21–22 and 28–29 documented in
[AG source review](../../pod-topology-v32/first-window-evidence/SOURCE-REVIEW-RESULT.md).
The five affected page-pair captures independently preserve their reference
fragment multisets **and order** after the fix.

Local checkpoint restoration of both complete captures produced byte-identical
`document.json` files: native SHA-256
`70673bdc5cb548d37c81efa91bb1c5460f71f94148bdb5d1218a319c6af9f152`
and Wiki06 SHA-256
`5f00af22b9264c32462f006f4debadff20fe52051424b38c8f06e5e28404cb68`.
This validates the local capture/restore seam only; it is not Q04 restored
workflow or exact replay acceptance.

For all 32 native and six Wiki06 splits, the two new nodes retain the reference
label, body parent, empty children and all non-text/provenance metadata; joining
their `text` and `orig` with one space and rebasing their provenance reproduces
the exact reference node. A **diagnostic-only** remap of those exact split
members plus unchanged one-to-one nodes produced equality of all nine graph
collections (`body`, `furniture`, `groups`, `texts`, `pictures`, `tables`,
`key_value_items`, `form_items`, `pages`) for each fixture. This is a proof of
the remaining representation delta, **not** authorization to normalize any
runtime result or change the oracle. The exact 38 split references, current
members, page numbers and source-fragment hashes are in
[SPLIT-WITNESSES.tsv](SPLIT-WITNESSES.tsv). Wiki06 source pages 7–8, 10–12, 13–14,
19–20 and 22–23 were rendered and inspected; the six splits follow the PDF
text, including a figure-interrupted continuation on pages 11–12.

Regression: two cross-column jumps failed on v1 and pass on v2; an adjacent
single-column join and old-method rejection pass. The 11 applicable historical
Q01 synthetic continuation checks, two method/dependency checks, and five Q04
acceptance-matrix checks pass. Historical Q01 checkpoint tests were not run
because `/private/tmp/t09a-r2-20260914/checkpoints` is absent. No resource
threshold, historical runner, AG artifact, reference or cluster state changed.

Post-test read-only cleanup verification found no running local Docling
container or Q04-named Pod. The retained AG PVC remains Bound at UID
`7770d9d2-dc31-4981-9a2e-25fc2fc07a1c`. All 32 historically held
Deployments still have their exact namespace/name/UID and zero desired/ready
replicas; the three Q04 namespace core services remain available.

The 38 components and duplicate picture label have now been source-reviewed in
[SOURCE-REVIEW-DECISION.md](SOURCE-REVIEW-DECISION.md). The fixture-specific
[EXACT-ORACLE.json](EXACT-ORACLE.json) freezes the complete v2 graph digests;
the runtime gate accepts only those exact graphs and mutation checks reject
extra splits and changes to text, geometry, relationships or order. This does
not retroactively accept the local captures. A new producer/runtime identity
must qualify fresh, restored, exact replay and the affected warm, resource and
interruption rows. The v2 raw documents still fail the historical reference's
strict equality; neither fixture nor #51 is accepted by this offline result.
