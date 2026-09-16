"""Combined full-request cases; invoke each case in a separate process within a coordinated window.

Real production Activities and shared storage; no imported checkpoint registrations.
The supplied profile must already be frozen with freeze_profile.py for this producer.
Full documents and runtime reports stay in the caller's private output directory.
"""
import argparse
import asyncio
import json
from pathlib import Path
import uuid
import copy
import fcntl
import os
import sys
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/"tests/pdf_processing/q02"))
from fixtures import policy as relationship_policy
from oracle.score import score
from pdf_processing.processing import encoded
from pdf_processing.relationships import validate

from pdf_processing.object_store import Store, digest


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


def verify_delivery(document, report, source, parsed, assembly, policy):
    verify_continuation(document)
    validate(report, document, source, parsed, assembly, policy)
    assert len(report['resolved']) == 2 and not report['unresolved']
    candidate = copy.deepcopy(report['candidates'])
    candidate['relationships'] = [{**r, 'disposition': 'candidate'} for r in report['resolved']]
    verdicts = score(document, candidate)
    assert len(verdicts) >= 2 and all(v['structure_pass'] for v in verdicts[:2])


def verify_work(result, selection, final, fresh):
    selected = selection['selected']
    assert selected, 'Actual selected OCR is required; empty selection is not acceptance'
    assert sorted(selected) == sorted(e['component'] for e in final['enrichments'])
    groups = [s for s in result['steps'] if s['stage'] == 'group']
    assemblies = [s for s in result['steps'] if s['stage'] == 'assembly']
    assert groups and len(assemblies) == 1, 'Missing executed parsing stages'
    assert all(s['reused'] is (not fresh) for s in groups+assemblies)
    ocr = [s for s in result['steps'] if s['stage'] == 'component_ocr']
    assert sorted(s['component'] for s in ocr) == sorted(selected)
    if fresh:
        assert all(s['reused'] is False for s in ocr), 'Fresh OCR must execute'


async def main(args):
    import boto3
    from temporalio.client import Client
    from temporalio.worker import Worker
    from pdf_processing.processing import Processing
    from pdf_processing.processing_workflow import PDFProcessing

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    profile = json.loads(Path(args.profile).read_text())
    producer = {p.name: digest(p.read_bytes()) for p in (ROOT/'src/pdf_processing').glob('*.py')}
    frozen = json.loads(Path(args.producer).read_text())
    assert producer == frozen['producer'], 'Re-freeze changed producer'
    profile['content_evidence'] = {**profile.get('content_evidence', {}),
        'version': 'typed-source-relationships-v2', 'relationships': relationship_policy()}
    profile['content_evidence'].setdefault('reviews', {})
    if args.case == 'evidence':
        profile['content_evidence']['relationships']['unresolved'] = 'allow_unknown'

    assert profile['method']['continuation']['version'] == 'column-edge-continuation-v1'
    pdf = Path(args.pdf).read_bytes()
    assert digest(pdf) == 'b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980'
    s3 = boto3.client('s3', endpoint_url=args.endpoint)
    assert s3.get_bucket_versioning(Bucket=args.bucket).get('Status') == 'Enabled'
    store = Store(s3, args.bucket, args.prefix)
    if args.case == 'fresh':
        assert not s3.list_objects_v2(Bucket=args.bucket, Prefix=store.prefix, MaxKeys=1).get('Contents'), 'Prefix must be unused'
    previous = None
    if args.case != 'fresh':
        previous = json.loads(Path(args.fresh_evidence).read_text())
        assert previous['endpoint'] == args.endpoint and previous['bucket'] == args.bucket and previous['prefix'] == args.prefix
        assert previous['verified'] is True and previous['case'] == 'fresh'
        assert previous['producer'] == producer
        assert previous['request']['artifact']['sha256'] == digest(pdf)
        profile['content_evidence']['reviews'] = previous['profile']['content_evidence']['reviews']
        expected_profile = copy.deepcopy(previous['profile'])
        if args.case == 'evidence':
            expected_profile['content_evidence']['relationships']['unresolved'] = 'allow_unknown'
        assert {k:v for k,v in profile.items() if k != 'release'} == {k:v for k,v in expected_profile.items() if k != 'release'}

    def capture(name, data):
        key = store.prefix+'sources/'+name
        response = s3.put_object(Bucket=args.bucket, Key=key, Body=data)
        return {'name': name, 'key': key, 'version_id': response['VersionId'], 'sha256': digest(data)}

    # Preserve selected original-source evidence, with separately captured references
    # in this run's namespace. Never mutate the prior profile or source objects.
    review = profile.get('content_evidence', {}).get('reviews', {}).get(digest(pdf), {})
    if args.case == 'fresh' and review.get('original_source'):
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
               'artifact': capture('08.pdf', pdf) if previous is None else previous['request']['artifact']}
    if previous is not None:
        profile['content_evidence']['reviews'] = previous['profile']['content_evidence']['reviews']
        if args.case == 'exact':
            request = previous['request']
            profile = previous['profile']
    if args.case != 'exact':
        profile['release'] = 'q01-q02-' + digest(encoded({'producer': producer,
            'profile': {k:v for k,v in profile.items() if k != 'release'}}))
    processing = Processing(store, out/'scratch', args.model_cache, profile)
    client = await Client.connect(args.temporal)
    queue = 'q01-'+uuid.uuid4().hex
    metadata = {'request': request, 'profile': profile, 'producer': processing.producer, 'queue': queue,
                'endpoint': args.endpoint, 'bucket': args.bucket, 'prefix': args.prefix, 'topology': args.topology,
                'pid': os.getpid(), 'case': args.case}
    (out/'admission.json').write_text(json.dumps(metadata, indent=2))

    def read(identity, name):
        registration = store.resolve(identity)
        assert registration is not None
        return store.read_artifact(next(f for f in registration['files'] if f['name'] == name))

    async with Worker(client, task_queue=queue, activities=[processing.run], workflows=[PDFProcessing],
                      max_concurrent_activities=1, graceful_shutdown_timeout=timedelta(seconds=30)):
        for trial in (args.case,):
            workflow_id = 'q01-'+trial+'-'+uuid.uuid4().hex
            handle = await client.start_workflow(PDFProcessing.run,
                {'request': request, 'activity_queue': queue}, id=workflow_id, task_queue=queue,
                execution_timeout=timedelta(seconds=args.timeout))
            try:
                result = await asyncio.wait_for(handle.result(), timeout=args.timeout+30)
            except BaseException:
                await handle.cancel()
                raise
            (out/'history.json').write_text((await handle.fetch_history()).to_json())
            (out/(trial+'-result.json')).write_text(json.dumps(result, indent=2))
            assert result['status'] == 'complete', result
            final = json.loads(read(result['processing_result'], 'processing-result.json'))
            assert final['processing_complete'] and not final['canonical_accepted'] and not final['quality_accepted']
            raw = read(final['assembly'], 'document.json')
            verify_continuation(json.loads(raw))
            evidence = json.loads(read(final['content_evidence'], 'content-evidence.json'))
            assert evidence['document_sha256'] == digest(raw) and evidence['source'] == request
            binding = json.loads(read(final['relationships'], 'relationships.json'))
            assert binding['content_evidence'] == final['content_evidence']
            verify_delivery(json.loads(raw), binding['relationships'], request, final['parsed_result'],
                            final['assembly'], profile['content_evidence']['relationships'])
            selection = json.loads(read(final['selection'], 'selection.json'))
            assert sorted(selection['selected']) == sorted(e['component'] for e in final['enrichments'])
            verify_work(result, selection, final, trial == 'fresh')
            for identity in [final['relationships'], final['content_evidence'], *(e['operation'] for e in final['enrichments'])]:
                registration = store.resolve(identity)
                assert registration is not None
                for artifact in registration['files']:
                    store.read_artifact(artifact)
            if previous is not None:
                assert final['assembly'] == previous['final']['assembly']
                if trial == 'exact':
                    assert result['processing_result'] == previous['processing_result']
                else:
                    assert result['processing_result'] != previous['processing_result']
                    assert final['content_evidence'] != previous['final']['content_evidence']
            metadata.update(final=final, processing_result=result['processing_result'],
                            selected_ocr=len(selection['selected']), verified=True)
            history = await client.get_workflow_handle(workflow_id).fetch_history()
            scheduled = [e.activity_task_scheduled_event_attributes.activity_type.name for e in history.events
                         if e.HasField('activity_task_scheduled_event_attributes')]
            assert scheduled
            (out/(trial+'-verification.json')).write_text(json.dumps({
                'workflow_id': workflow_id, 'activities': scheduled, 'final': final,
                'correct_continuation': True, 'required_artifacts_readable': True,
                'document_sha256': digest(raw)}, indent=2))
            (out/'accepted.json').write_text(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for option in ('profile', 'producer', 'pdf', 'model-cache', 'out', 'prefix', 'temporal', 'endpoint', 'bucket', 'topology'):
        parser.add_argument('--'+option, required=True)
    parser.add_argument('--case', choices=['fresh','reuse','exact','evidence'], required=True)
    parser.add_argument('--fresh-evidence')
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--capacity-approved', action='store_true')
    args = parser.parse_args()
    if not args.capacity_approved or (args.case != 'fresh' and not args.fresh_evidence) or args.timeout <= 0:
        parser.error('A coordinated capacity window, positive timeout and prior evidence for reuse are required')
    with open(os.environ.get('PDF_QUALIFICATION_LOCK', '/tmp/data-ingestion-pdf-qualification.lock'), 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(main(args))
