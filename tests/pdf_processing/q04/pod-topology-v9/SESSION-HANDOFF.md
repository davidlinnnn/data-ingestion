# Q04 / #51 J repair handoff

The requested acceptance-tool repair is implemented and reviewed at **2619844**.
One controlled J runtime completed the three YOLO business modes but failed the
unchanged resource-attribution completeness gate. It yielded complete automatic
failure evidence and clean teardown. **Q04 is not PASS; #51 cannot close.**

## Commits and tests

- `49eba63`: H sample retention / worker-log cleanup repairs and H diagnosis.
- `41a8816`: interrupted-seal allowlist correction; I execution source.
- `51e30d1`: preserved I failure evidence and transport diagnosis.
- `2619844`: J scratch boundary, separate sealed failure export, seal-order fix,
  regression tests and frozen manifests. This exact source was executed.
- This handoff's containing commit adds J evidence and unpublished ticket text.

114 tests passed before runtime, covering actual failure regressions, complete
CLI, isolated ConfigMap source projection, runtime contract, process interruption,
full controller cleanup, durable integrity and success/failure seal verification.
Two independent reviews had no blocking findings; Spec independently reran all
114 and Standards reran the 10 transport tests. See REVIEW.md and
OFFLINE-VALIDATION.md. A–I runner/evidence bytes are unchanged.

## Current acceptance matrix

| Area | Status | Evidence / remaining condition |
| --- | --- | --- |
| Rejecting sample retention | repaired; regression proven | J had no pressure rejection, so exact rejection branch remains local-test proof |
| Worker log / terminal cleanup | repaired; local and runtime proven | J seals and removes three worker generations |
| Scratch versus durable transport | repaired; local and J proven | 115 receipts; no scratch loss; strict durable checks retained |
| Failed-window automatic export | repaired; local and J proven | 77 sealed entries and tar independently verified before removal |
| Projected source / full argv / 11 pre-inference gates | passed | Frozen J manifests, local and live proof |
| YOLO fresh / restored / exact replay case checks | passed within unqualified J window | Each processing_complete=true and 15/15 registered; accepted.json verified=true |
| YOLO integrated acceptance / fresh index | NOT promoted | 54/1,023 attribution rows incomplete; pending index only |
| Resource limit / PSI / OOM observations | sampled guards passed | Not an accepted full process-attribution bound |
| Parser recycle exit / no warm-fresh overlap | J evidence present | Does not replace other required lifecycle/telemetry-loss rows |
| Native / WikiSkill 06 / remaining AIMA 08 Q04 modes | still unproven | No new runtime for these fixtures |
| ACL 09 / Keynote 10 bounded historical rows | unchanged | No expanded claim |
| Active telemetry-loss / process and Pod recovery | still unproven | Normal/failure cleanup is not recovery acceptance |
| Six-fixture matrix / #44 supported bounds / #51 closure | not ready | Existing missing rows plus attribution blocker remain |

## Why validation did not pass

J ingest operations succeeded. The acceptance checker correctly refused complete
resource qualification because process reads/coverage were incomplete. Recorded
PermissionError on shared-cgroup processes and process-set races are the direct
observed blockers. Exact process program, failing proc filename and underlying
permission cause are unknown; do not call them harmless or infer capacity
sufficiency. All sampled PSI/OOM guards passed; no deadline or Activity failure
triggered J. See first-window-evidence/RESULTS.md for causal timestamps and counts.

## Next bounded work; no automatic runtime retry

Preserve J and replay its collector rows offline. Add only the missing process
read diagnostic detail (filename, errno, PID/start_ticks and before/after identity)
at the shared read seam, without logging command secrets. Reproduce the exact
PermissionError/process-set lifecycle locally and identify whether the process
is workload-owned, monitoring-owned, or unrelated. Keep unknown PSS unknown.
If monitoring exec churn is proven, evaluate a persistent collector/transport
process using the existing same cgroup and producer; do not silently exempt
helpers or expand transition classifications. Review the resulting exact source
projection and regressions before proposing a new identity/window. Any changed
acceptance standard requires a concrete proposal and approval; no reason currently
supports more memory, replacing kind or raising PSI/gap thresholds.

Main may integrate the reviewed harness fixes and diagnostics while preserving
FAIL/unknown statuses. It must not promote the pending index or close #51. No
push, ticket publication, new ticket or second J attempt was performed. J and
historical PVCs/prefixes remain; 32 held Deployments are off, owned runtime absent.
TICKET-51-UPDATE-DRAFT.md is ready for main to publish after integration review.
