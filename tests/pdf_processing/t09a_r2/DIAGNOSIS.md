# #44 resumed diagnosis — 2026-09-14

Baseline fast-forwarded from `863d2d1` to integration
`0b537d06476f0b547c8428b2e0bfda5f08dcfd3e` from a clean worktree. Historical
`t09a/` reports and seals remain unchanged. This directory is a separate round.

## Feedback loop and observations

`python3 tests/pdf_processing/t09a_r2/diagnose.py --assert-stable` replays the
retained kernel and Pod lifecycle trace. It fails on the three matched global OOM
events and container restarts. This is a deterministic, seconds-long historical
failure detector, not reproduction of a newly controlled capacity run. Deliberately
causing another node OOM is unnecessary and unsafe before capacity reconciliation.

The same-timestamp kernel process table accounts for about 2.48–2.53 GiB Python
RSS, 2.01–2.02 GiB MinIO RSS and 1.22–1.23 GiB Temporal RSS across the VM at the
three failures. These are process-name aggregates, not exclusive ownership or
additive physical-memory accounting (shared pages can be counted more than once).
Active plus inactive anonymous memory was roughly 7 GiB, file cache was small,
and the 1 GiB swap had only 68–160 KiB free. The exact target container and Pod
match `global_oom/CONSTRAINT_NONE`; this is not evidence of a 5 GiB cgroup breach.

At resumed admission, `/proc/meminfo` reports only 1.635 GiB MemAvailable.
Kubelet's availableBytes reports a larger value under a different accounting
definition; it cannot substitute for VM MemAvailable. No new inference is admitted.
The read-only inventory finds no Running executions on any of the 11 retained
Temporal services. This does not establish that future/dynamic clients are absent.
Capacity candidates and persistence safeguards are in
[capacity-candidates.json](evidence/capacity-candidates.json). Main must authorize
any action on other owners' workloads; namespaces/PVCs are never deletion candidates.

## Ranked falsifiable hypotheses

1. **Aggregate retained service load leaves inadequate VM headroom.** Predicts
   exhaustion while the target remains below its configured cgroup limit; after
   an explicitly coordinated capacity change, the unchanged native workload should
   complete with continuous monitoring and no global OOM. Historical aggregate
   evidence supports this contributor but does not isolate a sole cause.
2. **Overlapping warm parser and assembly/OCR processes cause transient peaks.**
   Predicts largest container usage during overlaps; process creation identities,
   stage timestamps and whole-Pod samples distinguish it from service-only load.
3. **Warm converter retains memory across requests.** Predicts a rising child
   baseline before planned recycle even within a controlled VM capacity window,
   followed by a drop after replacement. Historical OOM resets and missing tails
   prevent confirming or rejecting this hypothesis; do not call it a leak.

## Controlled admission and stop conditions

Keep group size 5, one Activity/parser slot, profile/model/native options, 5 GiB /
4 CPU limits, 256 MiB/100m requests, 2 GiB scratch and max_requests=20 unchanged.
Admission requires explicit remote quiescence, the shared flock, 60 seconds of
MemAvailable >=3 GiB, no new OOM events or pressure, and a small preflight. This is
an experimental admission gate, not a proven supported envelope.

Every run uses new immutable code/driver config names, queues, request IDs and
evidence paths. New workers must never poll the original request's queue. Monitor
child identities, application cgroup, separate whole-Pod memory, VM available memory,
scratch and restart counters. Loss of monitoring or resource failure stops the
sequence; hold flock through absence of owned Pods **and** running CRI containers.
No silent memory-limit/recycle changes or automatic heavy reruns.

The old drain Workflow naturally closed at 2026-09-13 15:29:04 UTC with Temporal
status COMPLETED but business status **failed**, category `infrastructure`, code
`activity_budget_exhausted`, 51 registered pages. It was not resumed or terminated
by this round. Preserve its exact request/producer/config and stored artifacts;
new request identities may exercise explicitly validated compatible reuse.
