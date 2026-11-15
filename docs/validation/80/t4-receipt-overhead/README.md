# #133 V9: receipt overhead

V9 (#129; #93 §9): one document with 30 VLM requests; the receipts add less
than 100 ms per request at p95. Over budget: batch the receipt writes.

Each request makes three object store calls on its attempt's receipts (`Sends` in
`src/kp_canonicalization/stages/enrich_vlm.py`): a listing of them for the request cap, then
`put_if_absent` before the send and `put` after it. V9 is checked in two parts, both in
`tests/stages/test_enrich_vlm.py`, on the in-memory store and on the S3 stand-in:

| Part | Test | Runs |
|---|---|---|
| Each request makes exactly those three calls, and the stage one more listing when it starts | `test_v9_each_request_lists_the_receipts_once_and_writes_its_own_twice` | every pull request (`code-checks`) |
| The three calls take more than 0 and less than 100 ms per request at p95 | `test_v9_receipts_add_under_100_ms_per_request_at_p95` | on request, with `KP_WALLCLOCK=1`; skipped otherwise |

The time is not asserted on pull requests because it measures the machine as much as the code
(#216). With the same code and the same calls, without a retry, the p95 of the two writes was
10 to 14 ms on a quiet machine and 144 to 417 ms on the same machine with every core busy; a
shared CI runner read 193.3 ms. The number of calls is what a code change can raise, and no
runner changes it.

Until 2026-11-15 the time counted the two writes and left the listing out. On the quiet
machine the listing took 6 ms at p50 and 10 ms at p95 (31 listings, 3 runs), about as long as
the two writes. With a 0.12 s sleep in `S3ObjectStore.list_prefix`, the old time read 20.0 ms
and passed (one run); the time of the three calls read 155.5 and 158.4 ms and failed.

The time is the duration of the three calls. `Sends.send` holds a lock over the listing and
the first write, so a request also waits for those two calls of the document's other requests;
that wait is not in the time.

## Run

On a machine with nothing else running. The heavy lock keeps other sessions' heavy jobs out:

```sh
docker compose -f tests/s3/compose.yaml up -d --wait
scripts/heavy-lock v9 -- env KP_WALLCLOCK=1 HF_HUB_OFFLINE=1 \
  KP_S3_ENDPOINT=http://127.0.0.1:9100 KP_S3_BUCKET=kp-dev \
  AWS_ACCESS_KEY_ID=kpdev AWS_SECRET_ACCESS_KEY=kpdev-secret \
  .venv/bin/pytest tests/stages/test_enrich_vlm.py -k v9 -s
```

It prints `V9 p95 receipt overhead <n> ms over 30 requests` for each store and fails unless
0 < p95 < 100 ms. The in-memory store's p95 is positive and prints as 0.0.

## When to run

- Before merging a pull request that changes the calls on the receipts (`Sends`) or the S3
  adapter (`src/kp_canonicalization/ports/object_store.py`). The reading goes into the pull
  request and into the table below.
- When the object store behind the adapter changes. Today it is the stand-in; #57 decides the
  real one, and the reading that counts is the one against it.

## Results

p95 over 30 requests, in ms.

| Date | Machine | Calls timed | In-memory store | S3 stand-in | Source |
|---|---|---|---|---|---|
| 2026-11-01 | dev machine | two writes | 0.0 | 16.5 | pull request #149 |
| 2026-11-13 | dev machine | two writes | 0.0 | 18.1 | #80, closing comment |
| 2026-11-14 | shared CI runner | two writes | not printed | 193.3 | `code-checks` run 43614736805, attempt 1 |
| 2026-11-15 | dev machine, quiet | two writes | 0.0 | 10.2 to 14.3 (10 runs) | #216 |
| 2026-11-15 | dev machine, 36 busy loops on 18 cores | two writes | not run | 144.4 to 416.9 (16 runs) | #216 |
| 2026-11-15 | dev machine, quiet | listing and two writes | 0.0 | 16.6 to 36.3 (20 runs, 19 of them at most 20.5) | #216, follow-up |
