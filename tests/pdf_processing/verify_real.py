"""Explicit real Temporal/S3 acceptance run; writes only the caller's fresh prefix.

Run in the pinned Linux image with src and this script mounted/copied into it.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import boto3
from temporalio.client import Client
from temporalio.worker import Worker
from pdf_processing.object_store import Store
from pdf_processing.temporal import Activities, PDFExecution
from pdf_processing.execution import Execution, SourceRequest


def parse(mode, pdf, out, cache, checkpoint=None, scan=False):
    request = dict(mode=mode, pdf=str(pdf), out=str(out), model_cache=str(cache), scan=scan)
    if checkpoint: request['checkpoint'] = str(checkpoint)
    if mode == 'capture': request['checkpoint_only'] = True
    with out.with_suffix('.log').open('w') as log:
        subprocess.run([sys.executable, '-m', 'pdf_processing.parse'], input=json.dumps(request),
                       text=True, stdout=log, stderr=log, check=True)


async def main(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    fixture = Path(args.fixtures)
    cache = Path(args.model_cache)
    pdf = fixture/'llm-survey-2303.18223v1.pdf'
    for label, source, scan in [('native', pdf, False), ('scan', fixture/'scan-pages-3-5.pdf', True)]:
        for mode in ('baseline', 'capture', 'restore'):
            parse(mode, source, out/f'{label}-{mode}', cache,
                  out/f'{label}-capture' if mode == 'restore' else None, scan)
        baseline = json.loads((out/f'{label}-baseline/document.json').read_text())
        restored = json.loads((out/f'{label}-restore/document.json').read_text())
        assert baseline == restored
        metrics = json.loads((out/f'{label}-restore/metrics.json').read_text())
        assert not any(v for k,v in metrics['page_stage_inputs'].items() if k.endswith('Model'))
        assert metrics['pid'] != json.loads((out/f'{label}-capture/metrics.json').read_text())['pid']
    client = boto3.client('s3', endpoint_url=args.endpoint)
    if not any(b['Name'] == args.bucket for b in client.list_buckets()['Buckets']):
        client.create_bucket(Bucket=args.bucket)
    store = Store(client, args.bucket, args.prefix)
    assert not client.list_objects_v2(Bucket=args.bucket, Prefix=args.prefix+'/').get('KeyCount')
    source = dict(pdf=str(pdf), source_revision='paper:2303.18223v1',
        source_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
        method=json.loads((out/'native-baseline/method.json').read_text()), model_cache=str(cache))
    request = dict(source=source, groups=[[i,min(i+4,51)] for i in range(1,52,5)], components=['#/pictures/0'])
    temporal = await Client.connect(args.temporal)
    queue = 't01-' + uuid.uuid4().hex
    activities = Activities(store, out/'scratch')
    async with Worker(temporal, task_queue=queue, workflows=[PDFExecution], activities=[activities.produce], max_concurrent_activities=1):
        result = await temporal.execute_workflow(PDFExecution.run, request, id=queue, task_queue=queue)
    execution = Execution(SourceRequest(**{**source, 'pdf': pdf, 'model_cache': cache}), store, out/'scratch')
    execution.materialize(result['parsed'], out/'delivered')
    assert json.loads((out/'delivered/document.json').read_text()) == json.loads((out/'native-baseline/document.json').read_text())
    execution.materialize(result['ocr'][0], out/'ocr')
    ocr = json.loads((out/'ocr/ocr.json').read_text())
    reference = json.loads(Path(args.ocr_reference).read_text())
    normalize = lambda text: ''.join(c.lower() for c in text if c.isalnum())
    text = normalize(' '.join(ocr['texts']))
    assert all(normalize(label) in text for label in reference['labels'])
    # A new worker instance must reuse registrations without creating any objects.
    before = client.list_objects_v2(Bucket=args.bucket, Prefix=args.prefix+'/')['KeyCount']
    async with Worker(temporal, task_queue=queue, workflows=[PDFExecution], activities=[Activities(store,out/'fresh-scratch').produce], max_concurrent_activities=1):
        reused = await temporal.execute_workflow(PDFExecution.run, request, id=queue+'-reuse', task_queue=queue)
    assert reused == result
    assert client.list_objects_v2(Bucket=args.bucket, Prefix=args.prefix+'/')['KeyCount'] == before
    report = dict(result=result, request=request, native_equal=True, scan_equal=True,
        fresh_restore_zero_page_inference=True, fresh_worker_reuse_no_new_objects=True,
        ocr_labels=len(reference['labels']), queue=queue, bucket=args.bucket, prefix=args.prefix)
    (out/'verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('result','request')}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('out','fixtures','model-cache','ocr-reference','endpoint','bucket','prefix','temporal'):
        parser.add_argument('--'+name, required=True)
    asyncio.run(main(parser.parse_args()))
