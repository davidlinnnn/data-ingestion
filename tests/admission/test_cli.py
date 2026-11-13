"""The kp-admission roles as processes, on Testcontainers PostgreSQL and Temporal (#95)."""

import asyncio
import contextlib
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from kp_admission.cli import main
from tests.admission.support import request, revision, runs


def role(command: str, env: dict[str, str], **kwargs) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "kp_admission.cli", command],
        env=env,
        cwd=Path(__file__).parents[2],
        **kwargs,
    )


@pytest.mark.docker
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
    assert described.task_queue == "paper-pdf-1.orchestration"
    reconciler = role("reconcile", env, stdout=subprocess.PIPE, text=True)
    out, _ = reconciler.communicate(timeout=30)
    assert (reconciler.returncode, json.loads(out)) == (0, {"running": 6})


@pytest.mark.docker
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


@pytest.mark.parametrize("deployment", [None, "production", "Pilot"])
def test_the_api_refuses_the_allow_all_provider_outside_a_pilot(monkeypatch, capsys, deployment):
    monkeypatch.setenv("KP_ADMISSION_DATABASE_URL", "host=127.0.0.1 port=9")
    monkeypatch.setenv("KP_AUTHZ_PROVIDER", "allow-all")
    if deployment:
        monkeypatch.setenv("KP_DEPLOYMENT", deployment)
    else:
        monkeypatch.delenv("KP_DEPLOYMENT", raising=False)

    assert main(["api"]) == 2
    assert "KP_DEPLOYMENT=pilot" in capsys.readouterr().err


@pytest.mark.docker
@pytest.mark.network
async def test_the_api_in_a_pilot_serves_decisions_to_registered_peps_and_stops_on_sigterm(
    conn, dsn
):
    await conn.execute(
        "INSERT INTO authz.resource (resource_id, tenant_id, name, created_by_source)"
        " VALUES ('res_01', 't1', 'rd / nlp', 'rd_papers')"
    )
    with socket.socket() as probe:  # a free port: fixed ports collide across parallel runs
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = os.environ | {
        "KP_ADMISSION_DATABASE_URL": dsn,
        "KP_ADMISSION_API_PORT": str(port),
        "KP_AUTHZ_PROVIDER": "allow-all",
        "KP_DEPLOYMENT": "pilot",
        "KP_AUTHZ_PEP_CREDENTIALS": json.dumps({hashlib.sha256(b"pep-1").hexdigest(): "wiki"}),
    }
    check = {
        "subject": {"type": "user", "id": "alice"},
        "action": "read",
        "resource": {"type": "resource", "id": "res_01"},
        "trace_id": "t",
    }
    api = role("api", env, stderr=subprocess.PIPE, text=True)
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
            for _ in range(100):
                with contextlib.suppress(httpx.ConnectError):
                    registered = await http.post(
                        "/authz/v1/check", json=check, headers={"authorization": "Bearer pep-1"}
                    )
                    break
                await asyncio.sleep(0.1)
            unregistered = await http.post(
                "/authz/v1/check", json=check, headers={"authorization": "Bearer pep-2"}
            )
    finally:
        api.send_signal(signal.SIGTERM)

    _, log = api.communicate(timeout=10)
    assert api.returncode == -signal.SIGTERM
    assert "Finished server process" in log  # a graceful stop, not the signal's default action
    assert (registered.status_code, registered.json()["outcome"]) == (200, "allow")
    assert unregistered.status_code == 401


@pytest.mark.parametrize("credentials", ["not json", "[]"])
def test_the_api_refuses_pep_credentials_that_are_not_a_json_object(
    monkeypatch, capsys, credentials
):
    monkeypatch.setenv("KP_ADMISSION_DATABASE_URL", "host=127.0.0.1 port=9")
    monkeypatch.setenv("KP_AUTHZ_PROVIDER", "allow-all")
    monkeypatch.setenv("KP_DEPLOYMENT", "pilot")
    monkeypatch.setenv("KP_AUTHZ_PEP_CREDENTIALS", credentials)

    assert main(["api"]) == 2
    assert "KP_AUTHZ_PEP_CREDENTIALS" in capsys.readouterr().err
