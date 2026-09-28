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
        self.summary['observed_at'] = workflow.now().isoformat()
        request = submission.get('request', {})
        if not isinstance(request, dict) or request.get('version') not in (1, 2, 3):
            self.summary.update(status='failed', error={'category': 'input', 'code': 'invalid_request'})
            return self.summary
        queue = submission.get('activity_queue')
        if not isinstance(queue, str) or not queue:
            self.summary.update(status='failed', error={'category': 'input', 'code': 'invalid_activity_queue'})
            return self.summary

        async def call(value):
            return await self.call(value, submission)

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
            if request['version'] == 1:
                return self.summary
            self.summary['status'] = 'selecting'
            selection = await call({'stage': 'select', 'plan': prepared['plan'],
                                    'parsed_result': result['parsed_result']})
            self.summary.update(selection=selection['operation'], selected_components=len(selection['selected']),
                                registered_components=0, status='enriching')
            outcomes = []
            # One scheduled component at a time: bounded history and in-flight work.
            for component in selection['selected']:
                outcome = await call({'stage': 'component_ocr', 'plan': prepared['plan'],
                    'selection': selection['operation'], 'component': component})
                outcomes.append(outcome['operation'])
                self.summary['steps'].append(outcome)
                self.summary.update(registered_components=len(outcomes), observed_at=outcome['observed_at'])
            self.summary['status'] = 'finalizing'
            final = await call({'stage': 'finalize', 'plan': prepared['plan'],
                'selection': selection['operation'], 'outcomes': outcomes})
            self.summary.update(status='complete', processing_complete=True,
                                processing_result=final['operation'], observed_at=final['observed_at'])
        except ActivityError as error:
            cause = error.cause
            details = cause.details if isinstance(cause, ApplicationError) else []
            failure = details[0] if details else {'category': 'infrastructure', 'code': 'activity_budget_exhausted'}
            self.summary.update({'status': 'failed', 'error': failure,
                                 'observed_at': workflow.now().isoformat()})
        return self.summary

    async def call(self, value, submission):
        return await workflow.execute_activity('pdf_processing_step_v1', value, task_queue=submission['activity_queue'],
            start_to_close_timeout=timedelta(minutes=12),
            schedule_to_close_timeout=timedelta(minutes=40),
            heartbeat_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=10), maximum_attempts=3))
