# T02 verdict: supported within the native processing slice

Implementation: `3cc7d84` (following `7fcbc98` and bytecode cleanup `43d77ba`).
Producer hashes in `producer-hashes.json` and stored plans were checked byte-for-byte
against final mounted code; final follow-up commits only add tests/documentation/evidence.
The source baseline is accepted T01 `a05fb454779bf97e3fc11cdbd41fcc0eb3e8951f`.

## Verified

- Separate K8s Workflow and PDF Activity Deployments, explicit queues, actual Temporal
  and versioned MinIO. No mocked workers or object-store semantics.
- Three-page generated native PDF plus fixed 51-page paper: complete registered page
  coverage and fresh-process assembly. The paper's entire Docling JSON matches the
  fixed historical SHA-256 `fd45828175ad659df5b25d90a6c463adc43ddc8c813737d98e1ae6f583d71aab`.
  Generated native fixture text is checked against independent literal expectations.
- Assembly reports zero page-inference stage inputs. Result remains `parsed_ready`,
  `processing_complete=false`, `canonical_accepted=false`.
- Nine rejection cases: invalid contract, absent Activity queue, invalid PDF, password,
  page limit, render-pixel limit, byte limit, digest mismatch and missing source.
  Each has zero registered pages and a timestamped terminal result matching its query.
- Conflicting Source Revision under an existing internal request ID is rejected.
- Actual Activity Pod replacement: all 14 operations (12 groups + 2 assemblies) reused,
  zero uploaded bytes, identical parsed-result references. `/scratch` was empty.
  Worker UIDs and immutable actual image IDs are recorded in `runtime.json`.
- Intentionally incompatible Docling version attribution fails permanently as
  `method/worker_method_mismatch`, zero registered pages, observed Activity attempts
  never above 1. This uses its own Activity queue and a deliberately incompatible
  test-only profile; it does not alter the accepted profile or package installation.
- Existing T01 scanned fresh-restoration regression: one test passed in 26.984 s.
- Pyright: zero errors/warnings over processing, deployment entrypoint and T02 driver,
  using pinned interpreter plus external SDK sources. No type tools installed into
  the measured parser runtime. Fixed prototype/T01 evidence diff is empty.

The first complete native runs took about 12.38 s (3 pages) and 100.97 s (51 pages)
when summing recorded stage wall durations; these exclude preflight and orchestration
wait and are **not end-to-end latency measurements or SLAs**. Performance tuning and
production resource envelopes remain T09.

## Two-axis review

Standards: no documented-standard violations. Two nonblocking heuristic findings:
versioned source reads reach into Store's client/telemetry internals (candidate for a
future adapter refinement); duplicate measurement construction was removed.

Spec: two blocking findings were fixed and independently re-reviewed: early failure
query/result disagreement, and subprocess loss of permanent method/integrity error
categories. No remaining blocking spec findings; the additional absent-queue case
was added to cover the second early-return path.

## Retained runtime and limits

Local namespace `pdf-t02-validation`; bucket `t02`; final prefix `qualified`.
Coordinator raw reports at `/tmp/t02-qualified`; object artifacts remain on its MinIO
PVC. Earlier exploratory prefix `final` remains separate and is not final evidence.
Images/services use the pinned T01 Linux ARM64 runtime and local dev infrastructure;
actual image IDs are recorded. The checked-in validation manifest shows test settings;
for the final run the Activity prefix was explicitly changed to `qualified`.

Provisional validation envelope: 4 MiB, 100 pages, 20 million pixels/page, scale 1;
30 s preflight / 540 s processing child deadlines, finite Temporal budgets, one slot.
No shared GC, public admission/status DB, canonical mapping, OCR completion, warm
reuse, in-flight Pod-loss proof, upgrades, production HA or general quality claim.
Those remain with the scoped follow-up tickets and separate design tracks.
