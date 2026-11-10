"""The kp-admission roles as processes, on Testcontainers PostgreSQL and Temporal (#95)."""

import asyncio
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from kp_admission.cli import main
from kp_canonicalization.workflow import ORCHESTRATION_QUEUE
from tests.admission.support import request, revision, runs

pytestmark = pytest.mark.docker


def role(command: str, env: dict[str, str], **kwargs) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "kp_admission.cli", command],
        env=env,
        cwd=Path(__file__).parents[2],
        **kwargs,
    )


async def test_two_dispatcher_processes_start_each_request_once_and_stop_on_sigterm(
    conn, dsn, temporal, temporal_address
):
    env = os.environ | {"KP_ADMISSION_DATABASE_URL": dsn, "TEMPORAL_ADDRESS": temporal_address}
    dispatchers = [role("dispatcher", env) for _ in range(2)]
    try:
        request_ids = [(await request(conn, *await revision(conn)))[0] for _ in range(6)]
        for _ in range(100):
            cursor = await conn.execute("SELECT count(*) FROM outbox WHERE dispatched_at IS NULL")
            if await cursor.fetchone() == (0,):
                break
            await asyncio.sleep(0.1)
    finally:
        for dispatcher in dispatchers:
            dispatcher.send_signal(signal.SIGTERM)
    assert [dispatcher.wait(timeout=10) for dispatcher in dispatchers] == [0, 0]

    assert [await runs(temporal, request_id) for request_id in request_ids] == [1] * 6
    described = await temporal.get_workflow_handle(request_ids[0]).describe()
    assert described.task_queue == ORCHESTRATION_QUEUE  # until #135 part 2 names the queues
    reconciler = role("reconcile", env, stdout=subprocess.PIPE, text=True)
    out, _ = reconciler.communicate(timeout=30)
    assert (reconciler.returncode, json.loads(out)) == (0, {"running": 6})


async def test_the_dispatcher_starts_while_temporal_is_down_and_its_rows_wait(conn, dsn):
    await request(conn, *await revision(conn))
    env = os.environ | {"KP_ADMISSION_DATABASE_URL": dsn, "TEMPORAL_ADDRESS": "127.0.0.1:9"}
    dispatcher = role("dispatcher", env, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            cursor = await conn.execute("SELECT attempts, dispatched_at FROM outbox")
            if (await cursor.fetchone())[0]:
                break
            await asyncio.sleep(0.1)
    finally:
        dispatcher.send_signal(signal.SIGTERM)

    assert dispatcher.wait(timeout=30) == 0
    cursor = await conn.execute("SELECT attempts >= 1, dispatched_at FROM outbox")
    assert await cursor.fetchone() == (True, None)


def test_a_role_without_a_database_url_exits_2(monkeypatch, capsys):
    monkeypatch.delenv("KP_ADMISSION_DATABASE_URL", raising=False)

    assert main(["dispatcher"]) == 2
    assert "KP_ADMISSION_DATABASE_URL" in capsys.readouterr().err
