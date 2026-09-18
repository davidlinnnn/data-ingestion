# YOLO lifecycle candidate validation plan

This plan grants no runtime, K8s, publication or service-scaling authorization.
It fixes the scope for one separately authorized 1,500-second process-mode
fixture-07 window using the `q04-yolo-lifecycle-v1` candidate.

## Immutable setup

- Create a new phase, run ID, object prefix, state root, reservation and local
  evidence path. Never reuse `yolo-matrix-a` or `yolo-attribution-b` identities.
- Stage the candidate bundle whose `inputs.json` SHA-256 is
  `026884abc5f46f3cb94d213b0290d0693d3f5b4a5cb0bc022482e1fb1a3567c2` and
  producer-manifest SHA-256 is
  `dbfd558d1f9be7a0bd196af5a0fc61008b499370aee1f8e9d5b07f80ab926ce4`.
- At init, derive and retain a new profile release from the candidate producer
  and the new prefix's immutable original-source versions. Assert it differs
  from the frozen attribution-B release.
- Recheck coordinator/container/boot identity, VM and cgroup OOM counters,
  Temporal/object health, empty owned queues/prefixes and all 32 historical
  Deployments still at their expected UIDs with `replicas=ready=0`.

## Unchanged admission and guards

- Total window: 1,500 seconds; reserve the final 300 seconds for cleanup.
- Outer admission: observe at most 180 seconds and require 60 continuous seconds
  with at least 4.5 GiB available, PSI full avg10=0 and OOM unchanged.
- Preserve at least 825 seconds after outer admission for workload and case
  admission.
- Per-case admission: 60 seconds with at least 3 GiB available.
- Active guard: `memory.current <= 4,294,967,296`, available memory at least
  1.5 GiB, PSI full avg10=0, telemetry gap at most 3 seconds, and unchanged VM
  and cgroup OOM counters.
- Attribution collector: 250 ms target cadence, at most 1 second between
  attribution samples, complete process identity/PSS coverage, and no collector
  error. Use `candidate/yolo_candidate_measure.py` so `cancel_requested`
  surrounds the actual `q04_runtime.Run.cancel_owned` call; callback failure
  must not skip cleanup.

## Ordered workload

Run only fixture 07 in this order:

1. **Fresh.** Verify all 15 original pages, complete graph, six tables/60 cells,
   nine captions, source traversal, four required OCR registrations and fresh
   index. Verify the warm parser exits before fresh restore child birth, remains
   absent through that child's exit, and `memory.current` never crosses 4 GiB.
2. **Restored/new request.** Run only if fresh passes. Reuse the captured source
   object, require compatible group evidence, repeat every graph/oracle check and
   require full document equality with fresh.
3. **Exact replay.** Run only if restored passes. Reuse the exact restored
   request and require exact graph, registration and artifact identity without
   reinterpreting the request.

Any fresh failure ends the workload immediately. Any later failure also ends the
window. There is no automatic retry, threshold change, group-size change or
concurrency change.

## Required lifecycle and cleanup evidence

Retain synchronized samples for baseline, each group capture, warm handoff
requested/completed, fresh child birth/exit, publication, cancellation if any,
and post-cleanup. The candidate passes the lifecycle gate only if no sample has
both an owned warm parser and owned fresh parse child. Confirm the next capture
after a completed handoff can rebuild a new warm parser; restored/replay reuse
may legitimately avoid new parsing but must still preserve ownership facts.
If either the warm parser or fresh restore child cannot be reaped, require the
worker to remain draining and forbid any warm-parser rebuild.

On every exit, cancel and settle owned workflows, stop and reap the worker plus
all parser descendants, remove owned scratch, reject incomplete publication,
capture history and telemetry, release the reservation, and recheck health and
the unchanged 32-Deployment snapshot. A passed sentinel remains bounded fixture
07 evidence and does not close #51.
