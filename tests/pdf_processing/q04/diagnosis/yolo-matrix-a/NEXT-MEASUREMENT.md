# YOLO next measurement options

This document grants no runtime authorization. Matrix A, its prefix, paths and
reservation are consumed. Any measurement needs a new phase, prefix, root,
capacity record and explicit main-session window. Keep the 32 historical
Deployments closed and main-owned.

The reviewable offline implementation is
[`preflight/yolo-attribution-b/PLAN.md`](../../preflight/yolo-attribution-b/PLAN.md),
with phase `yolo-attribution-b`, a new root/prefix, fixed source hashes and
synthetic collector tests. Its presence still grants no runtime authorization.

## Recommended first measurement

Run one **fresh-only fixture 07 attribution calibration** before another
fresh/restored/replay matrix. Preserve the existing outer admission, 3 GiB
per-case admission, 1.5 GiB VM floor, 4 GiB active cgroup guard, PSI/OOM/sample-gap
guards and cleanup reserve. A repeated guard stop is acceptable because the goal
is attribution, not acceptance. Do not automatically retry or raise the guard.

Add an external 250 ms collector that does not alter producer/profile/oracle
bytes or scheduling. Capture from before worker start through owned cleanup:

- cgroup identity plus `memory.current`, `memory.peak`, `memory.events`, PSI and
  `memory.stat` anon/file/file-mapped/inactive-file/shmem/kernel/slab fields;
- identity-fenced process tree with PID, parent, start ticks, command-class hash,
  RSS/PSS, anonymous/file/shmem RSS, faults and CPU for controller, worker, warm
  parser and every fresh child;
- explicit operation markers for group capture, assembly materialization,
  fresh-child spawn/exit, publication, cancellation and cleanup;
- synchronized baseline, per-group completion, assembly start, first breach,
  peak, child exit and post-cleanup samples;
- cgroup current minus synchronized owned PSS as a diagnostic residual only.

The measurement passes its own purpose if hashes and ownership are complete,
sampling gaps stay within one second, the guard outcome is preserved, cleanup is
verified and the trace can distinguish simultaneous warm-parser, fresh-child and
shared-cgroup charges. It does not need the fixture to complete.

## Follow-up choices

| Option | Benefit | Cost and boundary | Recommendation |
| --- | --- | --- | --- |
| Shared coordinator cgroup with attribution collector | Smallest change; directly explains matrix A's measurement scope | Unrelated coordinator charges remain in the total | **First** |
| Isolated process worker cgroup | Separates worker/children from unrelated coordinator processes and gives a cleaner owned peak | Changes metric topology, requires cgroup delegation/cleanup proof, and still does not prove Pod replacement | Use only if the first trace remains ambiguous |
| Owned single-container Pod | Gives a distinct container cgroup and aligns resource observation with future Pod drain | Requires the missing owned Deployment, bundle/state/evidence mounts, UID/label fencing, readiness, CRI and emptyDir proof | Prepare separately; do not combine with the next calibration |

An isolated process cgroup can clarify resource ownership but cannot be counted as
Pod drain evidence. An owned Pod can support both cgroup attribution and later
drain work only after its topology is reviewed; creating that Deployment remains
outside this plan.

## Fix decision after measurement

Prefer no producer change if the collector shows expected bounded overlap and
clean post-run release. If simultaneous PSS shows the retained warm parser and
fresh restore child dominate the breach, review a qualification-specific parser
lifecycle change such as stopping/restarting the warm child before assembly.
That changes supervision behavior and requires new frozen hashes, compatibility
checks and full graph/oracle equivalence before adoption.

If file/cache residual dominates, review cgroup isolation and cleanup observation
before parser changes. If unrelated coordinator processes dominate, move the
qualification worker to an isolated cgroup or owned Pod. If no component explains
the delta, stop and improve instrumentation rather than increasing the guard.

The next complete YOLO acceptance window remains fresh/restored/exact replay with
all table/cell, caption, OCR, graph and source-evidence oracles. A resource
calibration pass alone does not accept fixture 07 or close #51.
