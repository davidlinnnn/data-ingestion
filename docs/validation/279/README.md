# #279: from a deletion or rebind to "not found" in the reference projection's query

[timing.py](timing.py) ran on 2026-11-24 on a Mac, with PostgreSQL 17.10 in Docker Desktop and the
platform API in process. The reader ran as its process does (`Projection.run`: a 1-second feed
poll, 4 workers and 1 narrowing worker), and the query app answered over ASGI for a user who may
read `s1/hr-all` only. 41 Documents were written and found. Then, one at a time, 20 were deleted
and 20 were rebound to `s1/legal`, and the query was repeated every 10 ms until it no longer found
the Document. Each reading runs from the commit of the call that appends the event to the first
answer without the Document. The last Document was never changed. It is the control, and it must
still be found.

```sh
.venv/bin/python docs/validation/279/timing.py
```

All 3 checks passed (each reading within 0 to 600 s; the control found). The readings are in [evidence.json](evidence.json).

| Event | p50 | max | min |
|---|---|---|---|
| `document_deleted` (20) | 1.016 s | 1.026 s | 0.97 s |
| `inclusion_changed`, rebind (20) | 1.002 s | 1.04 s | 0.996 s |

## What this settles

- **The reader's poll is the time.** After an empty read the reader waits 1 second
  (`poll_s`), so each event waits up to that long to be read; the run that removes the entry
  takes milliseconds and reports the removal in the same run. A shorter `poll_s` shortens it.
  Two earlier runs of the script on this branch read deletion maxima of 1.715 s and 1.689 s;
  the p50 stayed at 1.0 s.
- **The projection's share of `enforced`** (admission spec §8) is this plus the report, which
  goes in the same run; the platform then adds at most one `enforce` interval
  ([#98's reading](../98/README.md)).
- **No query-time check is involved** (ADR-0014): the query reads only the store.
- **These are not cluster numbers.** The rebind is the one #205 will record, fabricated here as
  in #127's tests. The SIT runs (#99) measure in the cluster.
