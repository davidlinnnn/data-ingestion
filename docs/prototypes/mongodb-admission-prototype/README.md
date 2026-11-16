# MongoDB admission guarantees prototype (#236)

Throwaway code that answers one question for
[#236](https://github.com/davidlinnnn/data-ingestion/issues/236): do the three
admission guarantees that rest on PostgreSQL mechanisms today, plus acknowledged
durability, hold on MongoDB? The answer is in [VERDICT.md](VERDICT.md); every
number is in [evidence/RESULTS.md](evidence/RESULTS.md).

## Setup

- MongoDB 7.0.48 and 9.0.8, the oldest supported and newest released majors on
  [MongoDB's lifecycle page](https://www.mongodb.com/legal/support-policy/lifecycles)
  on 2026-11-16 (7.0 ends 2027-08-31; 9.0 was released 2026-09).
- `rs.sh`: one container per major, three `mongod` processes on ports published
  1:1 (7.0 on 37071–37073, 9.0 on 37091–37093), replica set `rs0`, default
  settings (`electionTimeoutMillis` 10000, default write concern majority). The
  container's own disk, no tmpfs, so a killed member restarts on its data.
- PyMongo 4.20.0 under Python 3.12, through `uv run --with`. Docker 29.9.2 on
  macOS, 18 CPUs, 8 GiB for the Docker VM.

```sh
./rs.sh up 7 && ./rs.sh up 9
./run_version.sh 7 & ./run_version.sh 9 & wait   # about 70 minutes
python3 summarize.py                             # evidence/RESULTS.md, EXCLUDED.sha256
./rs.sh down 7 && ./rs.sh down 9
```

`./rs.sh up s` starts a third 9.0 set on 37061–37063 (`--major 6` in the
scripts) for developing a script while full runs hold the other two.

## Experiments

| Script | Ticket item | What runs |
|---|---|---|
| `exp1_feed_order.py` | 1. Change Feed order | #55's scenario (`part_a.py` of the [#55 validation](../../research/canonical-consumption-validation-2026-10-26/README.md)): 8 writer processes × 13,500 transactions, 5% rolled back, random sleeps at 0.1× of #55's, a 3 s transaction every 2,000 in three writers (21 in all). One reader process appends deliveries, then saves its cursor; it is SIGKILLed at half the events and restarted from the saved cursor. Modes `stream` (change stream, resume token), `seq` (`$inc` on a counter document inside the transaction), `control` (the same `$inc` outside the transaction: the positive control, expected to skip). Latency runs pace 8 writers at 1.5 transactions/s each (12 events/s) for 450 transactions, without a restart. |
| `exp2_dispatch.py` | 2. Dispatcher claim | 1,000 request documents carrying their dispatch fields; 2 or 4 dispatcher processes claim with one `find_one_and_update` that sets a 5 s lease, start a "workflow" (a collection keyed by `request_id`, standing in for Temporal's workflow ID with `REJECT_DUPLICATE`), then mark. A global in-flight budget of 20 is checked by a count before the claim. Dispatcher 0 is SIGKILLed after its 100th claim and before the start; dispatcher 1 after its 150th start and before the mark. |
| `exp3_finalize.py` | 3. Finalize serialization | 100 threads finalize one Document at once, over 1 or 3 contents. One transaction each: write the document, upsert the Source Revision, reuse an active request or insert one; a partial unique index over active process requests backs it. A completer finishes active requests meanwhile and a sampler reads all active requests in one snapshot. `control` drops the document write, the index and the upsert (positive control). |
| `exp4_durability.py` | 4. Acknowledged durability | 4 writers commit "document + request" transactions with `w: majority`; 10 rounds of SIGKILL of the primary (restarted after 15 s) and 10 rounds of `rs.stepDown(10)`. Every acknowledged request must be readable with read concern majority after all members are back. Write gap: the longest gap between acknowledgements in the round. |

## Limits

- One host. All members share a machine and a clock; no network partition, no
  disk loss and no node loss ran. The company's topology and settings are not
  known (#137).
- Delays and gaps are client-side: acknowledgement time stands in for commit
  time.
- Experiment 2 checks the global budget only. Per-Source budgets, fair rotation,
  backoff and the reconciler did not run.
- From 7.0's `seq` run on, the two majors' runs overlapped in time and shared
  the CPU (about 60% of it was idle); latencies and gaps may read slightly high.
- Experiment 3's sampler polls; a short-lived second active request between two
  samples would not be seen. The index makes one impossible, and the control
  shows the sampler sees them when they exist.

## Harness faults found and fixed during the runs

- The first background run was stopped with `pkill -f`, which missed the
  multiprocessing children; they kept writing into the next run's database. That
  run was discarded and experiment 1 now prefixes each run's events, counting
  strangers as `foreign_in_db` (0 in every committed run).
- The first stepdown runs used `rs.stepDown(60)`: half the rounds found no
  electable member and silently did nothing, and the 60 s gap windows overlapped
  across rounds. A round now must move the primary, waits out the 10 s stepdown,
  and its window ends at the next fault.
- With 4 dispatchers each made about 250 claims, so a crash set at the 300th
  never fired; it is at the 150th now.

## Not in git

`EXCLUDED.sha256` lists, with size and SHA-256, every raw record under
`evidence/` (writer and delivery logs, per-event dispatch logs, per-write
acknowledgements, the run logs): 161 MB. They are in the maintainer's offline
archive; `run_version.sh` regenerates them.
