# ACL fixture 09 post-Docker-restart window v3-a

**OUTER ADMISSION PASSED, BUT THE DRIVER FAILED BEFORE ACL workflow or
inference startup.** The authorized attempt stopped without retry. It provides
capacity and cleanup evidence only; it does not provide fresh, restored or exact
replay acceptance for fixture 09 and does not complete Q04 or #51.

## Window and frozen identity

- Runner commit: `3251c3eda00ee8c8d37de80838a6df35ca695613`
- Retained runtime source: `18be1b3fbcb929921ec986a1a0bf93e4be995b4d`
- Retained run ID: `q04-7b4f958ff3ac4e2da5b54dcaa66914b9`
- Retained object prefix: `q04/keynote-18be1b3-20260916-b/`
- Remote root: `/tmp/q04-keynote-18be1b3-20260916-b`
- Attempted phase: `acl-window-v3-a`
- Reserved interval: 2026-09-17 14:41:07.529–15:06:07.529 UTC
- Outer admission passed: 2026-09-17 14:42:08.430 UTC
- Driver failed and cleanup began: 2026-09-17 14:42:09.441 UTC
- Cleanup, evidence capture and reservation release finished: 2026-09-17
  14:42:14.141 UTC
- Retry count: zero

Before reservation, the exact post-restart Pod UID, container ID, restart count,
container start time, boot ID and PID 1 start ticks matched the reviewed baseline.
VM and cgroup OOM-kill counters were zero. Python 3.12.13, the Linux platform,
112 packages, 17 model artifacts, restored producer, frozen profile, bundle and
state all matched. The bundle SHA-256 remained
`b729891aa381ae25eef6ec2fbceefcdb43703d441762eafbb388627792833297`;
the frozen state SHA-256 remained
`6f83b29e73357e6576643948f18f0be2d461ae7285e433f2c810c5f8d4aca5b7`.

## Admission result

The unchanged outer admission target passed with no reset:

| Measurement | Observed | Required |
| --- | ---: | ---: |
| Samples | 61 | continuous 60 seconds, at most 180 seconds |
| Observed interval | 60.710 s | at least 60 s |
| Minimum available memory | 9,713,946,624 B (9.047 GiB) | at least 4,831,838,208 B (4.5 GiB) |
| Maximum full PSI avg10 | 0 | 0 |
| Maximum coordinator cgroup | 2,177,032,192 B (2.027 GiB) | active ceiling 3,221,225,472 B (3 GiB) |
| VM OOM-kill | 0 throughout | unchanged from 0 |
| cgroup OOM-kill | 0 throughout | unchanged from 0 |

The 3 GiB/60-second per-case admission and 825-second workload budget remained
configured, but no case reached them because the driver failed during its first
pre-runtime command. The 300-second cleanup reserve was not consumed.

## Driver failure and acceptance boundary

The first command in the runtime transport was the frozen bundle verification.
The generated nested shell command removed the Python string quotes around the
bundle path. Python received:

```text
verify_bundle(Path(/tmp/q04-keynote-18be1b3-20260916-b/inputs))
```

and exited with `SyntaxError: invalid decimal literal`. The transport returned 1
about one second after admission. The subsequent `q04_runtime.py --phase matrix
--fixture 09` command was never reached. No ACL controller, worker, workflow,
inference, result, accepted record, graph or oracle check was created. The three
workflows listed by cleanup are the already completed Keynote fixture 10
executions; they are not part of this attempt.

This is a runner command-rendering defect, not a capacity, PSI, OOM, parser,
fixture or oracle result. Fixing the quoting requires a reviewed runner change,
a new phase/output identity and separate runtime authorization. This consumed
identity must not be reused or overwritten.

## Cleanup and held services

Owner cleanup reported no controller, orphan, Running workflow, remaining owned
cwd process or scratch, and no cleanup error. The attempted phase directory is
absent and no phase-complete marker exists. The frozen state hash before and after
is identical. T09a Temporal was healthy and idle and object readiness returned
200 before the window and after cleanup.

All 32 historical Deployments retained the expected UIDs and stayed at
`replicas=0`, `ready=0`. Before and after snapshots are byte-identical with
SHA-256
`d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4`.
The runner performed no scale or restore operation.

An additional read-only final check after release found VM/cgroup OOM-kill still
zero, unchanged boot/PID identity and frozen state, no owned process, no phase
directory, a present release marker, a dead reservation PID and an unlocked
qualification lock. Cleanup is complete; the 32 Deployments remain main-owned and
closed.

## Evidence boundary

Original evidence is retained without modification at
`/private/tmp/q04-acl-window-20260917-v3-a`. The immutable remote capture is
`remote-evidence.tar`, 696,320 bytes, SHA-256
`802266c5a6ebd931615cd817ad41d64cf8445545ce482721ecc978d58a55776d`.
The extracted runtime error has SHA-256
`73aea4f630b9538de3891d562a8262cb24f71e342b5d0f074d1daa3ac9963bd6`.
Sanitized facts and private artifact hashes are recorded in
`evidence/summary.json`; raw samples, profiles, histories and environment details
remain outside Git.

No production implementation or frozen profile changed. No issue was published
or closed.
