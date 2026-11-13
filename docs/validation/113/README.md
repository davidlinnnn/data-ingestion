# #113: decision latency of the allow-all provider against `authz_timeout`

[latency.py](latency.py) ran on 2026-11-13 on a Mac: PostgreSQL 17.10 in Docker Desktop, the
`kp-admission api` role and the clients on the same machine. It times `check` and a full
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
| In process | 1 | 0.21 / 0.29 / 0.39 | 0.35 / 0.40 / 0.44 |
| In process | 32 | 1.65 / 1.92 / 2.16 | 3.69 / 4.33 / 4.81 |
| HTTP (httpx) | 1 | 1.36 / 1.65 / 2.44 | 1.82 / 2.20 / 2.38 |
| HTTP (`ab`) | 32 | 5.80 / 7.24 / 11.57, 5464 calls/s | 9.48 / 10.83 / 12.91, 3347 calls/s |

Control: with `authz.resource` locked by another transaction, every `check` read `unavailable`
after 502.5 to 502.6 ms, so the measurement sees a lookup that outlasts the timeout.

## What this settles

- **`authz_timeout` stays 500 ms.** The slowest p99, a full page over HTTP with 32 calls at once,
  is 11 ms, about 46 times below it; an earlier run of the same script read 19 ms. The headroom covers what this machine does not have: the network
  between nodes, waits for a pool connection once the Batch API's transactions (#96) share the
  pool, and PROD hardware. A longer timeout costs time only while the database is failing, when
  admission is down anyway (§4.3); a shorter one turns a stall into `503 AUTHZ_UNAVAILABLE`.
- **These are not PROD numbers.** The in-cluster reading belongs to the SIT runs (#99, #137).
- **A PEP's own client timeout must exceed `authz_timeout`**, so that the API's `unavailable`
  reaches it before its own timeout does; the PEP treats its own timeout as `unavailable` (#127).
