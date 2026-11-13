# #113: decision latency of the allow-all provider against `authz_timeout`

[latency.py](latency.py) ran on 2026-11-13 on a Mac: PostgreSQL 17.10 in Docker Desktop, the
`kp-admission api` role (FastAPI on uvicorn) and the clients on the same machine. It times `check` and a full
`list_resources` page (1000 Resources) in process, which is admission's path, and through the
authz API, which is the other PEPs' path, one call at a time and 32 at once. The pool has 5
connections, as the `api` role's. The 32-at-once HTTP load comes from ApacheBench, because one
Python client process saturates first: with httpx it read p99 218 ms while `ab` read 8 ms.

```sh
.venv/bin/python docs/validation/113/latency.py
```

All 10 checks passed, the expected set of readings among them; the readings are in [evidence.json](evidence.json).

| Path | Calls at once | `check` p50 / p99 / max (ms) | `list_resources`, 1000 ids, p50 / p99 / max (ms) |
|---|---|---|---|
| In process | 1 | 0.20 / 0.28 / 0.42 | 0.35 / 0.40 / 0.47 |
| In process | 32 | 1.65 / 2.01 / 2.81 | 3.70 / 4.11 / 4.40 |
| HTTP (httpx) | 1 | 1.32 / 1.75 / 2.13 | 1.81 / 2.25 / 2.51 |
| HTTP (`ab`) | 32 | 7.01 / 19.97 / 30.18, 4365 calls/s | 10.61 / 23.10 / 23.57, 2884 calls/s |

Control: with `authz.resource` locked by another transaction, every `check` read `unavailable`
after 501.6 to 501.7 ms, so the measurement sees a lookup that outlasts the timeout.

## What this settles

- **`authz_timeout` stays 500 ms.** The slowest p99, a full page over HTTP with 32 calls at once,
  is 23 ms, about 21 times below it. The headroom covers what this machine does not have: the
  network between nodes, waits for a pool connection once the Batch API's transactions (#96)
  share the pool, and PROD hardware. A longer timeout costs time only while the database is
  failing, when admission is down anyway (§4.3); a shorter one turns a stall into
  `503 AUTHZ_UNAVAILABLE`.
- **FastAPI costs about 20% of the HTTP throughput.** Before the API moved from Starlette to
  FastAPI, for its OpenAPI document, the same script read a slowest p99 of 11 and 19 ms in two
  runs and 5464 checks per second at 32 at once. The PROD burst needs fewer than 2 per second.
- **These are not PROD numbers.** The in-cluster reading belongs to the SIT runs (#99, #137).
- **A PEP's own client timeout must exceed `authz_timeout`**, so that the API's `unavailable`
  reaches it before its own timeout does; the PEP treats its own timeout as `unavailable` (#127).
