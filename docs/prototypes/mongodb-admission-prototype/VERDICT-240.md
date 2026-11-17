# Verdict (#240): a fenced tailer copies the change stream into a feed with nothing missed, repeated or out of order, under four conditions

Measured 2026-11-17 on a local three-member replica set, MongoDB 8.2.12 (the
company's major), PyMongo 4.20.0. Script `exp5_feed_tailer.py`, runs
`exp5_run.sh`, every number in [evidence/RESULTS.md](evidence/RESULTS.md)
(Experiment 5). A throwaway primary-source experiment for
[#240](https://github.com/davidlinnnn/data-ingestion/issues/240); the harness is
#236's ([README.md](README.md)).

**Holds, with conditions.** In two runs of 125,732 committed changes, one per
position scheme, each with seven faults (two SIGKILLs and two SIGSTOPs of the
lease holder, two SIGKILLs of the projection reader, one oplog loss), the feed
and the reader missed 0 changes, repeated 0 and put 0 out of commit order for
their Document. The two positive controls failed as designed. The conditions:

1. **Every feed write is fenced.** One transaction updates the lease document
   where `epoch` is the holder's, then inserts the entries. A takeover increments
   `epoch`. Each of the four woken holders was fenced and wrote nothing.
2. **The resume token is saved in that transaction**, so a crash can neither
   lose nor repeat a batch.
3. **Lost history is recovered from the records, not skipped.** The scan reads
   the revision records at one recorded cluster time, and the stream reopens at
   that time (below).
4. **The feed's delay is bounded by the lease, except when a holder freezes
   inside its feed transaction.** A takeover took 4.0–5.1 s with a 5 s lease in
   13 of 14 SIGKILLs and SIGSTOPs. One SIGSTOP froze the holder between its fence
   update and its commit. The takeover then waited 80.2 s, until the server
   aborted the open transaction ("Aborting transaction because it has been
   running for longer than 'transactionLifetimeLimitSeconds'", logged 80.07 s
   after the stop; the limit is 60 s here).

## Runs

| Run | Committed | Missed / repeated / out of order | Takeover (s) | Recovery |
|---|---:|---|---|---|
| Tailer's sequence, 7 faults | 125,732 | 0 / 0 / 0 | 3.97, 4.80, 4.38, 4.81 | 0.50 s, 10,641 backfilled |
| Derived position, 7 faults | 125,732 | 0 / 0 / 0 | 4.12, **80.16**, 4.65, 5.02 | 0.43 s, 6,615 backfilled |
| Control: no fence, 3 SIGSTOPs, sequence | 18,646 | 0 / **16 / 16** | 4.4–5.0 | - |
| Control: no fence, 3 SIGSTOPs, derived | 18,646 | 0 / 0 / 0 | 4.5–5.1 | - |
| Control: no recovery, sequence | 18,646 | **5,618** / 0 / 0 | - | stream reopened at now |
| Control: no recovery, derived | 18,646 | **2,318** / 0 / 0 | - | stream reopened at now |

- Writers: 8 processes, each on an absolute schedule of 20 transactions a
  second. 5% roll back and 21 transactions hold 3 s. 15% touch two or three
  Documents, so 15,414 committed transactions carried more than one change.
  Every change bumps a Document's revision counter and inserts a small revision
  record; the tailer watches only the revision records.
- The reader pages the feed by position with read concern majority, appends what
  it read, then saves its cursor. Its position never went backwards, and no page
  was read twice after a SIGKILL.
- Behind schedule, p99: 1.45–1.56 s over all transactions. The three writers
  that hold 3 s transactions fall behind their own schedule by design; the other
  five stayed within 0.05–0.06 s (p99).

At about 12 changes a second (11.64 achieved, #55's full sleeps, no fault), the
same for both position schemes:

| From commit to | p50 | p99 |
|---|---:|---:|
| feed entry written | 58–59 ms | 139–140 ms |
| read by the projection | 76 ms | 160 ms |

## Oplog loss and recovery

The oplog was resized to its minimum (990 MB; "The minimum size you can specify
is 990 megabytes",
[replSetResizeOplog](https://www.mongodb.com/docs/manual/reference/command/replsetresizeoplog/)).
Both tailers were SIGKILLed and filler was written until every member's oldest
oplog entry was newer than the time they stopped (1.9–3.3 GB in 36–58 s). Then
both restarted.

- Resuming from the saved token failed with code 286 (`ChangeStreamHistoryLost`):
  "Resume of change stream was not possible, as the resume point may no longer
  be in the oplog."
- Recovery: a fenced majority write on the lease gives the current cluster time
  `t_rec`. The tailer reads every revision record at `t_rec` (read concern
  `snapshot` with `atClusterTime`, paged by `_id`), inserts the ones the feed
  lacks, in Document and revision order and under the fence, saves `t_rec` as
  the resume point and reopens the stream at `t_rec`. Records committed by
  `t_rec` come from the scan, later ones from the stream.
- It took 0.43–0.50 s, scanning 67,818–71,862 records. The projection read the first
  backfilled entry 0.34–0.38 s and the last one 0.43–0.50 s after the tailer
  detected the loss. During that time it saw each Document's missed revisions in
  order, but not interleaved with other Documents in commit order. The feed gives
  no order across Documents.
- The scan works because every change is its own record: #57's revision record.
  Scanning only the Documents' current state would recover the last revision of
  each and lose the ones between.
- Without recovery the tailer did what Atlas Triggers do ("does not process any
  missed past events", quoted in #240) and resumed at the current time: every
  change committed during the outage was missing for good.

## Position: the tailer's own sequence

Both schemes held, and they cost the same. The sequence is the one to build on:

- **Neither is "free" of tailer state.** The documented event fields include no
  index within the transaction, and the manual does not say that
  resume tokens sort in event order. The derived position therefore had to be
  the event's cluster time plus an index the tailer counts and saves with the
  token, so that a stream resumed mid-transaction continues the count. All
  events of one transaction had one cluster time in every run.
- **Backfilled changes have no event.** After a recovery the derived scheme had
  to mint positions at `t_rec` itself; the sequence just continues.
- **The derived position does not remove the fence.** Without the fence, the
  woken holder's re-sent events got the same positions and were dropped as
  duplicate keys, which is why that control passed. That holds only while the
  woken holder is behind the new one. If it got ahead and both wrote, a reader
  could pass a position before the lower one became visible, and skip it.
- **A dense sequence lets a reader see a gap.** Positions are integers, one per
  change, so a missing number is visible. Cluster-time positions have no such
  property.

## For #239: what ADR-0009 and the port take from this

- The feed write: one transaction that updates the lease where `epoch` matches,
  setting the resume token and the last position, and inserts the batch. A
  takeover increments `epoch` and reads the token and position from the lease.
- The fence update locks the lease document until the commit. A holder frozen
  inside that window delays the takeover by up to `transactionLifetimeLimitSeconds`
  plus the server's abort sweep (80 s measured at the default 60 s). Moving the
  fence update to the last step narrows the window; a duplicate position before
  the fence must then count as fenced. That ordering was not measured.
- Save the post-batch resume token even when no event arrives, so a quiet
  revision collection does not fall off an oplog that other collections fill.
  The tailer here does so on each lease renewal; no run isolated it.
- The recovery flow above, run by the lease holder, and an alert on it: it means
  the tailer was down longer than the oplog window.
- The tailer watches only the revision records, as #57's handoff asks: an insert
  event carries the whole document.

## For #137: confirm on the company's MongoDB

- **Privileges:** `changeStream` and `find` on the revision collection;
  transactions; read concern `snapshot` with `atClusterTime`, for the recovery
  scan.
- **The oplog's size and `oplogMinRetentionHours`.** A tailer outage longer than
  the oplog window costs a recovery scan, not data, but the window decides how
  often that happens. The window is the oplog size divided by the replica set's
  whole write rate, every collection on it included. Measured here:

  | Per change in the oplog | Bytes |
  |---|---:|
  | Writer's transaction (counter + small revision record) | 508 |
  | Tailer's feed transaction (lease + feed entry): at 12 changes/s, at 90 changes/s | 620–685, 448–506 |
  | A document of 1 / 56 / 145 / 348 KB, inserted | 1,326 / 57,646 / 148,782 / 356,654 |

  | Case (#57 open) | 10,000 changes a day | 100,000 a day | Import of 10 million |
  |---|---:|---:|---:|
  | Content stored as objects: about 1.2 KB per change | 12 MB | 120 MB | 12 GB |
  | Content in MongoDB, written with each change: about 150 KB (median) | 1.5 GB | 15 GB | 1.5 TB |

  Ask for `oplogMinRetentionHours` of at least the longest tailer outage to ride
  out without a scan, and an oplog large enough to hold that many hours at peak
  writes. The default is 0: "By default MongoDB does not set a minimum oplog
  retention period"
  ([Replica Set Oplog](https://www.mongodb.com/docs/manual/core/replica-set-oplog/)).
- **`transactionLifetimeLimitSeconds`**: it bounds the worst takeover (condition
  4).
- **`minSnapshotHistoryWindowInSeconds`**: the recovery scan reads one snapshot,
  and "A read operation that lasts longer than `minSnapshotHistoryWindowInSeconds`
  may terminate"
  ([Read Concern "snapshot"](https://www.mongodb.com/docs/manual/reference/read-concern-snapshot/)).
  About 70,000 records took under 0.5 s here; ten million may not fit, in which case
  the scan needs another bound, such as an index on a commit-ordered field.
- **Monitoring:** tailer lag (now minus the cluster time of the last feed entry)
  and the oplog window (the time between its first and last entries) on every
  member.

## Limits

- One host, one clock. No primary failover ran while the tailer streamed; #236's
  experiment 4 covered acknowledged writes across one, not a stream across one.
- No SIGKILL landed inside a feed transaction. Whether a dead client's open
  transaction also holds the lease until it expires was not seen.
- The records are small. Content-sized documents in the feed's transactions were
  not run; the oplog sizes of large documents above are single inserts.
- Times are client-side.
- Truncation of the oplog follows checkpoints: 6 GB of filler written in 50 s
  left a 990 MB oplog untruncated until later writes came after a checkpoint.
  The filler therefore writes at a steady pace for up to 300 s.
