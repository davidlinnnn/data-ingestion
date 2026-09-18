# YOLO fixture 07 process-mode matrix A

**FAIL acceptance; PASS bounded stop and cleanup.** Outer admission and per-case
admission passed. Fresh parsed all three five-page groups and reached assembly,
then the unchanged 4 GiB cgroup guard fired. Restored and exact replay did not
run. No retry or threshold change occurred, and this result does not complete
Q04 or #51.

## Window and reviewed identity

- Runner/preparation commit: `2c774b02164a4e130a9ffc8ec2cb6dff57c4e03c`
- Semantic runner commit: `6f16ec8`
- Operational launcher SHA-256:
  `c2937100736b61377ad1cd5b9230d6149e4946513fa3aff2afa72494d323ef18`
- Phase: `yolo-matrix-a`
- Fixture: `07`, all original pages 1–15
- Run ID: `q04-b4be645ae8374d03944fe1970a0ccfee`
- Object prefix: `q04/yolo-matrix-20260918-a/`
- Reserved interval: 2026-09-18 13:37:01.801–14:02:01.801 UTC
- Fresh workflow submitted: 2026-09-18 13:39:08.179 UTC
- First cgroup breach: 2026-09-18 13:39:50.249 UTC
- Evidence capture, cleanup and release finished: 2026-09-18 13:40:00.161 UTC
- Retry count: zero

The preflight matched coordinator Pod UID
`39c4bf45-45ae-4646-8d7b-ec47b2c61785`, container ID, restart count, start time,
boot ID and PID 1 start ticks. VM and cgroup OOM-kill counters were zero. Python
3.12.13, 112 packages and 17 model artifacts matched the retained frozen bundle.
The accepted source state, old ACL request binding, bundle, producer/profile
snapshot and all new path-absence claims passed before ownership. Temporal was
healthy and idle, object readiness returned 200, and all 32 historical
Deployments had the expected UIDs with `replicas=0` and `ready=0`.

The fixed bundle SHA-256 was
`9e46ad75379dffed05c5e25ec36b22fdf0d680e30e7d2b298d5ac355d0e039f2`;
the accepted source-state SHA-256 was
`2a3264316e0a859b2a490b3724af09c2df16959b35d9c8116b02e078f50f0636`.
The live-init state SHA-256 remained
`9b724b599fbc5fbcad74ce497cdd7187943b42d8c2b30ae73a9ac6745b862321`
through capture and cleanup.

## Admission and resource result

Outer admission passed 61 samples over 60.714 seconds with 60.693 continuous
seconds and no reset:

| Measurement | Observed | Guard |
| --- | ---: | ---: |
| Minimum available memory | 9,092,145,152 B (8.468 GiB) | at least 4.5 GiB |
| Maximum cgroup usage | 2,371,477,504 B (2.208 GiB) | at most 4 GiB |
| Maximum full PSI avg10 | 0 | 0 |
| VM OOM-kill | 0 | unchanged at 0 |

The worker then passed the distinct per-case admission over 121 samples and
60.420 seconds:

| Measurement | Observed | Guard |
| --- | ---: | ---: |
| Minimum available memory | 8,894,246,912 B (8.283 GiB) | at least 3 GiB |
| Maximum cgroup usage | 2,504,437,760 B (2.332 GiB) | at most 4 GiB |
| Maximum full PSI avg10 | 0 | 0 |
| Maximum telemetry gap | 0.508 s | at most 3 s |
| VM/cgroup OOM-kill | 0 / 0 | unchanged at 0 / 0 |

Across the full 207-sample worker trace, maximum cgroup usage reached
4,337,156,096 bytes (4.039 GiB), 42,188,800 bytes (40.234 MiB) above the fixed
4 GiB ceiling. The first breach was 4,303,867,904 bytes at parser stage
`checkpoint_commit`; by then all three parser groups were complete. Minimum
available memory remained 7,200,411,648 bytes (6.706 GiB), full PSI stayed zero,
the largest telemetry gap was 0.508 seconds, and all VM/cgroup memory-event
counters stayed zero. The parser's largest reported peak RSS was 2,076,100 KiB
(1.980 GiB).

This is a cgroup-budget rejection during assembly. It is not a VM memory-floor,
PSI, OOM, telemetry-loss or workflow-timeout result. The 4 GiB guard was not
relaxed.

## Mode and acceptance boundary

Fresh request `q04-4773c8eb0b4a4895b1128d2157e0c562` used source version
`a5c85498-0ad5-47c9-816c-6387ec579321`, SHA-256
`e6bda9784cfd83fd38c92a1162731aa1ec3413dbe1505946611595bfe59f29ab`.
Workflow
`q04-b4be645ae8374d03944fe1970a0ccfee-fresh-07-7e209242cfc24d1fbbd3ceca76d59df8`
reached Temporal `COMPLETED`, which records lifecycle only. Its application
attempt failed with `ValueError: cgroup budget exceeded`.

The retained final progress record had `status=assembling`,
`processing_complete=false`, `canonical_accepted=false`, 15 pages and 15
partially registered pages. The three group durations were 16.057, 13.620 and
4.674 seconds. No complete delivery or consumer result exists.

| Mode | Result | Evidence boundary |
| --- | --- | --- |
| Fresh | **FAIL** | Fixed cgroup guard fired during assembly; no complete registration |
| Restored/new request | Not run | Fresh failure was terminal for the no-retry window |
| Exact replay | Not run | No accepted fresh request existed to replay |

Because fresh never reached the consumer, the six-table/60-cell oracle, nine
captions, complete typed graph and source traversal, four required OCR
registrations, restored equality and exact replay identity were not evaluated.
No fixture-07 fresh-index entry was integrated.

## Cleanup and retained state

All five fresh cleanup outcomes succeeded: workflow cancel, result-task
settlement, worker stop, incomplete-publication audit and history capture. Worker
PID 2294 was absent; parser and scratch were absent; sampler errors were empty.
Owner cleanup found no orphan, unexpected active process, Running workflow or
remaining current scratch. The incomplete request had no forbidden complete
publication. The current workflow was terminal, Temporal remained healthy and
idle, object readiness remained 200, and the exact reservation was released.

All 32 historical Deployments remained closed and were not restored. Their
before/after snapshots are byte-identical with SHA-256
`d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4`.
The accepted source state and the new live-init state both remained unchanged.

## Evidence boundary

Original evidence is retained at
`/private/tmp/q04-yolo-matrix-20260918-a`. The immutable remote capture is
`remote-evidence.tar`, 716,800 bytes, SHA-256
`1300f24aea574e4c921e275f3dca6ba4354252e94da3a225f77d91d37a35ea94`.
Sanitized facts and hashes for every top-level private artifact are recorded in
`evidence/summary.json`; raw samples, progress, histories, profiles and
environment inventories remain outside Git.

The phase, run identity, prefix, local/remote paths and reservation are consumed
and must not be reused or overwritten. Historical trials remain unchanged. No
production implementation, frozen oracle or capacity threshold changed. No
other fixture, warm/invalidation/resource/drain/Pod phase ran, and no issue was
published or closed.
