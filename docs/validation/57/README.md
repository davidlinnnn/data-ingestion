# #57: Change Feed positions after a point-in-time restore

The design result of #57 ([§7.2](../../design/knowledge-platform-canonical-persistence.md)) says
that after the platform's database is restored to an earlier time T, new events take positions a
projection has already passed, so every projection's cursor must go back to T before the read side
reopens. That was derived from the code. [restore_feed_positions.py](restore_feed_positions.py)
measured it on 2026-11-23 on a Mac: PostgreSQL 17.10 in Docker Desktop (the test suite's image),
`kp_admission`'s own `schema.sql` and `feed` module.

```sh
uv run python docs/validation/57/restore_feed_positions.py
```

Each run: a base backup; three events, read and reported by a projection; a named restore point T;
events after T, read and reported too, which leaves the projection's cursor past T; recovery from
the backup and the archived WAL up to T on a new data directory; then new events. Between two
events, three transactions write to another table, before and after the restore alike. The third
run commits 120 such transactions before its first new event. Readings are in
[evidence.json](evidence.json).

| Run | Events lost after T | New events until the stale cursor is handed one | Of those, skipped | Positions naming both a lost and a new event |
|---|---|---|---|---|
| 1 | 5 | 5 | 4 | 0 |
| 2 | 40 | 40 | 39 | 0 |
| 3, counter offset by 120 | 40 | 11 | 10 | 10 |

Controls, in every run: before the restore, a read from the cursor at T returned exactly the events
appended after it (the harness sees new events); after the restore, a read from the cursor at T
returned every new event (the rewind works); a read from the feed's start returned only the three
events before T (the restore lost the rest). The script asserts the controls and that no read
raised; they are not fields of the evidence file.

## What this settles

- **Transaction IDs are handed out again.** In runs 1 and 2, where the workload after the restore
  repeats the one before it, the new events got the very IDs of the lost ones (`2f3`, `2f7`,
  `2fb`, …); in run 3 the same IDs came back 30 events later.
- **A stale cursor skips the new events, and nothing says so.** `feed.read` returned an empty page
  and raised nothing. Every new event at or before the stale cursor is never handed to it: 4 of 5
  and 39 of 40. A projection is handed events again only once the counter passes its cursor, that
  is, after about as many transactions as the restore lost.
- **A position does not name one event across a restore.** The sequence came back 30 ahead of its
  value at T (3 to 33; PostgreSQL logs sequence values ahead), so with the same workload no position
  repeated. With the counter offset by 120 transactions, 10 positions named a lost event and then a
  different new one.
- **The cursor report notices, for a while.** Reporting the stale cursor was refused (`ValueError:
  position ahead of the feed`, which the API answers `400`, `api.py`) until the counter passed it,
  then accepted. The read is never refused. In run 3 the report was accepted after 10 new events,
  all of them skipped: an accepted report does not mean nothing was missed.
- **The platform's own record of the cursor goes back by itself.** `consumer_cursor` held the
  position reported at T after the restore.

The rule of §7.2 stands: the cursors go back to T before the read side reopens. The refused report
cannot stand in for it. The report goes through the read side, which is closed while the write side
keeps running, so the counter can pass the stale cursor before any projection reports.

## Not measured

- MongoDB. #239's feed is not built; #240's position format (epoch and sequence) suggests the same
  question, which #239 answers.
- The HTTP layer: the calls went to `kp_admission.feed`; the `400` is read from the handler.
- A restore to the last archived WAL instead of a named point, and an instance shared with other
  databases. The mechanism is the same: recovery ends at an earlier WAL position.
- The size of the sequence's jump is what this PostgreSQL version did here, not a promise.
