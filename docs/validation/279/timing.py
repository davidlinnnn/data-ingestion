"""#279 acceptance: how long after a deletion or a rebind is written the reference projection's
query stops finding the Document.

Starts PostgreSQL 17 with Testcontainers and serves the platform API in process, as #127's
tests do (content reads from fixtures until #268). The reader runs as its process does
(`Projection.run`, `poll_s` 1 s, 4 workers and 1 narrowing worker), and the query app answers
over ASGI for a user who may read `s1/hr-all` only. N Documents are written and found; then,
one at a time, each is deleted or rebound to `s1/legal`, and the query is repeated every 10 ms
until it no longer finds the Document. The time runs from the commit of the call that appends
the event to the first answer without it. A control Document, never changed, must still be
found at the end. Writes the readings to evidence.json next to this file and exits 1 when a
check fails.

    .venv/bin/python docs/validation/279/timing.py
"""

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import httpx
import psycopg
from psycopg.conninfo import make_conninfo
from psycopg_pool import AsyncConnectionPool
from testcontainers.community.postgres import PostgresContainer

sys.path.insert(0, str(Path(__file__).parents[3]))  # the test helpers build the fixtures

from kp_admission import SCHEMA as ADMISSION  # noqa: E402
from kp_admission.api import app  # noqa: E402
from kp_reference_projection import SCHEMA, query  # noqa: E402
from kp_reference_projection.projection import Projection  # noqa: E402
from kp_sdk.projection import ProjectionClient  # noqa: E402
from tests.admission.authz_fake import FakeAuthorizer  # noqa: E402
from tests.admission.support import INTAKE  # noqa: E402
from tests.admission.test_reference_projection import PIPELINES, Platform  # noqa: E402
from tests.admission.test_reference_query import USERS, delete, rebind  # noqa: E402
from tests.admission.test_serving import accepted, profile  # noqa: E402
from tests.admission.test_status import credential, digest, document  # noqa: E402

N = 20  # per kind
TARGET_S = 600  # `enforced` within 10 minutes (spec §11)


async def found(client: httpx.AsyncClient, word: str) -> bool:
    response = await client.post("/v1/entries:search", json={"query": word},
                                 headers={"authorization": "Bearer alice-token"})  # fmt: skip
    response.raise_for_status()
    return bool(response.json()["results"])


async def until_gone(client: httpx.AsyncClient, word: str, started: float) -> float:
    while await found(client, word):
        await asyncio.sleep(0.01)
    return time.monotonic() - started


def summary(samples: list[float]) -> dict:
    ordered = sorted(samples)
    return {
        "n": len(ordered),
        "p50_s": round(statistics.median(ordered), 3),
        "max_s": round(ordered[-1], 3),
        "min_s": round(ordered[0], 3),
    }


async def measure(admission: str, store_url: str) -> dict:
    async with (
        AsyncConnectionPool(admission, kwargs={"autocommit": True}) as pool,
        AsyncConnectionPool(store_url, kwargs={"autocommit": True}) as store,
        await psycopg.AsyncConnection.connect(admission, autocommit=True) as conn,
    ):
        platform = Platform(app(
            FakeAuthorizer(resource_ids=("s1/hr-all",)),
            {digest("retrieval"): "retrieval"},
            {digest("s1"): credential("s1")},
            pool,
            INTAKE,
            pipelines={digest("retrieval"): PIPELINES["retrieval"]},
        ))  # fmt: skip
        reader_sdk = ProjectionClient("http://api", "retrieval", "retrieval", transport=platform)
        query_sdk = ProjectionClient("http://api", "retrieval", "retrieval", transport=platform)
        await profile(conn, "retrieval")
        reader = Projection(reader_sdk, store, "b1")
        stop = asyncio.Event()
        task = asyncio.create_task(reader.run(stop, 4, 1, 60))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(query.app(query_sdk, store, USERS)),
            base_url="http://query",
        ) as client:
            ids = [f"D{i}" for i in range(2 * N + 1)]  # the last one is the control
            for document_id in ids:
                uid, srv = await document(conn, document_id)
                platform.contents[f"crv_{document_id}"] = [f"word{document_id.lower()} body"]
                await accepted(conn, uid, srv, f"crv_{document_id}")
            for document_id in ids:
                while not await found(client, f"word{document_id.lower()}"):
                    await asyncio.sleep(0.05)
            deleted, rebound = [], []
            for document_id in ids[:N]:
                await delete(conn, document_id)
                started = time.monotonic()
                deleted.append(await until_gone(client, f"word{document_id.lower()}", started))
            for document_id in ids[N : 2 * N]:
                await rebind(conn, f"doc_s1_{document_id}", "s1/legal")
                started = time.monotonic()
                rebound.append(await until_gone(client, f"word{document_id.lower()}", started))
            control = await found(client, f"word{ids[-1].lower()}")
        stop.set()
        await task
        await reader_sdk.aclose()
        await query_sdk.aclose()
    return {"deletion": summary(deleted), "rebind": summary(rebound), "control_found": control}


def main() -> int:
    with PostgresContainer("postgres:17.10-alpine", driver=None) as container:
        url = container.get_connection_url()
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute("CREATE DATABASE admission")
            conn.execute("CREATE DATABASE projection")
        admission, store = make_conninfo(url, dbname="admission"), make_conninfo(url, dbname="projection")  # fmt: skip
        with psycopg.connect(admission, autocommit=True) as conn:
            conn.execute(ADMISSION)
        with psycopg.connect(store, autocommit=True) as conn:
            conn.execute(SCHEMA)
        readings = asyncio.run(measure(admission, store))
    checks = {
        "deletion within the target": 0
        <= readings["deletion"]["min_s"]
        <= readings["deletion"]["max_s"]
        <= TARGET_S,
        "rebind within the target": 0
        <= readings["rebind"]["min_s"]
        <= readings["rebind"]["max_s"]
        <= TARGET_S,
        "the control is still found": readings["control_found"],
    }
    evidence = {"readings": readings, "checks": checks}
    (Path(__file__).parent / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
