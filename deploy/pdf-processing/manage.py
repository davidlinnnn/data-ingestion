"""Internal captured-source submission/status/result CLI; not HTTP admission."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE/'pdf_processing').is_dir() else HERE.parents[1]/'src'))
from pdf_processing.object_store import Store
from pdf_processing.routing import submission, validate


def store_for(route):
    import boto3
    from botocore.config import Config
    scope = route['binding']['store']
    return Store(boto3.client('s3', endpoint_url=os.environ['OBJECT_ENDPOINT'],
        config=Config(connect_timeout=5, read_timeout=30, retries={'max_attempts': 2})),
        scope['bucket'], scope['prefix'])


def read_json(store, operation, name):
    registration = store.resolve(operation)
    if registration is None:
        raise ValueError('Required registration missing: '+operation)
    entry = next(f for f in registration['files'] if f['name'] == name)
    return json.loads(store.read_artifact(entry))


def export_result(store, summary, out):
    if summary.get('processing_complete') is not True or summary.get('status') != 'complete':
        raise ValueError('No complete processing result')
    final = read_json(store, summary['processing_result'], 'processing-result.json')
    if final['processing_complete'] is not True or final['canonical_accepted'] is not False:
        raise ValueError('Invalid processing completion boundary')
    out.mkdir(parents=True, exist_ok=False)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (out/'processing-result.json').write_text(json.dumps(final, indent=2)+'\n')
    operations = {'assembly': final['assembly'], 'content-evidence': final['content_evidence'],
        'selection': final['selection'], 'plan': final['plan'], 'parsed-result': final['parsed_result']}
    if 'relationships' in final:
        operations['relationships'] = final['relationships']
    operations.update({f'ocr-{n}': item['operation'] for n, item in enumerate(final['enrichments'])})
    inventory = []
    for directory, operation in operations.items():
        registration = store.resolve(operation)
        if registration is None:
            raise ValueError('Required registration missing: '+operation)
        target = out/directory
        target.mkdir()
        for entry in registration['files']:
            path = target/entry['name']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(store.read_artifact(entry))
            inventory.append({'operation': operation, **entry})
    (out/'retained-references.json').write_text(json.dumps(inventory, indent=2)+'\n')
    return {'processing_complete': True, 'canonical_accepted': False,
            'processing_result': summary['processing_result'], 'checked_files': len(inventory)}


async def run(args):
    route = validate(json.loads(args.route.read_text()))
    if args.command == 'capture':
        store = store_for(route)
        if store.client.get_bucket_versioning(Bucket=store.bucket).get('Status') != 'Enabled':
            raise ValueError('Source capture requires Enabled bucket versioning')
        raw = args.pdf.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        key = store.prefix+'sources/'+uuid.uuid4().hex+'/'+args.pdf.name
        saved = store.client.put_object(Bucket=store.bucket, Key=key, Body=raw)
        version = saved.get('VersionId')
        if not version or version == 'null':
            raise ValueError('Versioned source capture required')
        return {'key': key, 'name': args.pdf.name, 'sha256': digest, 'version_id': version}
    from temporalio.client import Client
    from temporalio.common import WorkflowIDReusePolicy
    client = await Client.connect(os.environ['TEMPORAL_ADDRESS'])
    if args.command == 'submit':
        request = json.loads(args.request.read_text())
        if request.get('version') != 3 or request.get('completion') != 'required_evidence_v1':
            raise ValueError('Release submission requires v3 required_evidence_v1')
        value = submission(request, route['id'], {route['id']: route})
        handle = await client.start_workflow('PDFRolloutProcessing', value,
            id=args.workflow_id, task_queue=route['queues']['workflow'],
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
        return {'workflow_id': handle.id, 'routing_id': route['id']}
    handle = client.get_workflow_handle(args.workflow_id)
    description = await handle.describe()
    if description.status is None:
        raise ValueError('Workflow status unavailable')
    summary = await handle.query('progress') if description.status.name == 'RUNNING' else await handle.result()
    if summary.get('routing_id') != route['id']:
        raise ValueError('Workflow belongs to another release')
    if args.command == 'status':
        return {'temporal_status': description.status.name, **summary}
    return await asyncio.to_thread(export_result, store_for(route), summary, args.out)


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--route', type=Path, required=True)
    commands = cli.add_subparsers(dest='command', required=True)
    commands.add_parser('capture').add_argument('--pdf', type=Path, required=True)
    submit = commands.add_parser('submit')
    submit.add_argument('--request', type=Path, required=True)
    submit.add_argument('--workflow-id', required=True)
    commands.add_parser('status').add_argument('--workflow-id', required=True)
    result = commands.add_parser('export')
    result.add_argument('--workflow-id', required=True)
    result.add_argument('--out', type=Path, required=True)
    print(json.dumps(asyncio.run(run(cli.parse_args())), indent=2))
