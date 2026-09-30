import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from temporalio.worker import ActivityInboundInterceptor
from worker_measurement import install
from storage_measurement import _identity


class WorkerMeasurementTest(unittest.TestCase):
    def test_all_stage_calls_scoped_and_cancelled_context_cleared(self):
        class Next(ActivityInboundInterceptor):
            def __init__(self):
                pass

            async def execute_activity(self, input):
                identity = await asyncio.to_thread(_identity.get)
                self.identity = identity
                if input == 'cancel':
                    raise asyncio.CancelledError()
                return identity

        processing = SimpleNamespace(store=SimpleNamespace(client=object()))
        interceptor = install(processing, lambda row: None)
        with self.assertRaisesRegex(ValueError, 'already installed'):
            install(processing, lambda row: None)
        downstream = Next()
        wrapped = interceptor.intercept_activity(downstream)
        info = SimpleNamespace(workflow_id='workflow', workflow_run_id='run',
                               activity_id='activity', attempt=2)

        async def run():
            with patch('worker_measurement.activity.info', return_value=info):
                for stage in ('prepare', 'group', 'assembly', 'component_ocr', 'finalize'):
                    result = await wrapped.execute_activity(stage)
                    self.assertEqual(result['request_id'], 'workflow/run')
                    self.assertEqual(result['attempt'], 2)
                    self.assertIsNone(_identity.get())
                with self.assertRaises(asyncio.CancelledError):
                    await wrapped.execute_activity('cancel')
                self.assertIsNone(_identity.get())
        asyncio.run(run())
