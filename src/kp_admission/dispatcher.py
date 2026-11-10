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
# In-flight budgets, unmeasured until the cluster-tier capacity runs (§13): one Source may hold
# the whole PROD burst, 500 documents (#88), and two Sources may at once. Per-Source overrides
# wait for Source configuration (#78).
IN_FLIGHT = 1000
PER_SOURCE = 500

# Its columns are the §10 start input, in order.
# shortcut: dispatchers that claim at once can each take a budget's last place, so a budget can
# be exceeded by one per extra dispatcher; take an advisory lock once a budget is a hard limit.
_CLAIM = """
WITH in_flight AS (
    SELECT d.tenant_id, d.source_id, count(*) AS n
    FROM request r
    JOIN outbox o ON o.request_id = r.request_id
    JOIN document d ON d.document_uid = r.document_uid
    WHERE r.kind = 'process' AND r.state IN ('queued', 'processing')
      AND o.dispatched_at IS NOT NULL
    GROUP BY d.tenant_id, d.source_id
)
SELECT r.request_id, r.document_uid, r.source_revision_id, s.files, r.adopted_version,
       r.adoption_sequence, r.initiator, r.priority, r.trace_id
FROM outbox o
JOIN request r ON r.request_id = o.request_id
JOIN source_revision s ON s.source_revision_id = r.source_revision_id
JOIN document d ON d.document_uid = r.document_uid
LEFT JOIN in_flight f ON f.tenant_id = d.tenant_id AND f.source_id = d.source_id
WHERE o.dispatched_at IS NULL AND o.available_at <= now()
  AND coalesce(f.n, 0) < %(per_source)s
  AND (SELECT coalesce(sum(n), 0) FROM in_flight) < %(in_flight)s
ORDER BY r.priority = 'low', coalesce(f.n, 0), o.available_at
LIMIT 1
FOR UPDATE OF o SKIP LOCKED
"""

_DISPATCHED = """
UPDATE outbox SET attempts = attempts + 1, dispatched_at = now() WHERE request_id = %s
"""

# clock_timestamp(), not now(): the backoff starts when the start failed, not when the
# transaction began, which can be rpc_timeout earlier. 2 ^ attempts overflows past 1023.
_RETRY = """
UPDATE outbox SET attempts = attempts + 1,
                  available_at = clock_timestamp()
                                 + least(%s, 2 ^ least(attempts, 30)) * interval '1 second'
WHERE request_id = %s
"""

log = logging.getLogger(__name__)


async def dispatch_due(
    conn: AsyncConnection,
    start: StartWorkflow,
    *,
    in_flight: int = IN_FLIGHT,
    per_source: int = PER_SOURCE,
) -> int:
    """Starts the workflow of each due outbox row, in one transaction per row on an autocommit
    connection, while fewer than in_flight dispatched requests, and fewer than per_source of the
    row's Source, are still queued or processing; a request leaves the budgets when its outcome is
    recorded. Normal priority goes first; then the Source with the fewest requests in flight, so
    Sources take turns; then the oldest row. Returns how many rows it recorded as dispatched. It
    stops at the first start that fails: that row is due again 1, 2, 4, … seconds after its 1st,
    2nd, 3rd, … failure, at most BACKOFF_CAP_S, and the others keep their place."""
    budgets = {"in_flight": in_flight, "per_source": per_source}
    dispatched = 0
    while True:
        async with conn.transaction():
            cursor = conn.cursor(row_factory=dict_row)
            start_input = await (await cursor.execute(_CLAIM, budgets)).fetchone()
            if start_input is None:
                return dispatched
            request_id = start_input["request_id"]
            try:
                await start(start_input)
            except Exception:
                log.warning("starting %s failed; it waits and retries", request_id, exc_info=True)
                await conn.execute(_RETRY, (BACKOFF_CAP_S, request_id))
                return dispatched  # Temporal is likely down: the next row would fail too
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
