"""The adoption gate (#261, admission spec §3): a declared version is adopted only once Temporal
routes it and, for a version not adopted before, a test workflow of it completed.

1. Its Worker Deployment has a current build polling all five queues, and the routing change
   is COMPLETED. A state stuck IN_PROGRESS (temporalio/temporal#11842) falls back after
   ROUTING_LIMIT on the five queues alone, reason `routing_in_progress`.
2. A test workflow on that build returned outcome `complete` with a well-formed `candidate`
   (spec §7.3; #81): Temporal reads a workflow `COMPLETED` whatever its outcome, so the gate
   reads the result, and a version that completes without a candidate forms no acceptance.
   Each test is a new document, so no registered result is reused; a failed one is replaced
   CHECK_RETRY after it started. A
   version adopted through the gate before is not tested again (#57 B6): a rollback often
   happens while a model service is down.

The CronJob runs every minute; a test workflow outlives a run, so it is recorded in
`adoption_check` and read on a later run.
"""

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import Any, Literal

import psycopg
from psycopg import AsyncConnection
from pydantic import ValidationError
from temporalio.api.deployment.v1 import WorkerDeploymentInfo, WorkerDeploymentVersion
from temporalio.api.enums.v1 import RoutingConfigUpdateState
from temporalio.api.workflowservice.v1 import (
    DescribeWorkerDeploymentRequest,
    DescribeWorkerDeploymentVersionRequest,
)
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.service import RPCError, RPCStatusCode

from kp_admission.adoption import CHECK_PREFIX
from kp_admission.dispatcher import temporal_start
from kp_admission.requests import Candidate
from kp_admission.storage import ObjectStore
from kp_canonicalization.workflow import QUEUES, deployment_name, task_queue

log = logging.getLogger(__name__)
ROUTING_LIMIT = timedelta(minutes=10)  # as the promoter's alarm (#178)
CHECK_RETRY = timedelta(minutes=10)  # a failed test workflow is replaced no sooner
# A synthetic page with text, a picture and a table (tests/pdfs.py), no third-party content.
CHECK_FILES = {"application/pdf": ("check.pdf", files("kp_admission") / "check.pdf")}


def routing(
    info: WorkerDeploymentInfo, now: datetime, limit: timedelta
) -> Literal["completed", "fallback", "waiting"]:
    """Whether the deployment's routing change is done, or stuck past `limit` after its current
    build changed; an unknown change time waits."""
    if (
        info.routing_config_update_state
        == RoutingConfigUpdateState.ROUTING_CONFIG_UPDATE_STATE_COMPLETED
    ):
        return "completed"
    if not info.routing_config.HasField("current_version_changed_time"):
        return "waiting"
    changed = info.routing_config.current_version_changed_time.ToDatetime(UTC)
    return "fallback" if now - changed >= limit else "waiting"


class TemporalGate:
    """An adoption.Gate on `client`. Test workflows read their file from `store`, the custody
    bucket, which gets it under checks/ when it lacks it."""

    def __init__(
        self,
        conn: AsyncConnection,
        client: Client,
        store: ObjectStore,
        tenant_id: str,
        routing_limit: timedelta = ROUTING_LIMIT,
        check_retry: timedelta = CHECK_RETRY,
    ) -> None:
        self._conn, self._client, self._store = conn, client, store
        self._tenant_id, self._limit, self._retry = tenant_id, routing_limit, check_retry
        self._start = temporal_start(client, task_queue)

    async def __call__(
        self, media_type: str, version: str, adopted_before: bool
    ) -> tuple[bool, str]:
        service, namespace = self._client.workflow_service, self._client.namespace
        name = deployment_name(version)
        try:
            described = await service.describe_worker_deployment(
                DescribeWorkerDeploymentRequest(namespace=namespace, deployment_name=name)
            )
        except RPCError as missing:
            if missing.status != RPCStatusCode.NOT_FOUND:
                raise
            return False, "not_deployed"
        info = described.worker_deployment_info
        build_id = info.routing_config.current_deployment_version.build_id
        if not build_id:
            return False, "no_current_build"
        version_info = await service.describe_worker_deployment_version(
            DescribeWorkerDeploymentVersionRequest(
                namespace=namespace,
                deployment_version=WorkerDeploymentVersion(deployment_name=name, build_id=build_id),
            )
        )
        polled = {q.name for q in version_info.worker_deployment_version_info.task_queue_infos}
        if {task_queue(name, queue) for queue in QUEUES} - polled:
            return False, "queues_not_polled"
        routed = routing(info, datetime.now(UTC), self._limit)
        if routed == "waiting":
            return False, "routing_in_progress"
        fallback = "" if routed == "completed" else "routing_in_progress"
        if adopted_before:
            return True, fallback
        if media_type not in CHECK_FILES:
            return False, "no_check_file"
        return await self._check(media_type, version, build_id, fallback)

    async def _check(
        self, media_type: str, version: str, build_id: str, fallback: str
    ) -> tuple[bool, str]:
        row = await (
            await self._conn.execute(
                "SELECT check_id, attempt, now() - started_at FROM adoption_check"
                " WHERE media_type = %s AND version = %s ORDER BY attempt DESC LIMIT 1",
                (media_type, version),
            )
        ).fetchone()
        if row:
            handle = self._client.get_workflow_handle(row[0])
            try:
                described = await handle.describe()
            except RPCError as missing:
                if missing.status != RPCStatusCode.NOT_FOUND:
                    raise
                described = None  # never started, or past the namespace's retention
            if described and described.status == WorkflowExecutionStatus.RUNNING:
                return False, "check_running"
            if described and described.status == WorkflowExecutionStatus.COMPLETED:
                versioning = described.raw_description.workflow_execution_info.versioning_info
                ran_on = versioning.deployment_version.build_id
                result = await handle.result()
                try:
                    Candidate.model_validate(result.get("candidate"))
                    complete = result.get("outcome") == "complete"
                except ValidationError:
                    complete = False
                if complete and ran_on == build_id:
                    return True, fallback
                failed = not complete
            else:
                failed = described is not None
            if failed:
                ids = {"check_id": row[0], "version": version}
                log.warning("adoption check %s failed", row[0], extra={"correlation": ids})
            if failed and row[2] < self._retry:
                return False, "check_failed"  # each test costs model calls: not one every minute
        return await self._start_check(media_type, version, row[1] + 1 if row else 1)

    async def _start_check(self, media_type: str, version: str, attempt: int) -> tuple[bool, str]:
        check_id = f"{CHECK_PREFIX}{uuid.uuid4().hex}"
        try:
            await self._conn.execute(
                "INSERT INTO adoption_check (check_id, tenant_id, media_type, version, attempt)"
                " VALUES (%s, %s, %s, %s, %s)",
                (check_id, self._tenant_id, media_type, version, attempt),
            )
        except psycopg.errors.UniqueViolation:
            return False, "check_running"  # an overlapping run started this attempt
        await self._start(await self._input(media_type, version, check_id))
        ids = {"check_id": check_id, "version": version}
        log.info("adoption check %s started", check_id, extra={"correlation": ids})
        return False, "check_started"

    async def _input(self, media_type: str, version: str, check_id: str) -> dict[str, Any]:
        """The §10 start input of a test workflow: a new document, the shipped file."""
        path, resource = CHECK_FILES[media_type]
        data = resource.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        key = f"checks/{sha256}"
        if not await self._store.head(key):
            upload = await self._store.create_upload(key)
            etag = await self._store.upload_part(key, upload, 1, data)
            await self._store.complete_upload(key, upload, [etag])
        file = {"path": path, "role": "main", "custody_ref": f"s3://{self._store.bucket}/{key}",
                "sha256": sha256, "size": len(data), "media_type": media_type}  # fmt: skip
        return {
            "request_id": check_id,
            "document_uid": f"doc_{uuid.uuid4().hex}",
            "source_revision_id": f"srv_{uuid.uuid4().hex}",
            "files": [file],
            "adopted_version": version,
            "adoption_sequence": 0,
            "initiator": "platform",
            "priority": "normal",
            "trace_id": uuid.uuid4().hex[:16],
        }
