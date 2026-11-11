"""kp-admission command line: the dispatcher and reconciler roles (#95, admission spec §13).

The database comes from KP_ADMISSION_DATABASE_URL; Temporal from TEMPORAL_ADDRESS (default
localhost:7233) and TEMPORAL_NAMESPACE (default "default"), as for kp-canonicalization.
"""

import argparse
import asyncio
import contextlib
import json
import logging
import os
import signal
import sys

import psycopg

from kp_admission.dispatcher import dispatch_due, temporal_start
from kp_admission.reconciler import reconcile
from kp_canonicalization.cli import JsonFormatter, connect
from kp_canonicalization.workflow import ORCHESTRATION_QUEUE

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
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    return asyncio.run(run_dispatcher(dsn) if args.role == "dispatcher" else run_reconciler(dsn))


async def run_dispatcher(dsn: str) -> int:
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    # shortcut: every adopted_version starts on the shared orchestration queue; #135 part 2
    # replaces it with the queue of adopted_version.
    start = temporal_start(await connect(lazy=True), lambda _adopted_version: ORCHESTRATION_QUEUE)
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
