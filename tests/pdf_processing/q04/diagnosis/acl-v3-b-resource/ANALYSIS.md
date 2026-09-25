# ACL v3-b active-cgroup rejection diagnosis

## Verdict

ACL v3-b was correctly stopped by a **qualification harness ceiling**. The
captured coordinator-container cgroup rose above 3,221,225,472 bytes during the
fresh case. It was not stopped by Linux cgroup enforcement, Kubernetes, PSI, OOM,
low VM memory or a workflow timeout.

The 3,297,214,464-byte (3.071 GiB) maximum is a **censored lower bound**. The
controller stopped the case at the first sampled violation, so this number is
not a completed-run peak and cannot size a limit. The evidence does not support
the claim that OCR alone used 3.071 GiB.

The offline replay verifies the 23-file manifest and immutable remote tar SHA-256
`7e5f1733622aa750784834742692acb126f9c7efe1076e9cf58f82ff8817c829`.
Requiring the captured trace to remain within the guard exits nonzero with
`RED_CGROUP_GUARD_REJECTED`.

## Three different resource controls

| Control | Evidence | Meaning in v3-b |
| --- | --- | --- |
| Qualification guard | `telemetry.check_sample` compares sampled `/sys/fs/cgroup/memory.current` with `capacity.json:max_cgroup_bytes`; v3-b used exactly 3 GiB | A fail-closed experiment stop rule chosen by the capacity owner |
| Runtime resource policy | The frozen profile and worker/parser budgets define work grouping, concurrency and deadlines, but set no memory allocation or cgroup limit | No 3 GiB production policy was found |
| Kernel/Kubernetes hard limit | Runtime precheck recorded `memory.max=max`, `memory.high=max`, `/proc/self/cgroup` as `0::/`; no Pod resource limit was exercised | No kernel limit rejected or throttled the workload |

The capacity field first existed as a required but value-free contract in
`8c28eb5`. The numerical 3 GiB value first appears in `9ca14a8`'s bounded Keynote
preflight. That plan explicitly calls it a conservative sampled experiment stop
rule, says it includes all processes/cache charged to the Pod, and says it is not
supported sizing or a kernel hard limit. Later ACL plans preserved that value;
they did not establish a production requirement.

## What the trace establishes

The fresh workflow began at 15:11:48.006 UTC. Fifteen active samples cover 7.036
seconds. Cgroup usage rose from 2,360,336,384 bytes (2.198 GiB) on the first active
sample to 3,297,214,464 bytes (3.071 GiB), a sampled increase of 936,878,080 bytes
(893.5 MiB). The preceding 60-second per-case interval peaked at 2,311,819,264
bytes (2.153 GiB).

The first violation was 3,227,963,392 bytes, 6.426 MiB above the ceiling. Its most
recent child progress was `RapidOcrModel`. The last and largest sample was 72.469
MiB above the ceiling and its most recent progress was `checkpoint_commit`.
These labels are progress boundaries: `WarmParser` stores the last message read
from the child, and `RapidOcrModel` is emitted from a `finally` block after that
wrapped stage. They do not identify which process or allocation owns the sampled
bytes at that instant.

VM available memory never fell below 8,533,536,768 bytes (7.947 GiB), full-memory
PSI avg10 stayed zero, VM and cgroup OOM-kill stayed zero, and the maximum sample
gap was 0.507 seconds. The failure is therefore specific to the harness ceiling.

## Measurement boundary

`telemetry.sample()` reads the current process's cgroup-v2 `memory.current`.
Process mode starts the qualification worker as a coordinator-container child;
the worker starts `WarmParser` as another child. All remain in the same container
cgroup. The metric consequently includes the worker, parser, controller and other
coordinator-container processes, plus file/page cache and kernel memory charged to
that cgroup. It is not worker RSS or parser RSS.

The retained samples have no per-PID RSS/PSS, `/proc/<pid>/smaps_rollup`, cgroup
`memory.stat`, `memory.peak`, fault counts or cgroup path/mount identity. The
remote archive contains no equivalent decomposition. The trace can correlate the
rise with parser progress, but cannot divide the rise among model tensors, Python
heaps, page images, page cache, native allocator retention or unrelated container
work.

## Ranked hypotheses

1. **Shared-scope cold-start demand exceeded a conservative qualification
   envelope.** Strongly supported. The shared cgroup gained at least 893.5 MiB
   after submission while VM pressure remained low, and the guard was never a
   hard limit. A decomposed trace should show the increase split between owned
   processes and cgroup-only charges.
2. **Parser/model/page processing accounts for a material part of the increase.**
   Supported only by timing. Parser PID 522 existed throughout the active rise,
   and progress reached OCR and checkpoint boundaries. Per-PID PSS/RSS and faults
   should rise with the cgroup if this is dominant.
3. **File/page cache or other cgroup charges account for a material part.** Open.
   `memory.stat` file/inactive-file/slab growth should explain a large residual if
   true.
4. **Other coordinator-container work contributes to the rise.** Open. A process
   tree plus PSS reconciliation should show a changing non-worker residual if true.
5. **Warm-parser lifecycle retention would make later cases exceed the same
   envelope.** Unmeasured. Fresh was stopped before completion and restored/replay
   never ran; only an uncensored lifecycle trace can test accumulation or release.

The evidence falsifies a VM-capacity, PSI or OOM explanation for this stop. It does
not identify a single allocating component, and it does not justify processing
changes.

## Decision boundary

Changing only the qualification ceiling would create a new authorized phase and
evidence identity; it would not change the producer, frozen method/profile or
reinterpret the old request. Adding external telemetry has the same compatibility
property when it does not alter producer bytes or work scheduling.

Changing parser lifecycle, model construction, grouping, OCR selection or the
frozen profile changes the producer and possibly the method fingerprint. That path
requires a new frozen bundle/baseline and fresh compatibility and reuse review.
Old requests must continue to resolve against their original profile rather than
being replayed as if created under the changed method.

Pod isolation is a separate topology claim. A Pod/cgroup result cannot be relabelled
as process-mode evidence or as proof of production sizing.
