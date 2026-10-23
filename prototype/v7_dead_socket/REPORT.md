# V7 dead-socket deadline prototype — throwaway

Run date: 2026-10-23. **PASS for all three requested scenarios in this environment.** With httpx timeouts disabled, all nine attempts terminated in 5.002513–5.005062 seconds, below both the strict **deadline + 1 s = 6 s** acceptance threshold and the design goal of deadline + 5 s = 10 s. This is measured evidence for this client/backend and these local peers, rather than a universal cancellation guarantee.

## Environment and method

Python 3.11.15; macOS-26.4-arm64-arm-64bit; httpx 0.28.1, httpcore 1.0.9, anyio 4.12.1, h11 0.16.0. Exact dependency versions are in `requirements.txt` and `results.json`. Python 3.11 was selected explicitly because the default `python3` is 3.9.6. The venv was created with that interpreter using `-m venv .venv`. Packages were installed offline with pip `--no-index` from wheels reconstructed from already cached unpacked distributions; no downloads or external network calls occurred. All POSTs target ephemeral `127.0.0.1` TCP listeners; proxy/environment handling is disabled. No inference APIs, GitHub operations, commits, or pushes were used. Work completed within the 45-minute cap.

The requested `docs/design/knowledge-platform-processing-inference-capacity.md` is absent from this worktree. The V7 specification in the user prompt is the authority for this experiment; the absent document was not independently validated.

`servers.py` implements all three servers. A consumes the POST and sends nothing. B sends valid chunked HTTP/1.1 headers and a four-byte body fragment, then waits indefinitely for peer closure. C sends headers immediately and one-byte chunks every 10 seconds without a terminating chunk. Each handler records peer EOF and closes its server transport; no handler is cancelled to manufacture successful cleanup.

`harness.py` writes and fsyncs one JSONL receipt **before** starting each request, including item id, attempt, UTC timestamp, and `PRE_SEND`. It enriches that same line with timing and outcome using atomic file replacement, keeping one receipt per POST. Outcomes are therefore mutable receipt fields rather than separate appended JSONL events. There is no await between the pre-send receipt write and request scheduling. Curl and baseline controls are receipted too.

Each wrapped attempt owns a dedicated `httpx.AsyncClient`. The wrapper creates a request task, awaits `asyncio.wait_for(task, 5)`, explicitly cancels/drains it on expiry, and always awaits `client.aclose()`. The task awaits the **entire response body**, so a received header does not count as completion. Timings use `time.monotonic()` immediately before request task creation through completion of client closure; they exclude receipts, retry sleep, and later verification. This slightly overestimates send-to-termination time. Baseline timing starts in the child immediately before POST and includes parent SIGKILL/reaping overhead.

Each wrapped item has three attempts. The requested 0.5/1/2-second backoff schedule is applied after failures 1/2/3, including a final cooldown before recording `SERVICE_UNAVAILABLE`; there is no fourth request.

## Scenario reproduction with curl

Equivalent command per scenario: `curl --noproxy '*' --max-time 3 -sS -i -X POST --data '{}' http://127.0.0.1:<port>/infer`.

| Scenario | curl seconds | Exit | Observed response | Reproduced |
|---|---:|---:|---|---|
| A | 3.016415 | 28 | No response bytes | YES |
| B | 3.026012 | 28 | Valid 200 headers plus `part`, then no completion | YES |
| C | 3.024638 | 28 | Valid 200 headers; first body byte is scheduled after the 3-second cap | YES |

Full curl output is in `smoke.json`. C's three-second smoke cannot observe a ten-second drip; the 60-second baseline independently observed **5 body bytes** at offsets **[10.002, 20.005, 30.007, 40.009, 50.01] seconds** after acceptance. This confirms its continuing drip behavior and that it stays open, rather than merely acting like A or B.

## Matrix 1 — wrapper on, client timeouts off

Client: `httpx.AsyncClient(timeout=None, trust_env=False)`. Deadline: 5 seconds. All items ended `SERVICE_UNAVAILABLE` after three attempts.

| Scenario | Attempt | Seconds to termination | Outcome | Firing layer | ≤ 6 s |
|---|---:|---:|---|---|---|
| A | 1 | 5.003300 | DEADLINE_EXCEEDED | wrapper | PASS |
| A | 2 | 5.003750 | DEADLINE_EXCEEDED | wrapper | PASS |
| A | 3 | 5.004313 | DEADLINE_EXCEEDED | wrapper | PASS |
| B | 1 | 5.005062 | DEADLINE_EXCEEDED | wrapper | PASS |
| B | 2 | 5.003889 | DEADLINE_EXCEEDED | wrapper | PASS |
| B | 3 | 5.004160 | DEADLINE_EXCEEDED | wrapper | PASS |
| C | 1 | 5.003239 | DEADLINE_EXCEEDED | wrapper | PASS |
| C | 2 | 5.002513 | DEADLINE_EXCEEDED | wrapper | PASS |
| C | 3 | 5.004798 | DEADLINE_EXCEEDED | wrapper | PASS |

`checkpoint-matrix1.json` was written immediately after this matrix and before the baseline runs. Every request task was cancelled, every captured transport was closing, every underlying socket descriptor was `-1`, every client pool was empty, and all servers observed peer EOF. No pending tasks remained after each attempt.

## Matrix 2 — wrapper off, client timeouts off

One independent child process per scenario; no wrapper, client `timeout=None`. The parent observes the child through 60 seconds, records that it is still pending, then sends SIGKILL and reaps it. No extra baseline retries were run. B was omitted from this matrix as requested.

| Scenario | Attempt | Seconds to termination | Outcome | Firing layer | ≤ 6 s |
|---|---:|---:|---|---|---|
| A | 1 | 60.007155 | STILL_HANGING_AT_60S | outer_watchdog_SIGKILL | FAIL (baseline control) |
| C | 1 | 60.009654 | STILL_HANGING_AT_60S | outer_watchdog_SIGKILL | FAIL (baseline control) |

A was observed still hanging at 60.002648 s; C at 60.001848 s. Both exit codes were -9. Both server handlers observed peer EOF after process termination. These intentionally fail the 6-second deadline criterion and satisfy the ≥ 60-second baseline-control requirement. “Still hanging” is the observation at the cap; behavior beyond 60 seconds is UNKNOWN because the child was killed.

## Matrix 3 — wrapper on, client timeouts configured

Client timeout: `httpx.Timeout(connect=2, read=3, write=3, pool=2)`; wrapper deadline remains 5 seconds. All items ended `SERVICE_UNAVAILABLE` after three attempts.

| Scenario | Attempt | Seconds to termination | Outcome | Firing layer | ≤ 6 s |
|---|---:|---:|---|---|---|
| A | 1 | 3.007564 | ReadTimeout | client | PASS |
| A | 2 | 3.009753 | ReadTimeout | client | PASS |
| A | 3 | 3.008159 | ReadTimeout | client | PASS |
| B | 1 | 3.010636 | ReadTimeout | client | PASS |
| B | 2 | 3.011227 | ReadTimeout | client | PASS |
| B | 3 | 3.010743 | ReadTimeout | client | PASS |
| C | 1 | 3.012298 | ReadTimeout | client | PASS |
| C | 2 | 3.009799 | ReadTimeout | client | PASS |
| C | 3 | 3.010874 | ReadTimeout | client | PASS |

All nine failures were `httpx.ReadTimeout`; the client layer fired first. The task finished with a client exception rather than cancellation. Transport, socket, pool, peer EOF, and pending-task checks all passed.

## Per-scenario verdicts and accounting

| Scenario | Matrix 1: all 3 attempts ≤ 6 s | Matrix 3: all 3 attempts ≤ 6 s | Final item status (both wrapped matrices) |
|---|---|---|---|
| A | PASS; max 5.004313 s | PASS; max 3.009753 s | SERVICE_UNAVAILABLE |
| B | PASS; max 5.005062 s | PASS; max 3.011227 s | SERVICE_UNAVAILABLE |
| C | PASS; max 5.004798 s | PASS; max 3.012298 s | SERVICE_UNAVAILABLE |

- **23 receipt lines / 23 POSTs sent / 23 server accepts: MATCH.** This is 3 curl probes + 9 matrix-1 attempts + 2 baseline requests + 9 matrix-3 attempts. The two wrapped matrices alone contribute 18 receipt lines for 18 POSTs. All item/attempt pairs are unique; no unfinished `PRE_SEND` outcomes remain.
- All 18 wrapped attempts passed transport/socket/pool checks. The transport was **already closing before explicit `client.aclose()`** in every case, showing that httpx/httpcore cleaned it up during cancellation or client-timeout propagation in this environment. The wrapper still explicitly closes the owning client.
- All 23 server-side connections observed EOF and closed their transports. All listener servers were closed. The asyncio debug-mode runner asserted **zero pending tasks** and exited with code 0, with no task/resource warnings in `run.log`.

## Caveats and implementation implications

1. `asyncio.wait_for` requests cancellation and waits for cancellation to finish. It is not a hard process deadline if a coroutine suppresses cancellation, blocks the event loop, or hangs in cleanup. The tested httpx stack cooperated promptly; cancellation-resistant code and unbounded `aclose()` behavior are **UNKNOWN**, and this prototype does not establish a universal wall-clock guarantee for them.
2. A dedicated client per attempt gives the wrapper unambiguous ownership of its connection. Shared connection pools, HTTP/2 multiplexing, TLS, proxies, connect/write stalls, OS packet blackholes, alternate backends/platforms, and sustained-load behavior are **UNKNOWN**. The transport inspection uses pinned httpcore/anyio private attributes for evidence and should not become a production API dependency.
3. With the requested 10-second drip interval, the configured 3-second client read timeout fires before the first body byte; the 5-second wrapper also fires before the first byte when client timeouts are off. Thus C's continuing drip is proven by the baseline, but **defeating a read timeout that resets between chunks is not directly demonstrated by these parameter combinations**. A read timeout longer than 10 seconds with a total deadline spanning multiple chunks would be a separate experiment; its result is UNKNOWN here.
4. Cancellation and explicit transport closure are not isolated causal interventions in this run: cancellation already closed the connection before the explicit client close. What is proven is that the combined wrapper terminates and leaves no observed live connection for these cases. Baseline SIGKILL is an external control mechanism and is not part of layer 1.
5. Pre-send receipts are fsynced and later enriched; a crash can leave a `PRE_SEND` receipt whose remote completion is unknown. This is evidence for receipt ordering and count, not a production durable receipt store or retry-idempotency proof.

## Reproduce and inspect

From this directory, with Python 3.11+:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links wheels -r requirements.txt
.venv/bin/python -u harness.py > run.log 2>&1
```

The local `wheels/` and `.venv/` are intentionally ignored throwaway setup artifacts. A rerun overwrites receipts and evidence JSON; this report describes the recorded run, so regenerate its numbers if rerunning. Runtime is approximately four minutes. Inspect `results.json` for raw timings, versions, closure flags, and server drip timestamps; `receipts.jsonl` for per-POST receipts; `checkpoint-matrix1.json` for the mandatory checkpoint; `baseline.json`, `smoke.json`, and `run.log` for intermediate evidence. No production code was changed.
