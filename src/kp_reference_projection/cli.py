"""`kp-reference-projection`: the reference projection's one long-running process (#127): the
Change Feed reader, its workers and the heartbeat of its Build, until SIGTERM or SIGINT.

Environment:

- KP_PLATFORM_URL: the platform API's origin.
- KP_PROJECTION_CREDENTIAL: the service credential, registered under KP_PROJECTION_NAME both in
  KP_AUTHZ_PEP_CREDENTIALS and in KP_PIPELINES, with `stages` ["write"] (spec §7.4).
- KP_PROJECTION_NAME: the projection, as the Knowledge Profiles name it (default `retrieval`).
- KP_PROJECTION_BUILD_ID: the Build it serves (default `b1`).
- KP_PROJECTION_DATABASE_URL: its own PostgreSQL database; the schema is applied at start.
- KP_PROJECTION_WORKERS (default 4) and KP_PROJECTION_NARROWING_WORKERS (default 1): the fixed
  worker counts; narrowing workers take deletions and rebinds only.
- KP_PROJECTION_HEARTBEAT_S (default 60): below the pipeline's update_interval_s.
- KP_PROJECTION_METRICS_PORT (default 9100): Prometheus metrics at /metrics.

Exit codes: 0 after SIGTERM or SIGINT (the run in progress finishes first; a run cut short is
taken again at the next start); 1 on a failure, such as an expired cursor, which needs a
bootstrap (#280, #281), or a Build the platform already serves started on a new database,
which needs a new KP_PROJECTION_BUILD_ID; 2 for a missing or malformed setting; 3 when
another process already runs against the same database. One process per database, so its
Deployment uses the `Recreate` strategy; a run in progress may take up to 600 s, so a shorter
termination grace period only means that run is taken again at the next start.

Metrics, for alerts (CODING_STANDARDS § Logs and metrics): `kp_projection_write_seconds` (a
registration to its confirmation), `kp_projection_removal_seconds` (a narrowing event to its
removal taken), `kp_projection_failures_total{step, reason}` (feed reads, cursor reports, runs,
switches and heartbeats that failed) and `kp_projection_backlog{priority}`; the reader's lag is
the platform's `kp_feed_consumer_lag_seconds{projection}`. Log lines carry `build_id`,
`document_uid`, `resource_id`, `fact_version`, `state`, `kind`, `position` and `reason` as they
apply, never content or an error's message.
"""

import asyncio
import logging
import os
import signal

import prometheus_client
import psycopg
from psycopg_pool import AsyncConnectionPool

from kp_reference_projection import SCHEMA
from kp_reference_projection.projection import Expired, Projection
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
        expired = False
        try:
            async with AsyncConnectionPool(
                dsn, kwargs={"autocommit": True}, min_size=1, max_size=size
            ) as pool:
                await Projection(sdk, pool, build_id).run(
                    stop, workers, narrowing_workers, heartbeat_s
                )
        except* Expired:
            log.error("cursor expired: the projection needs a bootstrap")
            expired = True
        finally:
            await sdk.aclose()
    return 1 if expired else 0
