"""The reconciler (admission spec §9): run every 5 minutes, it settles each dispatched request
that has no terminal outcome against its workflow."""

import logging
from collections import Counter
from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from temporalio.client import (
    Client,
    WorkflowExecutionDescription,
    WorkflowExecutionStatus,
    WorkflowHandle,
)
from temporalio.service import RPCError, RPCStatusCode

ERROR_DOMAIN = "admission.knowledge-platform"

_UNSETTLED = """
SELECT request_id FROM outbox JOIN request USING (request_id)
WHERE dispatched_at IS NOT NULL AND state IN ('queued', 'processing')
"""

# The state guard keeps an outcome that status reports (#97) recorded meanwhile.
_RECORD = """
UPDATE request SET state = %s, terminal_at = %s, error = %s, updated_at = now()
WHERE request_id = %s AND state IN ('queued', 'processing')
"""

_REDISPATCH = """
UPDATE outbox SET dispatched_at = NULL, available_at = now(), redispatch_reason = %s
WHERE request_id = %s
"""

log = logging.getLogger(__name__)


async def reconcile(conn: AsyncConnection, client: Client) -> Counter[str]:
    """On an autocommit connection, for each dispatched process request still queued or
    processing: a running workflow is left alone; an ended one records the request's outcome,
    succeeded, or failed with the workflow's error block; a missing one goes back to the outbox,
    due now under the same request ID, with the reason in redispatch_reason. Returns how many
    requests went each way: running, recorded, redispatched. An unreachable Temporal raises."""
    actions: Counter[str] = Counter()
    for (request_id,) in await (await conn.execute(_UNSETTLED)).fetchall():
        handle = client.get_workflow_handle(request_id)
        try:
            described = await handle.describe()
        except RPCError as err:
            if err.status != RPCStatusCode.NOT_FOUND:
                raise
            log.warning("workflow %s is missing; it goes back to the outbox", request_id)
            await conn.execute(_REDISPATCH, (str(err), request_id))
            actions["redispatched"] += 1
            continue
        if described.status == WorkflowExecutionStatus.RUNNING:
            actions["running"] += 1
            continue
        state, error = await _outcome(handle, described)
        await conn.execute(
            _RECORD, (state, described.close_time, error and Jsonb(error), request_id)
        )
        actions["recorded"] += 1
    return actions


async def _outcome(
    handle: WorkflowHandle, described: WorkflowExecutionDescription
) -> tuple[str, dict[str, Any] | None]:
    status = described.status
    if status == WorkflowExecutionStatus.COMPLETED:
        result = await handle.result()
        if result.get("outcome") == "complete":
            return "succeeded", None
        if result.get("error"):
            return "failed", result["error"]
    name = status.name if status else "UNKNOWN"
    return "failed", {
        "domain": ERROR_DOMAIN,
        "reason": "WORKFLOW_ENDED_WITHOUT_RESULT",
        "message": f"The processing workflow ended {name} without an error block.",
        "retryable": True,
        "metadata": {"status": name},
        "support_ref": f"temporal:{described.id}/{described.run_id}",
    }
