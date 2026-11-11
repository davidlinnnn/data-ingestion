"""kp-admission command line: the dispatcher and reconciler roles (#95, admission spec §13).

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

from kp_admission.dispatcher import dispatch_due, temporal_start
from kp_admission.reconciler import reconcile
from kp_canonicalization.cli import connect, log_json_lines
from kp_canonicalization.workflow import task_queue

POLL_S = 1.0


def main(argv: list[str] | None = None) -> int:
    """`kp-admission dispatcher`: start the workflows of due outbox rows, looking every POLL_S
    seconds, until SIGTERM or SIGINT. It starts while Temporal is down; the rows wait.

    `kp-admission reconcile`: one reconciler run. It prints how many requests went each way, as
    JSON, and fails when Temporal is unreachable.

    Both log JSON lines to stderr and exit 2 without KP_ADMISSION_DATABASE_URL."""
    parser = argparse.ArgumentParser(prog="kp-admission")
    parser.add_argument("role", choices=["dispatcher", "reconcile"])
    args = parser.parse_args(argv)
    dsn = os.environ.get("KP_ADMISSION_DATABASE_URL")
    if not dsn:
        print("KP_ADMISSION_DATABASE_URL is required", file=sys.stderr)
        return 2
    log_json_lines()
    return asyncio.run(run_dispatcher(dsn) if args.role == "dispatcher" else run_reconciler(dsn))


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
