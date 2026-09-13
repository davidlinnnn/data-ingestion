"""Separate Workflow and PDF Activity deployment roles, one parser slot per Pod."""
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import signal

from temporalio.client import Client
from temporalio.worker import Worker


async def main():
    client = await Client.connect(os.environ['TEMPORAL_ADDRESS'])
    options = {'task_queue': os.environ['TASK_QUEUE'],
               'graceful_shutdown_timeout': timedelta(seconds=15)}
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
        processing = Processing(Store(client_s3, os.environ['OBJECT_BUCKET'], os.environ['OBJECT_PREFIX']),
            os.environ.get('SCRATCH', '/scratch'), os.environ['MODEL_CACHE'],
            json.loads(Path(os.environ['PROFILE_FILE']).read_text()),
            json.loads(os.environ['LIMITS']) if os.environ.get('LIMITS') else None)
        options.update(activities=[processing.run], max_concurrent_activities=1)
    else:
        raise ValueError('WORKER_ROLE must be workflow or activity')
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    async with Worker(client, **options):
        await stop.wait()


if __name__ == '__main__':
    asyncio.run(main())
