"""Run only in a coordinated capacity window, using isolated queues and a fresh prefix.

Real production Activities and shared storage; no imported checkpoint registrations.
The supplied profile must already be frozen with freeze_profile.py for this producer.
Full documents and runtime reports stay in the caller's private output directory.
"""
import argparse
import asyncio
import json
from pathlib import Path
import uuid

import boto3
from temporalio.client import Client
from temporalio.worker import Worker

from pdf_processing.object_store import Store, digest
from pdf_processing.processing import Processing
from pdf_processing.processing_workflow import PDFProcessing


def verify_continuation(document):
    # Independently pinned R2 source-region text hashes, never production inputs.
    expected = {5: '62cf9a379d2767569f3ed3fa6840724f5afd648cefe06ce14f49cf416f7fafcc',
                6: 'c348f3382fb87ab746b9bfaf718631782bd4cb9e6e9a5cfe49f5abd94fbbc141'}
    matches = []
    for item in document['texts']:
        parts = [(p['page_no'], digest(item['text'][slice(*p['charspan'])].encode()))
                 for p in item['prov']]
        if all((page, sha) in parts for page, sha in expected.items()):
            assert len(parts) == 2 and [p for p, _ in parts] == [5, 6]
            matches.append(item['self_ref'])
    assert len(matches) == 1, 'Required source continuation missing or wrongly joined'


async def main(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    profile = json.loads(Path(args.profile).read_text())
    assert profile['method']['continuation']['version'] == 'column-edge-continuation-v1'
    pdf = Path(args.pdf).read_bytes()
    assert digest(pdf) == 'b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980'
    s3 = boto3.client('s3', endpoint_url=args.endpoint)
    assert s3.get_bucket_versioning(Bucket=args.bucket).get('Status') == 'Enabled'
    store = Store(s3, args.bucket, args.prefix)
    assert not s3.list_objects_v2(Bucket=args.bucket, Prefix=store.prefix, MaxKeys=1).get('Contents'), 'Prefix must be unused'

    def capture(name, data):
        key = store.prefix+'sources/'+name
        response = s3.put_object(Bucket=args.bucket, Key=key, Body=data)
        return {'name': name, 'key': key, 'version_id': response['VersionId'], 'sha256': digest(data)}

    # Preserve selected original-source evidence, with separately captured references
    # in this run's namespace. Never mutate the prior profile or source objects.
    review = profile.get('content_evidence', {}).get('reviews', {}).get(digest(pdf), {})
    if review.get('original_source'):
        original = review['original_source']['artifact']
        body = s3.get_object(Bucket=args.bucket, Key=original['key'], VersionId=original['version_id'])['Body']
        try:
            data = body.read()
        finally:
            body.close()
        assert digest(data) == original['sha256']
        review['original_source']['artifact'] = capture('original.pdf', data)
    request = {'version': 3, 'completion': 'required_evidence_v1', 'profile': profile['id'],
               'request_id': 'q01-'+uuid.uuid4().hex, 'source_revision': 'q01-aima-99-110-'+digest(pdf),
               'artifact': capture('08.pdf', pdf)}
    processing = Processing(store, out/'scratch', args.model_cache, profile)
    client = await Client.connect(args.temporal)
    queue = 'q01-'+uuid.uuid4().hex
    metadata = {'request': request, 'profile': profile, 'producer': processing.producer, 'queue': queue}
    (out/'admission.json').write_text(json.dumps(metadata, indent=2))

    def read(identity, name):
        registration = store.resolve(identity)
        assert registration is not None
        return store.read_artifact(next(f for f in registration['files'] if f['name'] == name))

    async with Worker(client, task_queue=queue, activities=[processing.run], workflows=[PDFProcessing],
                      max_concurrent_activities=1):
        for trial in ('fresh', 'reuse'):
            request = {**request, 'request_id': 'q01-'+trial+'-'+uuid.uuid4().hex}
            workflow_id = 'q01-'+trial+'-'+uuid.uuid4().hex
            result = await client.execute_workflow(PDFProcessing.run,
                {'request': request, 'activity_queue': queue}, id=workflow_id, task_queue=queue)
            (out/(trial+'-result.json')).write_text(json.dumps(result, indent=2))
            assert result['status'] == 'complete', result
            final = json.loads(read(result['processing_result'], 'processing-result.json'))
            assert final['processing_complete'] and not final['canonical_accepted'] and not final['quality_accepted']
            raw = read(final['assembly'], 'document.json')
            verify_continuation(json.loads(raw))
            evidence = json.loads(read(final['content_evidence'], 'content-evidence.json'))
            assert evidence['document_sha256'] == digest(raw) and evidence['source'] == request
            selection = json.loads(read(final['selection'], 'selection.json'))
            assert sorted(selection['selected']) == sorted(e['component'] for e in final['enrichments'])
            for identity in [final['content_evidence'], *(e['operation'] for e in final['enrichments'])]:
                registration = store.resolve(identity)
                assert registration is not None
                for artifact in registration['files']:
                    store.read_artifact(artifact)
            if trial == 'reuse':
                assert all(s['reused'] for s in result['steps'] if s['stage'] in ('group', 'assembly'))
            else:
                assert all(not s['reused'] for s in result['steps'] if s['stage'] in ('group', 'assembly'))
            history = await client.get_workflow_handle(workflow_id).fetch_history()
            scheduled = [e.activity_task_scheduled_event_attributes.activity_type.name for e in history.events
                         if e.HasField('activity_task_scheduled_event_attributes')]
            assert scheduled
            (out/(trial+'-verification.json')).write_text(json.dumps({
                'workflow_id': workflow_id, 'activities': scheduled, 'final': final,
                'correct_continuation': True, 'required_artifacts_readable': True,
                'document_sha256': digest(raw)}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for option in ('profile', 'pdf', 'model-cache', 'out', 'prefix'):
        parser.add_argument('--'+option, required=True)
    parser.add_argument('--temporal', default='temporal:7233')
    parser.add_argument('--endpoint', default='http://objects:9000')
    parser.add_argument('--bucket', default='t09a')
    asyncio.run(main(parser.parse_args()))
