# ACL fixture 09 process-mode window v2-a

**OUTER ADMISSION REJECTED; no ACL workflow or inference ran.** The authorized
outer precondition required at least 4.5 GiB available memory with full PSI zero
for 60 continuous seconds, observed for at most 180 seconds. PSI stayed zero,
but none of the 179 samples reached the memory floor. The runner therefore did
not create the ACL phase or submit fresh, restored or replay. This is retained
failure evidence, not an ACL acceptance result and not completion of Q04 or
#51.

## Window and frozen identity

- Runtime source: `18be1b3fbcb929921ec986a1a0bf93e4be995b4d`
- Runner source: `fca98b9`
- Retained run ID: `q04-7b4f958ff3ac4e2da5b54dcaa66914b9`
- Retained object prefix: `q04/keynote-18be1b3-20260916-b/`
- Remote root: `/tmp/q04-keynote-18be1b3-20260916-b`
- Attempted phase: `acl-window-v2-a`
- Reserved interval: 2026-09-17 13:29:31.966–13:54:31.966 UTC
- Outer observation: 2026-09-17 13:29:32.168–13:32:32.151 UTC
- Cleanup and evidence capture finished: 2026-09-17 13:32:36.571 UTC
- Retry count: zero

Before reservation, the coordinator UID matched the accepted Keynote run. Python
3.12.13, the Linux platform, installed packages, 17 model artifacts, proposed
frozen producer, five-page method and frozen bundle matched. The coordinator's
`/app/pdf_processing` tree differed from the frozen producer and was not selected;
the retained `/tmp/q03-20260916-d/src/pdf_processing` producer had no differences.
The bundle hash remained
`b729891aa381ae25eef6ec2fbceefcdb43703d441762eafbb388627792833297`.
The frozen state hash was
`6f83b29e73357e6576643948f18f0be2d461ae7285e433f2c810c5f8d4aca5b7`
before and after the attempt. The accepted Keynote phase remained complete.

## Admission result

The outer memory target was 4,831,838,208 bytes. Admission sampled for the full
180-second observation budget and returned
`outer capacity observation deadline expired`.

| Measurement | Observed | Required |
| --- | ---: | ---: |
| Samples | 179 | up to 180 seconds |
| Available memory | 4,637,937,664–4,690,350,080 B (4.319–4.368 GiB) | at least 4,831,838,208 B |
| Samples meeting the outer pair of guards | 0 | 60 continuous seconds |
| Full PSI avg10 | 0 for every sample | 0 |
| Coordinator cgroup | 1,197,367,296–1,198,030,848 B | active guard at most 3,221,225,472 B |
| VM OOM counter | 28 throughout | unchanged from 28 |
| cgroup max / OOM-kill | 0 / 0 throughout | unchanged at zero |

Even at the highest-memory sample, the outer floor was missed by 141,488,128
bytes (about 134.9 MiB). Every sample reset the qualifying interval because of
available memory, not PSI. The 3 GiB/60-second per-case admission remained
configured correctly but was never reached. The 825-second workload budget was
not entered, and the final 300-second cleanup reserve was preserved.

## ACL acceptance boundary

The frozen fixture still identifies ACL Anthology source revision
`2024.findings-emnlp.317`, processed from original pages 2–4. The runner was
prepared to check all six reviewed equations, equation 2 as an actual text item,
complete graph/source artifacts and required OCR attribution for fresh, restored
and replay. None of those runtime gates were evaluated because outer admission
did not pass. No ACL phase directory or ACL log exists in the captured remote
evidence, and no ACL workflow, worker or inference process was created.

## Cleanup and held services

Owner cleanup found no Q04 controller, new worker, parser, orphan, scratch or
Running workflow. It rechecked only the three already completed Keynote
executions and left them terminal. T09a Temporal was healthy and idle and object
readiness returned 200 before the window and after cleanup. The reservation was
released while retaining the admission failure as the primary error.

The 32 historical Deployments remained main-owned and closed. All retained the
expected namespace/name/UID and `replicas=0`, `ready=0` before and after; the
snapshots are byte-identical with SHA-256
`d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4`.
The runner performed no scale or restore operation.

## Evidence boundary

Original evidence is retained without modification at
`/private/tmp/q04-acl-window-20260917-v2-a`. The remote evidence capture is
`remote-evidence.tar`, 552,960 bytes, SHA-256
`07887b36fb8e774096e72c5449e0cf133e339626b8efe0f5b36499303bdddc43`.
Within it, `admission-acl-window-v2-a.json` has SHA-256
`f4f31a30af441b5309c33f48f42e4e60dbfddb5cfb55562d55bb9a697a87a044`
and the immutable 179-sample series has SHA-256
`3a413949539f6c07e10138cbfc9941a7a29eecfc94cb222d001846760ec2bad3`.
Raw profiles, samples and histories remain outside Git; sanitized facts and
private-artifact hashes are recorded in `evidence/summary.json`.

The attempt's phase, capacity, reservation and local output identities are
consumed and must not be overwritten. Any later ACL attempt requires a new
authorization, phase, capacity file and output location. No production
implementation or profile changed, and no issue was published or closed.
