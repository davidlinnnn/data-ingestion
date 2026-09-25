# ACL fixture 09 process-mode window

**ADMISSION REJECTED; no ACL workflow or inference ran.** The authorized outer
precondition required at least 4.5 GiB available memory with full PSI zero for 60
continuous seconds. The first sample was below the memory floor, so the runner
stopped without creating `acl-window-3` or submitting fresh, restored or replay.
This is retained failure evidence, not an ACL acceptance result and not completion
of Q04 or #51.

## Window and frozen identity

- Runtime source: `18be1b3fbcb929921ec986a1a0bf93e4be995b4d`
- Retained run ID: `q04-7b4f958ff3ac4e2da5b54dcaa66914b9`
- Retained object prefix: `q04/keynote-18be1b3-20260916-b/`
- Remote root: `/tmp/q04-keynote-18be1b3-20260916-b`
- Attempted phase: `acl-window-3`
- Reserved interval: 2026-09-16 15:33:12.600–15:53:12.600 UTC
- Admission rejection and cleanup finish: 2026-09-16 15:33:16.799 UTC
- Retry count: zero

Before reservation, the coordinator UID matched the accepted Keynote run. Python
3.12.13, the Linux platform, installed packages, 17 model artifacts, producer,
five-page method and frozen bundle all matched. The bundle hash remained
`b729891aa381ae25eef6ec2fbceefcdb43703d441762eafbb388627792833297`.
The frozen state hash was
`6f83b29e73357e6576643948f18f0be2d461ae7285e433f2c810c5f8d4aca5b7`
before and after the attempt. The accepted Keynote phase remained complete.

## Admission result

The immutable outer target was 4,831,838,208 bytes. The first sample observed:

| Measurement | Observed | Required |
| --- | ---: | ---: |
| Available memory | 4,827,791,360 B | at least 4,831,838,208 B |
| Full PSI avg10 | 0 | 0 |
| Coordinator cgroup | 1,201,098,752 B | at most 3,221,225,472 B |
| VM OOM counter | 28 | unchanged from 28 |
| cgroup OOM / OOM-kill | 0 / 0 | unchanged at zero |

Available memory missed the floor by 4,046,848 bytes, about 3.86 MiB. Because the
first sample failed, there is one admission sample rather than a 61-sample passing
series. The guard was not lowered and the runner did not wait for a more favorable
sample, retry, submit a workflow or create a worker.

## ACL acceptance boundary

The frozen fixture still identifies ACL Anthology source revision
`2024.findings-emnlp.317`, processed from original pages 2–4. Static precheck
confirmed the existing consumer gates for all six reviewed equations, equation 2
as an actual text item, representation uncertainty, exact typed page coverage,
captions, complete graph/source artifacts and selected-component OCR attribution.
None of those runtime gates were evaluated in this attempt because admission did
not pass. There is no fresh, restored or replay result to compare or accept.

## Cleanup and held services

Owner cleanup found no Q04 controller, new worker, parser, orphan, scratch or
Running workflow. It rechecked only the three already completed Keynote executions
and left them terminal. T09a Temporal was healthy and idle and object readiness
returned 200 after cleanup. The reservation was released.

The 32 historical Deployments remained main-owned and closed. All retained the
expected UID and `replicas=0` before and after; the snapshots are byte-identical
with SHA-256
`d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4`.
The runner performed no scale or restore operation.

## Evidence boundary

Original evidence is retained at `/private/tmp/q04-acl-window-20260916-c`. The
remote evidence capture is `remote-evidence.tar`, 378,880 bytes, SHA-256
`1b77b56841a69af9dcae61f7d58596ae65c018c04ade6ed5727fdf78eb2c4533`.
It includes the failed sample, approved capacity record, unchanged frozen config,
reservation, prior terminal workflow cleanup histories and cleanup report. Raw
profiles and histories remain outside Git; sanitized facts and private-artifact
hashes are recorded in `evidence/summary.json`.

The attempt's capacity, reservation and local output identities are consumed and
must not be overwritten. Any later ACL attempt requires a new authorization, phase,
capacity file and output location. No production implementation or profile changed,
and no issue was published or closed.
