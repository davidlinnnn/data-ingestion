# T09b / #45 current acceptance state

Updated 2026-09-30 after PC3; #45 OPEN. Selected configuration remains group5,
one active parser child, unchanged supported budgets/resources. Diagnostic passes
are not production capacity, a backend ranking or a ticket closure claim.

| Requirement | Status | Evidence / limitation |
| --- | --- | --- |
| Normal group5 vs10 comparison | Measured | Three matched pairs A6/B2, B4/A7, A11/B5; full required work/output and cleanup; times overlap |
| Matched recovery/repeated work | Measured | RA2/RB1, same10 durable pages; group5 repeats5 vs group10 repeats10; full output, traffic and cleanup |
| Process-cold observations | Measured n=3 | Wiki06 from A6/A7/A11 first requests; YOLO07/AIMA08/native from PC1B/PC2/PC3 fresh workers; host caches uncontrolled |
| Later-request workflow observations | Measured n=3 | Existing selected group5 sequence; native spans recycle, not wholly warm |
| Stage timings / required OCR | Measured with explicit scopes | Temporal stage/queue/activity timings including all OCR; cold parser conversion and publication/readback timers exported from existing metrics/ledgers; nested timers not additive |
| Checkpoint size/readback/actual HTTP traffic | Measured | Complete ledgers, quiescent registered payload/prefix/orphans and scoped server counters; not packet-level wire bytes or version snapshots |
| Buffering | Partial | Publication inputs/read-chunk peaks and whole-Pod memory measured; caller-retained/native buffer boundary remains unresolved |
| Supported group choice | Selected5 | Small normal speed gain for10 with larger memory/traffic and repeated recovery work; retain existing setting |
| Conditional concurrency | Pending resolution | One child supported; two children not admitted without reviewed aggregate budget/implementation; no two-child failure claim |
| Final published support/budget matrix | Pending consolidation | Existing file/page/pixel/OOM/floor/timeout/retry/no-progress/recycle/drain bounds retained; no widening or unrelated Q04 rerun |
| Cleanup | Passed | PC2/PC3 restored32 Deployments off, no owned Pods/restoration errors, object identity/config unchanged; evidence PVCs/prefixes retained |

PC1's readiness sampling-lock failure is diagnosed, regression-locked and retained;
PC1B supersedes it as the first successful cold replicate. No automatic retries.
Relevant reports: COLD-WARM-DISTRIBUTIONS.md, RECOVERY-COMPARISON.md,
PROCESS-COLD-PLAN.md and per-cell evidence directories. Remaining work is the
buffering boundary, conditional concurrency decision and final bounds report.
