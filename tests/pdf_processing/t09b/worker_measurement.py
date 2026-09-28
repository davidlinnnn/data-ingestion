"""Opt-in harness wiring for Worker(interceptors=[StorageMeasurement()])."""
from temporalio import activity
from temporalio.worker import ActivityInboundInterceptor, Interceptor

from storage_measurement import MeasuredClient, scope


class StorageMeasurement(Interceptor):
    def intercept_activity(self, next):
        return ScopedActivity(next)


class ScopedActivity(ActivityInboundInterceptor):
    async def execute_activity(self, input):
        info = activity.info()
        # Workflow execution, Activity id and attempt distinguish retries and
        # reused application request IDs without inspecting stage-specific args.
        with scope(f'{info.workflow_id}/{info.workflow_run_id}',
                   info.activity_id, info.attempt):
            return await self.next.execute_activity(input)


def install(processing, emit):
    """Call before Worker starts; preserve Store and its production behavior."""
    if isinstance(processing.store.client, MeasuredClient):
        raise ValueError('measurement already installed')
    processing.store.client = MeasuredClient(processing.store.client, emit)
    return StorageMeasurement()
