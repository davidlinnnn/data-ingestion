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
from temporalio.client import Client

from kp_admission.dispatcher import dispatch_due, temporal_start
from kp_admission.reconciler import reconcile
from kp_canonicalization.cli import JsonFormatter
from kp_canonicalization.workflow import ORCHESTRATION_QUEUE

POLL_S = 1.0


def main(argv: list[str] | None = None) -> int:
    """`kp-admission dispatcher`: start the workflows of due outbox rows, looking every POLL_S
    seconds, until SIGTERM or SIGINT. It starts while Temporal is down; the rows wait.

    `kp-admission reconcile`: one reconciler run, which a CronJob repeats every 5 minutes. It
    prints how many requests went each way, as JSON, and fails when Temporal is unreachable.

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
    return asyncio.run(dispatcher(dsn) if args.role == "dispatcher" else reconcile_once(dsn))


async def connect(lazy: bool = False) -> Client:
    return await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        lazy=lazy,
    )


async def dispatcher(dsn: str) -> int:
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    # #135 part 2 replaces the shared queue with the orchestration queue of adopted_version.
    start = temporal_start(await connect(lazy=True), lambda _adopted_version: ORCHESTRATION_QUEUE)
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        while not stop.is_set():
            await dispatch_due(conn, start)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), POLL_S)
    return 0


async def reconcile_once(dsn: str) -> int:
    client = await connect()
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        print(json.dumps(await reconcile(conn, client)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
