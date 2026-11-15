"""#113: what a blocking call costs on the api role's one uvicorn worker per pod.

Three ASGI handlers wait 100 ms each: awaited, blocking in a thread, and blocking inline. Each is
served by one uvicorn worker and driven by ApacheBench (`ab`) with 320 requests, 32 at once.
Writes blocking_evidence.json next to this file and exits 1 when a check fails.

    .venv/bin/python docs/validation/113/blocking.py
"""

import asyncio
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

WAIT_S, REQUESTS, AT_ONCE = 0.1, 320, 32
HEADERS = [(b"content-type", b"text/plain"), (b"content-length", b"2")]
THREADS = min(32, (os.cpu_count() or 1) + 4)  # asyncio.to_thread's default executor
# The most requests per second each handler can reach; it must reach at least half of it.
CEILING = {
    "awaited": AT_ONCE / WAIT_S,
    "in_thread": min(AT_ONCE, THREADS) / WAIT_S,
    "blocking": 1 / WAIT_S,  # one request at a time
}


async def _reply(send) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": HEADERS})
    await send({"type": "http.response.body", "body": b"ok"})


async def awaited(scope, receive, send) -> None:
    await asyncio.sleep(WAIT_S)
    await _reply(send)


async def in_thread(scope, receive, send) -> None:
    await asyncio.to_thread(time.sleep, WAIT_S)
    await _reply(send)


async def blocking(scope, receive, send) -> None:
    time.sleep(WAIT_S)  # the mistake: every other request of the worker waits too
    await _reply(send)


def measure(handler: str) -> dict:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", f"blocking:{handler}", "--port", str(port)]
        + ["--lifespan", "off", "--log-level", "warning"],
        cwd=Path(__file__).parent,
    )
    try:
        for _ in range(100):
            with socket.socket() as attempt:
                if attempt.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.1)
        out = subprocess.run(
            ["ab", "-q", "-n", str(REQUESTS), "-c", str(AT_ONCE), f"http://127.0.0.1:{port}/"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    finally:
        server.send_signal(signal.SIGTERM)
        server.wait(timeout=10)

    def number(pattern: str) -> float:
        found = re.search(pattern, out)
        return float(found.group(1)) if found else -1.0

    return {
        "requests_per_s": number(r"Requests per second:\s+([\d.]+)"),
        "p99_ms": number(r"\n\s+99%\s+(\d+)"),
        "complete": number(r"Complete requests:\s+(\d+)"),
        "failed": number(r"Failed requests:\s+(\d+)"),
    }


def main() -> int:
    readings = {handler: measure(handler) for handler in CEILING}
    checks = {"every expected reading is present": set(readings) == set(CEILING)}
    for handler, ceiling in CEILING.items():
        reading = readings[handler]
        checks[f"{handler}: {ceiling / 2:g} <= requests per second <= {ceiling:g}, none failed"] = (
            ceiling / 2 <= reading["requests_per_s"] <= ceiling
            and reading["complete"] == REQUESTS
            and reading["failed"] == 0
        )
    evidence = {
        "date": time.strftime("%Y-%m-%d"),
        "host": "macOS; one uvicorn worker and ab on the same machine",
        "wait_ms": WAIT_S * 1000,
        "requests": REQUESTS,
        "at_once": AT_ONCE,
        "to_thread_threads": THREADS,
        "readings": readings,
        "checks": checks,
    }
    out = Path(__file__).parent / "blocking_evidence.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
