"""kp-admission command line: the api, dispatcher and reconciler roles (#95, #113, admission
spec §13), Change Feed retention and the Knowledge Profile write point (#126).

The database comes from KP_ADMISSION_DATABASE_URL; Temporal from TEMPORAL_ADDRESS (default
localhost:7233) and TEMPORAL_NAMESPACE (default "default"), as for kp-canonicalization.
"""

import argparse
import asyncio
import contextlib
import json
import logging
import os
import signal
import sys
from datetime import UTC, datetime
from typing import Any

import prometheus_client
import psycopg
import pydantic
import uvicorn
from psycopg_pool import AsyncConnectionPool

from kp_admission import feed
from kp_admission.api import CREDENTIALS, Credential, RequestLog, SourceCredential, app
from kp_admission.authz import AllowAll
from kp_admission.dispatcher import dispatch_due, temporal_start
from kp_admission.reconciler import reconcile
from kp_canonicalization.cli import connect, log_json_lines
from kp_canonicalization.workflow import task_queue

POLL_S = 1.0
POOL_SIZE = 5  # per api pod; the connection budget (#78 C14) counts it
POOL_WAIT_S = 2.0  # a /v1/ call waits this long for a connection, then answers 503
OBSERVE_S = 15.0

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """`kp-admission api [--metrics-port P]`: serve the platform API on KP_ADMISSION_API_PORT
    (default 8080) until SIGTERM or SIGINT; it finishes open requests, then ends by that signal, as
    uvicorn does. With P it serves kp_admission.api's metrics at http://0.0.0.0:P/metrics, and
    kp_admission.feed's gauges, measured every OBSERVE_S seconds.
    KP_AUTHZ_PROVIDER selects the authz provider: `allow-all`, the only one, which it refuses
    unless KP_DEPLOYMENT is `pilot` (#113; the marker is #78's). KP_AUTHZ_PEP_CREDENTIALS registers
    the PEPs that may call the authz API, as a JSON object from the SHA-256 hex digest of each
    credential to its service identity. KP_CREDENTIALS registers the Source and client
    credentials (§7), as a JSON object from the SHA-256 hex digest of each credential to
    `{"credential_id", "tenant_id", "source_id", "scopes": ["submit", "manage_relations"]}` or
    `{"credential_id", "client_id", "delegate"}`; a Source may hold several at once. Every
    credential_id is distinct and every Source credential names the deployment's one tenant (Q7).
    It starts while the database is down; decisions are then unavailable.

    `kp-admission dispatcher`: start the workflows of due outbox rows, looking every POLL_S
    seconds, until SIGTERM or SIGINT. It starts while Temporal is down; the rows wait.

    `kp-admission reconcile`: one reconciler run. It prints how many requests went each way, as
    JSON, and fails when Temporal is unreachable.

    `kp-admission feed-retention`: one Change Feed retention run (kp_admission.feed.retain), daily
    at least. It prints the partitions it created and dropped, as JSON.

    `kp-admission set-profile --tenant T SOURCE [PROJECTION ...]`: set the Source's Knowledge
    Profile, the Projection Types it requires, and print its profile_seq as JSON.

    All log JSON lines to stderr and exit 2 without KP_ADMISSION_DATABASE_URL or on another
    configuration error."""
    parser = argparse.ArgumentParser(prog="kp-admission")
    roles = parser.add_subparsers(dest="role", required=True)
    roles.add_parser("api").add_argument("--metrics-port", type=int)
    roles.add_parser("dispatcher")
    roles.add_parser("reconcile")
    roles.add_parser("feed-retention")
    profile = roles.add_parser("set-profile")
    profile.add_argument("--tenant", required=True)
    profile.add_argument("source")
    profile.add_argument("projections", nargs="*")
    args = parser.parse_args(argv)
    dsn = os.environ.get("KP_ADMISSION_DATABASE_URL")
    if not dsn:
        print("KP_ADMISSION_DATABASE_URL is required", file=sys.stderr)
        return 2
    if args.role == "api":
        if os.environ.get("KP_AUTHZ_PROVIDER") != "allow-all":
            print("KP_AUTHZ_PROVIDER must be allow-all, the only provider", file=sys.stderr)
            return 2
        if os.environ.get("KP_DEPLOYMENT") != "pilot":
            print("the allow-all authz provider needs KP_DEPLOYMENT=pilot", file=sys.stderr)
            return 2
        try:
            peps = json.loads(os.environ.get("KP_AUTHZ_PEP_CREDENTIALS", "{}"))
        except json.JSONDecodeError:
            peps = None
        if not isinstance(peps, dict) or not all(isinstance(v, str) for v in peps.values()):
            print("KP_AUTHZ_PEP_CREDENTIALS must be a JSON object of strings", file=sys.stderr)
            return 2
        try:
            credentials = CREDENTIALS.validate_json(os.environ.get("KP_CREDENTIALS", "{}"))
        except pydantic.ValidationError as error:
            where = [".".join(map(str, e["loc"])) for e in error.errors(include_input=False)]
            print(f"KP_CREDENTIALS is not valid at {', '.join(where)}", file=sys.stderr)
            return 2
        ids = [c.credential_id for c in credentials.values()]
        tenants = {c.tenant_id for c in credentials.values() if isinstance(c, SourceCredential)}
        if len(set(ids)) < len(ids) or len(tenants) > 1:
            print("KP_CREDENTIALS needs distinct credential_ids and one tenant_id", file=sys.stderr)
            return 2
        port = os.environ.get("KP_ADMISSION_API_PORT", "8080")
        if not port.isdecimal():
            print("KP_ADMISSION_API_PORT must be a port number", file=sys.stderr)
            return 2
        log_json_lines(RequestLog())
        if args.metrics_port is not None:
            prometheus_client.start_http_server(args.metrics_port)
        return asyncio.run(run_api(dsn, peps, credentials, int(port)))
    log_json_lines()
    if args.role == "feed-retention":
        return asyncio.run(run_feed_retention(dsn))
    if args.role == "set-profile":
        return asyncio.run(run_set_profile(dsn, args.tenant, args.source, args.projections))
    return asyncio.run(run_dispatcher(dsn) if args.role == "dispatcher" else run_reconciler(dsn))


async def run_api(
    dsn: str, peps: dict[str, str], credentials: dict[str, Credential], port: int
) -> int:
    pool = AsyncConnectionPool(
        dsn, max_size=POOL_SIZE, kwargs={"autocommit": True}, timeout=POOL_WAIT_S, open=False
    )
    async with pool:
        config = uvicorn.Config(
            app(AllowAll(pool), peps, credentials, pool), host="0.0.0.0", port=port, log_config=None
        )
        observing = asyncio.create_task(observe(pool))
        await uvicorn.Server(config).serve()
        observing.cancel()
    return 0


async def observe(pool: AsyncConnectionPool[Any]) -> None:
    while True:
        try:
            async with pool.connection() as conn:
                await feed.observe(conn)
        except Exception as error:  # the gauges keep their last values; the api keeps serving
            log.warning("feed metrics not measured: %s", type(error).__name__)
        await asyncio.sleep(OBSERVE_S)


async def run_feed_retention(dsn: str) -> int:
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        print(json.dumps(await feed.retain(conn, datetime.now(UTC))))
    return 0


async def run_set_profile(dsn: str, tenant: str, source: str, projections: list[str]) -> int:
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        seq = await feed.set_profile(
            conn, tenant_id=tenant, source_id=source, projections=projections
        )
    print(json.dumps({"profile_seq": seq}))
    return 0


async def run_dispatcher(dsn: str) -> int:
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    start = temporal_start(await connect(lazy=True), task_queue)
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        while not stop.is_set():
            await dispatch_due(conn, start)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), POLL_S)
    return 0


async def run_reconciler(dsn: str) -> int:
    client = await connect()
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        print(json.dumps(await reconcile(conn, client)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
