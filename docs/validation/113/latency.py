"""#113 acceptance 4: check and list_resources latency of the allow-all provider, in process
(admission's path) and through the authz API (the other PEPs' path), against authz_timeout.

Starts PostgreSQL 17 with Testcontainers and `kp-admission api` on a free port, writes the
readings to evidence.json next to this file and exits 1 when a check fails. The concurrent HTTP
load comes from ApacheBench (`ab`, in macOS; apache2-utils on Linux): one Python client process
saturates before the api does.

    .venv/bin/python docs/validation/113/latency.py
"""

import asyncio
import csv
import hashlib
import json
import os
import re
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import psycopg
from psycopg_pool import AsyncConnectionPool
from testcontainers.community.postgres import PostgresContainer

from kp_admission import SCHEMA
from kp_admission.authz import PAGE_SIZE, TIMEOUT_S, AllowAll, Ref

ROOT = Path(__file__).parents[3]
CALLS, WARMUP, CONCURRENCY = 2000, 100, 32
ALICE = Ref(type="user", id="alice")
CHECK = {
    "subject": {"type": "user", "id": "alice"},
    "action": "read",
    "resource": {"type": "resource", "id": "res_0500"},
    "trace_id": "latency",
}
LIST = {key: value for key, value in CHECK.items() if key != "resource"}
TOKEN = "pep"


def summary(samples: list[float], outcomes: list[str]) -> dict:
    ms = sorted(s * 1000 for s in samples)
    return {
        "calls": len(ms),
        "p50_ms": round(statistics.median(ms), 2),
        "p99_ms": round(ms[int(len(ms) * 0.99) - 1], 2),
        "max_ms": round(ms[-1], 2),
        "outcomes": sorted(set(outcomes)),
    }


async def timed(call, calls: int, concurrency: int) -> dict:
    """Runs `call` (returning an outcome) `calls` times over `concurrency` workers."""
    for _ in range(WARMUP):
        await call()
    samples, outcomes, left = [], [], iter(range(calls))

    async def worker():
        for _ in left:
            start = time.perf_counter()
            outcomes.append(await call())
            samples.append(time.perf_counter() - start)

    await asyncio.gather(*(worker() for _ in range(concurrency)))
    return summary(samples, outcomes)


def ab(port: int, path: str, body: dict, calls: int) -> dict:
    """ApacheBench at CONCURRENCY with keep-alive. Its outcome reads `allow` when every response
    was a 200 of the first one's length: ab fails the others, and an unavailable decision differs
    in length from an allow."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "body.json").write_text(json.dumps(body))
        out = subprocess.run(
            ["ab", "-k", "-n", str(calls), "-c", str(CONCURRENCY), "-p", f"{tmp}/body.json"]
            + ["-T", "application/json", "-H", f"authorization: Bearer {TOKEN}"]
            + ["-e", f"{tmp}/percentiles.csv", f"http://127.0.0.1:{port}{path}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        with open(f"{tmp}/percentiles.csv") as f:
            percentiles = {int(row[0]): float(row[1]) for row in list(csv.reader(f))[1:]}
    complete = int(re.search(r"Complete requests:\s+(\d+)", out).group(1))
    failed = int(re.search(r"Failed requests:\s+(\d+)", out).group(1))
    ok = complete == calls and failed == 0 and "Non-2xx" not in out
    return {
        "calls": complete,
        "p50_ms": percentiles[50],
        "p99_ms": percentiles[99],
        "max_ms": percentiles[100],
        "requests_per_s": float(re.search(r"Requests per second:\s+([\d.]+)", out).group(1)),
        "outcomes": ["allow"] if ok else ["not all allow"],
    }


async def main() -> int:
    with PostgresContainer("postgres:17.10-alpine", driver=None) as container:
        dsn = container.get_connection_url()
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(SCHEMA)
            conn.execute(
                "INSERT INTO authz.resource (resource_id, tenant_id, name, created_by_source)"
                " SELECT 'res_' || lpad(i::text, 4, '0'), 't1', 'r', 'src'"
                " FROM generate_series(1, %s) AS i",
                (PAGE_SIZE,),
            )
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        env = os.environ | {
            "KP_ADMISSION_DATABASE_URL": dsn,
            "KP_ADMISSION_API_PORT": str(port),
            "KP_AUTHZ_PROVIDER": "allow-all",
            "KP_DEPLOYMENT": "pilot",
            "KP_AUTHZ_PEP_CREDENTIALS": json.dumps(
                {hashlib.sha256(TOKEN.encode()).hexdigest(): "probe"}
            ),
        }
        api = subprocess.Popen(
            [sys.executable, "-m", "kp_admission.cli", "api"],
            env=env,
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
        try:
            readings = await in_process(dsn) | await over_http(port)
        finally:
            api.send_signal(signal.SIGTERM)
            api.wait(timeout=10)

    limit_ms = TIMEOUT_S * 1000
    checks = {
        f"{name}: 0 <= p99 <= authz_timeout and every outcome allow": 0
        <= reading["p99_ms"]
        <= limit_ms
        and reading["outcomes"] == ["allow"]
        for name, reading in readings.items()
        if name != "control_locked_table"
    }
    control = readings["control_locked_table"]
    checks["control: a locked table reads unavailable after authz_timeout"] = (
        control["outcomes"] == ["unavailable"] and limit_ms <= control["max_ms"] <= limit_ms + 250
    )
    evidence = {
        "date": time.strftime("%Y-%m-%d"),
        "host": "macOS, Docker Desktop PostgreSQL 17.10; client, api and database on one machine",
        "authz_timeout_ms": limit_ms,
        "page_size": PAGE_SIZE,
        "resources": PAGE_SIZE,
        "readings": readings,
        "checks": checks,
    }
    (Path(__file__).parent / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    return 0 if all(checks.values()) else 1


async def in_process(dsn: str) -> dict:
    readings = {}
    async with AsyncConnectionPool(dsn, max_size=5, kwargs={"autocommit": True}) as pool:
        provider = AllowAll(pool)

        async def check():
            return (await provider.check(ALICE, "read", "res_0500", trace_id="t")).outcome

        async def page():
            return (await provider.list_resources(ALICE, "read", trace_id="t")).outcome

        for n in (1, CONCURRENCY):
            readings[f"in_process_check_c{n}"] = await timed(check, CALLS, n)
            readings[f"in_process_list_1000_c{n}"] = await timed(page, CALLS // 4, n)

        async with await psycopg.AsyncConnection.connect(dsn) as locker:
            await locker.execute("LOCK TABLE authz.resource IN ACCESS EXCLUSIVE MODE")
            readings["control_locked_table"] = await timed(check, 5, 1)
    return readings


async def over_http(port: int) -> dict:
    headers = {"authorization": f"Bearer {TOKEN}"}
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", headers=headers) as http:
        for _ in range(100):
            try:
                await http.post("/authz/v1/check", json=CHECK)
                break
            except httpx.ConnectError:
                await asyncio.sleep(0.1)

        async def check():
            return (await http.post("/authz/v1/check", json=CHECK)).json()["outcome"]

        async def page():
            return (await http.post("/authz/v1/list_resources", json=LIST)).json()["outcome"]

        return {
            "http_check_c1": await timed(check, CALLS, 1),
            "http_list_1000_c1": await timed(page, CALLS // 4, 1),
            f"http_check_c{CONCURRENCY}_ab": ab(port, "/authz/v1/check", CHECK, CALLS * 2),
            f"http_list_1000_c{CONCURRENCY}_ab": ab(port, "/authz/v1/list_resources", LIST, CALLS),
        }


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
