# T07 acceptance verdict

**PASS for the internal compatibility contract and bounded synthetic source scope.**
This is neither canonical acceptance nor new PDF quality, throughput, capacity or
production durability qualification. The T06 AIMA association/order limitations
remain in force. No new broad language or whole-book claim is made.

| #42 acceptance | Evidence and result |
|---|---|
| Stage dependencies | `compatibility.py` owns parsing, assembly, selection, OCR, evidence and finalization dependencies; source object/revision, complete group plan, stage implementation and active method are bound. Full accepted provenance is separate. |
| Outer reuse and persisted restoration | [OCR case](matrix/ocr.json): the newly requested OCR implementation/scale reuses the actual baseline group and assembly registrations. Saved group sidecars/methods/bytes are validated on reuse. A separate fresh restore child loads that baseline checkpoint, executes zero page stages and produces full JSON equal to the prior assembly. |
| New required OCR and completion | Subprocess audit events show no parse/assembly launches and exactly four OCR launches. Four newly executed components at render scale 4, under the actual changed OCR module, with exact new request/selection/method attribution. A distinct v3 complete result links durable source-bound evidence; canonical acceptance stays false. The old request is rejected on the changed worker rather than reinterpreted. |
| Invalidation and irrelevant changes | [Revision](matrix/revision.json), [bytes](matrix/bytes.json), [group plan](matrix/group-plan.json) and [parser implementation](matrix/parser-implementation.json) execute new parsing and assembly. [Unrelated adapter](matrix/unrelated.json) reuses both. [Evidence policy](matrix/policy.json) reuses both while delivering the exact new synthetic-source review and changed evidence coverage. |
| Unsupported method and formats | [Unsupported parser configuration](matrix/parser.json) fails permanently with `worker_method_mismatch`, with zero registered pages and no fallback. The OCR restore case rejects a future document format and an undeclared checkpoint producer transition. |
| Duplicate and lost acknowledgements | Each complete matrix request is repeated against real Temporal/shared storage; all parse/assembly/OCR steps reuse the same registrations and complete result. [T03 storage regression](store-regression.json) reruns real concurrent-winner, lost-write-ACK, corrupt/missing payload, access-denied and configuration/transient checks. A separate [real Temporal second-read failure](second-read.json) rejects missing committed content permanently on attempt 1. |
| Authorization and legacy | [Identical bytes outside source scope](matrix/unauthorized.json) are rejected before parsing. [v1](matrix/legacy-v1.json) remains parsed_ready/incomplete; [v2](matrix/legacy-v2.json) completes required OCR without a v3 evidence requirement. |
| Checks and review | [All 10 unit regressions](full-suite.log), including real scanned fresh-process restoration, pass. [Typecheck](typecheck.log): zero errors/warnings. Independent Standards and Spec reviews and correction rechecks have no outstanding implementation finding: [review](../REVIEW.md). |

[Temporal histories](matrix/temporal.json) bind scenario requests to actual workflow
and run IDs, dedicated Activity queues and scheduled Activity types.
[Runtime](runtime.json) records the isolated Pod UIDs/images and final source hashes.
Every scenario records its full declared environment/profile and actual producer
hashes. OCR uses a real implementation-output attribution change plus scale 3→4;
this run does **not** claim a separately installed OCR package/model upgrade.
The inactive native OCR option is changed in the new profile and must pass projected
persisted method validation. Unknown runtime changes remain conservative.

The main OCR-only request performs no page inference and no assembly. The explicit
restore verification intentionally performs assembly once with page-stage guards;
its `document_assembly` page count of zero means assembly has no page-stage inputs,
not that the restore check skipped document assembly. The saved checkpoint and prior
assembly remain readable and unchanged. All full documents/crops/source artifacts
stay in isolated local storage; committed reports contain metadata and hashes only.

The internal v2 operation namespace requires a compatibility sidecar. Baseline
checkpoints here are created under that contract before the OCR change. Pre-T07
T06 registrations are not migrated automatically; undeclared imports are rejected.
See the [consumer/version-transition contract](../../../../src/pdf_processing/README.md#stage-compatibility-and-deliberate-reprocessing-t07).

The initial [red case](red-reprocess.json) recorded repeated parsing/assembly. One
exploratory restore assertion omitted the zero-valued model-initialization metric;
it was corrected without changing the expected zero-inference guarantee. A later
unsupported-method assertion was aligned with validation ordering. Final accepted
matrix reports were regenerated after the reviewed source corrections.
