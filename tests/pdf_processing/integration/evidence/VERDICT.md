# Merged integration: PASS (bounded implementation gate)

Producer **456e7c9** combines T03 `8715507`, T04 `050f9cd`, T05 `b7c72b8` and two
integration fixes: checked enrichment second reads, and fresh-child/process-group
reaping before both Activity/OCR scratch cleanup at worker shutdown.

| Gate | Result |
| --- | --- |
| Real Temporal + MinIO, warm native parsing then fresh OCR | PASS |
| Multiple pictures, no pictures, real no-text picture | PASS |
| NCCU screenshot final refs contain 我的專區 and 最新公告 | PASS |
| Unsupported selected rotated crop | Explicit integrity failure |
| Repeat complete request | Same final identity, all reusable steps reused |
| Legacy version1 | parsed_ready, processing_complete=false |
| Version2 required OCR | Complete only after required outputs; canonical_accepted=false |
| Committed payload lost on enrichment second read | Permanent committed_payload_missing, one Activity attempt |
| SIGTERM with stopped fresh OCR child | 31.4147s; child gone, registry empty, scratch empty |
| SIGTERM with OCR publication paused90s | 30.8901s; registry empty, scratch empty |
| Replacement after each shutdown | Attempt2; both required OCR outputs complete and text refs verified |
| T04/T05 focused contracts | 5 + 4 tests PASS |
| Full processing package + worker Pyright | 0 errors, 0 warnings |

Lifecycle settings are Pod60 / SDK30 / warm child TERM5 / reap5 seconds. These are
SIGTERM-to-container-PID1 tests, not additional Pod-deletion tests. The active case
SIGSTOPs a real freshly spawned OCR child; it proves cancellation/reaping during an
active OCR Activity, not specifically interruption inside neural inference. The
publication pause is before the real object PUT. Existing T03/T05 Pod-loss evidence
remains separately attributed. The Temporal service here is the local SQLite dev
server on a PVC, not a production HA qualification.

## Review

Standards: PASS, no hard violations or blockers. One optional duplicated-code
heuristic: fresh single-child kill/wait/discard appears in normal cleanup and the
worker cleanup loop; centralizing that policy can be considered later.

Spec: PASS, no blocking code discrepancy. Reviewer also checked both lifecycle
results and their limited claims. Checked-read executable regression is recorded
separately in second-read.json (real service, attempt1), not a reviewer rerun.

Both reviewers inspected `9f829a7...456e7c9` and shared Processing/Execution merge
against accepted T02 `e09f23e`. Existing all-producer identity remains unchanged;
T07 owns selective compatibility. No formula/CodeItem expansion, canonical schema,
quality acceptance, downstream delivery or shared GC was introduced.

## Evidence corrections during setup

Two initial normal attempts used exploratory bytes from the old T04 ConfigMap;
they correctly failed the expected multiple-picture fixture assertion. The second
attempt still had the inherited environment-variable name wrong. The final suite
uses the qualified fixture hashes in attribution.json. Those initial requests
remain in the isolated service; they are not passing evidence.

The first integrity-harness attempt used default rather than frozen deployment
limits and correctly failed worker_method_mismatch. The corrected harness uses
the recorded limits and reaches the intended second-read seam. Initial local
Pyright lacked native dependency paths; the final full-package run includes the
existing pinned venv. No product logic was changed to bypass these checks.

No 51-page inference rerun was necessary: independent native-fidelity evidence is
unchanged, and this gate targets the newly combined seams. This PASS does not
close S2 quality qualification, T06 result handoff, or later sustained-load tuning.
