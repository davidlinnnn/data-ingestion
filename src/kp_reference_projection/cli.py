"""`kp-reference-projection`: the reference projection's reader process (#127, #280): the
Change Feed reader, its workers, the heartbeat of every Build not retired and the retirement of
expired ones, until SIGTERM or SIGINT.

Environment:

- KP_PLATFORM_URL: the platform API's origin.
- KP_PROJECTION_CREDENTIAL: the service credential, registered under KP_PROJECTION_NAME both in
  KP_AUTHZ_PEP_CREDENTIALS and in KP_PIPELINES, with `stages` ["write"] (spec §7.4).
- KP_PROJECTION_NAME: the projection, as the Knowledge Profiles name it (default `retrieval`).
- KP_PROJECTION_BUILD_ID: the Build that should serve (default `b1`; ruling A2 on #280). An id
  not seen before starts a new Build, which reads every Source and switches once it passes the
  gates; the one it replaces is retained. The id of a retained Build switches back to it, a
  rollback. A candidate no longer named is given up: its data cleared, it is reported retired.
- KP_PROJECTION_RETENTION_S (default 604800, 7 days, DR D2): how long a replaced Build is kept.
- KP_PROJECTION_APPROVAL_REF, KP_PROJECTION_EVIDENCE_REF (optional): recorded with the switch and
  sent with it; not in production, so no approval is waited for (ruling A3).
- KP_PROJECTION_DATABASE_URL: its own PostgreSQL database; the schema is applied at start.
- KP_PROJECTION_WORKERS (default 4) and KP_PROJECTION_NARROWING_WORKERS (default 1): the fixed
  worker counts; narrowing workers take deletions and rebinds only.
- KP_PROJECTION_HEARTBEAT_S (default 60): below the pipeline's update_interval_s.
- KP_PROJECTION_METRICS_PORT (default 9100): Prometheus metrics at /metrics.

Exit codes: 0 after SIGTERM or SIGINT (the run in progress finishes first; a run cut short is
taken again at the next start); 1 on a failure, such as an expired cursor, which needs a
bootstrap (#281), a Build the platform already serves started on a new database, or a retired
KP_PROJECTION_BUILD_ID, each of which needs a new KP_PROJECTION_BUILD_ID; 2 for a missing or
malformed setting; 3 when another process already runs against the same database. One process
per database, so its Deployment uses the `Recreate` strategy; a run in progress may take up to
600 s, so a shorter termination grace period only means that run is taken again at the next
start.

Metrics, for alerts (CODING_STANDARDS § Logs and metrics): `kp_projection_write_seconds` (a
registration to its confirmation), `kp_projection_removal_seconds` (a narrowing event to its
removal taken), `kp_projection_failures_total{step, reason}` (feed reads, cursor reports, runs,
source passes, switches, retirements and heartbeats that failed: `read_feed`, `report_cursor`,
`reconcile`, `reconcile_source`, `switch`, `retire`, `heartbeat`),
`kp_projection_backlog{priority}` (a new Build's first reads are `background`) and
`kp_projection_source_passes`; the reader's lag is the platform's
`kp_feed_consumer_lag_seconds{projection}`. Log lines carry `projection`, `build_id`,
`switch_seq`, `source_id`, `profile_seq`, `document_uid`, `resource_id`, `fact_version`,
`state`, `attempt_no`, `kind`, `position`, `reason` and `gate` as they apply, never content or
an error's message.
"""

import asyncio
import json
import logging
import os
import signal

import prometheus_client
import psycopg
import uvicorn
from psycopg_pool import AsyncConnectionPool

from kp_reference_projection import SCHEMA, query
from kp_reference_projection.projection import RETENTION_S, Expired, Projection, Retired
from kp_sdk.projection import ProjectionClient

log = logging.getLogger(__name__)
LOCK = 127_127  # the advisory lock that keeps one process per database


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # a line per poll otherwise
    try:
        settings = {
            "url": os.environ["KP_PLATFORM_URL"],
            "credential": os.environ["KP_PROJECTION_CREDENTIAL"],
            "dsn": os.environ["KP_PROJECTION_DATABASE_URL"],
            "projection": os.environ.get("KP_PROJECTION_NAME", "retrieval"),
            "build_id": os.environ.get("KP_PROJECTION_BUILD_ID", "b1"),
            "workers": int(os.environ.get("KP_PROJECTION_WORKERS", "4")),
            "narrowing_workers": int(os.environ.get("KP_PROJECTION_NARROWING_WORKERS", "1")),
            "heartbeat_s": float(os.environ.get("KP_PROJECTION_HEARTBEAT_S", "60")),
            "metrics_port": int(os.environ.get("KP_PROJECTION_METRICS_PORT", "9100")),
            "retention_s": float(os.environ.get("KP_PROJECTION_RETENTION_S", RETENTION_S)),
            "approval_ref": os.environ.get("KP_PROJECTION_APPROVAL_REF") or None,
            "evidence_ref": os.environ.get("KP_PROJECTION_EVIDENCE_REF") or None,
        }
    except KeyError as missing:
        log.error("setting missing: %s", missing.args[0])
        return 2
    except ValueError:
        log.error("a numeric KP_PROJECTION_ setting is not a number")
        return 2
    return asyncio.run(run(**settings))


async def run(
    url: str,
    credential: str,
    dsn: str,
    projection: str,
    build_id: str,
    workers: int,
    narrowing_workers: int,
    heartbeat_s: float,
    metrics_port: int,
    retention_s: float = RETENTION_S,
    approval_ref: str | None = None,
    evidence_ref: str | None = None,
) -> int:
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as lock:
        [(held,)] = await (
            await lock.execute("SELECT pg_try_advisory_lock(%s)", (LOCK,))
        ).fetchall()
        if not held:
            log.error("another process holds the projection's database")
            return 3
        await lock.execute(SCHEMA)
        prometheus_client.start_http_server(metrics_port)
        stop = asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        size = workers + narrowing_workers + 2
        sdk = ProjectionClient(url, credential, projection)
        failed = False
        try:
            async with AsyncConnectionPool(
                dsn, kwargs={"autocommit": True}, min_size=1, max_size=size
            ) as pool:
                await Projection(
                    sdk,
                    pool,
                    build_id,
                    retention_s=retention_s,
                    approval_ref=approval_ref,
                    evidence_ref=evidence_ref,
                ).run(stop, workers, narrowing_workers, heartbeat_s)
        except* Expired:
            log.error("cursor expired: the projection needs a bootstrap")
            failed = True
        except* Retired:
            log.error("build retired: build_id=%s; name a new KP_PROJECTION_BUILD_ID", build_id)
            failed = True
        finally:
            await sdk.aclose()
    return 1 if failed else 0


def query_main() -> int:
    """`kp-reference-projection-query`: the query API (#279), the second role, in its own
    process (DR A7); any number of replicas. It reads the store the reader's process writes and
    never applies the schema.

    Environment: KP_PLATFORM_URL; KP_PROJECTION_CREDENTIAL, registered in
    KP_AUTHZ_PEP_CREDENTIALS for the authz API; KP_PROJECTION_DATABASE_URL, the reader's
    database; KP_QUERY_USERS, a JSON object from the SHA-256 hex of each user's bearer token to
    the user id (shortcut: a fixed list instead of the identity component of guide §5.1; the
    real query entry is #76's and #125's); KP_QUERY_PORT (default 8080) and
    KP_QUERY_METRICS_PORT (default 9101). Exit 2 for a missing or malformed setting."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        url, credential = os.environ["KP_PLATFORM_URL"], os.environ["KP_PROJECTION_CREDENTIAL"]
        dsn = os.environ["KP_PROJECTION_DATABASE_URL"]
        users = json.loads(os.environ["KP_QUERY_USERS"])
        port = int(os.environ.get("KP_QUERY_PORT", "8080"))
        metrics_port = int(os.environ.get("KP_QUERY_METRICS_PORT", "9101"))
    except KeyError as missing:
        log.error("setting missing: %s", missing.args[0])
        return 2
    except ValueError:
        log.error("KP_QUERY_USERS is not JSON, or a port is not a number")
        return 2
    if not isinstance(users, dict) or not all(isinstance(v, str) for v in users.values()):
        log.error("KP_QUERY_USERS is not an object of user ids")
        return 2
    prometheus_client.start_http_server(metrics_port)

    async def serve() -> None:
        sdk = ProjectionClient(url, credential, os.environ.get("KP_PROJECTION_NAME", "retrieval"))
        try:
            async with AsyncConnectionPool(
                dsn, kwargs={"autocommit": True}, min_size=1, max_size=4, timeout=2
            ) as pool:
                config = uvicorn.Config(query.app(sdk, pool, users), host="0.0.0.0", port=port)
                await uvicorn.Server(config).serve()
        finally:
            await sdk.aclose()

    asyncio.run(serve())
    return 0
