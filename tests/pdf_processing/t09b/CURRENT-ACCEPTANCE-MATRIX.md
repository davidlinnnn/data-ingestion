# T09b / #45 current acceptance state

Updated 2026-09-30 after final support/budget consolidation; #45 OPEN pending integration review. Selected configuration remains group5,
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
| Buffering/readback | Measured with explicit scopes | Publication input and GET chunk peaks, complete amplification and whole-Pod safety; no total simultaneous/native/caller-retained byte claim; SUPPORTED-CONFIGURATION.md |
| Supported group choice | Selected5 | Small normal speed gain for10 with larger memory/traffic and repeated recovery work; retain existing setting |
| Conditional concurrency | Admission evaluated; C not admitted | Planning reservation exceeds retained guard; select one child; two-child throughput/recovery unqualified, not a runtime failure |
| Final support/budget matrix | Consolidated | SUPPORTED-CONFIGURATION.md and SUPPORTED-BOUNDS.json export unchanged selected bounds separately from tested fixtures; no widening |
| Cleanup | Passed | PC2/PC3 restored32 Deployments off, no owned Pods/restoration errors, object identity/config unchanged; evidence PVCs/prefixes retained |

PC1's readiness sampling-lock failure is diagnosed, regression-locked and retained;
PC1B supersedes it as the first successful cold replicate. No automatic retries.
Relevant reports: COLD-WARM-DISTRIBUTIONS.md, RECOVERY-COMPARISON.md,
PROCESS-COLD-PLAN.md and per-cell evidence directories. Final support, buffering boundaries and conditional concurrency nonadmission are
recorded in SUPPORTED-CONFIGURATION.md. Final dev integration review remains;
no additional inference or main merge is implied.
