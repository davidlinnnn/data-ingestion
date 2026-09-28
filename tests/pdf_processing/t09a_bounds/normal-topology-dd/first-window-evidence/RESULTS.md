# DD — native object candidate rejected by strict PSI gate

One execution at58fb304, identity `t09a-bounds-20260928-dd`, prefix
`t09a/bounds-20260928-dd/`, existing kind/namespace; no automatic retry.
Result: **FAIL_INITIAL_SCOPE_QUALIFICATION**. The readiness repair worked:
initial rollout and deliberate Pod replacement both reached Service HTTP200;
the replacement retained768Mi request/1Gi limit/Recreate and the original
object PVC. Existing Wiki source readback returned1,177,706bytes beginning
with the PDF signature. All32 historical Deployments were temporarily Ready.
No host memory.low override or diagnostic OCR constructor override was used.

## Completed and incomplete gates

| Gate | DD result |
| --- | --- |
| All11 pre-inference gates | PASS |
| MinIO rollout/replacement/settings/PVC/readback | PASS |
| Wiki06 / YOLO07 / AIMA08 business completion | PASS:28/15/12 pages,11/4/9 components |
| Those three full documents/checks vs accepted AI/AJ fresh | Equal; verified=true |
| Native51 | FAILED:10 registered pages,processing_complete=false |
| Fifth Wiki /29groups /request20 recycle /two parser generations | Not reached |
| Original zero-new-object-full-PSI gate | FAIL: first27us; final867us |
| Object max/OOM and observed VM avg10/OOM/floor guards | No violation observed |
| Full terminal worker resource/lifecycle qualification | Not qualified after guard interruption |
| Fixed auxiliary node attribution | Start/end present; signal stop; encloses runner and owned-runtime cleanup |
| Independent cleanup/restoration | PASS |
| Permanent native object adoption /#44closure | Not eligible |

## Stop and business causality

At2026-09-28T06:47:35.323689Z the retained object sample changed full total
from0 to27us. The exact container charged501,501,952bytes under its1Gi limit,
with max/OOM counters0,full avg10=0.00 and container/Pod low=min=0.
The preceding sample at06:47:35.071326Z had total0. The controller sent the
owned supervisor signal at06:47:35.526449Z. Temporal received workflow cancel
at06:47:35.786910Z and completed at06:47:35.802401Z with the failed business
result `infrastructure/activity_budget_exhausted`,10/51 registered pages and
processing_complete=false. No Activity-failed or timed-out event precedes
this cancellation. The workflow started06:47:07.137373Z with180s execution/run
limits; cancellation arrived after about28.65s. This is guard-driven interruption,
not demonstrated deadline exhaustion and not successful ingestion merely
because Temporal's execution status is COMPLETED.

The second native group checkpoint completed before the trigger; Temporal
scheduled the next group at06:47:35.264017Z but there is no subsequent Activity
start before cancellation. The retained process/worker export does not contain
a completed measurement contract or final lifecycle sealing. The864 raw inflight
process rows all report complete attribution, but that does not make the
terminal qualification PASS. Forensic export and old runtime/scratch removal
are recorded separately in outer-cleanup.json.

The auxiliary observer ended after runner cleanup and before outer restoration
of32 Deployments/object resources. Restoration has independent readback, not
auxiliary whole-node attribution coverage.

Object telemetry:1,510samples,max gap0.259072s,peak539,328,512bytes,zero max/OOM,
full avg10 always0.00,total full increase867us through cleanup. Worker VM
telemetry:860samples,worker charge peak2,536,509,440bytes,minimum available
2,899,464,192bytes,node full avg10 always0,VM OOM delta0. These are partial
window observations, not a supported capacity ceiling or full-window PASS.

## Diagnosis and remaining uncertainty

The immediate stop is proven: the existing strict rule rejects any new object
full PSI. The first trigger was27us, not the later867us cleanup total. Linux
PSI's cumulative microsecond counter can capture short stalls that do not show
in avg10; zero avg10 does not imply zero cumulative stalls.
[Kernel PSI documentation](https://docs.kernel.org/accounting/psi.html).

No object limit hit or OOM was observed. Actual low/min were0 despite the768Mi
Kubernetes request; the request did not install the managed protection used
by DB. This difference is measured, but DB/DD are not a causal A/B experiment.
The stalled task/kernel callsite, allocation or cache-fault mechanism is unknown:
DD contains cgroup attribution, not a direct task/kernel stall trace. Cannot
conclude capacity is insufficient, PSI is a false reading, protection would
solve it, or kind must be replaced. No acceptance threshold was changed.

The next useful diagnosis is a small object read/write probe that records
actual latency and a direct stall callsite under this native setting, rather
than another full PDF window or a larger limit. A sustainable protection policy
or revised PSI acceptance rule would be a separate critical decision with
explicit evidence; neither is adopted by this failed trial. The already
approved CS functional policy remains historical and was not substituted for
DD's declared strict gate.

## Restoration and evidence

Exact128Mi request/512Mi limit/cpu100m and RollingUpdate25%/25% restored.
Independent readback confirms32 exact/off Deployments,no owned Pods,DD runtime
and both observers absent,Temporal healthy/idle and objectHTTP200. Original
object PVC UID `ebd0ba41-443c-4971-859a-3b2ca8f5b1d4` remains Bound on its
original PV. New evidence PVC UID `7c6203b8-620e-47d2-b58a-0acce0809d47` is
Bound and retained. No historical prefix/PVC/evidence was deleted or overwritten.
Main checkout changes were preserved.

Raw runtime `/private/tmp/t09a-bounds-20260928-dd`, object telemetry
`/private/tmp/t09a-bounds-object-20260928-dd`, outer controller
`/private/tmp/t09a-normal-topology-20260928-dd`. This directory retains summaries,
exact trigger/previous samples, native Temporal history, cleanup, logs and
compressed raw object/VM/process/auxiliary telemetry. Full outputs remain in the
raw export and retained PVC; the three completed output comparisons are retained.

DD pre-runtime launch/projection/contract/cleanup checks and both review axes
passed. Shared readiness policy has five regression cases; inherited DC guard,
interrupt/cleanup regressions remain unchanged and passed. Recovery source-impact
mapping and six relevant current-source local checks are recorded in
[RECOVERY-IMPACT.md](../../RECOVERY-IMPACT.md). #44 remains OPEN, #45 blocked;
#51's original scoped closure is unchanged.
