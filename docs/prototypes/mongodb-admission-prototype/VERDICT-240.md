# Verdict (#240): a fenced tailer copies the change stream into a feed with nothing missed, repeated or out of order, under four conditions

Measured 2026-11-17 on a local three-member replica set, MongoDB 8.2.12 (the
company's major), PyMongo 4.20.0. Script `exp5_feed_tailer.py`, runs
`exp5_run.sh`, every number in [evidence/RESULTS.md](evidence/RESULTS.md)
(Experiment 5). A throwaway primary-source experiment for
[#240](https://github.com/davidlinnnn/data-ingestion/issues/240); the harness is
#236's ([README.md](README.md)).

A side track. The December pilot runs on PostgreSQL as built, the outbox queue
and ADR-0009's feed included
([#78](https://github.com/davidlinnnn/data-ingestion/issues/78#issuecomment-6949497546)).
This verdict feeds the post-pilot port to MongoDB,
[#239](https://github.com/davidlinnnn/data-ingestion/issues/239), a gate for
PROD; it changes nothing the pilot builds.

**Holds, with conditions.** In three runs of 125,732 committed changes, one per
position scheme, each with seven faults (two SIGKILLs and two SIGSTOPs of the
lease holder, two SIGKILLs of the projection reader, one oplog loss; the third
run two in-transaction freezes more), the feed and the reader missed 0 changes,
repeated 0 and put 0 out of commit order for their Document. The two positive
controls failed as designed. The conditions:

1. **Every feed write is fenced.** One transaction inserts the entries and
   updates the lease document where `epoch` is the holder's. A takeover
   increments `epoch`. Each of the 17 woken holders was fenced and wrote nothing.
2. **The resume token is saved in that transaction**, so a crash can neither
   lose nor repeat a batch.
3. **Lost history is recovered from the records, not skipped.** The scan reads
   the revision records at one recorded cluster time, and the stream reopens at
   that time (below).
4. **The feed's delay is bounded by the lease only if a frozen holder's open
   transaction blocks nothing the new holder writes.** A holder frozen inside its
   feed transaction keeps that transaction's writes locked until the server
   aborts it ("Aborting transaction because it has been running for longer than
   'transactionLifetimeLimitSeconds'"; the limit is 60 s here, and the abort came
   60–88 s after the freeze). With the lease update first, the new holder cannot
   take the lease until then. With the lease update last but positions the new
   holder also computes, it takes the lease in 4–5 s and then conflicts on those
   positions until then. With the lease update last and the epoch in front of
   each position, a frozen holder held up nothing: the new holder's first entries
   were readable 4.1–5.1 s after each of five freezes, as after a SIGKILL.

## Runs

| Run | Committed | Missed / repeated / out of order | Takeover (s) | Recovery |
|---|---:|---|---|---|
| Sequence, lease update first, 7 faults | 125,732 | 0 / 0 / 0 | 4.00, 4.81, 4.39, 4.83 | 0.50 s, 10,641 backfilled |
| Derived, lease update first, 7 faults | 125,732 | 0 / 0 / 0 | 4.15, **80.16**, 4.66, 5.03 | 0.43 s, 6,615 backfilled |
| Sequence behind the epoch, lease update last, 7 faults and 2 freezes | 125,732 | 0 / 0 / 0 | 4.03, 4.77, 4.08, 4.67, 5.11, 5.06 | 0.45 s, 6,110 backfilled |
| 3 freezes, sequence, lease update first | 37,273 | 0 / 0 / 0 | **60.68, 80.69, 70.81** | - |
| 3 freezes, sequence, lease update last | 37,273 | 0 / 0 / 0 | **87.71, 77.66, 67.55** (lease after 4.2–4.7) | - |
| 3 freezes, sequence behind the epoch, lease update last | 37,273 | 0 / 0 / 0 | 4.77, 4.94, 4.23 | - |
| Control: no fence, 3 SIGSTOPs, sequence | 18,646 | 0 / **16 / 16** | 4.4–5.0 | - |
| Control: no fence, 3 SIGSTOPs, derived | 18,646 | 0 / 0 / 0 | 4.5–5.1 | - |
| Control: no recovery, sequence | 18,646 | **5,618** / 0 / 0 | - | stream reopened at now |
| Control: no recovery, derived | 18,646 | **2,318** / 0 / 0 | - | stream reopened at now |

- Takeover is the time from the fault to the reader's first entry from the new
  holder. A freeze is the holder stopping itself (SIGSTOP) inside its feed
  transaction right after the transaction's first write, staying stopped until the
  new holder's entries are in the feed, waking 2 s later.
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
same for the sequence and the derived position (the epoch in front was not run at this rate):

| From commit to | p50 | p99 |
|---|---:|---:|
| picked up by the tailer (batch formed; its commit follows) | 58–59 ms | 139–140 ms |
| read by the projection | 76 ms | 160 ms |

## Oplog loss and recovery

The oplog was resized to its minimum (990 MB; "The minimum size you can specify
is 990 megabytes",
[replSetResizeOplog](https://www.mongodb.com/docs/manual/reference/command/replsetresizeoplog/)).
Both tailers were SIGKILLed and filler was written until every member's oldest
oplog entry was newer than the time they stopped (1.7–3.3 GB in 33–58 s). Then
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
- It took 0.43–0.50 s in the three runs, scanning 67,328–71,862 records. The projection read the first
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

## Position: the tailer's own sequence, behind the lease epoch

All three schemes held, and they cost the same. A position is the epoch and then
the sequence, as fixed-width digits (`'%06d%012d' % (epoch, seq)`):

- **The epoch keeps a frozen holder from stalling the feed.** A new holder's
  positions never equal the ones a frozen holder has inserted but not committed,
  so the new holder does not wait for the server to abort them (condition 4).
  The positions still rise: an epoch only grows.
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
- **A dense sequence lets a reader see a gap.** The sequence part counts one per
  change across epochs, so a missing number is visible. Cluster-time positions
  have no such property.

## For #239: what ADR-0009 and the port take from this

- The feed write: one transaction that inserts the batch at positions behind
  the holder's epoch, then updates the lease where `epoch` matches, setting the
  resume token and the last sequence number. A duplicate position counts as
  fenced. A takeover increments `epoch` and reads the token and sequence from the
  lease.
- Either half alone does not help. Only the lease update last, measured three
  times, still stalled the feed 68–88 s per freeze; only the epoch in front, with
  the lease update first, still leaves the lease locked: the lease-first freezes
  waited 61–81 s for the lease itself.
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
- **`transactionLifetimeLimitSeconds`**: how long a frozen client's open
  transaction keeps its locks (60–88 s measured at 60). With the lease update
  last and the epoch in each position, it bounds the takeover only when a holder
  freezes in the round trip between its lease update and its commit.
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

- A holder frozen between its last write (the lease update) and its commit still
  locks the lease until the server aborts the transaction. That window is one
  round trip; no freeze was placed there.
- The derived position was not run with the lease update last; its positions are
  the same for both holders, so it would conflict as the sequence did.
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
