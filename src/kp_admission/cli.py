"""kp-admission command line: the api, dispatcher and reconciler roles, batch expiry and the two
adoption commands (#95, #113, #96, admission spec §3, §13).

The database comes from KP_ADMISSION_DATABASE_URL; Temporal from TEMPORAL_ADDRESS (default
localhost:7233) and TEMPORAL_NAMESPACE (default "default"), as for kp-canonicalization.
"""

import argparse
import asyncio
import contextlib
import json
import os
import signal
import sys

import prometheus_client
import psycopg
import pydantic
import uvicorn
from psycopg_pool import AsyncConnectionPool

from kp_admission import adoption, batches
from kp_admission.api import CREDENTIALS, Credential, RequestLog, SourceCredential, app
from kp_admission.authz import AllowAll
from kp_admission.dispatcher import dispatch_due, temporal_start
from kp_admission.reconciler import reconcile
from kp_admission.storage import S3ObjectStore
from kp_canonicalization.cli import connect, log_json_lines
from kp_canonicalization.workflow import task_queue

POLL_S = 1.0
POOL_SIZE = 5  # per api pod; the connection budget (#78 C14) counts it
POOL_WAIT_S = 2.0
SOURCES = pydantic.TypeAdapter(
    dict[str, batches.SourceSettings]
)  # a /v1/ call waits this long for a connection, then answers 503


def main(argv: list[str] | None = None) -> int:
    """`kp-admission api [--metrics-port P]`: serve the platform API on KP_ADMISSION_API_PORT
    (default 8080) until SIGTERM or SIGINT; it finishes open requests, then ends by that signal, as
    uvicorn does. With P it serves kp_admission.api's metrics at http://0.0.0.0:P/metrics.
    KP_AUTHZ_PROVIDER selects the authz provider: `allow-all`, the only one, which it refuses
    unless KP_DEPLOYMENT is `pilot` (#113; the marker is #78's). KP_AUTHZ_PEP_CREDENTIALS registers
    the PEPs that may call the authz API, as a JSON object from the SHA-256 hex digest of each
    credential to its service identity. KP_CREDENTIALS registers the Source and client
    credentials (§7), as a JSON object from the SHA-256 hex digest of each credential to
    `{"credential_id", "tenant_id", "source_id", "scopes": ["submit", "manage_relations"]}` or
    `{"credential_id", "client_id", "delegate"}`; a Source may hold several at once. Every
    credential_id is distinct and every Source credential names the deployment's one tenant (Q7).
    KP_SOURCES holds each Source's settings (admission spec §2), as a JSON object from source_id
    to `{"ordering": "source_version" | "arrival", "default_resource_id": <its own key>}`; a
    Source not in it orders by source_version and has no default. The custody bucket is
    KP_S3_ENDPOINT and KP_S3_BUCKET with the AWS_* credentials, as for the processing workers; the
    credentials need s3:ListBucket, without which S3 answers a missing object with 403.
    KP_MAX_FILE_SIZE is the maximum file size in bytes (default 50 MB); with KP_PAUSE_BACKLOG,
    declarations are refused while that many process requests are queued.
    It starts while the database or storage is down; decisions are then unavailable.

    `kp-admission dispatcher`: start the workflows of due outbox rows, looking every POLL_S
    seconds, until SIGTERM or SIGINT. It starts while Temporal is down; the rows wait.

    `kp-admission reconcile`: one reconciler run. It prints how many requests went each way, as
    JSON, and fails when Temporal is unreachable.

    `kp-admission expire`: one batch expiry run, the hourly CronJob: every batch open 24 hours is
    expired (§11). It prints how many, as JSON.

    `kp-admission adopt <media_type> <version>` and `kp-admission cancel-adoption <media_type>
    <version>`: the Processing Profile owner's adoption commands (§3), for the tenant
    KP_TENANT_ID. Adopting supersedes the version adopted before for that media type; cancelling
    the adopted version leaves none, and fails (exit 1) for a version that is not the adopted
    one. Each prints the result as JSON and opens no refresh request (#98 does).

    All of them log JSON lines to stderr and exit 2 without KP_ADMISSION_DATABASE_URL or on another
    configuration error."""
    parser = argparse.ArgumentParser(prog="kp-admission")
    roles = parser.add_subparsers(dest="role", required=True)
    roles.add_parser("api").add_argument("--metrics-port", type=int)
    roles.add_parser("dispatcher")
    roles.add_parser("reconcile")
    roles.add_parser("expire")
    for command in ("adopt", "cancel-adoption"):
        parser_of = roles.add_parser(command)
        parser_of.add_argument("media_type")
        parser_of.add_argument("version")
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
        try:
            sources = SOURCES.validate_json(os.environ.get("KP_SOURCES", "{}"))
        except pydantic.ValidationError:
            print("KP_SOURCES is not valid", file=sys.stderr)
            return 2
        limits = {k: os.environ.get(k, "") for k in ("KP_MAX_FILE_SIZE", "KP_PAUSE_BACKLOG")}
        if not all(v.isdecimal() for v in limits.values() if v):
            print("KP_MAX_FILE_SIZE and KP_PAUSE_BACKLOG must be numbers", file=sys.stderr)
            return 2
        if not all(os.environ.get(k) for k in ("KP_S3_ENDPOINT", "KP_S3_BUCKET")):
            print("KP_S3_ENDPOINT and KP_S3_BUCKET are required", file=sys.stderr)
            return 2
        intake = batches.Intake(
            S3ObjectStore.from_env(),
            sources,
            int(limits["KP_MAX_FILE_SIZE"] or batches.MAX_FILE_SIZE),
            int(limits["KP_PAUSE_BACKLOG"]) if limits["KP_PAUSE_BACKLOG"] else None,
        )
        port = os.environ.get("KP_ADMISSION_API_PORT", "8080")
        if not port.isdecimal():
            print("KP_ADMISSION_API_PORT must be a port number", file=sys.stderr)
            return 2
        log_json_lines(RequestLog())
        if args.metrics_port is not None:
            prometheus_client.start_http_server(args.metrics_port)
        return asyncio.run(run_api(dsn, peps, credentials, intake, int(port)))
    log_json_lines()
    if args.role in ("adopt", "cancel-adoption"):
        tenant_id = os.environ.get("KP_TENANT_ID")
        if not tenant_id:
            print("KP_TENANT_ID is required", file=sys.stderr)
            return 2
        return asyncio.run(run_adoption(dsn, tenant_id, args.role, args.media_type, args.version))
    if args.role == "expire":
        return asyncio.run(run_expiry(dsn))
    return asyncio.run(run_dispatcher(dsn) if args.role == "dispatcher" else run_reconciler(dsn))


async def run_api(
    dsn: str,
    peps: dict[str, str],
    credentials: dict[str, Credential],
    intake: batches.Intake,
    port: int,
) -> int:
    pool = AsyncConnectionPool(
        dsn, max_size=POOL_SIZE, kwargs={"autocommit": True}, timeout=POOL_WAIT_S, open=False
    )
    async with pool:
        config = uvicorn.Config(
            app(AllowAll(pool), peps, credentials, pool, intake),
            host="0.0.0.0",
            port=port,
            log_config=None,
        )
        await uvicorn.Server(config).serve()
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


async def run_expiry(dsn: str) -> int:
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        print(json.dumps({"expired": await batches.expire(conn)}))
    return 0


async def run_adoption(
    dsn: str, tenant_id: str, command: str, media_type: str, version: str
) -> int:
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        if command == "adopt":
            sequence = await adoption.adopt(
                conn, tenant_id=tenant_id, media_type=media_type, version=version
            )
            print(json.dumps({"adopted_version": version, "adoption_sequence": sequence}))
            return 0
        cancelled = await adoption.cancel(conn, media_type=media_type, version=version)
        print(json.dumps({"cancelled": cancelled}))
        return 0 if cancelled else 1


if __name__ == "__main__":
    sys.exit(main())
