# CO: short1GiB/full-topology control did not reproduce object PSI

One controlled diagnostic ran on the existing kind cluster, with no ingestion,
no automatic retry, and no object mutation. Exact32 historical Deployments became
Ready. The existing MinIO process/cache was preserved while its container and
exact Pod memory limits temporarily changed512MiB→1GiB; the Kubernetes resource
spec stayed512MiB. This deliberately avoids a rollout/cache reset and is not a
full repetition of CD's newly rolled-out object Pod or mixed producer workload.

The55.11s measured interval includes activation/readiness,30s idle observation,
and one bounded read of20 preserved CB objects totaling4,066,907 bytes. The
original VM admission floor4,831,838,208 bytes, runtime floor1,610,612,736 bytes,
VM full-PSI avg10/OOM, and object full-PSI/max/OOM stop rules were retained.
Each sample was saved before guard validation. No producer or acceptance rule changed.

## Results

- Object container and Pod effective limits stayed1,073,741,824 bytes throughout.
  Their full-PSI, max and OOM deltas were zero. Object max usage535,519,232 bytes;
  file-refault delta991. All observed ancestor-local max/OOM deltas were zero.
- VM minimum available5,582,077,952 bytes. Direct/background scan deltas0;
  compaction stalls+7, VM file refaults+11,071. No formal VM guard violation.
- The direct function tracer captured36 VM calls (23folio_wait_bit_common,
  6read_pages,7direct_compact) in the measured interval and **zero exact-target
  object calls**. All trace buffers report zero overruns/dropped events.
- Ancestor full-total PSI deltas were small but nonzero (up to64us at the
  node cgroup root), while object/Pod totals and VM avg10 stayed zero. Do not
  describe this as zero PSI everywhere. Ancestor totals are diagnostic evidence;
  they did not replace the existing formal guard.

The short all-on background/read window was insufficient to reproduce CD.
It weakens the hypothesis that normal topology plus these object reads alone
necessarily causes CD's stall. It does not exclude intermittent behavior,
longer duration, different reads, the full producer's memory demand, or different
cache/reclaim state. Unlike CD, this window had no VM direct/background scanning.
No new production remedy or permanent sizing conclusion follows from this negative
control. CK/CM/CN's512MiB resting-pressure mechanism remains independently proven.

## Verification and restoration

`python3 -B tests/pdf_processing/t09a_bounds/object-stall-probe/check_co.py`
checks the actual CL ancestor-cap mistake and the controller's persist-before-stop
path. The new sampler also passed a real read-only six-level cgroup smoke check.
`python3 -B tests/pdf_processing/t09a_bounds/object-stall-probe/verify_co.py`
replays guards against all retained samples and verifies effective caps, trace
loss counters, same object identity, and cleanup. Both passed. No unrelated
producer regression suite was rerun because no producer code changed.

All32 Deployments returned0/0 with no owned Pods. Exact leaf/Pod caps returned
512MiB, object service remained Ready with health HTTP200, and all owned diagnostic
containers/private trace instances were absent. PVCs and prefixes were preserved.
The independent cleanup script initially treated a string return as a process
object; correcting that read-only check yielded PASS without changing the runtime.
Raw samples/trace, terminal record, analysis and cleanup are retained here.

## Next discriminating scope

Stop standalone idle/read variants. The missing combination is the actual mixed
producer's memory/reclaim activity with MinIO reads. If proceeding with another
runtime, use the original [06,07,08,native,06] workload once with the new ancestor
sampler plus direct PSI attribution, preserving the first trigger and existing
guards. The added measurement must distinguish limit-charge stalls from page-read
waits under VM reclaim; it must not be counted as a remedy just because it passes.
There is no evidence-backed production/configuration change to apply yet.
#44 remains open, #45 remains blocked, and #51's accepted history is unchanged.
