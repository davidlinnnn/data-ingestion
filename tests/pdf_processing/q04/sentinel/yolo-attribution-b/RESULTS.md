# YOLO fixture 07 fresh-only resource attribution B

**FAIL acceptance; INCOMPLETE attribution contract; PASS bounded stop and
cleanup.** The one authorized fresh-only run passed outer and per-case
admission, then the unchanged 4 GiB shared-cgroup guard stopped the workload
during assembly. The 250 ms collector captured complete process and cgroup
samples around the peak, but the controller did not emit the required
`cancel_requested` callback marker. This run is therefore useful diagnostic
evidence, not a complete attribution measurement or a Q04 acceptance pass.

No retry, restored request or replay ran. The guard, frozen profile, source,
oracles and production code were unchanged. This result does not complete Q04
or close #51.

## Window and identity

- Reviewed runner commit: `1d72b0cc97c6f63f82b0e30703c17934ecb346ab`
- Phase: `yolo-attribution-b`
- Fixture: `07`, all original pages 1–15, fresh only
- Run ID: `q04-c084987e5c5047f0b9346ab1a26a1d66`
- Request ID: `q04-bf3908f27ef0482883726697d5931478`
- Workflow ID:
  `q04-c084987e5c5047f0b9346ab1a26a1d66-fresh-07-186e3614688f478e92f9ce1ed9c4eb53`
- Object prefix: `q04/yolo-attribution-20260918-b/`
- Reserved interval: 2026-09-18 23:11:01.253–23:36:01.253 UTC
- Evidence capture, cleanup and release finished: 2026-09-18 23:15:11.001 UTC
- Retry count: zero

Preflight matched coordinator Pod UID
`39c4bf45-45ae-4646-8d7b-ec47b2c61785`, container identity, restart count,
boot ID and PID 1 start ticks. VM and cgroup OOM-kill counters were zero. The
frozen bundle SHA-256 was
`9e46ad75379dffed05c5e25ec36b22fdf0d680e30e7d2b298d5ac355d0e039f2`;
the accepted source-state SHA-256 was
`2a3264316e0a859b2a490b3724af09c2df16959b35d9c8116b02e078f50f0636`.
All run identities and output locations were absent before ownership. Temporal
was healthy and idle, object readiness returned 200, and all 32 historical
Deployments had their expected UIDs with `replicas=0` and `ready=0`.

## Admission and workload result

Outer admission passed 143 samples over 143.546 seconds. After 28 resets, it
held the required qualifying interval for 60.654 continuous seconds. During the
full observation the minimum available memory was 8,837,328,896 bytes (8.230
GiB), maximum cgroup usage was 2,459,123,712 bytes (2.290 GiB), and all sampled
VM OOM-kill counters were zero. The qualifying interval met the unchanged
PSI=0 requirement.

The distinct per-case admission passed 121 samples over 60.376 seconds:

| Measurement | Observed | Guard |
| --- | ---: | ---: |
| Minimum available memory | 8,703,275,008 B (8.105 GiB) | at least 3 GiB |
| Maximum cgroup usage | 2,592,174,080 B (2.414 GiB) | at most 4 GiB |
| Maximum full PSI avg10 | 0 | 0 |
| Maximum sample gap | 0.507 s | at most 3 s |
| VM/cgroup OOM-kill | 0 / 0 | unchanged at 0 / 0 |

Fresh registered all 15 pages and reached `assembling`. It did not complete
processing, delivery or consumer-oracle evaluation. The first guard breach was
4,302,082,048 bytes, and the attributed peak was 4,581,400,576 bytes (4.267
GiB), 286,433,280 bytes (273.164 MiB) above the fixed 4 GiB ceiling. The
application failure was `ValueError: cgroup budget exceeded`. Temporal reached
`COMPLETED`, which records workflow lifecycle rather than application
acceptance. Fresh remained rejected; no fresh-index entry was created.

## Attribution and measurement boundary

The collector retained 379 samples at a 250 ms target interval. The maximum
sample gap was 0.264 seconds, no sample was incomplete, the peak sample was
complete, and the collector reported no error.

| Measurement | Baseline | Peak | Baseline-to-peak delta |
| --- | ---: | ---: | ---: |
| `memory.current` | 2,518,003,712 B | 4,581,400,576 B | +2,063,396,864 B |
| Owned process PSS | 78,239,744 B | 2,449,306,624 B | +2,371,066,880 B |
| All same-cgroup process PSS | 85,202,944 B | 2,455,813,120 B | +2,370,610,176 B |
| Diagnostic residual | 2,432,800,768 B | 2,125,587,456 B | -307,213,312 B |
| `memory.stat anon` | 73,166,848 B | 2,094,469,120 B | +2,021,302,272 B |
| `memory.stat file` | 2,371,465,216 B | 2,394,968,064 B | +23,502,848 B |

The increase is owned anonymous process memory. File-backed memory changed by
only 22.414 MiB and the diagnostic residual decreased by 292.981 MiB; cache or
unattributed shared-cgroup growth does not explain the breach. At the peak, the
two dominant owned processes were:

| Process class | PID | PSS |
| --- | ---: | ---: |
| warm parser | 2745 | 1,655,742,464 B (1.542 GiB) |
| fresh parse child | 2800 | 626,794,496 B (597.758 MiB) |

The retained Temporal history records cancellation requested at
23:15:01.249849 UTC. The attributed peak followed 2.396 seconds later, with both
processes still live; both exits were observed about 4.46 seconds after that
request. This supports a narrow implementation investigation into binding the
assembly fresh-child and warm-parser lifetimes to cancellation and preventing
their post-cancel overlap before changing any resource threshold.

The measurement contract still requires an ordered controller
`cancel_requested` callback marker. It observed the baseline, assembly,
cancel-outcome file and post-cleanup marker, but not that callback. Temporal
history and the successful cancel-outcome are retained as independent facts;
they are not substituted after the run to reinterpret the contract. The
attribution result therefore remains **incomplete** even though every collected
sample and the peak attribution are complete.

Any repeated measurement needs a reviewed runner that emits or observes the
controller cancel request when trial guard cancellation occurs before
`run.active` is cleared, a new identity and separate runtime authorization.
There is no automatic retry and no current authorization to run again.

## Cleanup and evidence

The workflow was terminal, worker and owned parser processes were absent, no
scratch or incomplete publication remained, and owner cleanup found no orphan,
unexpected active process or Running workflow. Temporal was healthy and idle,
object readiness remained 200, the source and live state were unchanged, and
the reservation was released. All 32 historical Deployments remained closed;
their before/after snapshots are byte-identical with SHA-256
`d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4`.

Original local evidence is retained at
`/private/tmp/q04-yolo-attribution-20260918-b`. The immutable remote capture is
`remote-evidence.tar`, 4,126,720 bytes, SHA-256
`4505366203e9824d8c8b312a8c7a8ebfd07e2fb2781b7aca5667515e34122062`.
Sanitized facts and hashes for every top-level private artifact are recorded in
`evidence/summary.json`; raw samples, logs, histories, profiles and environment
inventories remain outside Git.

The phase, run identity, prefix, local and remote paths and reservation are
consumed and must not be reused or overwritten. Historical trials remain
unchanged. No production implementation, frozen oracle, guard or capacity
threshold changed. No other fixture, restored/replay, warm, invalidation,
drain or Pod phase ran, and no issue was published or closed.
