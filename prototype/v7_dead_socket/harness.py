"""THROWAWAY V7 evidence runner. Run with .venv/bin/python harness.py."""
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
from datetime import datetime, timezone

import httpx
from servers import Servers

ROOT = Path(__file__).resolve().parent
DEADLINE = 5
BACKOFF = (0.5, 1, 2)
RECEIPTS = ROOT / "receipts.jsonl"


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def receipt_start(item, attempt):
    receipt = {"item_id": item, "attempt": attempt,
               "timestamp": datetime.now(timezone.utc).isoformat(), "outcome": "PRE_SEND"}
    with RECEIPTS.open("a") as f:
        f.write(json.dumps(receipt) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return receipt


def receipt_finish(receipt, result):
    # Enrich the same logical receipt, preserving one line per outbound POST.
    receipt.update(result)
    lines = [json.loads(line) for line in RECEIPTS.read_text().splitlines()]
    for i, row in enumerate(lines):
        if (row["item_id"], row["attempt"]) == (receipt["item_id"], receipt["attempt"]):
            lines[i] = receipt
            break
    temp = ROOT / "receipts.tmp"
    with temp.open("w") as f:
        f.write("".join(json.dumps(row) + "\n" for row in lines))
        f.flush()
        os.fsync(f.fileno())
    temp.replace(RECEIPTS)


async def kill_wrapper(request, deadline, item, attempt, timeout):
    receipt = receipt_start(item, attempt)
    transports = []
    streams = []

    async def trace(event, info):
        if event == "connection.connect_tcp.complete":
            stream = info["return_value"]
            streams.append(stream)
            # Instrumentation only: pinned httpcore/anyio asyncio backend internals.
            transports.append(stream._stream._transport)

    client = httpx.AsyncClient(timeout=timeout, trust_env=False)
    started = time.monotonic()
    task = asyncio.create_task(request(client, trace))
    try:
        await asyncio.wait_for(task, deadline)
        outcome, layer = "COMPLETED", "none"
    except TimeoutError:
        outcome, layer = "DEADLINE_EXCEEDED", "wrapper"
        task.cancel()  # wait_for already delivered cancellation and awaited it.
        await asyncio.gather(task, return_exceptions=True)
    except httpx.TimeoutException as exc:
        outcome, layer = type(exc).__name__, "client"
    finally:
        closed_after_request = bool(transports) and all(t.is_closing() for t in transports)
        # A dedicated client owns exactly this attempt; closing it cannot harm others.
        await client.aclose()
    elapsed = time.monotonic() - started
    assert task.done()
    assert transports and all(t.is_closing() for t in transports)
    assert all(s.get_extra_info("socket").fileno() == -1 for s in streams)
    assert client.is_closed and not client._transport._pool.connections
    result = {"killed_at_seconds": elapsed, "outcome": outcome, "firing_layer": layer,
              "task_cancelled": task.cancelled(), "transport_closed": True,
              "socket_fd_closed": True, "pool_empty": True,
              "closed_before_explicit_aclose": closed_after_request,
              "within_deadline_plus_1": elapsed <= deadline + 1}
    receipt_finish(receipt, result)
    return result


async def matrix(servers, name, timeout):
    rows, items = [], {}
    for scenario in "ABC":
        item = f"{name}-{scenario}"
        for attempt in range(1, 4):
            async def request(client, trace):
                return await client.post(servers.url(scenario), content=b"{}",
                                         extensions={"trace": trace})
            result = await kill_wrapper(request, DEADLINE, item, attempt, timeout)
            rows.append({"scenario": scenario, "attempt": attempt, **result})
            await servers.settled()
            assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
            print(name, scenario, attempt, round(result["killed_at_seconds"], 3), result["firing_layer"], flush=True)
            # Interpret the requested 0.5/1/2 schedule as a cooldown after each
            # failed attempt, including the final one before marking unavailable.
            await asyncio.sleep(BACKOFF[attempt - 1])
        items[scenario] = "SERVICE_UNAVAILABLE"
    return {"rows": rows, "items": items}


async def smoke(servers):
    rows = []
    for scenario in "ABC":
        receipt = receipt_start(f"curl-{scenario}", 1)
        started = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            "curl", "--noproxy", "*", "--max-time", "3", "-sS", "-i",
            "-X", "POST", "--data", "{}", servers.url(scenario),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        result = {"scenario": scenario, "killed_at_seconds": time.monotonic() - started,
                  "outcome": f"curl_exit_{proc.returncode}", "firing_layer": "curl_max_time",
                  "stdout": stdout.decode(), "stderr": stderr.decode()}
        assert proc.returncode == 28
        assert (not stdout) if scenario == "A" else b"HTTP/1.1 200 OK" in stdout
        if scenario == "B":
            assert stdout.endswith(b"part")
        receipt_finish(receipt, result)
        rows.append(result)
        await servers.settled()
    return rows


async def baseline(servers):
    rows = []
    for scenario in "AC":
        receipt = receipt_start(f"baseline-{scenario}", 1)
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(Path(__file__).resolve()), "--baseline-child", servers.url(scenario),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        start_message = json.loads(await proc.stdout.readline())
        started = start_message["send_monotonic"]
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), max(0, 60 - (time.monotonic() - started)))
            outcome, layer = "TERMINATED_EARLY", "client_or_error"
        except TimeoutError:
            hanging = proc.returncode is None
            assert hanging
            observed = time.monotonic() - started
            proc.kill()
            stdout, stderr = await proc.communicate()
            outcome, layer = "STILL_HANGING_AT_60S", "outer_watchdog_SIGKILL"
        result = {"scenario": scenario, "attempt": 1, "killed_at_seconds": time.monotonic() - started,
                  "outcome": outcome, "firing_layer": layer, "exit_code": proc.returncode,
                  "stdout": stdout.decode(), "stderr": stderr.decode()}
        if outcome == "STILL_HANGING_AT_60S":
            result["observed_hanging_seconds"] = observed
            assert observed >= 60 and proc.returncode == -9
        receipt_finish(receipt, result)
        rows.append(result)
        await servers.settled()
        print("baseline", scenario, result["killed_at_seconds"], outcome, flush=True)
    return {"rows": rows}


async def baseline_child(url):
    async with httpx.AsyncClient(timeout=None, trust_env=False) as client:
        print(json.dumps({"send_monotonic": time.monotonic()}), flush=True)
        await client.post(url, content=b"{}")  # Deliberately no application deadline.


async def main():
    assert sys.version_info >= (3, 11)
    RECEIPTS.write_text("")
    results = {"python": platform.python_version(), "platform": platform.platform(),
               "deadline": DEADLINE, "versions": {p: importlib.metadata.version(p) for p in
               ("httpx", "httpcore", "anyio", "h11", "certifi", "idna", "typing_extensions")}}
    servers = await Servers().start()
    results["smoke"] = await smoke(servers)
    save(ROOT / "smoke.json", results["smoke"])
    results["matrix1"] = await matrix(servers, "matrix1", None)
    save(ROOT / "checkpoint-matrix1.json", results["matrix1"])
    print("CHECKPOINT matrix1 written", flush=True)
    results["matrix2"] = await baseline(servers)
    save(ROOT / "baseline.json", results["matrix2"])
    results["matrix3"] = await matrix(servers, "matrix3", httpx.Timeout(connect=2, read=3, write=3, pool=2))
    await servers.close()
    results["server_connections"] = servers.connections
    results["receipts_count"] = len(RECEIPTS.read_text().splitlines())
    results["requests_sent"] = len(servers.connections)
    assert results["receipts_count"] == results["requests_sent"] == 23
    assert all(json.loads(line)["outcome"] != "PRE_SEND" for line in RECEIPTS.read_text().splitlines())
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    assert not pending, pending
    results["pending_tasks_at_exit"] = len(pending)
    results["all_server_transports_closed"] = True
    save(ROOT / "results.json", results)
    print("CLEAN EXIT: 23 receipts / 23 POSTs; zero pending tasks; all transports closed", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--baseline-child":
        asyncio.run(baseline_child(sys.argv[2]))
    else:
        asyncio.run(main(), debug=True)
