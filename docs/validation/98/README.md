# #98: time to `applied` and `enforced` for Source Deletion

[timing.py](timing.py) ran on 2026-11-24 on a Mac, with PostgreSQL 17.10 in Docker Desktop and the
platform API in process. The pool had 5 connections, as the `api` role's does. 1001 accepted
Documents were each included by one serving Build of `retrieval`. The script deleted 500 of
them one call at a time and 500 more with 32 calls at once. The projection then reported 1000
of them removed, and one `kp-admission enforce` run judged them. The last Document's removal
was never reported. It is the control, and it must stay `applied`.

```sh
.venv/bin/python docs/validation/98/timing.py
```

All 4 checks passed. The readings are in [evidence.json](evidence.json).

| Stage | Reading | Target (spec §11) |
|---|---|---|
| `applied`, one call at a time | p50 1.55 ms, p99 2.52 ms, max 3.96 ms | 1 minute |
| `applied`, 32 calls at once | p50 17.7 ms, p99 33.5 ms, max 35.3 ms | 1 minute |
| Removal reports for 1000 Documents | 0.90 s (one facts call per 1000) | — |
| One `enforce` run over 1001 applied deletions | 0.77 s: 1000 `enforced`, 1 held | — |

## What this settles

- **`applied` is reached when the call returns.** The deletion is recorded in the call's own
  transaction (spec §5.8). The slowest of 1000 calls took 35 ms against the 1-minute target.
- **The platform adds at most one CronJob interval to `enforced`.** A deletion becomes
  `enforced` at the first `enforce` run after the last projection reports it removed. The
  recommended schedule is every minute, and one run judged 1001 deletions in 0.8 s. So the
  platform's share of the 10-minute target is the interval plus under a second per thousand
  deletions.
- **The projections' share is not measured.** It is the time a projection takes to read the
  `document_deleted` event, remove the content and report it, and no projection exists yet
  (#127). Until one does, the end-to-end `enforced` time against #56's cleanup limit is
  unmeasured.
- **Judgment pauses are not in these numbers.** No judgment runs while a Build lacks liveness, or
  after lost writes until the Builds are repaired (§8). `kp_admission_deletions_unenforced` counts
  such deletions by reason once they pass 10 minutes.
- **These are not PROD numbers.** The in-cluster readings belong to the SIT runs (#99).
