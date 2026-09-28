"""Explicit-queue Workflow type; legacy PDFProcessing histories keep their type."""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from .processing_workflow import PDFProcessing
from .routing import validate, stage_for


@workflow.defn
class PDFRolloutProcessing(PDFProcessing):
    @workflow.run
    async def run(self, submission: dict) -> dict:
        try:
            route = validate(submission['routing'])
            if not isinstance(submission.get('request'), dict):
                raise ValueError('invalid_routing')
            if (workflow.info().task_queue != route['queues']['workflow'] or
                    submission['request'].get('routing_id') != route['id']):
                raise ValueError('invalid_routing')
        except (KeyError, TypeError, ValueError):
            self.summary.update(status='failed', error={'category':'configuration', 'code':'invalid_routing'})
            return self.summary
        self.summary['routing_id'] = route['id']
        return await super().run({**submission, 'activity_queue': route['queues']['prepare']})

    async def call(self, value, submission):
        route = submission['routing']
        return await workflow.execute_activity('pdf_processing_routed_step_v1',
            {**value, 'routing_id': route['id']}, task_queue=route['queues'][stage_for(value)],
            start_to_close_timeout=timedelta(minutes=12),
            schedule_to_close_timeout=timedelta(minutes=40),
            heartbeat_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=10), maximum_attempts=3))
