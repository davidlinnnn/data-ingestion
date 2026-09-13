"""Guard a stage worker with its retained release and exact execution inventory."""
import asyncio
from temporalio import activity
from .processing import reject
from .routing import validate, release_binding, stage_for, STAGES
from .object_store import StoreFailure



class RoutedActivity:
    def __init__(self, processing, route, stage, queue, image):
        self.processing = processing
        self.route = validate(route)
        self.stage = stage
        if (release_binding(processing.profile, processing.producer, processing.limits,
                processing.store.bucket, processing.store.prefix) != route['binding'] or stage not in STAGES or
                queue != route['queues'][stage] or image != route['images'][stage]):
            raise ValueError('worker_routing_mismatch')

    @activity.defn(name='pdf_processing_routed_step_v1')
    async def run(self, value):
        try:
            stage = stage_for(value)
        except (KeyError, TypeError, ValueError):
            reject('invalid_routing_stage', 'method')
        if (value.get('routing_id') != self.route['id'] or
                activity.info().task_queue != self.route['queues'][self.stage] or
                stage != self.stage):
            reject('worker_routing_mismatch', 'method')
        if value['stage'] == 'prepare':
            request = value['request']
        else:
            try:
                plan = await asyncio.to_thread(self.processing.load_plan, value['plan'])
            except StoreFailure as error:
                reject(error.code, error.category)
            request = plan['request']
        if request.get('routing_id') != self.route['id']:
            reject('request_routing_conflict', 'method')
        result = await self.processing.run(value)
        return {**result, 'routing_id': self.route['id'], 'worker_stage': self.stage,
            'attempt': activity.info().attempt,
            'task_queue': activity.info().task_queue}
