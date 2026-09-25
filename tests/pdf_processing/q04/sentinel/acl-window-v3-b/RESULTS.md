# ACL fixture 09 process-mode window v3-b

**FAIL: fresh stopped at the unchanged 3 GiB cgroup guard; restored and exact
replay did not run.** Outer admission and per-case admission passed, but cgroup
usage crossed the active ceiling while the fresh parser was loading/executing
models. The authorized attempt stopped without retry or threshold change. It does
not provide ACL acceptance and does not complete Q04 or #51.

## Window and frozen identity

- Runner commit: `8e44d6f5a9414bcaefca34217e75cdfa43a2403c`
- Retained runtime source: `18be1b3fbcb929921ec986a1a0bf93e4be995b4d`
- Retained run ID: `q04-7b4f958ff3ac4e2da5b54dcaa66914b9`
- Retained object prefix: `q04/keynote-18be1b3-20260916-b/`
- Phase: `acl-window-v3-b`
- Reserved interval: 2026-09-17 15:09:45.145–15:34:45.145 UTC
- Outer admission passed and runtime began: 15:10:46.003 UTC
- Fresh workflow: 15:11:48.006–15:11:55.107 UTC
- First cgroup breach: 15:11:54.914 UTC
- Cleanup began: 15:11:57.436 UTC
- Evidence capture, health check and reservation release finished: 15:12:01.961 UTC
- Retry count: zero

The preflight matched the exact reviewed Pod/container/restart/start/boot/PID 1
identity. VM and cgroup OOM-kill counters were zero. Python 3.12.13, 112 packages,
17 model artifacts, restored producer, profile, bundle and frozen state matched.
All nine v3-b remote identities and the local output were absent. T09a Temporal
was healthy and idle, object readiness returned 200, and the 32 historical PDF
Deployments had the expected UIDs with `replicas=0`, `ready=0` and no matching
Pods.

Bundle SHA-256 remained
`b729891aa381ae25eef6ec2fbceefcdb43703d441762eafbb388627792833297`;
frozen state SHA-256 remained
`6f83b29e73357e6576643948f18f0be2d461ae7285e433f2c810c5f8d4aca5b7`.

## Admission and resource result

Outer admission passed 61 samples over 60.664 seconds with no reset:

| Measurement | Observed | Guard |
| --- | ---: | ---: |
| Minimum available memory | 9,683,513,344 B (9.018 GiB) | at least 4.5 GiB |
| Maximum cgroup usage | 2,178,662,400 B (2.029 GiB) | at most 3 GiB |
| Maximum full PSI avg10 | 0 | 0 |
| VM/cgroup OOM-kill | 0 / 0 | unchanged at 0 / 0 |

The fresh worker then passed per-case admission with 121 samples over 60.436
seconds:

| Measurement | Observed | Guard |
| --- | ---: | ---: |
| Minimum available memory | 9,530,527,744 B (8.876 GiB) | at least 3 GiB |
| Maximum cgroup usage | 2,311,819,264 B (2.153 GiB) | at most 3 GiB |
| Maximum full PSI avg10 | 0 | 0 |
| Maximum telemetry gap | 0.512 s | at most 3 s |
| VM/cgroup OOM-kill | 0 / 0 | unchanged at 0 / 0 |

After workflow submission, 15 active samples covered 7.036 seconds. The first
breach was 3,227,963,392 bytes during `RapidOcrModel`, 6.426 MiB above the
3,221,225,472-byte ceiling. Maximum cgroup usage was 3,297,214,464 bytes
(3.071 GiB), 72.469 MiB above the ceiling; the final sample identified parser
stage `checkpoint_commit`. Minimum VM available memory remained 8,533,536,768
bytes (7.947 GiB), full PSI stayed zero, maximum telemetry gap was 0.507 seconds,
and both OOM-kill counters stayed zero.

This is an active cgroup-budget rejection. It is not a VM capacity, PSI, OOM,
telemetry-loss or workflow-timeout result. The 3 GiB guard was not relaxed.

## Mode results and acceptance boundary

| Mode | Result | Evidence boundary |
| --- | --- | --- |
| Fresh | **FAIL** | One workflow started; `ValueError: cgroup budget exceeded`; no complete registration |
| Restored | Not run | Fresh failure was terminal for the no-retry window |
| Exact replay | Not run | No accepted fresh request existed to replay |

Fresh workflow
`q04-7b4f958ff3ac4e2da5b54dcaa66914b9-fresh-09-d9f88a98696b4e0abcd7e7e44ac03459`
was cancellation-requested and reached Temporal `COMPLETED`. Its application
result is failed: `processing_complete=false`, `canonical_accepted=false`,
`registered_pages=0`, `pages=3`, `steps=[]`, error category `infrastructure`,
code `activity_budget_exhausted`. Temporal `COMPLETED` records lifecycle only and
does not convert this into acceptance.

The six equations, equation 2 `TextItem`, complete graph, source evidence and OCR
oracles were not evaluated. No fresh, restored or replay graph/result pair exists
for comparison.

## Cleanup and final verification

All five fresh failure-cleanup outcomes succeeded: workflow cancel, result-task
settlement, worker stop, incomplete-publication audit and history capture. Worker
PID 489 stopped; parser PID 522 and scratch were absent; sampler errors were
empty. Phase cleanup and owner cleanup reported no error, orphan, Running
workflow, remaining owned cwd process or scratch. The incomplete request had no
complete publication.

The runner retained partial phase/history/resource evidence, verified the frozen
state hash, captured the remote tree and released the exact reservation. An
independent read-only check after release found the reservation PID dead, release
marker present, shared lock and v3-b driver lock unlocked, no owned process,
VM/cgroup OOM still zero, T09a healthy and idle, and object readiness 200.

All 32 historical Deployments remained closed. The before/after snapshots are
byte-identical with SHA-256
`d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4`;
the later independently formatted snapshot also confirmed every expected UID,
`replicas=0`, `ready=0` and no matching Pod. No scale or restore operation ran.

## Evidence boundary

Original evidence is retained at
`/private/tmp/q04-acl-window-20260917-v3-b`. The immutable remote capture is
`remote-evidence.tar`, 1,116,160 bytes, SHA-256
`7e5f1733622aa750784834742692acb126f9c7efe1076e9cf58f82ff8817c829`.
The 23-file private manifest has SHA-256
`98a2ef44c70a0c0dfbde77f781762c1b8f7931104353423ff2a597bbf91843f5`.
Sanitized facts and selected artifact hashes are recorded in
`evidence/summary.json`; raw samples, histories, profiles and environment details
remain outside Git.

The v3-b phase, paths, driver lock, reservation and local output are consumed and
must not be overwritten or reused. Historical v3-a evidence remains unchanged.
No production implementation or profile changed, and no issue was published or
closed.
