"""Small real-service harness for the extracted operation seam.

The caller supplies source/method and page groups; T02 owns policy and admission.
"""
import asyncio
from datetime import timedelta
from pathlib import Path

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Worker
from .execution import Execution, SourceRequest


class Activities:
    def __init__(self, store, scratch):
        self.store, self.scratch = store, scratch

    @activity.defn(name='pdf_operation')
    async def produce(self, request):
        source = dict(request['source'])
        for key in ('pdf', 'model_cache'): source[key] = Path(source[key])
        execution = Execution(SourceRequest(**source), self.store, self.scratch, activity.heartbeat)
        return await execution.produce(request['operation'])


@workflow.defn(sandboxed=False)
class PDFExecution:
    @workflow.run
    async def run(self, request):
        async def call(operation):
            return await workflow.execute_activity('pdf_operation',
                {'source': request['source'], 'operation': operation},
                start_to_close_timeout=timedelta(minutes=10),
                heartbeat_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(maximum_attempts=4))
        groups = []
        for start, end in request['groups']:
            groups.append(await call({'kind': 'group', 'start': start, 'end': end}))
        parsed = await call({'kind': 'assembly', 'groups': groups,
            'start': request['groups'][0][0], 'end': request['groups'][-1][1]})
        ocr = []
        for component in request['components']:
            ocr.append(await call({'kind': 'ocr', 'parsed': parsed, 'component': component}))
        return {'groups': groups, 'parsed': parsed, 'ocr': ocr}


async def serve(client: Client, task_queue, store, scratch):
    activities = Activities(store, Path(scratch))
    async with Worker(client, task_queue=task_queue, workflows=[PDFExecution],
                      activities=[activities.produce], max_concurrent_activities=1):
        await asyncio.Event().wait()
