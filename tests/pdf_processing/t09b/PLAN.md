# T09b measurement plan and tooling audit

2026-09-28. Planning only; no runtime executed or configuration selected.
Issue: https://github.com/davidlinnnn/data-ingestion/issues/45
Branch: `feat/t09b-calibration`, based on dev `9e00ddc`.

## Scope and prerequisites

Retain the accepted Wiki06, YOLO07, AIMA08 and native51 fixtures, required OCR,
complete graph/checks, models and profiles. Compare full business completion,
not Temporal COMPLETED alone. #44 and #51 are closed; their historical recovery
proofs retain their original identities and do not prove new concurrent recovery.
Before runtime, verify publication-wait removal and warm/profile isolation in
the active source and tests, rather than inferring these prerequisites from closure.

Use existing kind/namespace and retained object request 768Mi/limit 1Gi/Recreate.
Keep OCR intra-op 4, recycle 20, worker 4 CPU/5Gi hard limit/4Gi sample guard and
all accepted PSI/OOM/floor/deadline/telemetry/cleanup rules. No host cache flushing,
new environment or resource-limit increase. Record actual image, architecture,
model/profile/source identity and storage conditions once per comparison batch.
Hold topology identical across comparisons; any temporary activation of the 32
historical Deployments needs an explicitly declared window and restoration to off.

## Small adaptive comparison set

| Step | Group size | Active parser children | Purpose |
| --- | --- | --- | --- |
| A | 5 | 1 | Matched baseline with the completed measurement instrumentation |
| B | 10 | 1 | Test grouping overhead versus repeated work and peak buffering |
| C, conditional | Selected A/B size | 2 isolated children | Test bounded concurrency only after aggregate admission and lifecycle checks |

The group-10 choice is an experimental candidate, not an accepted bound. Do not
silently retain it. C requires a reviewed scheduling implementation, one active
slot per child, and a concrete shared resource budget within existing limits.
Do not merely increase Temporal activity concurrency on a shared mutable converter.
If that cannot fit the present budget, record C as not admitted and retain serial
support; do not claim #45 complete without resolving its concurrency requirement.

For A/B, predeclare three matched pairs, alternating order A/B, B/A, A/B.
Each cell starts a fresh parser and processes the same fixed mixed sequence.
Report first-request process-cold timing separately from later warm timings;
host/filesystem caches are uncontrolled and must not be called cold. This design
does not supply cold distributions for every fixture. If #45 needs those, add
matched fresh-parser runs for those fixtures before claiming that coverage.
Report all observations, median and range, no p95/SLA/confidence claim from n=3.
DH is a correctness/reference anchor, not a substitute for this matched baseline.

Runs are individually admitted, use fresh identities/prefixes and stop on failure.
Planned successful replicates are not failure retries. A guard, quality or cleanup
failure stops the batch; diagnose and revise the plan before any new run.

## Required measurements and current gaps

| Requirement | Existing seam | Necessary work before comparison |
| --- | --- | --- |
| Workflow and stage time | Temporal history; `src/pdf_processing/parse.py` events and `stage_seconds_sum_not_wall`; `tests/pdf_processing/t09a_r3/collect.py` | Aggregate queue, parse, required OCR, assembly, publication and terminal wall times by request/attempt. Stage sums are not wall time under concurrency. |
| Application storage cost | `object_store.Store.io`; `processing.py` per-operation storage deltas | Preserve per-request attribution and all attempts. Successful payload-byte counters omit failed/SDK-retried transfers and protocol overhead; never label them total network traffic. |
| Actual traffic and readback amplification | Store get/put and resolve/read_artifact paths | Instrument the existing client request boundary or scoped server request records for attempts, transferred bytes, key/category and outcome. Validate retry/partial-read accounting locally. Exclude observer/verifier traffic or report it separately. |
| Checkpoint size and buffering | `Store.inventory()` and immutable manifest sizes; Pod collector | At quiescence report unique registered payload bytes and total prefix bytes including orphan attempts. Count repeated reads separately. Measure peak in-flight payload buffers; Pod peak alone is not a buffering measurement. |
| Resource/lifecycle | DH resource collector, terminal guard and cleanup | Reuse unchanged guards; record whole-Pod, child, scratch, object and node observations. Multi-child attribution and aggregate admission need local checks before C. |
| Output equivalence | DH `verify_results.py`, accepted AI/AJ outputs | Reuse full graph/checks expectations, but make the new verifier accept explicit paths and expected grouping. Historical DH is hardcoded to local reference paths, 29 groups and 2 PIDs. Preserve it. Review any group-dependent output identity rather than stripping fields blindly. |
| Recovery cost | Q04 BE/BH; `t09a_bounds/RECOVERY-IMPACT.md` | Run matched baseline and selected-candidate interruption under current settings; inherited proofs cannot measure their new cost. |

Define payload read amplification as successful application GET payload bytes /
unique logical payload bytes required by that request; write amplification as
attempted transmitted PUT payload bytes / unique committed payload bytes. Report
denominators and failed/unknown-byte attempts, plus actual transport bytes separately.
Do not derive traffic from object inventory or report missing telemetry as zero.
Avoid using shared Store counter differences for overlapping requests: those can
attribute one request's traffic to another.

## Recovery and selection

After successful normal-path comparison, inject one matched in-flight group loss
for baseline and selected candidate after the same durable page boundary (10 pages
for groups 5/10), with unchanged finite recovery rules. Record loss-to-completion,
retried pages/groups, bytes, resource peak and equality to uninterrupted output.
Verify old runtime cleanup and registered-output reuse. A selected concurrent
configuration additionally needs its affected isolation/recovery proof. One fault
pair is a measured case, not a recovery-time distribution or reliability guarantee.

Quality, resource, complete telemetry and cleanup are hard prerequisites. Prefer
the existing configuration if matched timings overlap or recovery/storage costs
make the tradeoff unclear. Publish all normal/recovery costs; do not invent a
single weighted score or silently trade safety for speed. A material tradeoff
requires a documented decision before changing the supported configuration.

Final output must list file/page/pixel admission ceilings separately from tested
fixtures, and actual memory, timeout, retry/no-progress, recycle and drain settings.
Requalify only gates affected by the selected setting, including compatibility
invalidation and complete-output equality. Do not promote arbitrary maxima or
scan-first/whole-book support. Keep main unchanged; PR targets dev.

## Next implementation slice

Trace and complete measurement export at the existing storage/execution seams,
then add focused local checks for retry byte accounting, request attribution,
group-dependent verifier expectations and interruption cleanup. Review the runnable
launch contract before admitting A. No new benchmark framework, hash scheme or
unchanged full Q04 rerun is needed. This plan is not a #45 completion claim.
