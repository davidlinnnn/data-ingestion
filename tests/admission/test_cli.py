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
from tests.admission.support import request, resource, revision, runs

CHECK = {
    "subject": {"type": "user", "id": "alice"},
    "action": "read",
    "resource": {"type": "resource", "id": "res_01"},
}


def role(command: str, env: dict[str, str], *options: str, **kwargs) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "kp_admission.cli", command, *options],
        env=env,
        cwd=Path(__file__).parents[2],
        **kwargs,
    )


def free_port() -> int:
    with socket.socket() as probe:  # fixed ports collide across parallel runs
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


S3 = {  # the api reaches storage only when a batch is finalized
    "KP_S3_ENDPOINT": "http://127.0.0.1:9",
    "KP_S3_BUCKET": "kp-custody",
    "AWS_ACCESS_KEY_ID": "x",
    "AWS_SECRET_ACCESS_KEY": "x",
}


def api_env(dsn: str, port: int) -> dict[str, str]:
    """A pilot api on `port` with one registered PEP, wiki, whose credential is pep-1; the Source
    km, whose credential is km-1; and the client research-agent, whose credential is agent-1."""
    return os.environ | {
        "KP_ADMISSION_DATABASE_URL": dsn,
        "KP_ADMISSION_API_PORT": str(port),
        "KP_AUTHZ_PROVIDER": "allow-all",
        "KP_DEPLOYMENT": "pilot",
        **S3,
        "KP_AUTHZ_PEP_CREDENTIALS": json.dumps({hashlib.sha256(b"pep-1").hexdigest(): "wiki"}),
        "KP_CREDENTIALS": json.dumps(
            {
                hashlib.sha256(b"km-1").hexdigest(): {
                    "credential_id": "km-1",
                    "tenant_id": "t1",
                    "source_id": "km",
                    "scopes": ["submit", "manage_relations"],
                },
                hashlib.sha256(b"agent-1").hexdigest(): {
                    "credential_id": "agent-1",
                    "client_id": "research-agent",
                    "delegate": True,
                },
            }
        ),
    }


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


@pytest.mark.parametrize("command", ["dispatcher", "reconcile"])
def test_only_the_api_takes_a_metrics_port(monkeypatch, command):
    monkeypatch.setenv("KP_ADMISSION_DATABASE_URL", "host=127.0.0.1 port=9")

    with pytest.raises(SystemExit) as refused:
        main([command, "--metrics-port", "9100"])
    assert refused.value.code == 2


@pytest.mark.docker
@pytest.mark.network
async def test_the_api_in_a_pilot_serves_decisions_to_registered_peps_and_stops_on_sigterm(
    conn, dsn
):
    await resource(conn)
    port = free_port()
    api = role("api", api_env(dsn, port), stderr=subprocess.PIPE, text=True)
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
            for _ in range(100):
                with contextlib.suppress(httpx.ConnectError):
                    registered = await http.post(
                        "/authz/v1/check", json=CHECK, headers={"authorization": "Bearer pep-1"}
                    )
                    break
                await asyncio.sleep(0.1)
            unregistered = await http.post(
                "/authz/v1/check", json=CHECK, headers={"authorization": "Bearer pep-2"}
            )
    finally:
        api.send_signal(signal.SIGTERM)

    _, log = api.communicate(timeout=10)
    assert api.returncode == -signal.SIGTERM
    assert "Finished server process" in log  # a graceful stop, not the signal's default action
    assert (registered.status_code, registered.json()["outcome"]) == (200, "allow")
    assert unregistered.status_code == 401


SOURCE = {"credential_id": "c1", "tenant_id": "t1", "source_id": "km", "scopes": ["submit"]}


@pytest.mark.parametrize(
    "variable, value",
    [
        ("KP_AUTHZ_PEP_CREDENTIALS", "not json"),
        ("KP_AUTHZ_PEP_CREDENTIALS", "[]"),
        ("KP_AUTHZ_PEP_CREDENTIALS", '{"digest": 1}'),
        ("KP_CREDENTIALS", "not json"),
        ("KP_CREDENTIALS", '{"digest": {"credential_id": "c1", "source_id": "km"}}'),
        (
            "KP_CREDENTIALS",
            '{"digest": {"credential_id": "c1", "tenant_id": "t1",'
            ' "source_id": "km", "scopes": []}}',
        ),
        ("KP_CREDENTIALS", json.dumps({"d1": SOURCE, "d2": SOURCE})),
        (
            "KP_CREDENTIALS",
            json.dumps({"d1": SOURCE, "d2": SOURCE | {"credential_id": "c2", "tenant_id": "t2"}}),
        ),
        ("KP_ADMISSION_API_PORT", "http"),
        ("KP_SOURCES", '{"km": {"ordering": "newest"}}'),
        ("KP_MAX_FILE_SIZE", "50MB"),
        ("KP_PAUSE_BACKLOG", "-1"),
        ("KP_S3_BUCKET", ""),
    ],
)
def test_the_api_refuses_a_malformed_setting(monkeypatch, capsys, variable, value):
    monkeypatch.setenv("KP_ADMISSION_DATABASE_URL", "host=127.0.0.1 port=9")
    monkeypatch.setenv("KP_AUTHZ_PROVIDER", "allow-all")
    monkeypatch.setenv("KP_DEPLOYMENT", "pilot")
    for name, setting in S3.items():
        monkeypatch.setenv(name, setting)
    monkeypatch.setenv(variable, value)

    assert main(["api"]) == 2
    assert variable in capsys.readouterr().err


@pytest.mark.network
async def test_the_api_without_a_database_stays_healthy_and_its_503s_reach_metrics_and_logs():
    port, metrics_port = free_port(), free_port()
    trace = "4bf92f3577b34da6a3ce929d0e0e4736"
    api = role(
        "api",
        api_env("host=127.0.0.1 port=9", port),
        "--metrics-port",
        str(metrics_port),
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
            for _ in range(100):
                with contextlib.suppress(httpx.ConnectError):
                    health = await http.get("/healthz")
                    break
                await asyncio.sleep(0.1)
            checked = await http.post(
                "/authz/v1/check",
                json=CHECK,
                headers={
                    "authorization": "Bearer pep-1",
                    "traceparent": f"00-{trace}-00f067aa0ba902b7-01",
                },
            )
            metrics = (await http.get(f"http://127.0.0.1:{metrics_port}/metrics")).text
    finally:
        api.send_signal(signal.SIGTERM)

    _, log = api.communicate(timeout=10)
    assert health.status_code == 200
    assert (checked.status_code, checked.headers["x-trace-id"]) == (503, trace)
    counted = 'kp_authz_decisions_total{operation="check",outcome="unavailable",pep="wiki"} 1.0'
    assert counted in metrics.splitlines()
    lines = [json.loads(line) for line in log.splitlines()]
    [no_decision] = [line for line in lines if line["message"] == "no decision"]
    assert (no_decision["trace_id"], no_decision["pep"]) == (trace, "wiki")
    [access] = [line for line in lines if "/authz/v1/check" in line["message"]]
    assert (access["logger"], access["trace_id"]) == ("uvicorn.access", trace)


@pytest.mark.docker
@pytest.mark.network
async def test_the_api_serves_registered_sources_and_clients_and_logs_and_counts_each_call(dsn):
    port, metrics_port = free_port(), free_port()
    api = role(
        "api",
        api_env(dsn, port),
        "--metrics-port",
        str(metrics_port),
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
            for _ in range(100):
                with contextlib.suppress(httpx.ConnectError):
                    await http.get("/healthz")
                    break
                await asyncio.sleep(0.1)
            registered = await http.put(
                "/v1/resources/hr%2Fall", headers={"authorization": "Bearer km-1"}
            )
            by_client = await http.get("/v1/resources", headers={"authorization": "Bearer agent-1"})
            unknown = await http.get("/v1/resources", headers={"authorization": "Bearer pep-1"})
            metrics = (await http.get(f"http://127.0.0.1:{metrics_port}/metrics")).text
    finally:
        api.send_signal(signal.SIGTERM)

    _, log = api.communicate(timeout=10)
    assert (registered.status_code, registered.json()["key"]) == (201, "hr/all")
    assert (by_client.status_code, unknown.status_code) == (403, 401)
    counted = 'kp_api_calls_total{operation="register_resource",status="201"} 1.0'
    assert counted in metrics.splitlines()
    lines = [json.loads(line) for line in log.splitlines()]
    [put] = [line for line in lines if '"PUT /v1/resources/' in line["message"]]
    assert (put["source_id"], put["credential_id"]) == ("km", "km-1")
    [client] = [
        line for line in lines if '"GET /v1/resources' in line["message"] and line.get("client_id")
    ]
    assert client["credential_id"] == "agent-1"


async def test_the_adoption_commands_and_the_expiry_run_print_their_outcome(dsn, conn):
    env = os.environ | {"KP_ADMISSION_DATABASE_URL": dsn, "KP_TENANT_ID": "t1"}

    def run(*args: str) -> tuple[int, dict]:
        done = subprocess.run(
            [sys.executable, "-m", "kp_admission.cli", *args],
            env=env,
            capture_output=True,
            text=True,
        )
        return done.returncode, json.loads(done.stdout)

    assert run("adopt", "application/pdf", "paper-pdf@1") == (
        0,
        {"adopted_version": "paper-pdf@1", "adoption_sequence": 1},
    )
    assert run("cancel-adoption", "application/pdf", "paper-pdf@2") == (1, {"cancelled": False})
    assert run("cancel-adoption", "application/pdf", "paper-pdf@1") == (0, {"cancelled": True})
    await conn.execute(
        "INSERT INTO batch (batch_id, tenant_id, source_id, state, expires_at)"
        " VALUES ('bat_1', 't1', 'km', 'open', now() - interval '1 minute')"
    )
    assert run("expire") == (0, {"expired": 1})
