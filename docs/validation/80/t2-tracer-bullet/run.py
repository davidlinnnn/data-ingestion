"""Seam B for #131: one paper through the real stack, uninterrupted and with a killed worker.

    .venv/bin/python docs/validation/80/t2-tracer-bullet/run.py CORPUS_MANIFEST [PAPER_INDEX]

Needs the S3 stand-in (tests/s3/compose.yaml, port 9100), the `temporal` CLI and the model
weights. Starts its own Temporal dev server (port 7244) and fake_admission (port 8091), runs
kp-processing workers as subprocesses with the DEV profile, and writes evidence.json plus each
case's result and received reports next to this file. The paper itself stays out of git.

Cases:
  A  uninterrupted run in a fresh bucket
  B  the same paper in another fresh bucket; the inference worker is killed (SIGKILL) once two
     groups are registered and restarted; the result must equal A's
  C  a new request for B's document: every registered item is reused
  D  the start input of A again: counts as success, nothing reruns
  E  the report receiver is down: processing still completes
  F  a password-protected PDF and an adopted_version mismatch: failure reports
"""

import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from botocore.exceptions import ClientError
from temporalio.client import Client

from kp_processing.ports.object_store import S3ObjectStore

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TEMPORAL = "127.0.0.1:7244"
ADMISSION = "http://127.0.0.1:8091"
RUN = uuid.uuid4().hex[:6]
BASE_ENV = {
    **os.environ,
    "KP_S3_ENDPOINT": "http://127.0.0.1:9100",
    "AWS_ACCESS_KEY_ID": "kpdev",
    "AWS_SECRET_ACCESS_KEY": "kpdev-secret",
    "TEMPORAL_ADDRESS": TEMPORAL,
    "KP_ADMISSION_URL": ADMISSION,
    "HF_HUB_OFFLINE": "1",
}
CLI = [str(REPO / ".venv/bin/kp-processing")]
PROFILE = str(REPO / "tests/profiles/paper-pdf-dev.yaml")
LOGS = Path(os.environ.get("SEAMB_LOGS", "/tmp")) / f"seamb-{RUN}"


def env(bucket: str) -> dict[str, str]:
    return {**BASE_ENV, "KP_S3_BUCKET": bucket}


def store(bucket: str) -> S3ObjectStore:
    os.environ.update(env(bucket))
    s = S3ObjectStore.from_env()
    try:
        s.client.head_bucket(Bucket=bucket)
    except ClientError:
        s.client.create_bucket(Bucket=bucket)
    return s


def worker(bucket: str, name: str, queue: str) -> subprocess.Popen:
    log = open(LOGS / f"worker-{name}-{queue}.log", "w")
    return subprocess.Popen(
        [*CLI, "worker", "--queue", queue, "--profile", PROFILE,
         "--build-id", "seamb-r1"],
        env=env(bucket), stdout=log, stderr=subprocess.STDOUT, cwd=REPO,
    )  # fmt: skip


def workers_for(bucket: str, name: str) -> list[subprocess.Popen]:
    """One process per task queue; the inference one last."""
    return [worker(bucket, name, q) for q in ("orchestration", "inference")]


def start_input(sha: str, data: bytes, bucket: str, request_id: str, **overrides) -> dict:
    start = {
        "request_id": request_id,
        "document_uid": f"doc_{sha[:16]}",
        "source_revision_id": "srv_1",
        "files": [{"path": "paper.pdf", "role": "main",
                   "custody_ref": f"s3://{bucket}/custody/{sha}", "sha256": sha,
                   "size": len(data), "media_type": "application/pdf"}],
        "adopted_version": "paper-pdf@1",
        "adoption_sequence": 1,
        "initiator": "source",
        "priority": "normal",
        "trace_id": sha[:16],
    }  # fmt: skip
    return {**start, **overrides}


def start_request(bucket: str, start: dict, wait: bool = True) -> tuple[int, str]:
    path = LOGS / f"{start['request_id']}.json"
    path.write_text(json.dumps(start))
    done = subprocess.run(
        [*CLI, "start-request", str(path), *(["--wait"] if wait else [])],
        env=env(bucket), capture_output=True, text=True, cwd=REPO,
    )  # fmt: skip
    return done.returncode, done.stdout + done.stderr


async def reports(request_id: str) -> list[dict]:
    async with httpx.AsyncClient() as http:
        return (await http.get(f"{ADMISSION}/v1/requests/{request_id}/status-reports")).json()


async def activity_history(client: Client, request_id: str) -> list[dict]:
    """Per Activity execution: type, attempt that completed, and the reused flag."""
    history = await client.get_workflow_handle(request_id).fetch_history()
    scheduled, started, out = {}, {}, []
    for event in history.events:
        if event.HasField("activity_task_scheduled_event_attributes"):
            scheduled[event.event_id] = event.activity_task_scheduled_event_attributes.activity_type.name
        elif event.HasField("activity_task_started_event_attributes"):
            a = event.activity_task_started_event_attributes
            started[a.scheduled_event_id] = a.attempt
        elif event.HasField("activity_task_completed_event_attributes"):
            a = event.activity_task_completed_event_attributes
            payload = json.loads(a.result.payloads[0].data) if a.result.payloads else None
            out.append({
                "activity": scheduled[a.scheduled_event_id],
                "attempt": started.get(a.scheduled_event_id),
                "reused": payload.get("reused") if isinstance(payload, dict) else None,
            })  # fmt: skip
    return out


async def wait_for_groups(s: S3ObjectStore, uid: str, count: int) -> float:
    begin = time.monotonic()
    while True:
        keys = await s.list_prefix(f"documents/{uid}/items/")
        if sum(k.endswith("/group.json") for k in keys) >= count:
            return time.monotonic() - begin
        await asyncio.sleep(0.5)


def shape(received: list[dict]) -> list[list]:
    return [[r["seq"], r["stage"], r["state"], r["progress"]] for r in received]


async def main(manifest: Path, index: int) -> int:
    LOGS.mkdir(parents=True)
    paper = next(p for p in json.loads(manifest.read_text())["papers"] if p["index"] == index)
    data = (manifest.parent / paper["file"]).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    assert sha == paper["sha256"], "paper does not match the corpus manifest"
    uid = f"doc_{sha[:16]}"
    evidence: dict = {"run": RUN, "paper": {k: paper[k] for k in ("index", "file", "sha256", "pages")}}

    temporal = subprocess.Popen(
        ["temporal", "server", "start-dev", "--headless", "--port", "7244", "--ui-port", "7245",
         "--db-filename", str(LOGS / "temporal.db"), "--log-level", "warn"],
        stdout=open(LOGS / "temporal.log", "w"), stderr=subprocess.STDOUT,
    )  # fmt: skip
    admission = subprocess.Popen(
        [str(REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server", "--port", "8091",
         "--log", str(LOGS / "reports.jsonl")], cwd=REPO,
    )  # fmt: skip
    workers: list[subprocess.Popen] = []
    try:
        for _ in range(60):
            try:
                client = await Client.connect(TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        evidence["temporal"] = subprocess.run(
            ["temporal", "--version"], capture_output=True, text=True
        ).stdout.strip()

        # A: uninterrupted
        bucket_a, bucket_b = f"seamb-{RUN}-a", f"seamb-{RUN}-b"
        sa, sb = store(bucket_a), store(bucket_b)
        for s in (sa, sb):
            await s.put_if_absent(f"custody/{sha}", data)
        workers += workers_for(bucket_a, "a")
        a = start_input(sha, data, bucket_a, f"req_{RUN}_a")
        begin = time.monotonic()
        code, out = start_request(bucket_a, a)
        evidence["A"] = {"exit": code, "seconds": round(time.monotonic() - begin, 1),
                         "outcome": out.strip().splitlines()[-1]}  # fmt: skip
        result_a = json.loads(await sa.get(f"requests/{a['request_id']}/result.json"))
        evidence["A"]["reports"] = shape(await reports(a["request_id"]))
        evidence["A"]["activities"] = await activity_history(client, a["request_id"])
        (HERE / "result-A.json").write_text(json.dumps(result_a, indent=2) + "\n")
        (HERE / "reports-A.json").write_text(json.dumps(await reports(a["request_id"]), indent=2) + "\n")
        # Both buckets' workers share the task queues, so only one set may run at a time.
        while workers:
            workers[-1].terminate()
            workers.pop().wait()

        # B: kill the worker once two groups are registered, then restart it
        workers += workers_for(bucket_b, "b1")
        b = start_input(sha, data, bucket_b, f"req_{RUN}_b")
        begin = time.monotonic()
        code, _ = start_request(bucket_b, b, wait=False)
        killed_after = await wait_for_groups(sb, uid, 2)
        workers[-1].send_signal(signal.SIGKILL)
        workers[-1].wait()
        groups_at_kill = sum(k.endswith("/group.json") for k in await sb.list_prefix(f"documents/{uid}/items/"))
        workers.pop()
        workers.append(worker(bucket_b, "b2", "inference"))
        code, out = start_request(bucket_b, b)
        result_b = json.loads(await sb.get(f"requests/{b['request_id']}/result.json"))
        evidence["B"] = {
            "exit": code, "seconds": round(time.monotonic() - begin, 1),
            "killed_after_s": round(killed_after, 1), "groups_registered_at_kill": groups_at_kill,
            "outcome": out.strip().splitlines()[-1],
            "reports": shape(await reports(b["request_id"])),
            "activities": await activity_history(client, b["request_id"]),
            "native_equals_A": result_b["native"] == result_a["native"],
            "inventory_equals_A": result_b["inventory"] == result_a["inventory"],
            "profile_equals_A": result_b["profile"] == result_a["profile"],
        }  # fmt: skip

        # C: a new request for B's document reuses every registered item
        c = start_input(sha, data, bucket_b, f"req_{RUN}_c")
        begin = time.monotonic()
        code, out = start_request(bucket_b, c)
        evidence["C"] = {"exit": code, "seconds": round(time.monotonic() - begin, 1),
                         "activities": await activity_history(client, c["request_id"])}  # fmt: skip

        # D: starting A's request again counts as success
        code, out = start_request(bucket_b, a, wait=False)
        evidence["D"] = {"exit": code, "output": out.strip()}

        # E: the report receiver is down
        admission.terminate()
        admission.wait()
        e = start_input(sha, data, bucket_b, f"req_{RUN}_e")
        begin = time.monotonic()
        code, out = start_request(bucket_b, e)
        evidence["E"] = {"exit": code, "seconds": round(time.monotonic() - begin, 1),
                         "result_registered": await sb.head(f"requests/{e['request_id']}/result.json") is not None}  # fmt: skip
        admission = subprocess.Popen(
            [str(REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server", "--port", "8091",
             "--log", str(LOGS / "reports.jsonl")], cwd=REPO,
        )  # fmt: skip
        await asyncio.sleep(1)

        # F: failure reports
        sys.path.insert(0, str(REPO))
        from tests.pdfs import encrypt, paper as synthetic, write_pdf

        locked = encrypt(write_pdf(synthetic(2)))
        locked_sha = hashlib.sha256(locked).hexdigest()
        await sb.put_if_absent(f"custody/{locked_sha}", locked)
        cases = {
            "password": start_input(locked_sha, locked, bucket_b, f"req_{RUN}_f1"),
            "version": start_input(sha, data, bucket_b, f"req_{RUN}_f2", adopted_version="paper-pdf@2"),
        }
        evidence["F"] = {}
        for name, start in cases.items():
            code, out = start_request(bucket_b, start)
            failure = json.loads(await sb.get(f"requests/{start['request_id']}/failure.json"))
            received = await reports(start["request_id"])
            evidence["F"][name] = {
                "exit": code, "cause": failure["cause"], "stage": failure["stage"],
                "reason": failure["error"]["reason"], "category": failure["error"]["metadata"]["category"],
                "reports": shape(received), "last_report_error_reason": received[-1]["error"]["reason"],
                "last_report_manifest_ref": received[-1]["manifest_ref"],
            }  # fmt: skip
            (HERE / f"failure-{name}.json").write_text(json.dumps(failure, indent=2) + "\n")
    finally:
        for p in (*workers, admission, temporal):
            p.terminate()
    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    print(f"logs in {LOGS}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 2)))
