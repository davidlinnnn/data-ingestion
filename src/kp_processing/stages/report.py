"""Status report delivery, a separate retried Activity (#129, admission integration)."""

from kp_processing.ports.status_reporter import StatusReport
from kp_processing.stages import Ports


class ReportNotDelivered(Exception):
    """Raised so that Temporal retries the delivery."""


async def run(report: StatusReport, ports: Ports) -> None:
    """Send the report as built by the workflow. Returns when delivered, or when the receiver
    answered with its position (out of order: a retry cannot help). Raises ReportNotDelivered
    otherwise."""
    outcome = await ports.reporter.report(report)
    if not outcome.delivered and outcome.position is None:
        raise ReportNotDelivered(outcome.error)
