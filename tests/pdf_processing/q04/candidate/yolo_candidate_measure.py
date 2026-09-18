"""Run adapter for the next YOLO candidate measurement harness."""

from candidate.yolo_lifecycle import CancellationObservedRunMixin
from q04_runtime import Run


class AttributedCandidateRun(CancellationObservedRunMixin, Run):
    """Bind resource health and cancellation markers to the real Q04 Run."""

    def __init__(self, *args, collector, **kwargs):
        self.collector = collector
        super().__init__(*args, observe_cancel=collector.observe, **kwargs)

    async def guard(self):
        self.collector.require_healthy()
        row = await super().guard()
        self.collector.require_healthy()
        return row
