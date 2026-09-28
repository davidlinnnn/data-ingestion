# YOLO matrix A resource diagnosis

## Verdict

The matrix A attempt was correctly stopped by the fixed qualification guard after
assembly was scheduled while progress read `assembling`. The evidence does not identify
a production memory limit or a single allocating process. The sampled 4.039 GiB
maximum is the highest guard-censored observation. It was sampled after the
cancel request, so it neither bounds the counterfactual uncensored peak nor
defines a required ceiling.

The trace establishes that one warm parser handled the three capture groups and
that assembly was scheduled before the cgroup breach. The code configures that
warm parser to remain alive until worker cleanup and would use a separate fresh
child when assembly invokes `restore`, but the trace does not record Activity
start, fresh-child spawn, or simultaneous liveness. It contains the warm
parser's lifetime peak RSS, but lacks synchronized current RSS/PSS with complete
process coverage, `memory.stat`, the fresh-child PID and a post-cleanup cgroup
sample. The source of the assembly-period rise therefore remains unresolved.

The offline analyzer verifies all 23 private top-level artifact hashes and the
immutable archive SHA-256
`1300f24aea574e4c921e275f3dca6ba4354252e94da3a225f77d91d37a35ea94`.
The deterministic guard check exits nonzero with
`RED_CGROUP_GUARD_DURING_ASSEMBLY`; the attribution requirement independently
exits nonzero with `ATTRIBUTION_INCOMPLETE`.

## Reconstructed timeline

Temporal history, progress queries and the 207 worker samples establish this
sequence. Memory values are the nearest 0.5-second shared-cgroup sample, not
per-process readings.

| Boundary (UTC) | Nearest `memory.current` | Parser observation | Meaning |
| --- | ---: | --- | --- |
| Workflow start 13:39:08.181 | 2,504,400,896 B | count 0 | Per-case admission had completed |
| Pages 1–5 complete 13:39:24.395 | 3,520,454,656 B | count 1; next request already visible | First group registered |
| Pages 6–10 complete 13:39:38.037 | 3,556,569,088 B | count 2; next request already visible | Second group registered |
| Pages 11–15 complete 13:39:42.730 | 3,930,976,256 B | count 3; `checkpoint_commit` | Third group registered |
| Assembly scheduled 13:39:42.742 | 3,930,976,256 B | same count/request/stage | Fresh restore path is scheduled; warm observation stops changing |
| First breach 13:39:50.249 | 4,303,867,904 B | same stale observation | 8,900,608 B over the 4 GiB guard |
| Cancel requested 13:39:50.738 | preceding sample 4,303,867,904 B | same stale observation | Workflow cancellation requested; no retry |
| Sampled maximum 13:39:51.252 | 4,337,156,096 B | same stale observation | 42,188,800 B over guard; after cancel request |
| Cleanup starts 13:39:55.216 | no sample | n/a | Owned cleanup procedure begins |
| Cleanup finishes 13:39:57.690 | no sample | n/a | Owned cleanup reports no errors |

The worker log later recorded `Activity not found on completion` at 13:39:53.951,
evidence of a late Activity completion attempt after the workflow had already
closed. It does not identify the attempted Activity's internal stage. Temporal
lifecycle ended `COMPLETED`, while application delivery remained
incomplete and no consumer/oracle evaluation ran.

## `parser_count` and stage semantics

`parser_count=3` does **not** mean three parser processes. `worker.py` samples
`WarmParser.count`; `WarmParser.run()` increments that field after each completed
request and resets it only when the parser stops or recycles. All three accepted
group steps name the same warm parser PID 2327 and three different request IDs.

The `checkpoint_commit` label at the breach is also not the current assembly
stage. Samples copy `WarmParser.observation`. The final warm-parser request
completed at 13:39:42.625, before assembly was scheduled. In `Execution.child`,
only a parse request with `mode=capture` uses the warm child runner. Assembly
calls parse with `mode=restore`, which would take the fresh-child path. The
history only proves that assembly was scheduled; it does not show whether the
Activity began, how far materialization proceeded, or whether a fresh child was
spawned. The sampler repeats the last warm-parser observation throughout this
period.

This corrects two tempting but unsupported readings of the raw trace: the number
three is a completed-request counter, and `checkpoint_commit` cannot attribute
the breach to checkpoint writing.

## What assembly can overlap

The fixed code supports a concrete overlap mechanism:

1. The worker is configured to retain the warm parser after the third capture
   group until cleanup; no stop is recorded before assembly scheduling.
2. Assembly materializes each immutable group into a separate input directory,
   verifies its complete manifest, and copies every checkpoint JSON and PNG into
   a merged directory.
3. The restore child loads all 15 checkpoint records and their page images into
   `Page` objects, then constructs the full document and writes JSON/Markdown.
4. If restore invocation is reached while the configured warm parser is still
   alive, the group inputs, merged copy, restore result, warm parser and fresh
   child can coexist inside the same Activity temporary directory and
   coordinator cgroup.

These code paths make transient checkpoint/image/model and serialization overlap
plausible. They do not quantify it. The 42,188,800-byte overshoot is the point at
which the guard stopped observing, not the amount by which a complete run would
need a larger limit.

## ACL comparison and attribution boundary

The post-restart ACL fresh resource trace used the same coordinator container and
included a separate 250 ms PSS/`memory.stat` collector. It provides a useful
measurement-method comparison, not a fixture scaling formula.

| Observation | ACL fixture 09 | YOLO fixture 07 |
| --- | ---: | ---: |
| Initial/baseline cgroup | 2,248,318,976 B | 2,503,032,832 B (first worker sample) |
| Sampled cgroup maximum | 3,851,812,864 B | 4,337,156,096 B (guard-censored) |
| Cgroup after owned cleanup | 2,281,771,008 B | not sampled |
| Owned PSS at cgroup peak | 1,996,055,552 B | not sampled |
| Diagnostic residual at peak | 1,855,757,312 B | not computable |
| Parser maximum PSS | 1,345,460,224 B | not sampled |
| Other owned descendant maximum PSS | 603,068,416 B | not sampled |

ACL showed that the shared cgroup baseline was dominated by file/cache/kernel
charges rather than owned PSS, and that an assembly/other owned descendant could
be material. Its class maxima are not simultaneous and must not be summed. YOLO's
reported parser peak RSS of 2,076,100 KiB is a process lifetime high-water mark;
without synchronized PSS it cannot be subtracted from cgroup current or compared
as simultaneous ownership.

YOLO cleanup proved process, parser, scratch, workflow and publication absence,
but did not sample `memory.current` after cleanup. The trace therefore cannot say
how much memory/cache the run released. It also cannot divide the peak among the
configured warm parser, possible fresh child, worker/controller,
object-store/page cache, kernel charges or unrelated coordinator work.

## Ranked cause assessment

1. **Checkpoint/image materialization or full-document construction.** The code
   permits both after scheduling, but the trace has no Activity-start or
   operation markers. Prediction: new markers will locate the rise before or
   after restore-child spawn.
2. **Configured warm parser plus possible fresh assembly child.** Code permits
   this overlap, but neither warm-parser liveness nor fresh-child spawn is
   observed. Prediction: synchronized process identity and PSS will show whether
   both processes are resident during the rise.
3. **Shared cgroup baseline/cache contribution.** Supported by the earlier ACL
   decomposition, unmeasured in this run. Prediction: `memory.stat` plus the gap
   between cgroup current and synchronized owned PSS will remain material.
4. **Unrelated coordinator-process growth.** Open. Prediction: an identity-fenced
   full process tree will show changing PSS outside the owned controller/worker
   tree if this contributes.

The evidence rules out PSI, OOM, telemetry loss, VM memory floor and runtime
deadline as the stop reason. It does not support changing the producer, profile,
oracle, grouping, concurrency or cgroup guard.

## Decision

Do not raise the ceiling because this trace crossed it by 40.234 MiB. First run a
separately authorized, fresh-only attribution calibration with the current guard
and explicit fresh-child/process/cache telemetry. Use an isolated worker cgroup
only if the shared-cgroup residual remains ambiguous. Pod isolation belongs to the
separate drain topology and still requires owned Deployment, UID/label fencing,
shared paths, replacement readiness, CRI absence and emptyDir proof.

No runtime, workflow, reservation or Kubernetes mutation was performed during
this diagnosis. The retained final snapshot keeps all 32 historical Deployments
closed; their ownership remains with the main session.
