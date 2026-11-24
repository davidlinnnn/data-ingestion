"""#81 acceptance end to end: papers submitted through the real platform API, processed by the
paper-pdf workflow, until the Document has a current revision.

    set -a; . ~/.config/kp-dev/anthropic.env; set +a
    scripts/heavy-lock 81-e2e -- env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/81/e2e.py \
        OUT MANIFEST ARCHIVE D3_PACKAGE D3_PYTHON INDEX...

Arguments as for #199's run.py, whose helpers this reuses (profile, S3 stand-in, d3 server,
workers, VLM and summary stand-ins). What differs from #199: no fake_admission. PostgreSQL 17
(Testcontainers) with kp_admission's schema; `kp-admission api` (with its metrics port) and
`kp-admission dispatcher` as processes; the orchestration worker reports to that api with the
token registered in KP_PIPELINES. The adoption is `kp-admission adopt` (the gate of
`apply-adoption` needs versioned workers; its candidate check is a unit test). W2 runs on the
stand-ins, a corpus paper on the providers, as in #199.

Per paper: register the Resource, declare, PUT the file, finalize, then poll the request until
it ends. It records the request's state, the Source Revision's outcome, the Document's current
revision (read API and database), the feed's current_revision_changed event, the candidate
against the stored content object and the database row, kp_admission_not_accepted_total
before and after, and finalize's Activity time from the workflow history. Rows go to
OUT/papers/<index>.json, content objects to OUT/content/<index>.json (both outside git) and the
summary to e2e.json here. Ports 9281, 7381, 7382 and 8281-8285 must be free.
"""

import asyncio
import hashlib
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import UTC
from pathlib import Path

import httpx
import psycopg
from temporalio.client import Client
from testcontainers.community.postgres import PostgresContainer

from kp_admission import SCHEMA

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "199"))
import run as r199  # noqa: E402

t2, t5, t5c = r199.t2, r199.t5, r199.t5c
S3_PORT, TEMPORAL_PORT, API_PORT, METRICS_PORT, VLM_PORT, SUMMARY_PORT, D3_PORT = (
    9281, 7381, 8281, 8282, 8283, 8284, 8285)  # fmt: skip
r199.VLM_PORT, r199.SUMMARY_PORT, r199.D3_PORT, t5c.D3_PORT = VLM_PORT, SUMMARY_PORT, D3_PORT, D3_PORT
API = f"http://127.0.0.1:{API_PORT}"
t2.TEMPORAL, t2.ADMISSION = f"127.0.0.1:{TEMPORAL_PORT}", API
t2.BASE_ENV.update(TEMPORAL_ADDRESS=t2.TEMPORAL, KP_ADMISSION_URL=API,
                   KP_S3_ENDPOINT=f"http://127.0.0.1:{S3_PORT}")  # fmt: skip
TENANT, SOURCE, RESOURCE = "t1", "km", "e2e-81"
PUBLIC = "https://kp.example"  # the api wants an https origin; uploads are sent to API instead
DONE = {"succeeded", "failed", "cancelled"}
TIMEOUT_S = 1800


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def not_accepted() -> float:
    with urllib.request.urlopen(f"http://127.0.0.1:{METRICS_PORT}/metrics", timeout=5) as r:
        text = r.read().decode()
    # Present before any increment (its HELP and TYPE lines): a missing series must not read 0.
    assert "# TYPE kp_admission_not_accepted_total counter" in text, "the counter is not exported"
    return sum(float(m.group(1)) for m in
               re.finditer(r"^kp_admission_not_accepted_total\{[^}]*\} (\S+)$", text, re.M))  # fmt: skip


async def finalize_seconds(client: Client, request_id: str) -> list[float]:
    """Each finalize Activity attempt's started-to-closed time, from the workflow history."""
    started, spans = {}, []
    async for event in client.get_workflow_handle(request_id).fetch_history_events():
        if event.HasField("activity_task_scheduled_event_attributes"):
            if event.activity_task_scheduled_event_attributes.activity_type.name == "finalize":
                started[event.event_id] = None
        elif event.HasField("activity_task_started_event_attributes"):
            scheduled = event.activity_task_started_event_attributes.scheduled_event_id
            if scheduled in started:
                started[scheduled] = event.event_time.ToDatetime(tzinfo=UTC)
        elif event.HasField("activity_task_completed_event_attributes"):
            scheduled = event.activity_task_completed_event_attributes.scheduled_event_id
            if started.get(scheduled):
                spans.append((event.event_time.ToDatetime(tzinfo=UTC) - started[scheduled]).total_seconds())
    return spans


async def submit(http: httpx.AsyncClient, index: str, data: bytes) -> dict:
    document_id = f"paper:{index}"
    sha = hashlib.sha256(data).hexdigest()
    declared = await http.post("/v1/batches", headers={"Idempotency-Key": secrets.token_hex(16)},
                               json={"items": [{"document_id": document_id, "source_version": "1",
                                                "resources": [RESOURCE], "title": f"paper {index}",
                                                "files": [{"path": f"{index}.pdf", "role": "main",
                                                           "sha256": sha, "size": len(data),
                                                           "media_type": "application/pdf"}]}]})  # fmt: skip
    assert declared.status_code == 201, declared.text
    batch = declared.json()
    item = batch["items"][0]
    assert item["status"] == "declared", item
    for upload in item["uploads"]:
        assert upload["url"].startswith(PUBLIC + "/"), upload
        put = await http.put(upload["url"].removeprefix(PUBLIC), content=data,
                             headers={"Content-Type": "application/pdf"})  # fmt: skip
        assert put.status_code == 204, put.text
    finalized = await http.post(f"/v1/batches/{batch['batch_id']}/finalize")
    assert finalized.status_code == 202, finalized.text
    item = finalized.json()["items"][0]
    assert "request_id" in item, item
    return {"document_id": document_id, "document_uid": item["document_uid"],
            "request_id": item["request_id"], "source_revision_id": item["source_revision_id"]}  # fmt: skip


async def case(http, reader, client, store, dsn, out, index, data) -> dict:
    head = (await reader.get("/read/v1/feed")).json()["next_cursor"]
    before = not_accepted()
    started = time.monotonic()
    ids = await submit(http, index, data)
    while True:
        request = (await http.get(f"/v1/requests/{ids['request_id']}")).json()
        if request.get("state") in DONE or time.monotonic() - started > TIMEOUT_S:
            break
        await asyncio.sleep(5)
    seconds = round(time.monotonic() - started, 1)
    await asyncio.sleep(2)  # the last report's acceptance is written with it; margin for the scrape
    after = not_accepted()
    events = (await reader.get("/read/v1/feed", params={"cursor": head, "limit": 1000})).json()["events"]
    state = (await reader.get(f"/read/v1/documents/{ids['document_uid']}/state")).json()
    document = (await http.get(f"/v1/documents/{ids['document_id']}")).json()
    with psycopg.connect(dsn) as conn:
        outcome = conn.execute("SELECT outcome FROM source_revision WHERE source_revision_id = %s",
                               (ids["source_revision_id"],)).fetchone()  # fmt: skip
        revision = conn.execute(
            "SELECT canonical_revision_id, content_ref, content_sha256, content_size, adopted_version"
            " FROM canonical_revision WHERE request_id = %s", (ids["request_id"],),
        ).fetchone()  # fmt: skip
    row = {**ids, "state": request.get("state"), "seconds": seconds,
           "request": request, "source_revision_outcome": outcome and outcome[0],
           "not_accepted_delta": after - before, "finalize_activity_s": [],
           "feed": [e for e in events if e.get("document_uid") == ids["document_uid"]],
           "read_state": state, "document": document}  # fmt: skip
    if revision:
        crv, ref, sha, size, version = revision
        body = await store.get(ref)
        (out / "content").mkdir(exist_ok=True)
        (out / "content" / f"{index}.json").write_bytes(body)
        content = json.loads(body)
        row |= {"canonical_revision": {"id": crv, "ref": ref, "sha256": sha, "size": size,
                                       "adopted_version": version},
                "stored_matches_row": hashlib.sha256(body).hexdigest() == sha and len(body) == size,
                "content": {"schema": content["schema"], "pages": len(content["pages"]),
                            "blocks": len(content["blocks"]), "artifacts": len(content["artifacts"]),
                            "tables_html": sum(1 for b in content["blocks"] if b["kind"] == "table"
                                               and b["markdown"].startswith("<table")),
                            "processing": content["processing"]}}  # fmt: skip
    row["finalize_activity_s"] = await finalize_seconds(client, ids["request_id"])
    row["pass"] = bool(
        row["state"] == "succeeded"
        and row["source_revision_outcome"] == "accepted"
        and revision
        and row["stored_matches_row"]
        and (state.get("current") or {}).get("canonical_revision_id") == revision[0]
        and any(e.get("kind") == "current_revision_changed" for e in row["feed"])
        and row["not_accepted_delta"] == 0
    )
    return row


def start(args: list[str], env: dict, log: Path) -> subprocess.Popen:
    return subprocess.Popen([str(t2.REPO / ".venv/bin/kp-admission"), *args], env=env, cwd=t2.REPO,
                            stdout=open(log, "a"), stderr=subprocess.STDOUT)  # fmt: skip


async def main(argv: list[str]) -> int:
    out, manifest, archive = Path(argv[0]).expanduser(), Path(argv[1]), Path(argv[2]).expanduser()
    package, python, indices = Path(argv[3]), argv[4], argv[5:]
    ports = (S3_PORT, TEMPORAL_PORT, TEMPORAL_PORT + 1, API_PORT, METRICS_PORT, VLM_PORT,
             SUMMARY_PORT, D3_PORT)  # fmt: skip
    if busy := [port for port in ports if t5.taken(port)]:
        raise SystemExit(f"ports already in use: {busy}")
    if out.exists() and any(out.iterdir()):
        raise SystemExit("OUT is not empty: use a new one")
    out.mkdir(parents=True, exist_ok=True)
    t2.LOGS = out / "logs"
    t2.LOGS.mkdir()
    (out / "papers").mkdir()
    corpus = {str(p["index"]): p for p in json.loads(manifest.read_text())["papers"]}
    if any(i != "w2" for i in indices):
        r199.check_key()
    profile, differs = r199.run_profile(out)
    bucket = f"e2e-81-{t2.RUN}"
    source, report, pep = (secrets.token_urlsafe(24) for _ in range(3))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    processes: list[subprocess.Popen] = []
    workers: dict[str, subprocess.Popen] = {}
    servers = []
    s3 = r199.s3_up(out, S3_PORT)
    try:
        with PostgresContainer("postgres:17.10-alpine", driver=None) as pg:
            dsn = pg.get_connection_url()
            with psycopg.connect(dsn, autocommit=True) as conn:
                conn.execute(SCHEMA)
            store = t2.store(bucket)
            env = {**t2.env(bucket), "KP_ADMISSION_DATABASE_URL": dsn,
                   "KP_AUTHZ_PROVIDER": "allow-all", "KP_DEPLOYMENT": "pilot",
                   "KP_ADMISSION_API_PORT": str(API_PORT), "KP_ADMISSION_PUBLIC_URL": PUBLIC,
                   "KP_CREDENTIALS": json.dumps({digest(source): {
                       "credential_id": "km-1", "tenant_id": TENANT, "source_id": SOURCE,
                       "scopes": ["submit", "manage_relations"]}}),
                   "KP_PIPELINES": json.dumps({digest(report): {
                       "pipeline_id": "kp-canonicalization", "track": "canonical",
                       "stages": ["prepare", "parse", "enrich", "finalize"],
                       "start_deadline_s": 1800, "update_interval_s": 1800}}),
                   "KP_AUTHZ_PEP_CREDENTIALS": json.dumps({digest(pep): "e2e-reader"})}  # fmt: skip
            adopted = subprocess.run(
                [str(t2.REPO / ".venv/bin/kp-admission"), "adopt", "--tenant", TENANT,
                 "application/pdf", "paper-pdf@1"], env=env, capture_output=True, text=True,
            )  # fmt: skip
            assert adopted.returncode == 0, adopted.stderr
            key = secrets.token_hex(16)
            d3_env = {"KP_D3_BASE_URL": f"http://127.0.0.1:{D3_PORT}", "KP_D3_API_KEY": key}
            d3 = subprocess.Popen(
                [python, str(package / "d3_server.py"), "--device", "mps", "--batch-size", "1",
                 "--port", str(D3_PORT)],
                env={**os.environ, "DECISION_API_KEY": key, "HF_HUB_OFFLINE": "1",
                     "TRANSFORMERS_OFFLINE": "1", "PYTORCH_ENABLE_MPS_FALLBACK": "0"},
                stdout=open(t2.LOGS / "d3-server.log", "a"), stderr=subprocess.STDOUT,
            )  # fmt: skip
            temporal = subprocess.Popen(
                ["temporal", "server", "start-dev", "--headless", "--port", str(TEMPORAL_PORT),
                 "--ui-port", str(TEMPORAL_PORT + 1), "--db-filename", str(out / "temporal.db"),
                 "--log-level", "warn", *t2.SEARCH_ATTRIBUTE_FLAGS],
                stdout=open(t2.LOGS / "temporal.log", "a"), stderr=subprocess.STDOUT,
            )  # fmt: skip
            processes += [d3, temporal]
            servers = [t5.stand_in(t5c.Replay, VLM_PORT), t5.stand_in(t5c.Summary, SUMMARY_PORT)]
            serves = t5c.wait_for_d3(d3, key)
            client = None
            for _ in range(60):
                try:
                    client = await Client.connect(t2.TEMPORAL)
                    break
                except RuntimeError:
                    await asyncio.sleep(0.5)
            assert client is not None
            processes += [start(["api", "--metrics-port", str(METRICS_PORT)], env, t2.LOGS / "api.log"),
                          start(["dispatcher"], env, t2.LOGS / "dispatcher.log")]  # fmt: skip
            for _ in range(60):
                if t5.taken(API_PORT) and t5.taken(METRICS_PORT):
                    break
                await asyncio.sleep(0.5)
            rows, real = {}, None
            async with (
                httpx.AsyncClient(base_url=API, headers={"Authorization": f"Bearer {source}"},
                                  timeout=60) as http,
                httpx.AsyncClient(base_url=API, headers={"Authorization": f"Bearer {pep}"},
                                  timeout=60) as reader,
            ):  # fmt: skip
                registered = await http.put(f"/v1/resources/{RESOURCE}")
                assert registered.status_code in (200, 201), registered.text
                for index in indices:
                    if real != (index != "w2"):
                        real = index != "w2"
                        t5c.stop(list(workers.values()))
                        envs = r199.worker_env(real, d3_env)
                        envs["orchestration"] = {"KP_ADMISSION_URL": API, "KP_ADMISSION_TOKEN": report}
                        workers = {q: t5c.worker(bucket, "real" if real else "stand-in", q,
                                                 profile, extra)
                                   for q, extra in envs.items()}  # fmt: skip
                    if index == "w2":
                        data = (archive / r199.W2).read_bytes()
                    else:
                        data = (manifest.parent / corpus[index]["file"]).read_bytes()
                        assert hashlib.sha256(data).hexdigest() == corpus[index]["sha256"]
                    row = await case(http, reader, client, store, dsn, out, index, data)
                    row |= {"paper_sha256": hashlib.sha256(data).hexdigest(),
                            "services": "providers" if real else "stand-ins"}  # fmt: skip
                    (out / "papers" / f"{index}.json").write_text(json.dumps(row, indent=1) + "\n")
                    rows[index] = row
                    print(index, json.dumps({k: row.get(k) for k in (
                        "pass", "state", "seconds", "source_revision_outcome",
                        "not_accepted_delta", "finalize_activity_s")}), flush=True)  # fmt: skip
    finally:
        t5c.stop([*workers.values(), *processes])
        for server in servers:
            server.shutdown()
        subprocess.run(["docker", "stop", s3], capture_output=True)
    summary = {
        "profile_differs_from_released": differs, "d3_server": serves,
        "papers": {i: {k: r.get(k) for k in (
            "pass", "state", "seconds", "services", "paper_sha256", "source_revision_outcome",
            "not_accepted_delta", "finalize_activity_s", "stored_matches_row", "content")}
            | {"feed_kinds": [e.get("kind") for e in r["feed"]],
               "current": r["read_state"].get("current"),
               "candidate_ref_form": (r.get("canonical_revision") or {}).get("ref", "").startswith(
                   f"documents/{r['document_uid']}/revisions/crv_")}
            for i, r in rows.items()},
    }  # fmt: skip
    (HERE / "e2e.json").write_text(json.dumps(summary, indent=1) + "\n")
    failed = [i for i in indices if not rows.get(i, {}).get("pass")]
    print("failed:", failed or "none", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
