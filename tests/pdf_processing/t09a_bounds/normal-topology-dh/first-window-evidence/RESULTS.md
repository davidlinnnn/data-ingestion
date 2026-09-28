# DH: approved initial operating scope passes

DH ran once with fresh identity `t09a-bounds-20260928-dh`, fresh prefix,
all 32 recorded Deployments active, and the approved object configuration:
768Mi request, 1Gi limit, `Recreate`, with no host memory.low override. There
was no retry.

| Check | Result |
| --- | --- |
| Admission and pre-inference | PASS; 11/11 gates |
| Five business workflows | PASS; 28/15/12/51/28 registered pages and 11/4/9/7/11 components |
| Full documents/checks | Exact equality with all five accepted AI/AJ references |
| Temporal | Five completed workflows; `processing_complete=true`, no Activity failure, timeout, or cancellation |
| Warm lifecycle | 29 groups, request-20 recycle, two parser PIDs, post-recycle completion |
| Worker resource gate | PASS; 1,358 complete samples, max 2,852,814,848 bytes, no PSI/OOM violation |
| Object service | 1,995 samples, max 736,923,648 bytes, full PSI delta 0, avg10 0, max/OOM delta 0 |
| VM guard | Minimum 2,719,670,272 available bytes; avg10 0 and OOM 0 |
| Terminal boundary | Three durable proofs observed; no post-terminal PSI occurred in DH |
| Cleanup and retained configuration | PASS |

The workload exited 0 without timeout or forced stop. The terminal worker
sample passed before Kubernetes cleanup. The runner and outer controller both
exited 0; independent replay again verified all five full documents/checks,
29 groups, recycle, Temporal results, object telemetry, and lossless traces.

Independent cleanup confirms 32/32 historical Deployments are off with no
owned Pods, Temporal is idle, object health is 200, the original object PVC UID
is unchanged and Bound, the DH evidence PVC is Bound, and the trace container
and private trace instance are absent. The new prefix is retained with 914
objects. The original object PVC identity is unchanged, and the runtime check
read a preserved DB object. Cleanup did not inventory every historical prefix
or PVC.

The candidate is retained at request 768Mi, limit 1Gi, and `Recreate`. This
qualifies the explicitly approved initial scope: one serial worker, the fixed
Wiki06/YOLO07/AIMA08/native51/Wiki06 sequence, group size 5, recycle at 20,
4 CPU, 5Gi worker limit, and 4Gi sample guard. The configured 100MiB file,
51-page, and 20M-pixel admission values remain rejection ceilings; arbitrary
inputs at those maxima, concurrency, whole books, and scan-first workloads are
outside this accepted scope.

DH did not reproduce DG's post-workload kindnet PSI. It therefore does not
resolve whether that earlier work came from Pod cleanup or periodic network
reconciliation, and it is not evidence of universal zero pressure. The
approved rule still records post-terminal node PSI as telemetry only after
successful workload exit, a passing terminal worker sample, and complete
worker-child cleanup; VM OOM and the memory floor remain fatal throughout.

This supplies the missing #44 operating-scope qualification and makes #44
ready for closure for the approved initial scope after the unified ticket
update is published. #51 remains closed and accepted; it does not need to be
reopened. Broader bounds require a separate explicit scope decision.
