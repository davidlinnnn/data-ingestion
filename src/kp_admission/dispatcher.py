"""The dispatcher (admission spec §9): starts the canonical workflow of each due outbox row. Run
at least two; they claim rows with FOR UPDATE SKIP LOCKED, so none waits for a row another
holds."""

import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from temporalio.client import Client
from temporalio.common import SearchAttributePair, TypedSearchAttributes, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from kp_canonicalization.workflow import SEARCH_ATTRIBUTES, WORKFLOW, priority

StartWorkflow = Callable[[dict[str, Any]], Awaitable[None]]
"""Starts the workflow of a §10 start input with workflow ID = its request_id. It returns
normally when that workflow exists already and raises when it cannot tell that it started."""

# Provisional until the cluster-tier Temporal outage run (§13).
BACKOFF_CAP_S = 60

# Its columns are the §10 start input, in order.
_CLAIM = """
SELECT r.request_id, r.document_uid, r.source_revision_id, s.files, r.adopted_version,
       r.adoption_sequence, r.initiator, r.priority, r.trace_id
FROM outbox o
JOIN request r ON r.request_id = o.request_id
JOIN source_revision s ON s.source_revision_id = r.source_revision_id
WHERE o.dispatched_at IS NULL AND o.available_at <= now()
ORDER BY o.available_at
LIMIT 1
FOR UPDATE OF o SKIP LOCKED
"""

_DISPATCHED = """
UPDATE outbox SET attempts = attempts + 1, dispatched_at = now() WHERE request_id = %s
"""

# clock_timestamp(), not now(): the backoff starts when the start failed, not when the
# transaction began, which can be rpc_timeout earlier.
_RETRY = """
UPDATE outbox SET attempts = attempts + 1,
                  available_at = clock_timestamp() + least(%s, 2 ^ attempts) * interval '1 second'
WHERE request_id = %s
"""

log = logging.getLogger(__name__)


async def dispatch_due(conn: AsyncConnection, start: StartWorkflow) -> int:
    """Starts the workflow of each due outbox row, oldest first, in one transaction per row on an
    autocommit connection, and returns how many rows it recorded as dispatched. It stops at the
    first start that fails, since Temporal is likely down: that row is due again 1, 2, 4, …
    seconds after its 1st, 2nd, 3rd, … failure, at most BACKOFF_CAP_S, and the others keep their
    place."""
    dispatched = 0
    while True:
        async with conn.transaction():
            cursor = conn.cursor(row_factory=dict_row)
            start_input = await (await cursor.execute(_CLAIM)).fetchone()
            if start_input is None:
                return dispatched
            request_id = start_input["request_id"]
            try:
                await start(start_input)
            except Exception:
                log.warning("starting %s failed; it waits and retries", request_id, exc_info=True)
                await conn.execute(_RETRY, (BACKOFF_CAP_S, request_id))
                return dispatched
            await conn.execute(_DISPATCHED, (request_id,))
        dispatched += 1


def temporal_start(
    client: Client,
    task_queue: Callable[[str], str],
    rpc_timeout: timedelta = timedelta(seconds=10),
) -> StartWorkflow:
    """The StartWorkflow of the canonical workflow on `client`, with REJECT_DUPLICATE, on the task
    queue task_queue(adopted_version) (#135 names the queues), giving up after rpc_timeout."""

    async def start(start_input: dict[str, Any]) -> None:
        try:
            await client.start_workflow(
                WORKFLOW,
                start_input,
                id=start_input["request_id"],
                task_queue=task_queue(start_input["adopted_version"]),
                priority=priority(start_input["priority"]),
                search_attributes=TypedSearchAttributes(
                    [
                        SearchAttributePair(key, start_input[field])
                        for field, key in SEARCH_ATTRIBUTES.items()
                    ]
                ),
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                rpc_timeout=rpc_timeout,
            )
        except WorkflowAlreadyStartedError:
            pass

    return start
