"""#98 acceptance: how long Source Deletion takes to reach `applied` and `enforced`, against the
targets of admission spec §11 (1 minute, 10 minutes).

Starts PostgreSQL 17 with Testcontainers, serves the platform API in process, and holds N
accepted Documents, each included by one serving Build of `retrieval`. It times each
`DELETE /v1/documents/{id}`, one call at a time and 32 at once: the deletion is applied when the
call returns. The projection then reports every Document removed, as one facts call, and one
`enforce` run judges them; a Document whose removal is never reported is the control, which
must stay `applied`. Writes the readings to evidence.json next to this file and exits 1 when a
check fails.

    .venv/bin/python docs/validation/98/timing.py
"""

import asyncio
import hashlib
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psycopg
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool
from testcontainers.community.postgres import PostgresContainer

from kp_admission import SCHEMA, deletion
from kp_admission.api import SourceCredential, app
from kp_admission.authz import AllowAll
from kp_admission.batches import Intake
from kp_admission.cli import POOL_SIZE
from kp_admission.reports import Pipeline
from kp_admission.requests import Candidate, record_outcome
from kp_admission.storage import FakeObjectStore

N, CONCURRENCY = 500, 32
APPLIED_TARGET_S, ENFORCED_TARGET_S = 60, 600
RETRIEVAL = Pipeline(
    pipeline_id="kp-retrieval",
    track="retrieval",
    stages=["read", "index"],
    start_deadline_s=600,
    update_interval_s=600,
)
FILES = [{"path": "a.pdf", "role": "main", "custody_ref": "s3://k/a", "sha256": "a" * 64,
          "size": 1, "media_type": "application/pdf"}]  # fmt: skip


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def summary(samples: list[float]) -> dict:
    ms = sorted(s * 1000 for s in samples)
    return {
        "calls": len(ms),
        "p50_ms": round(statistics.median(ms), 2),
        "p99_ms": round(ms[int(len(ms) * 0.99) - 1], 2),
        "max_ms": round(ms[-1], 2),
    }


async def documents(conn, n: int) -> list[tuple[str, str, str]]:
    """n accepted Documents of Source s1: (document_id, uid, srv, crv)."""
    made = []
    for k in range(n):
        uid, srv, request_id = f"doc_{k:04}", f"srv_{k:04}", f"req_{k:032x}"
        await conn.execute(
            "INSERT INTO document (document_uid, tenant_id, source_id, document_id, resource_id)"
            " VALUES (%s, 't1', 's1', %s, 's1/r')",
            (uid, f"d{k:04}"),
        )
        await conn.execute(
            "INSERT INTO source_revision (source_revision_id, tenant_id, document_uid, files,"
            " sequence) VALUES (%s, 't1', %s, %s, 1)",
            (srv, uid, Jsonb(FILES)),
        )
        await conn.execute(
            "UPDATE document SET latest_source_revision_id = %s WHERE document_uid = %s", (srv, uid)
        )
        await conn.execute(
            "INSERT INTO request (request_id, tenant_id, kind, document_uid, source_revision_id,"
            " state, initiator, priority, adopted_version, adoption_sequence, trace_id) VALUES"
            " (%s, 't1', 'process', %s, %s, 'processing', 'source', 'normal', 'paper-pdf@1', 1,"
            " 't')",
            (request_id, uid, srv),
        )
        crv = "crv_" + request_id.removeprefix("req_")
        ref = f"documents/{uid}/revisions/{crv}.json"
        assert await record_outcome(
            conn, request_id, "succeeded", None, None, Candidate(ref=ref, sha256="c" * 64, size=1)
        )
        made.append((f"d{k:04}", uid, srv, crv))
    return made


def fact(uid: str, srv: str, crv: str, version: int, state: str) -> dict:
    return {"document_uid": uid, "resource_id": "s1/r", "source_revision_id": srv,
            "canonical_revision_id": crv, "fact_version": version, "state": state,
            "issued_at": "2026-11-24T08:00:00Z"}  # fmt: skip


async def main() -> int:
    with PostgresContainer("postgres:17.10-alpine", driver=None) as container:
        url = container.get_connection_url()
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(SCHEMA)
        async with (
            AsyncConnectionPool(url, max_size=POOL_SIZE, kwargs={"autocommit": True}) as pool,
            await psycopg.AsyncConnection.connect(url, autocommit=True) as conn,
        ):
            credential = SourceCredential.model_validate(
                {"credential_id": "s1-1", "tenant_id": "t1", "source_id": "s1",
                 "scopes": ["submit"]}
            )  # fmt: skip
            application = app(
                AllowAll(pool),
                {digest("retrieval"): "retrieval"},
                {digest("s1"): credential},
                pool,
                Intake(FakeObjectStore()),
                pipelines={digest("retrieval"): RETRIEVAL},
            )

            def client(token: str) -> httpx.AsyncClient:
                return httpx.AsyncClient(
                    transport=httpx.ASGITransport(application),
                    base_url="http://api",
                    headers={"authorization": f"Bearer {token}"},
                )

            made = await documents(conn, 2 * N + 1)
            serial, burst, control = made[:N], made[N : 2 * N], made[-1]
            async with client("retrieval") as projection, client("s1") as source:
                head = (await projection.get("/read/v1/feed")).json()["next_cursor"]
                built = await projection.put(
                    "/report/v1/builds/b1",
                    json={"state": "serving", "switch_seq": 1, "replaces": None,
                          "feed_position": head},
                )  # fmt: skip
                assert built.status_code == 200, built.text
                for start in range(0, len(made), 1000):
                    page = [fact(u, s, c, 1, "included") for _, u, s, c in made[start:start + 1000]]
                    assert (await projection.post("/report/v1/builds/b1/facts",
                                                  json={"facts": page})).status_code == 200  # fmt: skip

                async def delete(document_id: str) -> float:
                    began = time.perf_counter()
                    answer = await source.delete(f"/v1/documents/{document_id}")
                    took = time.perf_counter() - began
                    assert answer.status_code == 202 and answer.json()["state"] == "applied"
                    return took

                one_at_a_time = [await delete(d) for d, *_ in serial]
                gate = asyncio.Semaphore(CONCURRENCY)

                async def bounded(document_id: str) -> float:
                    async with gate:
                        return await delete(document_id)

                at_once = await asyncio.gather(*(bounded(d) for d, *_ in burst))
                await delete(control[0])

                removed_at = time.perf_counter()
                gone = [fact(u, s, c, 2, "removed") for _, u, s, c in serial + burst]
                for start in range(0, len(gone), 1000):
                    page = gone[start : start + 1000]
                    answer = await projection.post("/report/v1/builds/b1/facts",
                                                   json={"facts": page})  # fmt: skip
                    assert answer.status_code == 200
                reported = time.perf_counter() - removed_at

            judged_at = time.perf_counter()
            judged = await deletion.enforce(conn, {"retrieval": RETRIEVAL}, datetime.now(UTC))
            judging = time.perf_counter() - judged_at
            states = dict(
                await (
                    await conn.execute(
                        "SELECT state, count(*) FROM request WHERE kind = 'delete' GROUP BY 1"
                    )
                ).fetchall()
            )

    readings = {
        "documents": 2 * N + 1,
        "delete_one_at_a_time": summary(one_at_a_time),
        f"delete_{CONCURRENCY}_at_once": summary(list(at_once)),
        "removal_report_s": round(reported, 3),
        "enforce_run_s": round(judging, 3),
        "judged": dict(judged),
        "delete_requests_by_state": states,
    }
    worst_applied = max(max(one_at_a_time), max(at_once))
    checks = {
        "every deletion is applied within its target": 0 < worst_applied <= APPLIED_TARGET_S,
        "one run judges every removed Document enforced": judged["enforced"] == 2 * N,
        "control: the Document still included stays applied": (
            judged["held"] == 1 and states == {"enforced": 2 * N, "applied": 1}
        ),
        "the platform's share of enforced is within its target": (
            0 < reported + judging <= ENFORCED_TARGET_S
        ),
    }
    readings["checks"] = checks
    (Path(__file__).parent / "evidence.json").write_text(json.dumps(readings, indent=2) + "\n")
    print(json.dumps(readings, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
