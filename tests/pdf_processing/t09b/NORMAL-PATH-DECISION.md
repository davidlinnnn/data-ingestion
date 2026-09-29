# T09b normal-path decision

Three matched pairs completed in the declared A/B, B/A, A/B order:
A6→B2, B4→A7 and A11→B5. Every counted cell passed full output equality,
Temporal business completion, traffic reconciliation, telemetry and cleanup.

| Measure | A: group 5, serial | B: group 10, serial |
| --- | ---: | ---: |
| Counted runs | 3 | 3 |
| Controller runtime, median (range) | 526.83 s (524.75–536.74) | 517.67 s (495.88–520.27) |
| Whole-Pod peak, median (range) | 2,830,946,304 B (2,807,054,336–2,925,199,360) | 3,213,393,920 B (3,094,589,440–3,338,715,136) |
| Server RX, median (range) | 324,581,123 B (324,581,117–324,582,045) | 323,874,711 B (323,874,695–323,874,719) |
| Server TX, median (range) | 3,614,672,367 B (3,614,672,249–3,614,679,573) | 4,095,841,710 B (4,095,841,470–4,095,841,798) |
| Parser generations per run | 2 | 1 |

B's median controller runtime was 9.16 seconds (1.7%) lower, while its median
whole-Pod peak was 382,447,616 bytes higher and median server TX was 481,169,343
bytes higher. These are measured ranges from three runs, not an SLA or confidence
claim. Host/filesystem caches were uncontrolled.

The selected supported setting remains **group 5, one active parser child**.
The small runtime difference does not justify group 10's higher observed memory
and readback cost under the plan's rule to retain the existing configuration when
the tradeoff is unclear.

Two active parser children are not admitted. A single child already produced a
3,338,715,136-byte whole-Pod peak; the current 4 GiB sample guard has no reviewed
aggregate budget that proves two isolated children fit. Temporal concurrency alone
would also share the mutable converter. Serial support is retained without changing
the existing memory limits or acceptance thresholds.

Selection does not close #45. Selected-setting checkpoint/buffering inventory,
matched interruption recovery, and final affected-bound publication remain.
