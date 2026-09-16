"""Qualification-only multi-queue host for unchanged production Activities.

Each queue has one immutable profile. A single WarmParser is shared serially,
allowing the six fixed inputs to exercise the same child lifetime. Never deploy
this harness as the production worker package.
"""
import argparse
import asyncio
from contextlib import AsyncExitStack
from datetime import timedelta
import json
import os
from pathlib import Path
import signal
import sys
import time

from consumer import require, sha
from telemetry import sample


async def run(config_path, out, generation):
    import psutil
    import boto3
    from temporalio.client import Client
    from temporalio.worker import Worker
    from pdf_processing.object_store import Store
    from pdf_processing.processing import Processing
    from pdf_processing.supervision import WarmParser
    from pdf_processing.execution import stop_fresh_children

    config = json.loads(config_path.read_text())
    import pdf_processing
    actual = {p.name: sha(p.read_bytes()) for p in Path(pdf_processing.__file__).parent.glob('*.py')}
    require(actual == config['producer'], 'worker producer drift')
    out.mkdir(parents=True, exist_ok=False)
    identity = {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'generation': generation, 'config_sha256': sha(config_path.read_bytes())}
    (out/'ownership.json').write_text(json.dumps(identity))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    client = await Client.connect(config['temporal'])
    s3 = boto3.client('s3', endpoint_url=config['endpoint'])
    store = Store(s3, config['bucket'], config['prefix'])
    parser = WarmParser(**config['parser_budgets'])
    scratch = (Path('/scratch')/config['run_id']/str(generation)) if config.get('pod_namespace') else out/'scratch'
    workers = []
    sampler_error = []

    async def observe():
        try:
            with (out/'samples.jsonl').open('x', buffering=1) as stream:
                while not stop.is_set():
                    if (out/'stop-sampling').exists():
                        return
                    row = sample()
                    row.update(worker_pid=os.getpid(), generation=generation,
                        parser=dict(parser.observation), parser_count=parser.count)
                    stream.write(json.dumps(row)+'\n')
                    await asyncio.sleep(.5)
                stream.write(json.dumps({**sample(), 'worker_pid': os.getpid(), 'generation': generation, 'parser': dict(parser.observation), 'parser_count': parser.count})+'\n')
        except BaseException as error:
            sampler_error.append(type(error).__name__)
            stop.set()

    sampler = asyncio.create_task(observe())
    try:
        async with AsyncExitStack() as stack:
            for key, profile in config['profiles'].items():
                processing = Processing(store, scratch/key, config['model_cache'], profile,
                    config['limits'], child_runner=parser)
                worker = Worker(client, task_queue=config['queues'][key], activities=[processing.run],
                    max_concurrent_activities=1, graceful_shutdown_timeout=timedelta(seconds=config['drain_seconds']))
                await stack.enter_async_context(worker)
                workers.append(worker)
            (out/'ready.tmp').write_text(json.dumps({**identity, 'time': time.time()}))
            (out/'ready.tmp').replace(out/'ready.json')
            await stop.wait()
    finally:
        stop.set()
        await parser.close()
        await stop_fresh_children()
        await asyncio.gather(sampler, return_exceptions=True)
        import shutil
        shutil.rmtree(scratch, ignore_errors=True)
        (out/'stopped.json').write_text(json.dumps({'pid': os.getpid(), 'time': time.time(),
            'generation': generation, 'parser_absent': parser.process is None,
            'scratch_absent': not scratch.exists(), 'sampler_errors': sampler_error}))
    require(not sampler_error, 'sampler failed')


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--config', type=Path, required=True)
    cli.add_argument('--out', type=Path, required=True)
    cli.add_argument('--generation', type=int, required=True)
    args = cli.parse_args()
    # The coordinator is the authority for runtime admission. Worker requires its
    # exact config plus a live, externally approved window and an owned queue set.
    config = json.loads(args.config.read_text())
    require(config['window']['starts_at'] <= time.time() < config['window']['ends_at'], 'outside capacity window')
    try:
        asyncio.run(asyncio.wait_for(run(args.config, args.out, args.generation),
            timeout=config['window']['ends_at']-time.time()))
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.exit(1)
