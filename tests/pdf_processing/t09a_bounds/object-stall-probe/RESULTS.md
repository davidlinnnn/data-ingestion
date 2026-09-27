# Minimal object-read diagnostics

CE observed 45 seconds with all 32 held Deployments off and object at restored
512Mi. Direct function tracing captured PSI memory-stall entry callers and
live task cgroups, but no target MinIO stall. This does not reproduce CD.
CE exposed a diagnostic cleanup defect: switching current_tracer while the
trace_pipe fd was open returned EBUSY. The exact private instance was then
removed; the tracer now closes the fd before switching to nop. CF and the CG
one-second start/end check verified the corrected real cleanup path.

CF performed one bounded, read-only sweep of the preserved CB object prefix
through the existing coordinator. It read 27,377,764 bytes within the 30-second /
32MiB bound, with no retry, no object mutation and no target object PSI increase.
The direct-caller tracer exited cleanly. No deployment replicas or resource
limits changed. Two local attempts before CF started stopped at import time;
no remote work occurred. The final script uses the coordinator's installed
client rather than installing a new dependency.

A standalone read does not reproduce the mixed-load failure. The next
measurement (CG) keeps CD's workload/guards and replaces broad MinIO
sched stacks with direct psi_memstall_enter stacks and task cgroups.


## CH–CN: idle pressure attributed; effective-limit reversal (2026-09-27)

This is a diagnostic result, not a new full ingestion acceptance. Formal
thresholds, model/producer code, Kubernetes object resource specification,
PVCs and object prefixes are unchanged. Each intervention ran once with a
fresh identity; failures stopped rather than triggering an automatic retry.

### Findings

CK captured three direct `psi_memstall_enter <- try_charge_memcg` stacks in
the exact object container. All belong to the actual `minio server /data`
process (host TGID778767), not an inspection subprocess. They traverse
`ext4_readdir` / `__arm64_sys_getdents64` and file-cache or buffer-head allocation.
Full PSI increased67us in0.58s, direct-scan pages increased320 and file refaults
increased207. OOM/swap were zero. Trace buffers report zero overruns/drops.
There was no ingestion, object exec, S3 request or reclaim intervention during
CK. This establishes server directory work causing memory-charge stalls at
512MiB. The particular Go scanner/request origin remains unknown.

The effective budget is constrained by both the container and its Pod ancestor.
Container `memory.events` does not report events local to its parent. At the
start of CM, the leaf max-event counter was2 while the exact Pod counter was970.
Reading only the leaf therefore misses the limiting ancestor, even though
leaf PSI still detects the stall. See the kernel documentation on hierarchical
limits and [memory.events.local](https://www.kernel.org/doc/html/v6.12/admin-guide/cgroup-v2.html).

| Probe | Intervention / result | Interpretation |
| --- | --- | --- |
| CH | Read20 preserved CB objects (4,066,907 bytes), reclaim8MiB once, reread. No PSI or file refault. | Selected pages were not demonstrably evicted; does not refute refault pressure. |
| CI | Admission found existing PSI396us/max1 before intervention. | Stopped before reads, tracer or larger reclaim; no runtime result. |
| CJ | Observer overlapped our `minio --version` subprocess. | Contaminated. Target traces belong to TGID795580, not server778767; excluded from idle-server attribution. |
| CK | Read-only idle observation; server directory stacks; PSI+67us. | Direct attribution of the idle512MiB mechanism. |
| CL | Leaf raised to1GiB, but Pod stayed512MiB; PSI+74us. | Invalid effective-capacity contrast; not evidence against1GiB. Leaf restored. |
| CM | Both exact leaf and Pod raised to1GiB for30.20s, same process. PSI/direct reclaim/max events unchanged; file cache grew18,092,032 bytes. | Continued cache work without this stall within the short larger-budget window. Both limits restored512MiB. |
| CN | Read-only observation after restoration; PSI+51us in0.51s. Pod max+2; leaf max unchanged; direct scan+128 pages. | Reversal supports effective512MiB limit as the cause of this idle pressure. OOM remained zero. |

These controls are intentionally separate from full qualification. The CM
budget change was temporary, in the existing exact cgroups, with in-process
finally restoration. No Deployment resource spec or replica count changed.
Restoration itself reclaimed5,120 pages; CN began44s later, and its server PSI
and Pod max events increased during the new read-only interval, not merely in
the limit-write interval.

### What this does and does not explain

The retained CD/CG guard replay still returns CD=FAIL and CG=PASS. CD had more
worker file refaults (82,562 versus7,491) and VM background scans (744,300 versus
434,849), while CG had more compaction stalls (65 versus27) and a lower minimum
available memory. These are correlations across different completed work, not
proof of a capacity requirement or of tracing causing CD. `cd-cg-comparison.json`
records the comparison; its extraction script uses the preserved local raw runs.

CK/CM/CN explain a separate reproducible resting512MiB pressure mechanism.
**They do not prove the historical CD1GiB event had the same caller or limiting
ancestor.** CD lacked exact task attribution and ancestor-local trigger counters.
Do not conclude that adding memory permanently solves CD, that PSI was a false
positive, or that the cluster must be replaced. The OCR-only NumPy hugepage fix
and CG functional acceptance remain valid within their previously recorded scope.
#51's historical acceptance is unchanged; #44 remains open and #45 remains blocked.

### Verification and cleanup

Run `python3 tests/pdf_processing/t09a_bounds/object-stall-probe/verify_idle_cause.py`.
It parses the original CK trace, verifies server/cgroup attribution and buffer
loss counters, checks every CM sample's effective limits and unchanged pressure,
and checks the CN ancestor-only limit events plus restoration. It runs offline.
`python3 -B tests/pdf_processing/t09a_bounds/object-stall-probe/compare_cd_cg.py`
replayed the actual formal guard against preserved CD/CG samples successfully.
No producer changes occurred, so another full producer suite was unnecessary.

Independent live cleanup confirmed exact32 recorded Deployments at0/0 with no
owned Pods, object Deployment512Mi/Ready and health HTTP200, no diagnostic
containers, and no private q44 trace instances. CM also records restored leaf
and Pod limits. No PVC or object deletion occurred. Exact executed scripts and
raw summaries/traces (gzip for larger files) are retained in the CH–CN directories.
They are forensic records with used identities, not commands to rerun unchanged.

### Next justified measurement

Do not run another identical full matrix. The missing CD evidence is the
limiting level and direct caller **under the original1GiB/full-topology scope**.
A next measurement must record the leaf and ancestor `memory.max`,
`memory.events.local`, PSI and reclaim/refault counters together, preserving the
trigger sample and exact MinIO TGID. Use the short directory-read observation
first; proceed to full ingestion only if a specific fix or discriminating
workload hypothesis requires it. Keep the existing zero-event guards and all32-off
resting state; permanent resource/acceptance changes remain a separate decision.


## CO follow-up

The proposed1GiB/all32-on short control is complete:30s idle plus20 read-only
objects produced no target PSI, with effective ancestor limits recorded. No VM
reclaim occurred, so this did not reproduce the original mixed-load state.
See [CO results](co-normal/RESULTS.md). Stop standalone idle/read variants;
any next runtime needs the actual mixed producer plus ancestor/direct-call evidence.
