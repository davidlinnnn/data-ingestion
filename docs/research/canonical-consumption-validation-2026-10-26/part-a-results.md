# Part A — PostgreSQL cursor experiment

Status: COMPLETE (an observed failure remains a finding).

8 writer processes × 400 transactions = 3,200 attempted transactions per run; 5% randomized rollback, three 3-second transactions; two live consumers poll every 20 ms, batch 100. Delivery delay uses PostgreSQL commit timestamps (not insertion time).

| Seed | Committed | A missed | A duplicated | B missed | B duplicated | B max delay (s) |
|---|---:|---:|---:|---:|---:|---:|
| 5501 | 3017 | 279 | 0 | 0 | 0 | 3.023658 |
| 5502 | 3035 | 276 | 0 | 0 | 0 | 2.994735 |
| 5503 | 3053 | 297 | 0 | 0 | 0 | 2.942187 |

## Long transactions

- Seed 5501: 384 commits occurred while a 3-second transaction was open; maximum B delay for these = 3.023658s, other commits = 0.227170s; long transaction rollbacks = 0.
- Seed 5502: 397 commits occurred while a 3-second transaction was open; maximum B delay for these = 2.994735s, other commits = 0.244223s; long transaction rollbacks = 0.
- Seed 5503: 401 commits occurred while a 3-second transaction was open; maximum B delay for these = 2.942187s, other commits = 0.216780s; long transaction rollbacks = 0.

Long-lived transactions hold back xmin, so newer committed rows wait until that horizon advances. The observed tail latency is a consequence of the ordering policy. The delays for other commits can also include ordinary xmin waits and polling/backlog drain.

Raw evidence: `part-a-run-<seed>.json` contains every attempted transaction, every committed row, every delivered row and every poll. Seeds reproduce random sleep/rollback choices; OS scheduling remains nondeterministic.

PostgreSQL: `PostgreSQL 18.4 (Debian 18.4-1.pgdg13+1) on aarch64-unknown-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit`

Errors: `[[], [], []]`
