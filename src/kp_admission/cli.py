"""kp-admission command line: the api, dispatcher and reconciler roles (#95, #113, admission
spec §13).

The database comes from KP_ADMISSION_DATABASE_URL; Temporal from TEMPORAL_ADDRESS (default
localhost:7233) and TEMPORAL_NAMESPACE (default "default"), as for kp-canonicalization.
"""

import argparse
import asyncio
import contextlib
import json
import os
import signal
import sys

import psycopg
import uvicorn
from psycopg_pool import AsyncConnectionPool

from kp_admission.api import app
from kp_admission.authz import AllowAll
from kp_admission.dispatcher import dispatch_due, temporal_start
from kp_admission.reconciler import reconcile
from kp_canonicalization.cli import connect, log_json_lines
from kp_canonicalization.workflow import task_queue

POLL_S = 1.0
POOL_SIZE = 5  # per api pod; the connection budget (#78 C14) counts it


def main(argv: list[str] | None = None) -> int:
    """`kp-admission api`: serve the platform API on KP_ADMISSION_API_PORT (default 8080) until
    SIGTERM or SIGINT; it finishes open requests, then ends by that signal, as uvicorn does.
    KP_AUTHZ_PROVIDER selects the authz provider: `allow-all`, the only one, which it refuses
    unless KP_DEPLOYMENT is `pilot` (#113; the marker is #78's). KP_AUTHZ_PEP_CREDENTIALS registers
    the PEPs that may call the authz API, as a JSON object from the SHA-256 hex digest of each
    credential to its service identity. It starts while the database is down; decisions are then
    unavailable.

    `kp-admission dispatcher`: start the workflows of due outbox rows, looking every POLL_S
    seconds, until SIGTERM or SIGINT. It starts while Temporal is down; the rows wait.

    `kp-admission reconcile`: one reconciler run. It prints how many requests went each way, as
    JSON, and fails when Temporal is unreachable.

    All three log JSON lines to stderr and exit 2 without KP_ADMISSION_DATABASE_URL or on another
    configuration error."""
    parser = argparse.ArgumentParser(prog="kp-admission")
    parser.add_argument("role", choices=["api", "dispatcher", "reconcile"])
    args = parser.parse_args(argv)
    dsn = os.environ.get("KP_ADMISSION_DATABASE_URL")
    if not dsn:
        print("KP_ADMISSION_DATABASE_URL is required", file=sys.stderr)
        return 2
    if args.role == "api":
        if os.environ.get("KP_AUTHZ_PROVIDER") != "allow-all":
            print("KP_AUTHZ_PROVIDER must be allow-all, the only provider", file=sys.stderr)
            return 2
        if os.environ.get("KP_DEPLOYMENT") != "pilot":
            print("the allow-all authz provider needs KP_DEPLOYMENT=pilot", file=sys.stderr)
            return 2
        try:
            peps = json.loads(os.environ.get("KP_AUTHZ_PEP_CREDENTIALS", "{}"))
        except json.JSONDecodeError:
            peps = None
        if not isinstance(peps, dict):
            print("KP_AUTHZ_PEP_CREDENTIALS must be a JSON object", file=sys.stderr)
            return 2
        log_json_lines()
        return asyncio.run(run_api(dsn, peps, int(os.environ.get("KP_ADMISSION_API_PORT", 8080))))
    log_json_lines()
    return asyncio.run(run_dispatcher(dsn) if args.role == "dispatcher" else run_reconciler(dsn))


async def run_api(dsn: str, peps: dict[str, str], port: int) -> int:
    pool = AsyncConnectionPool(dsn, max_size=POOL_SIZE, kwargs={"autocommit": True}, open=False)
    async with pool:
        config = uvicorn.Config(
            app(AllowAll(pool), peps), host="0.0.0.0", port=port, log_config=None
        )
        await uvicorn.Server(config).serve()
    return 0


async def run_dispatcher(dsn: str) -> int:
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    start = temporal_start(await connect(lazy=True), task_queue)
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        while not stop.is_set():
            await dispatch_due(conn, start)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), POLL_S)
    return 0


async def run_reconciler(dsn: str) -> int:
    client = await connect()
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        print(json.dumps(await reconcile(conn, client)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
