"""Separate Workflow and PDF Activity deployment roles, one parser slot per Pod."""
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import signal
import shutil
import traceback

from temporalio.client import Client
from temporalio.worker import Worker, Interceptor, ActivityInboundInterceptor


class SerialActivities(Interceptor):
    """All explicit stage queues share the qualified one-Activity budget."""
    def __init__(self):
        self.lock = asyncio.Lock()

    def intercept_activity(self, next):
        lock = self.lock
        class SerialActivity(ActivityInboundInterceptor):
            async def execute_activity(self, input):
                async with lock:
                    return await super().execute_activity(input)
        return SerialActivity(next)


async def cleanup_owned_work(parser, reason='worker_shutdown', *, starting=False):
    from pdf_processing.execution import stop_owned_children
    # A new parser has no children; shutdown irreversibly closes its admission.
    await stop_owned_children(None if starting else parser, reason)
    for pattern in ('preflight-*', 'activity-*', 'ocr-*'):
        for path in Path(os.environ.get('SCRATCH', '/scratch')).glob(pattern):
            shutil.rmtree(path, ignore_errors=True)


async def main():
    client = await Client.connect(os.environ['TEMPORAL_ADDRESS'])
    route = None
    if os.environ.get('ROUTING_FILE'):
        from pdf_processing.routing import validate
        route = validate(json.loads(Path(os.environ['ROUTING_FILE']).read_text()))
    parser = None
    processing = None
    grace = int(os.environ.get('DRAIN_SECONDS', '30'))
    options = {'task_queue': os.environ['TASK_QUEUE'],
               'graceful_shutdown_timeout': timedelta(seconds=grace)}
    if os.environ['WORKER_ROLE'] == 'workflow':
        from pdf_processing.processing_workflow import PDFProcessing
        if route is None:
            options['workflows'] = [PDFProcessing]
        else:
            from pdf_processing.rollout_workflow import PDFRolloutProcessing
            from pdf_processing.routing import fingerprint
            from pdf_processing.object_store import digest
            import pdf_processing
            producer = {p.name: digest(p.read_bytes()) for p in Path(pdf_processing.__file__).parent.glob('*.py')}
            if (os.environ['TASK_QUEUE'] != route['queues']['workflow'] or
                    os.environ['WORKER_IMAGE'] != route['images']['workflow'] or
                    fingerprint(producer) != route['binding']['producer']):
                raise ValueError('worker_routing_mismatch')
            options['workflows'] = [PDFRolloutProcessing]
    elif os.environ['WORKER_ROLE'] == 'activity':
        if route is not None:
            from bootstrap import memory_policy
            print(json.dumps({'event':'memory_policy_verified', **memory_policy()}), flush=True)
        import boto3
        from botocore.config import Config
        from pdf_processing.object_store import Store
        from pdf_processing.processing import Processing
        client_s3 = boto3.client('s3', endpoint_url=os.environ['OBJECT_ENDPOINT'],
            config=Config(connect_timeout=5, read_timeout=30, retries={'max_attempts': 2}))
        from pdf_processing.supervision import WarmParser
        if os.environ.get('PARSER_MODE', 'warm') == 'warm':
            parser = WarmParser(**json.loads(os.environ.get('PARSER_BUDGETS', '{}')))
        elif os.environ['PARSER_MODE'] != 'fresh':
            raise ValueError('PARSER_MODE must be warm or fresh')
        profile = json.loads(Path(os.environ['PROFILE_FILE']).read_text())
        if route is not None:
            from bootstrap import verify
            print(json.dumps({'event': 'bootstrap_verified', **verify(profile, os.environ['MODEL_CACHE'])}), flush=True)
        processing = Processing(Store(client_s3, os.environ['OBJECT_BUCKET'], os.environ['OBJECT_PREFIX']),
            os.environ.get('SCRATCH', '/scratch'), os.environ['MODEL_CACHE'],
            profile,
            json.loads(os.environ['LIMITS']) if os.environ.get('LIMITS') else None, child_runner=parser)
        run = processing.run
        if route is not None and os.environ['WORKER_STAGE'] != 'all':
            from pdf_processing.routed_activity import RoutedActivity
            routed = RoutedActivity(processing, route, os.environ['WORKER_STAGE'],
                os.environ['TASK_QUEUE'], os.environ['WORKER_IMAGE'])
            run = routed.run
        options.update(activities=[run], max_concurrent_activities=1)
    else:
        raise ValueError('WORKER_ROLE must be workflow or activity')
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    if route is not None and os.environ['WORKER_ROLE'] == 'activity' and os.environ['WORKER_STAGE'] == 'all':
        from pdf_processing.routing import STAGES
        from pdf_processing.routed_activity import RoutedActivity
        assert processing is not None
        serial = SerialActivities()
        workers = [Worker(client, **{**options, 'task_queue': route['queues'][stage],
            'activities': [RoutedActivity(processing, route, stage, route['queues'][stage], os.environ['WORKER_IMAGE']).run],
            'interceptors': [serial]}) for stage in STAGES]
    else:
        workers = [Worker(client, **options)]
    # Container restart may retain emptyDir bytes from an abruptly stopped PID1.
    # Scratch is exclusive to this worker; shared store references are never removed.
    await cleanup_owned_work(parser, 'worker_startup', starting=True)
    tasks = [asyncio.create_task(worker.run()) for worker in workers]
    stopping = asyncio.create_task(stop.wait())
    try:
        done, _ = await asyncio.wait({*tasks, stopping}, return_when=asyncio.FIRST_COMPLETED)
        if stopping not in done:
            for task in done:
                await task
            return
        # SDK shutdown stops polling first and gives active Activities time to publish.
        shutdown = asyncio.gather(*(worker.shutdown() for worker in workers))
        try:
            await asyncio.wait_for(asyncio.shield(shutdown), grace + 5)
        except TimeoutError:
            # Thread-backed publication cannot be cancelled safely in Python. The
            # worker process is the final isolation unit after the drain deadline.
            await cleanup_owned_work(parser, 'drain_deadline')
            print(json.dumps({'event':'forced_worker_exit', 'reason':'drain_deadline'}), flush=True)
            os._exit(75)
        await asyncio.gather(*tasks)
    finally:
        stopping.cancel()
        await asyncio.gather(stopping, return_exceptions=True)
        await cleanup_owned_work(parser)


async def entrypoint():
    # asyncio.run otherwise waits for default-executor threads after main returns.
    # A cancelled publication may still be blocked in a transport call. Once SDK
    # drain and child cleanup have finished, the process is the isolation limit.
    try:
        await main()
    except BaseException:
        traceback.print_exc()
        os._exit(1)
    print(json.dumps({'event': 'worker_shutdown_complete'}), flush=True)
    os._exit(0)


if __name__ == '__main__':
    asyncio.run(entrypoint())
