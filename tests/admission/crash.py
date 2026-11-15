"""A dispatcher process that dies at a failpoint (#95):

    python -m tests.admission.crash after_commit|before_start|after_start DSN TEMPORAL_ADDRESS

It creates one process request and then dispatches it. after_commit: it dies once the request
is committed. before_start: it has claimed the row and dies before starting the workflow.
after_start: the workflow has started and it dies before recording the row as dispatched. It
exits with CRASHED at the failpoint, 1 when it never reached one."""

import asyncio
import os
import sys

import psycopg
from temporalio.client import Client

from kp_admission.dispatcher import dispatch_due, temporal_start
from tests.admission.support import queue, request, revision

CRASHED = 70


async def main(point: str, dsn: str, address: str) -> None:
    real = temporal_start(await Client.connect(address), queue)

    async def start(start_input):
        if point == "after_start":
            await real(start_input)
        os._exit(CRASHED)  # no cleanup, no rollback: the connection just drops

    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        await request(conn, *await revision(conn))
        if point == "after_commit":
            os._exit(CRASHED)
        await dispatch_due(conn, start)


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:]))
    sys.exit(1)
