"""Status report delivery, a separate Activity (#129, admission integration)."""

import asyncio
import logging
import time

from kp_processing.ports.status_reporter import StatusReport
from kp_processing.stages import Ports, Runtime

log = logging.getLogger(__name__)


async def run(report: StatusReport, ports: Ports, runtime: Runtime) -> bool:
    """Send the report exactly as the workflow built it, so a receiver deduplicates resends by
    seq. Retries undelivered reports with backoff (1 s, doubling, at most 10 s) for
    runtime status_report_budget_s, then gives up. Never raises: a report that cannot be
    delivered must not fail processing. Returns whether the receiver took it; an out-of-order
    answer (the receiver's position) is final and not retried."""
    deadline = time.monotonic() + runtime.profile.runtime["status_report_budget_s"]
    delay = 1.0
    while True:
        outcome = await ports.reporter.report(report)
        if outcome.delivered or outcome.position is not None:
            if outcome.position is not None:
                log.warning("report seq %s out of order at %s", report.seq, outcome.position)
            return outcome.delivered
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            log.warning("report seq %s not delivered: %s", report.seq, outcome.error)
            return False
        await asyncio.sleep(min(delay, remaining))
        delay = min(delay * 2, 10.0)
