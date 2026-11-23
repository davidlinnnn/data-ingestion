"""kp-admission command line: the api, dispatcher and reconciler roles (#95, #113, admission
spec §13), Change Feed retention and the Knowledge Profile write point (#126), batch expiry and
the two adoption commands (#96, admission spec §3), the upload cleanup (#194).

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
from urllib.parse import urlsplit

import prometheus_client
import psycopg
import pydantic
import uvicorn
from psycopg_pool import AsyncConnectionPool

from kp_admission import adoption, batches, feed, reports, serving, status, uploads
from kp_admission.api import CREDENTIALS, Credential, RequestLog, SourceCredential, app
from kp_admission.authz import AllowAll
from kp_admission.dispatcher import dispatch_due, temporal_start
from kp_admission.reconciler import reconcile
from kp_admission.storage import S3ObjectStore
from kp_canonicalization.cli import connect, log_json_lines
from kp_canonicalization.workflow import task_queue

POLL_S = 1.0
POOL_SIZE = 5  # per api pod; the connection budget (#78 C14) counts it
POOL_WAIT_S = 2.0  # a /v1/ call waits this long for a connection, then answers 503
OBSERVE_S = 15.0

log = logging.getLogger(__name__)
SOURCES = pydantic.TypeAdapter(dict[str, batches.SourceSettings])
PIPELINES = pydantic.TypeAdapter(dict[str, reports.Pipeline])


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
    KP_SOURCES holds each Source's settings (admission spec §2), as a JSON object from source_id
    to `{"ordering": "source_version" | "arrival", "default_resource_id": <its own key>}`; a
    Source not in it orders by source_version and has no default. KP_PIPELINES registers the
    status reporters (#97, admission spec §7.3), as a JSON object from the SHA-256 hex digest of
    each reporter's credential to `{"pipeline_id", "track", "stages", "start_deadline_s",
    "update_interval_s"}`; the credentials of one pipeline_id, several while one is rotated, carry
    the same registration, and no two pipelines share a track: `canonical` is canonical
    processing's, any other a projection's (§7.4). Without it every status report is 401 and no
    attempt is progress_stalled. The custody bucket is KP_S3_ENDPOINT and KP_S3_BUCKET with the
    AWS_* credentials, as for the processing workers; the credentials need s3:ListBucket, without
    which S3 answers a missing object with 403.
    KP_MAX_FILE_SIZE is the maximum file size in bytes (default 50 MB); with KP_PAUSE_BACKLOG,
    declarations are refused while that many normal-priority process requests are queued.
    KP_ADMISSION_PUBLIC_URL is the https origin Sources call through the ingress, such as
    https://kp.example: every upload URL a declaration returns names it (§5.1), whatever headers
    the ingress forwards. The api also writes uploads (§5.2), so its storage credentials need
    s3:PutObject and s3:AbortMultipartUpload as well.
    It starts while the database or storage is down; decisions are then unavailable.

    `kp-admission dispatcher`: start the workflows of due outbox rows, looking every POLL_S
    seconds, until SIGTERM or SIGINT. It starts while Temporal is down; the rows wait.

    `kp-admission reconcile`: one reconciler run. It prints how many requests went each way, as
    JSON, and fails when Temporal is unreachable.

    `kp-admission feed-retention`: one Change Feed retention run (kp_admission.feed.retain), daily
    at least. It prints the partitions it created and dropped, as JSON.

    `kp-admission set-profile --tenant T SOURCE [PROJECTION ...]`: set the Source's Knowledge
    Profile, the Projection Types it requires, and print its profile_seq as JSON.

    `kp-admission expire`: one batch expiry and upload cleanup run, the hourly CronJob: every
    batch open 24 hours is expired (§11), then the uploads not admitted of every batch that ended
    an hour before are deleted and its incomplete uploads aborted (§6.2,
    kp_admission.uploads.clean). It prints how many batches it expired, cleaned and left to the
    next run because storage failed, as JSON, and fails (exit 1) when it left any. It takes the
    custody bucket's settings as the api does; its credentials need s3:DeleteObject,
    s3:AbortMultipartUpload and s3:ListBucketMultipartUploads.

    `kp-admission adopt --tenant T MEDIA_TYPE VERSION` and `kp-admission cancel-adoption --tenant
    T MEDIA_TYPE VERSION`: the Processing Profile owner's adoption commands (§3). Adopting
    supersedes the version adopted before for that media type; cancelling the adopted version
    leaves none, and fails (exit 1) for a version that is not the adopted one. Each prints the
    result as JSON and opens no refresh request (#98 does).

    `kp-admission writes-lost EVENT`: operations' declaration that the admission database lost
    committed writes (a restore, a point-in-time restore, a failover that lost commits; DR §5.6),
    run by a Job of the deployment repo with the event's number, which each such declaration
    raises (#78's runbook). Every Build not retired is asked for a repair view, and Source
    Deletion's judgment stays suspended until a view captured after the run repairs each one
    (kp_admission.serving.writes_unrepaired). EVENT is a number from 1, above every earlier
    declaration's, kept in the deployment repo. The event applied last, run again, changes
    nothing, so the Job can run again; an event below it fails (exit 1) and changes nothing. It
    prints whether it applied the event and how many Builds it asked, as JSON.

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
    roles.add_parser("expire")
    roles.add_parser("writes-lost").add_argument("event", type=_positive)
    for command in ("adopt", "cancel-adoption"):
        adopting = roles.add_parser(command)
        adopting.add_argument("--tenant", required=True)
        adopting.add_argument("media_type")
        adopting.add_argument("version")
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
            pipelines = PIPELINES.validate_json(os.environ.get("KP_PIPELINES", "{}"))
        except pydantic.ValidationError:
            pipelines = None
        # Several credentials may name one pipeline, to rotate them, with one registration.
        by_id = {p.pipeline_id: p for p in (pipelines or {}).values()}
        tracks = [p.track for p in by_id.values()]
        if (
            pipelines is None
            or any(by_id[p.pipeline_id] != p for p in pipelines.values())
            or len(set(tracks)) < len(tracks)
        ):
            print("KP_PIPELINES is not valid", file=sys.stderr)
            return 2
        port = os.environ.get("KP_ADMISSION_API_PORT", "8080")
        if not port.isdecimal():
            print("KP_ADMISSION_API_PORT must be a port number", file=sys.stderr)
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
        if not _storage_set():
            return 2
        public = urlsplit(os.environ.get("KP_ADMISSION_PUBLIC_URL", ""))
        if (
            public.scheme != "https"
            or not public.hostname
            or "@" in public.netloc
            or public.path not in ("", "/")
            or public.query
            or public.fragment
        ):
            print("KP_ADMISSION_PUBLIC_URL must be an https origin", file=sys.stderr)
            return 2
        intake = batches.Intake(
            S3ObjectStore.from_env(),
            sources,
            int(limits["KP_MAX_FILE_SIZE"] or batches.MAX_FILE_SIZE),
            int(limits["KP_PAUSE_BACKLOG"]) if limits["KP_PAUSE_BACKLOG"] else None,
            f"{public.scheme}://{public.netloc}",
        )
        log_json_lines(RequestLog())
        if args.metrics_port is not None:
            prometheus_client.start_http_server(args.metrics_port)
        return asyncio.run(run_api(dsn, peps, credentials, intake, int(port), pipelines))
    log_json_lines()
    if args.role == "feed-retention":
        return asyncio.run(run_feed_retention(dsn))
    if args.role == "set-profile":
        return asyncio.run(run_set_profile(dsn, args.tenant, args.source, args.projections))
    if args.role in ("adopt", "cancel-adoption"):
        return asyncio.run(run_adoption(dsn, args.tenant, args.role, args.media_type, args.version))
    if args.role == "writes-lost":
        return asyncio.run(run_writes_lost(dsn, args.event))
    if args.role == "expire":
        return asyncio.run(run_expiry(dsn)) if _storage_set() else 2
    return asyncio.run(run_dispatcher(dsn) if args.role == "dispatcher" else run_reconciler(dsn))


def _positive(value: str) -> int:
    if not value.isdecimal() or int(value) < 1:
        raise argparse.ArgumentTypeError("a number from 1")
    return int(value)


def _storage_set() -> bool:
    storage = ("KP_S3_ENDPOINT", "KP_S3_BUCKET", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
    if all(os.environ.get(k) for k in storage):
        return True
    print(f"{', '.join(storage)} are required", file=sys.stderr)
    return False


async def run_api(
    dsn: str,
    peps: dict[str, str],
    credentials: dict[str, Credential],
    intake: batches.Intake,
    port: int,
    pipelines: dict[str, reports.Pipeline],
) -> int:
    pool = AsyncConnectionPool(
        dsn, max_size=POOL_SIZE, kwargs={"autocommit": True}, timeout=POOL_WAIT_S, open=False
    )
    async with pool:
        config = uvicorn.Config(
            app(AllowAll(pool), peps, credentials, pool, intake, pipelines),
            host="0.0.0.0",
            port=port,
            log_config=None,
        )
        by_track = {p.track: p for p in pipelines.values()}
        observing = asyncio.create_task(observe(pool, by_track))
        await uvicorn.Server(config).serve()
        observing.cancel()
    return 0


async def observe(pool: AsyncConnectionPool[Any], pipelines: dict[str, reports.Pipeline]) -> None:
    while True:
        try:
            async with pool.connection() as conn:
                await feed.observe(conn)
                await serving.silent(conn, pipelines, datetime.now(UTC))
        except Exception as error:  # the gauges keep their last values; the api keeps serving
            log.warning("feed and liveness metrics not measured: %s", type(error).__name__)
        await asyncio.sleep(OBSERVE_S)


async def run_feed_retention(dsn: str) -> int:
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        print(json.dumps(await feed.retain(conn, datetime.now(UTC))))
    return 0


async def run_writes_lost(dsn: str, event: int) -> int:
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        try:
            builds = await serving.lose_writes(conn, event)
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
    print(json.dumps({"applied": builds is not None, "builds": builds or 0}))
    return 0


async def run_set_profile(dsn: str, tenant: str, source: str, projections: list[str]) -> int:
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        seq = await feed.set_profile(
            conn, tenant_id=tenant, source_id=source, projections=projections
        )
        await status.refresh_source(conn, source)  # a dropped projection stops counting
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


async def run_expiry(dsn: str) -> int:
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        expired = await batches.expire(conn)
        cleaned, left = await uploads.clean(conn, S3ObjectStore.from_env())
    print(json.dumps({"expired": expired, "cleaned": cleaned, "left": left}))
    return 1 if left else 0


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
