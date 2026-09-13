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
from temporalio.worker import Worker


async def cleanup_fresh_work():
    from pdf_processing.execution import stop_fresh_children
    await stop_fresh_children()
    for pattern in ('activity-*', 'ocr-*'):
        for path in Path(os.environ.get('SCRATCH', '/scratch')).glob(pattern):
            shutil.rmtree(path, ignore_errors=True)


async def main():
    client = await Client.connect(os.environ['TEMPORAL_ADDRESS'])
    parser = None
    grace = int(os.environ.get('DRAIN_SECONDS', '30'))
    options = {'task_queue': os.environ['TASK_QUEUE'],
               'graceful_shutdown_timeout': timedelta(seconds=grace)}
    if os.environ['WORKER_ROLE'] == 'workflow':
        from pdf_processing.processing_workflow import PDFProcessing
        options['workflows'] = [PDFProcessing]
    elif os.environ['WORKER_ROLE'] == 'activity':
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
        processing = Processing(Store(client_s3, os.environ['OBJECT_BUCKET'], os.environ['OBJECT_PREFIX']),
            os.environ.get('SCRATCH', '/scratch'), os.environ['MODEL_CACHE'],
            json.loads(Path(os.environ['PROFILE_FILE']).read_text()),
            json.loads(os.environ['LIMITS']) if os.environ.get('LIMITS') else None, child_runner=parser)
        options.update(activities=[processing.run], max_concurrent_activities=1)
    else:
        raise ValueError('WORKER_ROLE must be workflow or activity')
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    worker = Worker(client, **options)
    running = asyncio.create_task(worker.run())
    stopping = asyncio.create_task(stop.wait())
    try:
        done, _ = await asyncio.wait({running, stopping}, return_when=asyncio.FIRST_COMPLETED)
        if running in done:
            await running
            return
        # SDK shutdown stops polling first and gives active Activities time to publish.
        shutdown = asyncio.create_task(worker.shutdown())
        try:
            await asyncio.wait_for(asyncio.shield(shutdown), grace + 5)
        except TimeoutError:
            # Thread-backed publication cannot be cancelled safely in Python. The
            # worker process is the final isolation unit after the drain deadline.
            if parser is not None:
                await parser.stop('drain_deadline')
            await cleanup_fresh_work()
            print(json.dumps({'event':'forced_worker_exit', 'reason':'drain_deadline'}), flush=True)
            os._exit(75)
        await running
    finally:
        stopping.cancel()
        await asyncio.gather(stopping, return_exceptions=True)
        if parser is not None:
            await parser.close()
        await cleanup_fresh_work()


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
