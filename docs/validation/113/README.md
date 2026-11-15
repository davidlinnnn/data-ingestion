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
| In process | 1 | 0.21 / 0.28 / 0.35 | 0.35 / 0.42 / 0.44 |
| In process | 32 | 1.67 / 2.42 / 2.91 | 3.68 / 4.47 / 4.57 |
| HTTP (httpx) | 1 | 0.93 / 1.31 / 2.68 | 1.27 / 1.48 / 1.71 |
| HTTP (`ab`) | 32 | 6.83 / 17.54 / 23.74, 4565 calls/s | 10.39 / 22.12 / 23.07, 2963 calls/s |

Control: with `authz.resource` locked by another transaction, every `check` read `unavailable`
after 502.2 to 502.6 ms, so the measurement sees a lookup that outlasts the timeout.

## What this settles

- **`authz_timeout` stays 500 ms.** The slowest p99, a full page over HTTP with 32 calls at once,
  is 22 ms, about 23 times below it. The headroom covers what this machine does not have: the
  network between nodes, waits for a pool connection once the Batch API's transactions (#96)
  share the pool, and PROD hardware. A longer timeout costs time only while the database is
  failing, when admission is down anyway (§4.3); a shorter one turns a stall into
  `503 AUTHZ_UNAVAILABLE`.
- **FastAPI costs about 16% of the HTTP throughput.** Before the API moved from Starlette to
  FastAPI, for its OpenAPI document, the same script read a slowest p99 of 11 and 19 ms in two
  runs and 5464 checks per second at 32 at once, against 4565 now. The rate the read PEPs will
  ask for over HTTP is not specified yet (#76, #88). Admission's placement checks run in
  process: fewer than 2 per second at the PROD burst (#88).
- **These are not PROD numbers.** The in-cluster reading belongs to the SIT runs (#99, #137).
- **A PEP's own client timeout must exceed `authz_timeout`**, so that the API's `unavailable`
  reaches it before its own timeout does; the PEP treats its own timeout as `unavailable` (#127).

## A blocking call on the one worker

The `api` role runs one uvicorn worker per pod (admission spec §13). [blocking.py](blocking.py)
ran on 2026-11-13 on the same Mac: one uvicorn worker, 320 requests, 32 at once, each waiting
100 ms in one of three ways. All 4 checks passed; the readings are in
[blocking_evidence.json](blocking_evidence.json).

```sh
.venv/bin/python docs/validation/113/blocking.py
```

| The 100 ms wait | Requests per second | p99 (ms) |
|---|---|---|
| Awaited (`asyncio.sleep`) | 284 | 104 |
| Blocking, in a thread (`asyncio.to_thread`, 22 threads here) | 193 | 208 |
| Blocking, inline in the `async def` handler | 9.6 | 4155 |

A blocking call written inline serves one request at a time, and nothing else of that pod
answers meanwhile. That is the condition one worker per pod depends on, and the rule in
`CODING_STANDARDS.md` (Platform API).
