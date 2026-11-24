"""The reconciler (admission spec §9): run every 5 minutes, it settles each dispatched request
that has no terminal outcome against its workflow."""

import logging
from collections import Counter
from typing import Any, Literal

from psycopg import AsyncConnection
from pydantic import ValidationError
from temporalio.api.errordetails.v1 import NamespaceNotFoundFailure
from temporalio.client import (
    Client,
    WorkflowExecutionDescription,
    WorkflowExecutionStatus,
    WorkflowHandle,
)
from temporalio.service import RPCError, RPCStatusCode

from kp_admission import adoption
from kp_admission.requests import ERROR_DOMAIN, Candidate, end_withdrawn, record_outcome

_UNSETTLED = """
SELECT request_id, adopted_version, files FROM outbox JOIN request USING (request_id)
JOIN source_revision USING (source_revision_id)
WHERE dispatched_at IS NOT NULL AND kind = 'process' AND state IN ('queued', 'processing')
"""

_REDISPATCH = """
UPDATE outbox SET dispatched_at = NULL, available_at = now(), redispatch_reason = %s
WHERE request_id = %s
"""

# Until the dispatcher records the next run, reports wait (#97): none of the lost run's count.
_NO_ATTEMPT = """
UPDATE request SET attempt_id = NULL, last_report = NULL, reported_at = NULL WHERE request_id = %s
"""

log = logging.getLogger(__name__)


async def reconcile(conn: AsyncConnection, client: Client) -> Counter[str]:
    """On an autocommit connection, for each dispatched process request still queued or
    processing: a running workflow is left alone; an ended one records the request's outcome,
    succeeded with its result's candidate, or failed with the workflow's error block, as
    requests.record_outcome does; a missing one goes back to the outbox, due now under the same
    request ID, with the reason in redispatch_reason and no current attempt. A running workflow of
    a version withdrawn for its media type is terminated and its request ends failed with
    VERSION_WITHDRAWN (#98). Returns how many requests went each way: running, recorded,
    redispatched, withdrawn. An unreachable Temporal or a
    missing namespace raises."""
    actions: Counter[str] = Counter()
    for request_id, version, files in await (await conn.execute(_UNSETTLED)).fetchall():
        handle = client.get_workflow_handle(request_id)
        try:
            described = await handle.describe()
        except RPCError as err:
            # A missing namespace is NOT_FOUND too, and must not send every request back.
            details = err.grpc_status.details
            if err.status != RPCStatusCode.NOT_FOUND or any(
                detail.Is(NamespaceNotFoundFailure.DESCRIPTOR) for detail in details
            ):
                raise
            log.warning("workflow %s is missing; it goes back to the outbox", request_id)
            async with conn.transaction():
                await conn.execute(_REDISPATCH, (str(err), request_id))
                await conn.execute(_NO_ATTEMPT, (request_id,))
            actions["redispatched"] += 1
            continue
        if described.status == WorkflowExecutionStatus.RUNNING:
            if version not in await adoption.withdrawn(conn, _media_type(files)):
                actions["running"] += 1
                continue
            # It would block its revision's rerun (#98): a withdrawn version's result is discarded.
            try:
                await handle.terminate("Processing Profile version withdrawn")
            except RPCError as err:
                if err.status != RPCStatusCode.NOT_FOUND:  # NOT_FOUND: it ended meanwhile
                    raise
            described = await handle.describe()
            if described.status == WorkflowExecutionStatus.TERMINATED:
                await end_withdrawn(conn, request_id)
                actions["withdrawn"] += 1
                continue
        state, error, candidate = await _outcome(handle, described)
        # An outcome that status reports (#97) recorded meanwhile stays.
        await record_outcome(conn, request_id, state, error, described.close_time, candidate)
        actions["recorded"] += 1
    return actions


def _media_type(files: list[dict[str, Any]]) -> str:
    return next(f["media_type"] for f in files if f["role"] == "main")


async def _outcome(
    handle: WorkflowHandle, described: WorkflowExecutionDescription
) -> tuple[Literal["succeeded", "failed"], dict[str, Any] | None, Candidate | None]:
    status = described.status
    if status == WorkflowExecutionStatus.COMPLETED:
        result = await handle.result()
        if result.get("outcome") == "complete":
            return "succeeded", None, _candidate(described.id, result.get("candidate"))
        if result.get("error"):
            return "failed", result["error"], None
    name, closed = status.name if status else "UNKNOWN", described.close_time
    return (
        "failed",
        {
            "domain": ERROR_DOMAIN,
            "reason": "WORKFLOW_ENDED_WITHOUT_RESULT",
            "message": f"The processing workflow ended {name} without an error block.",
            "retryable": True,
            "metadata": {"status": name},
            "support_ref": f"temporal:{described.id}/{described.run_id}",
            "occurred_at": closed and closed.isoformat().replace("+00:00", "Z"),
        },
        None,
    )


def _candidate(request_id: str, value: Any) -> Candidate | None:
    """The workflow result's candidate (spec §7.3); one that is not well formed is none, so the
    request still ends, without an acceptance."""
    if value is None:
        return None
    try:
        return Candidate.model_validate(value)
    except ValidationError:
        log.warning("workflow %s returned a malformed candidate", request_id)
        return None
