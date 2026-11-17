# Verdict: all four guarantees hold on MongoDB 7.0 and 9.0, each under stated conditions

Measured 2026-11-16 on a local three-member replica set per major (7.0.48 and
9.0.8), PyMongo 4.20.0. A throwaway primary-source experiment; method and limits
in [README.md](README.md), every number in [evidence/RESULTS.md](evidence/RESULTS.md).
No guarantee failed in any committed run on either major. Each positive
control failed as designed, so the checks can see a failure.

| Guarantee | Verdict | Condition |
|---|---|---|
| 1. Change Feed skips no committed event | Holds, both approaches | Change stream: the oplog must still hold the reader's resume point. Sequence in the transaction: all feed writers serialize on one counter document, so a transaction must hold it for well under 80 ms to carry 12 events a second. |
| 2. An accepted request is dispatched and starts one workflow | Holds | The claim filters on the dispatch fields only; the start is idempotent by `request_id`. |
| 3. One active request per Document and Source Revision | Holds | Concurrent finalizes of one Document retry instead of queueing. |
| 4. A majority-acknowledged write survives primary failure | Holds | Writes stall for about one election timeout on primary loss, once twice that. |

## 1. Change Feed order

102,640 committed events per run (8 writers, 21 transactions held open 3 s,
5% rolled back), reader SIGKILLed halfway and resumed from its saved cursor:

| Approach | 7.0 missed | 9.0 missed | Duplicates | Retries mean / max |
|---|---:|---:|---:|---|
| Change stream, resume token | 0 | 0 | 0 | none |
| `$inc` sequence inside the transaction | 0 | 0 | 0 | 16.5–16.7 / 1,038–1,309 |
| Positive control: sequence outside the transaction | 17,245 | 19,395 | 0 | none |

At 12 transactions offered a second (8 writers on a fixed schedule, 5% rolled
back, three 3 s transactions), the same on both majors:

| Approach | Committed/s | Behind schedule p50 / p99 | Delay commit to delivery p50 / p99 | Retries mean / max |
|---|---:|---|---|---|
| Change stream | 11.05 | 4 ms / 0.28 s | 23 ms / 127–129 ms | none |
| Sequence, counter held about 100 ms | 7.1 | 76–101 s / 250 s | 12 ms / 25 ms | 16–17 / 1,622–2,035 |
| Sequence, counter held about 10 ms | 11.06 | 4 ms / 1.8 s | 12–13 ms / 26 ms | 3.8–4.1 / 569–730 |

- The change stream reports only majority-committed changes in commit order,
  which is why it does not skip: "Change streams only notify on data changes
  that have persisted to a majority of data-bearing members in the replica set"
  ([Change Streams](https://www.mongodb.com/docs/manual/changeStreams/)). Its
  limit is how far it can resume: "The oplog must have enough history to locate
  the operation associated with the token" (same page). The oplog is a size- or
  time-bounded window, not ADR-0009's 90-day feed, so a change stream cannot be
  the feed that projections page through; it can be what fills one.
- The in-transaction sequence does not skip because a second transaction cannot
  update the counter until the first one commits: commit order equals sequence
  order. Feed writers therefore commit one at a time. The 100k run took 33–35
  minutes against 4–4.5 for the change stream, and every 3 s transaction made
  the other writers retry, up to 2,035 times for one transaction. Its throughput
  is one over the time a transaction holds the counter: holding it about 100 ms
  (#55's sleeps) it committed 7.1 events a second against 12 offered and fell
  minutes behind; holding it about 10 ms it kept up. The sequence approach holds
  at 12 events a second only if the counter update is the transaction's last
  step, or nearly.
  ADR-0009's xmin wait is replaced by write conflicts and retries.
- Which one the port builds on is the port ticket's design choice; both hold.

## 2. Dispatcher claim without an outbox

1,000 requests, global in-flight budget 20, lease 5 s, on both majors:

- Every request started exactly one workflow and was marked dispatched, with 2
  and with 4 dispatchers.
- Each SIGKILL, after the claim and before the start or after the start and
  before the mark, left a request that another dispatcher re-claimed 5.0 s
  later, once the lease expired. The re-start after a crash between start and
  mark came back as a duplicate, counted as success.
- In-flight peaked at 21 with 2 dispatchers and 23 with 4: overshoot 1 and 3,
  exactly the allowed "dispatchers − 1", because the count and the claim are two
  operations.
- The claim must not filter on the request's state. The first version did, and
  stalled: a workflow finished before its crashed dispatcher marked it, the
  request left `queued`, and nothing ever marked it dispatched.

## 3. Finalize serialization

100 concurrent finalizes of one Document, a completer finishing requests meanwhile:

| Variant | Max active per revision (7.0 / 9.0) | Retries max | Slowest finalize |
|---|---|---|---|
| Document write + partial unique index, 1 content | 1 / 1 | 204 / 251 | 4.5 s / 4.7 s |
| Same, 3 contents | 1 / 1 | 177 / 691 | 5.8 s / 20.9 s |
| Positive control: neither | 32 / 23 | 1 | 0.06 s |

- A partial unique index with `$in` in its filter builds on both majors.
- MongoDB does not queue a writer behind a lock the way a PostgreSQL row lock
  does. A transaction whose document another write changed after it began
  "aborts because of a write conflict"
  ([Production Considerations](https://www.mongodb.com/docs/manual/core/transactions-production-consideration/)),
  and the application retries the whole transaction. A hundred simultaneous
  finalizes of one Document cost seconds of retries; the port should retry with
  backoff.
- The 9.0 three-content run stalled about 17 s at its start: even a finalize that
  committed at its first try took 17.4 s. Three reruns took 4–6 s. It followed
  the drop of a database just filled by experiments 2 and 4. Cause not found.

## 4. Acknowledged durability

10 rounds each of SIGKILL of the primary and of `rs.stepDown`:

| Fault | Acknowledged (7.0 / 9.0) | Missing | Write gap per round |
|---|---|---|---|
| SIGKILL | 226,685 / 103,868 | 0 | 10.0–11.1 s; one 7.0 round 21.0 s |
| stepDown | 132,587 / 202,563 | 0 | 0.01–0.38 s |

- A killed primary stops writes for about `electionTimeoutMillis` (default 10 s,
  [replica set configuration](https://www.mongodb.com/docs/manual/reference/replica-configuration/)),
  and the driver's transaction retry hides it: no write failed, they waited. The
  21 s round was two elections: the first, 10 s after the kill, did not elect a
  primary and the next succeeded 10 s later, so the documentation's "You can
  expect the failover timeout to not exceed the value of electionTimeoutMillis"
  did not hold once in ten.
- In a development run, a commit retried across a stepdown re-ran the
  transaction after the first attempt had committed, and the request insert
  failed with a duplicate key for its own `request_id` (15 of about 30,000). The
  port must treat its own `request_id` already present as success.

## For #137: confirm on the company's MongoDB

- Major version (7.0 or later, as tested), members and their placement.
- Transactions and change streams are allowed for the platform's user, including
  the `changeStream` and `find` privileges on the collections.
- The default write concern is majority; `electionTimeoutMillis`.
- The oplog's size and `oplogMinRetentionHours`: the longest feed-reader outage
  a change stream survives.
- Transaction limits: `transactionLifetimeLimitSeconds`, the lock wait.
