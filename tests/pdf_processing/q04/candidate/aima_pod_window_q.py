"""Run P's reviewed AIMA matrix with Q's exact process telemetry."""

from candidate import aima_pod_window_o as base
from sentinel.aima_attribution_telemetry_q import (
    StrictAttributionCollector as QCollector,
)


class StrictAttributionCollector(QCollector):
    def stop(self, **kwargs):
        if kwargs.pop("require_handoff", False):
            kwargs["require_warm_continuity"] = True
        return super().stop(require_handoff=False, **kwargs)


base.StrictAttributionCollector = StrictAttributionCollector
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
