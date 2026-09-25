# YOLO lifecycle resource decision

## Decision

The retained run remains **`FAIL_RESOURCE_GATE`** under the complete 250 ms
stream. The active 0.5-second guard missing the peak does not override the one
complete sample above 4 GiB.

The preferred next candidate is a fixture-window lifecycle change from
`parser_budgets.max_requests=20` to `1`. It is pending main approval, inactive,
and changes no production code. If that candidate still fails, move the
validation workload into a dedicated cgroup or separate Linux environment
under the same 4 GiB limit. Do not keep adding collectors or raise the limit.

## Peak attribution

All 397 samples are complete. Sample 322 is the only violation:

| Observation | Value |
| --- | ---: |
| `memory.current` | 4,403,523,584 bytes (4.101 GiB) |
| excess over 4 GiB | 108,556,288 bytes (103.527 MiB) |
| owned PSS | 2,201,500,672 bytes (2.050 GiB) |
| warm parser PSS | 2,020,127,744 bytes (1.881 GiB) |
| controller PSS | 98,876,416 bytes |
| worker PSS | 82,496,512 bytes |
| cgroup anon | 1,845,858,304 bytes |
| cgroup file | 2,461,163,520 bytes |
| cgroup inactive file | 2,449,694,720 bytes |
| cgroup kernel | 84,828,160 bytes |

The peak is inside group 3 at epoch `1789780955.0727022`. It has a warm parser
and no fresh parse child. PSI and every OOM counter are zero. The prior overlap
cause is therefore absent.

Only one sample is above the limit, so the data does not establish a positive
duration. The adjacent complete samples are below the limit at
`1789780954.8158236` and `1789780955.3298962`; the exceedance is bounded by
their 0.514073-second interval.

## Phase timeline

| Phase | PID | Recycles | Parser RSS high-water | Maximum `memory.current` |
| --- | ---: | ---: | ---: | ---: |
| group 1 | 3486 | 0 | 1,820,176 KiB | 4,109,717,504 bytes |
| group 2 | 3486 | 0 | 1,906,860 KiB | 4,280,303,616 bytes |
| group 3 | 3486 | 0 | 1,994,884 KiB | 4,403,523,584 bytes |

The same warm parser served all three requests with `restarts=1`, `recycles=0`,
and monotonically increasing high-water. After group 3, the warm parser was
reaped before the fresh assembly child: the handoff was observed and no sample
contains both processes. Assembly stayed below the limit; OCR and cleanup were
substantially lower.

The group-to-assembly transition spans 31 samples and peaks at 4,107,407,360
bytes at sample 331, immediately before the fresh child appears at sample 332.
`warm_handoff_observed` follows at sample 334. The four OCR intervals are also
fully covered:

| OCR component | Samples | Maximum `memory.current` | Maximum owned PSS |
| --- | ---: | ---: | ---: |
| `#/pictures/0` | 6 | 2,959,106,048 | 476,755,968 |
| `#/pictures/1` | 3 | 2,858,991,616 | 381,679,616 |
| `#/pictures/2` | 5 | 2,979,373,056 | 499,328,000 |
| `#/pictures/3` | 4 | 2,946,613,248 | 465,192,960 |

All four outcomes are `text_detected`. The complete machine timeline, including
workflow intent, merge, fresh-child birth, handoff, cancellation, owned cleanup,
and post-cleanup observations, is in
[`evidence/resource-peak.json`](evidence/resource-peak.json).

The pre-worker baseline was 2,564,382,720 bytes (2.388 GiB), including
2,446,516,224 bytes (2.278 GiB) inactive file. At the peak,
`memory.current` increased by 1,839,140,864 bytes and anon increased by
1,815,715,840 bytes, while file increased by only 3,211,264 bytes. The immediate
violation is thus the warm parser's third sequential request above a large,
stable shared baseline, rather than a new cache surge or warm/fresh overlap.

The final sample is index 396 and carries both `owned_cleanup_finished` and
`post_cleanup_sample`: `memory.current` is 2,681,995,264 bytes and owned PSS is
149,692,416 bytes.

## New gate

[`analyze_resource_peak.py`](analyze_resource_peak.py) applies one rule to every
sample, including post-run cleanup:

> Every attribution sample must be complete and `memory.current` must be at or
> below 4,294,967,296 bytes; the final sample must carry both
> `owned_cleanup_finished` and `post_cleanup_sample`.

The current run deterministically fails this gate at index 322. The offline
regressions reject incomplete samples, either missing final cleanup marker, an
early-only cleanup marker, and a single 250 ms violation even if the coarser
active guard did not see it.

The inactive resource candidate is in
[`../../candidate/yolo-resource-v1/`](../../candidate/yolo-resource-v1/). A
future approved run must use a new identity, preserve the no-overlap handoff,
pass graph/oracle and cleanup, and pass this all-sample gate. No new runtime is
authorized by this decision.
