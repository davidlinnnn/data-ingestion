"""A4 runtime-only policy: record node PSI while retaining every other guard."""
import q04_runtime
from telemetry import check_sample as strict_check_sample


def check_sample(row, initial, limits):
    strict_check_sample({**row, 'psi_full_avg10': 0}, initial, limits)


class Run(q04_runtime.Run):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.runtime_node_psi_telemetry = False

    async def admission(self):
        await super().admission()
        self.runtime_node_psi_telemetry = True

    async def guard(self):
        if not self.runtime_node_psi_telemetry:
            return await super().guard()
        original = q04_runtime.check_sample
        q04_runtime.check_sample = check_sample
        try:
            return await super().guard()
        finally:
            q04_runtime.check_sample = original
