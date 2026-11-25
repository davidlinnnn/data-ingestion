"""The kp-admission roles as processes, on Testcontainers PostgreSQL and Temporal (#95)."""

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from kp_admission import adoption, feed, serving
from kp_admission.cli import JsonFormatter, main
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
    "KP_ADMISSION_PUBLIC_URL": "https://kp.example",
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
PIPELINE = {
    "pipeline_id": "kp-canonicalization",
    "track": "canonical",
    "stages": ["prepare", "parse", "enrich", "finalize"],
    "start_deadline_s": 1800,
    "update_interval_s": 1800,
}


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
        ("KP_PIPELINES", "not json"),
        ("KP_PIPELINES", '{"d1": {"pipeline_id": "kp-canonicalization", "track": "canonical"}}'),
        # Two credentials of one pipeline rotate; they must not disagree on its registration.
        ("KP_PIPELINES", json.dumps({"d1": PIPELINE, "d2": PIPELINE | {"stages": ["prepare"]}})),
        ("KP_PIPELINES", json.dumps({"d1": PIPELINE, "d2": PIPELINE | {"pipeline_id": "other"}})),
        # A projection's reports are keyed by its track, so one pipeline has it (spec §7.4).
        (
            "KP_PIPELINES",
            json.dumps(
                {
                    "d1": PIPELINE | {"track": "wiki"},
                    "d2": PIPELINE | {"pipeline_id": "w2", "track": "wiki"},
                }
            ),
        ),
        ("KP_ADMISSION_API_PORT", "http"),
        ("KP_SOURCES", '{"km": {"ordering": "newest"}}'),
        ("KP_MAX_FILE_SIZE", "50MB"),
        ("KP_PAUSE_BACKLOG", "-1"),
        ("KP_S3_BUCKET", ""),
        ("KP_ADMISSION_PUBLIC_URL", ""),
        ("KP_ADMISSION_PUBLIC_URL", "http://kp.example"),
        ("KP_ADMISSION_PUBLIC_URL", "https://kp.example/v1"),
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
    env = os.environ | {"KP_ADMISSION_DATABASE_URL": dsn, **S3}

    def run(*args: str) -> tuple[int, dict]:
        done = subprocess.run(
            [sys.executable, "-m", "kp_admission.cli", *args],
            env=env,
            capture_output=True,
            text=True,
        )
        return done.returncode, json.loads(done.stdout)

    assert run("adopt", "--tenant", "t1", "application/pdf", "paper-pdf@1") == (
        0,
        {"adopted_version": "paper-pdf@1", "adoption_sequence": 1},
    )
    assert run("adopt", "--tenant", "t1", "--refresh", "all", "application/pdf", "paper-pdf@1") == (
        0,
        {"adopted_version": "paper-pdf@1", "adoption_sequence": 2},
    )  # a new refresh scope is a new adoption
    cancel = ("cancel-adoption", "--tenant", "t1", "application/pdf")
    assert run(*cancel, "paper-pdf@2") == (1, {"cancelled": False})
    assert run(*cancel, "paper-pdf@1") == (0, {"cancelled": True})
    await conn.execute(
        "INSERT INTO batch (batch_id, tenant_id, source_id, state, expires_at)"
        " VALUES ('bat_1', 't1', 'km', 'open', now() - interval '1 minute')"
    )
    assert run("expire") == (
        0,
        {"expired": 1, "cleaned": 0, "left": 0},
    )  # it expired under an hour ago


@pytest.mark.docker
async def test_set_profile_and_feed_retention_are_one_shot_runs_that_print_json(conn, dsn):
    env = os.environ | {"KP_ADMISSION_DATABASE_URL": dsn}
    runs_ = [
        role(
            "set-profile", env, "--tenant", "t1", "s1", "retrieval", "wiki", stdout=subprocess.PIPE
        ),
        role("feed-retention", env, stdout=subprocess.PIPE),
    ]
    outs = [json.loads(run.communicate(timeout=30)[0]) for run in runs_]

    assert [run.returncode for run in runs_] == [0, 0]
    assert await feed.profile(conn, "s1") == feed.Profile(
        source_id="s1", projections=["retrieval", "wiki"], profile_seq=outs[0]["profile_seq"]
    )
    assert outs[1] == {"created": [], "dropped": []}


@pytest.mark.docker
async def test_writes_lost_applies_each_declared_event_once(conn, dsn):
    """DR §5.6, K2: a Job of the deployment repo runs it with the event's number."""
    await conn.execute(
        "INSERT INTO build (projection, build_id, state) VALUES ('wiki', 'b1', 'serving')"
    )
    env = os.environ | {"KP_ADMISSION_DATABASE_URL": dsn}
    outs = []
    for event in ("2", "2", "1", "0"):
        run = role("writes-lost", env, event, stdout=subprocess.PIPE)
        printed = run.communicate(timeout=30)[0]
        outs.append((json.loads(printed) if printed else None, run.returncode))

    assert outs[:2] == [({"applied": True, "builds": 1}, 0), ({"applied": False, "builds": 0}, 0)]
    assert outs[2:] == [(None, 1), (None, 2)]  # lower than applied; not a number from 1
    assert await serving.writes_unrepaired(conn) == [("wiki", "b1")]


@pytest.mark.docker
@pytest.mark.network
async def test_the_api_exports_the_feed_and_liveness_gauges_on_its_metrics_port(conn, dsn):
    await feed.report_cursor(conn, "wiki", await feed.head(conn))
    await conn.execute(  # an enforce run's record (#98)
        "INSERT INTO job_gauge (name, label, value)"
        " VALUES ('kp_admission_deletions_unenforced', 'held', 2)"
    )
    await conn.execute(  # an apply-adoption run's record (#261)
        "INSERT INTO adoption_status (tenant_id, media_type, result, reason, since)"
        " VALUES ('t1', 'application/pdf', 'refused', 'version_withdrawn', now())"
    )
    await conn.execute(
        "INSERT INTO build (projection, build_id, state, reported_at)"
        " VALUES ('wiki', 'b1', 'serving', now() - interval '1 hour')"
    )
    port, metrics_port = free_port(), free_port()
    wiki = PIPELINE | {"pipeline_id": "kp-wiki", "track": "wiki", "update_interval_s": 600}
    env = api_env(dsn, port) | {"KP_PIPELINES": json.dumps({"d1": wiki})}
    api = role("api", env, "--metrics-port", str(metrics_port))
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{metrics_port}") as http:
            for _ in range(100):
                with contextlib.suppress(httpx.ConnectError):
                    page = (await http.get("/metrics")).text
                    # The gauge the observe loop sets last: a scrape mid-loop lacks the rest.
                    if 'kp_admission_deletions_unenforced{reason="held"}' in page:
                        break
                await asyncio.sleep(0.1)
    finally:
        api.send_signal(signal.SIGTERM)
        api.wait(timeout=10)

    assert 'kp_feed_consumer_lag_seconds{projection="wiki"} 0.0' in page
    assert "kp_feed_oldest_xmin_age_seconds " in page
    assert 'kp_serving_builds_without_liveness{projection="wiki"} 1.0' in page
    assert (
        'kp_admission_adoption_status{media_type="application/pdf",reason="version_withdrawn",'
        'result="refused"} 1.0'
    ) in page
    assert 'kp_admission_deletions_unenforced{reason="held"} 2.0' in page


@pytest.mark.docker
async def test_apply_adoption_logs_one_line_per_media_type_and_fails_on_a_refusal(
    dsn, conn, temporal_address
):
    """The CronJob of #261. Storage is unreachable: no test workflow is started here, so the
    gate stops at Temporal, where no version is deployed."""
    env = os.environ | {"KP_ADMISSION_DATABASE_URL": dsn, "TEMPORAL_ADDRESS": temporal_address}
    env |= S3

    def run(declared: object, **more: str) -> tuple[int, list[dict]]:
        done = subprocess.run(
            [sys.executable, "-m", "kp_admission.cli", "apply-adoption", "--tenant", "t1"],
            env=env | {"KP_ADOPTION": json.dumps(declared)} | more,
            capture_output=True,
            text=True,
        )
        lines = [json.loads(line) for line in done.stderr.splitlines()]
        return done.returncode, [line for line in lines if "result" in line]

    pdf = {"declaration": 1, "version": "paper-pdf@1", "refresh": "none"}
    waiting, waits = run({"application/pdf": pdf})
    down, downs = run({"application/pdf": pdf}, TEMPORAL_ADDRESS="127.0.0.1:9")
    cancel = {"declaration": 1, "version": "none", "refresh": "none"}
    applied, applies = run({"application/pdf": cancel})
    refused, refusals = run({"application/pdf": cancel | {"version": "paper-pdf@1"}})
    bad = subprocess.run(
        [sys.executable, "-m", "kp_admission.cli", "apply-adoption", "--tenant", "t1"],
        env=env | {"KP_ADOPTION": "[]"},
        capture_output=True,
    )

    fields = ("media_type", "declaration", "version", "result", "reason")
    assert (waiting, [tuple(w[f] for f in fields) for w in waits]) == (
        0,
        [("application/pdf", 1, "paper-pdf@1", "waiting", "not_deployed")],
    )
    assert (down, [(d["result"], d["reason"]) for d in downs]) == (
        1,
        [("waiting", "gate_unavailable")],
    )
    assert (applied, [a["result"] for a in applies]) == (0, ["applied"])
    assert (refused, [(r["result"], r["reason"]) for r in refusals]) == (
        1,
        [("refused", "declaration_not_raised")],
    )
    assert bad.returncode == 2


@pytest.mark.docker
async def test_enforce_and_scan_are_one_shot_runs_that_print_their_counts(conn, dsn):
    """#98: the deployment repo's CronJobs; enforce reads KP_PIPELINES as the api does."""
    uid, srv = await revision(conn)
    await conn.execute(
        "UPDATE document SET latest_source_revision_id = %s WHERE document_uid = %s", (srv, uid)
    )
    await adoption.adopt(conn, tenant_id="t1", media_type="application/pdf", version="paper-pdf@1")
    env = os.environ | {"KP_ADMISSION_DATABASE_URL": dsn}
    wiki = PIPELINE | {"pipeline_id": "kp-wiki", "track": "wiki", "update_interval_s": 600}

    def run(command: str, **more: str) -> tuple[int, object]:
        process = role(command, env | more, stdout=subprocess.PIPE)
        printed = process.communicate(timeout=60)[0]
        return process.returncode, json.loads(printed) if printed else None

    assert run("scan") == (0, {"rerun": 1})
    assert run("scan") == (0, {})  # its request is active
    assert run("enforce", KP_PIPELINES=json.dumps({"d1": wiki})) == (0, {})
    assert run("enforce", KP_PIPELINES="[]") == (2, None)
    assert run("enforce") == (2, None)  # unset: no liveness to suspend on


def test_a_logged_exception_keeps_its_types_and_frames_and_drops_every_message():
    secret, body = "s3cr3t", "Q3 revenue"

    def check():
        raise ValueError(f"credential: {secret}")

    try:
        try:
            check()
        except ValueError as cause:
            raise RuntimeError(f"body: {body}") from cause
    except RuntimeError:
        record = logging.LogRecord(
            "kp_admission.api", logging.WARNING, __file__, 1, "call failed", None, sys.exc_info()
        )
    record.correlation = {"trace_id": "4bf92f3577b34da6"}

    line = json.loads(JsonFormatter().format(record))

    assert re.fullmatch(
        r'RuntimeError\n  File ".*test_cli.py", line \d+, in test_a_logged_.*\n.*\n'
        r'caused by ValueError\n  File ".*test_cli.py", line \d+, in test_a_logged_.*\n.*\n'
        r'  File ".*test_cli.py", line \d+, in check\n.*\n',
        line["exception"],
    )
    assert line["trace_id"] == "4bf92f3577b34da6"
    assert "s3cr3t" not in json.dumps(line) and "revenue" not in json.dumps(line)
