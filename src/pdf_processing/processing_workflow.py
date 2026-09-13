"""Deterministic internal parsing orchestration; never imports Docling or storage."""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError


@workflow.defn
class PDFProcessing:
    def __init__(self):
        self.summary = {'version': 1, 'status': 'preparing', 'registered_pages': 0,
                        'processing_complete': False, 'canonical_accepted': False,
                        'steps': [], 'error': None}

    @workflow.query
    def progress(self) -> dict:
        return self.summary

    @workflow.run
    async def run(self, submission: dict) -> dict:
        request = submission.get('request', {})
        if not isinstance(request, dict) or request.get('version') != 1:
            return {**self.summary, 'status': 'failed',
                    'error': {'category': 'input', 'code': 'invalid_request'}}
        queue = submission.get('activity_queue')
        if not isinstance(queue, str) or not queue:
            return {**self.summary, 'status': 'failed',
                    'error': {'category': 'input', 'code': 'invalid_activity_queue'}}

        async def call(value):
            return await workflow.execute_activity('pdf_processing_step_v1', value, task_queue=queue,
                start_to_close_timeout=timedelta(minutes=12),
                schedule_to_close_timeout=timedelta(minutes=40),
                heartbeat_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=10), maximum_attempts=3))
        try:
            prepared = await call({'stage': 'prepare', 'request': request})
            self.summary.update({'plan': prepared['plan'], 'pages': prepared['pages'], 'status': 'parsing',
                                 'observed_at': prepared['observed_at']})
            groups = []
            for start, end in prepared['groups']:
                result = await call({'stage': 'execute', 'plan': prepared['plan'],
                                    'operation': {'kind': 'group', 'start': start, 'end': end}})
                groups.append(result['operation'])
                self.summary['steps'].append(result)
                self.summary['registered_pages'] += end-start+1
                self.summary['observed_at'] = result['observed_at']
            self.summary['status'] = 'assembling'
            result = await call({'stage': 'execute', 'plan': prepared['plan'],
                'operation': {'kind': 'assembly', 'start': 1, 'end': prepared['pages'], 'groups': groups}})
            self.summary['steps'].append(result)
            self.summary.update({'status': 'parsed_ready', 'parsed_result': result['parsed_result'],
                                 'observed_at': result['observed_at']})
        except ActivityError as error:
            cause = error.cause
            details = cause.details if isinstance(cause, ApplicationError) else []
            failure = details[0] if details else {'category': 'infrastructure', 'code': 'activity_budget_exhausted'}
            self.summary.update({'status': 'failed', 'error': failure,
                                 'observed_at': workflow.now().isoformat()})
        return self.summary
