"""Prepared Q03 seeded-finalization driver; actual Temporal/shared storage NOT RUN.

Seeds plan, parsed, assembly and empty OCR selection. Only evidence rendering and
finalization are real. No native parsing, OCR, full-request or canonical claim.
"""
import argparse
import asyncio
import copy
import fcntl
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
from datetime import timedelta
import uuid

from temporalio import workflow
from temporalio.common import RetryPolicy
from pdf_processing.processing import Processing, encoded
from pdf_processing.object_store import Store, digest
from pdf_processing.compatibility import dependencies
from pdf_processing.enrichment import Enrichment
from fixtures import document, mutate, SOURCE, BASELINE
from test_publication import seed
from q03_fixtures import profile
from interruption import EvidenceInterruption, interrupted_call, registration_operations


@workflow.defn
class Q03FinalBoundary:
    @workflow.run
    async def run(self, value: dict) -> dict:
        return await workflow.execute_activity(
            'pdf_processing_step_v1', value,
            start_to_close_timeout=timedelta(minutes=12),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1))


def application_failure(error):
    """Return the outer application classification, preserving nested diagnostics."""
    from temporalio.exceptions import ApplicationError
    while error is not None:
        if isinstance(error, ApplicationError):
            return error
        error = getattr(error, 'cause', None)
    return None


def scenarios():
    yield 'valid', None
    yield 'split', None
    yield 'interrupted-evidence', None
    for ri, review in enumerate(profile()['content_evidence']['relationships']['representation']['reviews']):
        for stream, declaration in review['streams'].items():
            for di in range(len(declaration['differences'])):
                yield f'gate-{ri}-{stream}-{di}', (ri, stream, di)
        for si in range(len(review['isolated_symbols'])):
            yield f'gate-{ri}-symbol-{si}', (ri, 'symbol', si)
    for name in ('missing_body', 'missing_recursive_body', 'missing_caption',
                 'wrong_raw_offset', 'fabricated_symbol_position', 'wrong_review',
                 'wrong_page', 'wrong_source', 'wrong_document', 'corrupt_page',
                 'missing_source', 'missing_page'):
        yield name, None


def inject(files, case, doc, request, prof):
    from pdf_processing.relationships import build
    report = build(doc, request, 'parsed', 'assembly', prof['content_evidence']['relationships'])
    if case in ('split', 'missing_body'):
        report = mutate(report, case, doc)
    elif case == 'missing_recursive_body': report['resolved'][2]['members'].pop(1)
    elif case == 'missing_caption': report['resolved'][3]['members'].pop()
    elif case == 'wrong_raw_offset':
        report['resolved'][2]['representation']['streams']['header_body']['differences'][0]['raw_extracted_ranges'][0]['range'] = [447, 448]
    elif case == 'fabricated_symbol_position':
        report['resolved'][2]['representation']['isolated_symbols'][0]['position_in_body'] = 1
    elif case == 'wrong_review': report['resolved'][2]['representation']['review_id'] = 'unrelated'
    files['relationships.json'] = encoded(report)
    content = json.loads(files['content-evidence.json'])
    content['source'] = copy.deepcopy(request)
    if case == 'wrong_page': content['pages']['9']['physical_page'] = 10
    elif case == 'wrong_source': content['source']['source_revision'] = 'other'
    elif case == 'wrong_document': content['document_sha256'] = 'a'*64
    elif case == 'missing_source': del files['source.pdf']
    elif case == 'missing_page': del files[content['pages']['9']['artifact']]
    elif case == 'corrupt_page':
        data = b'hash-consistent but unreadable PNG'
        files[content['pages']['9']['artifact']] = data
        content['pages']['9']['sha256'] = digest(data)
    files['content-evidence.json'] = encoded(content)


def producer_manifest():
    import pdf_processing.processing as module
    root = Path(module.__file__).resolve().parent
    return {p.name: digest(p.read_bytes()) for p in sorted(root.glob('*.py'))}


def retain(store, identity, directory):
    registration = store.resolve(identity)
    assert registration is not None
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'registration.json').write_bytes(encoded(registration))
    files = {}
    for entry in registration['files']:
        data = store.read_artifact(entry)
        path = directory/entry['name']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files[entry['name']] = data
    return registration, files


def absent_complete(store):
    ids = registration_operations(store)
    assert not any(i.startswith('pdf-complete-') for i in ids), ids
    return ids


async def run(args):
    import boto3
    from botocore.config import Config
    from docling_core.types.doc import DoclingDocument
    from temporalio.client import Client, WorkflowFailureError
    from temporalio.exceptions import ApplicationError
    from temporalio.worker import Worker, UnsandboxedWorkflowRunner
    from oracle.score import score
    from pdf_processing.relationships import validate

    producer = producer_manifest()
    assert json.loads(Path(args.producer).read_text())['producer'] == producer, 'Producer manifest differs from actual source files'
    source = Path(args.pdf).read_bytes()
    assert digest(source) == SOURCE
    prof = profile()
    assert prof['content_evidence']['version'] == 'typed-source-relationships-v2'
    assert prof['content_evidence']['relationships']['representation']['version'] == 'source-reviewed-representation-v1'
    prof['method']['packages']['pypdfium2'] = importlib.metadata.version('pypdfium2')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'source.pdf').write_bytes(source)
    (out/'baseline-document.json').write_bytes(BASELINE.read_bytes())
    DoclingDocument.model_validate(document()).save_as_json(out/'document.json')
    raw = (out/'document.json').read_bytes()
    doc = json.loads(raw)
    run_id = uuid.uuid4().hex
    prefix = args.prefix.strip('/')
    assert prefix and all(p not in ('', '.', '..') for p in prefix.split('/'))
    metadata = {'scope': __doc__, 'seeded': ['plan', 'parsed', 'assembly', 'group', 'empty OCR selection'],
                'producer': producer, 'driver_sha256': digest(Path(__file__).read_bytes()),
                'interruption_hook_sha256': digest(Path(__file__).with_name('interruption.py').read_bytes()),
                'topology': args.topology, 'capacity_acknowledged': True, 'pid': os.getpid(),
                'case_selection': args.case,
                'prefix': prefix, 'run_id': run_id, 'source_sha256': SOURCE,
                'endpoint': args.endpoint, 'bucket': args.bucket,
                'review_sha256': digest((Path(__file__).parent/'reviewed-representation.json').read_bytes()),
                'document_sha256': digest(raw), 'results': []}
    (out/'admission.json').write_bytes(encoded(metadata))
    s3 = boto3.client('s3', endpoint_url=args.endpoint,
                      config=Config(connect_timeout=10, read_timeout=30, retries={'max_attempts': 2}))
    assert s3.get_bucket_versioning(Bucket=args.bucket).get('Status') == 'Enabled'
    assert not s3.list_objects_v2(Bucket=args.bucket, Prefix=prefix+'/', MaxKeys=1).get('Contents'), 'Prefix must be unused'
    client = await asyncio.wait_for(Client.connect(args.temporal), 30)
    original_files = None
    for case, gate in scenarios():
        if args.case != 'matrix' and case != args.case:
            continue
        assert producer_manifest() == producer, 'Source changed during qualification'
        case_out = out/case
        case_out.mkdir()
        store = Store(s3, args.bucket, f'{prefix}/{run_id}/{case}')
        case_profile = copy.deepcopy(prof)
        if gate:
            ri, stream, index = gate
            review = case_profile['content_evidence']['relationships']['representation']['reviews'][ri]
            observation = review['isolated_symbols'][index] if stream == 'symbol' else review['streams'][stream]['differences'][index]
            observation['disposition'] = 'release_gate'
        saved = s3.put_object(Bucket=args.bucket, Key=store.prefix+'sources/source.pdf', Body=source, IfNoneMatch='*')
        assert saved.get('VersionId') and saved['VersionId'] != 'null'
        request = {'version': 3, 'completion': 'required_evidence_v1', 'profile': 'native-v1',
                   'request_id': 'q03-'+uuid.uuid4().hex, 'source_revision': 'q03:seeded-retained-aima',
                   'artifact': {'sha256': SOURCE, 'key': store.prefix+'sources/source.pdf',
                                'version_id': saved['VersionId'], 'name': 'source.pdf'}}
        with tempfile.TemporaryDirectory(prefix='q03-runtime-') as tmp:
            processing = Processing(store, tmp, tmp, case_profile)
            assert processing.producer == producer
            processing.validate_request(request)
            seed(processing, doc, request, document_bytes=raw)
            evidence_id = 'pdf-evidence-v1:' + digest(encoded({'assembly': 'assembly', 'parsed_result': 'parsed',
                'source': request, 'policy': case_profile['content_evidence'],
                'dependencies': dependencies('evidence', case_profile, producer)}))
            real_child = case in ('valid', 'interrupted-evidence') or gate is not None
            if not real_child:
                assert original_files is not None
                files = copy.deepcopy(original_files)
                inject(files, case, doc, request, case_profile)
                store.publish(evidence_id, files)
            else:
                assert store.resolve(evidence_id) is None
            queue = 'q03-'+uuid.uuid4().hex
            record = {'case': case, 'gate': gate, 'request': request, 'profile': case_profile,
                      'queue': queue, 'prefix': store.prefix, 'evidence': evidence_id,
                      'evidence_origin': 'real supervised child' if real_child else 'fault-injected copy of valid child output'}
            (case_out/'admission.json').write_bytes(encoded(record))
            value = {'stage': 'finalize', 'plan': 'plan', 'selection': 'selection', 'outcomes': []}
            async with Worker(client, task_queue=queue, workflows=[Q03FinalBoundary], activities=[processing.run],
                              workflow_runner=UnsandboxedWorkflowRunner(), max_concurrent_activities=1,
                              graceful_shutdown_timeout=timedelta(seconds=30)):
                async def execute(label):
                    handle = await client.start_workflow(Q03FinalBoundary.run, value,
                        id='q03-'+uuid.uuid4().hex, task_queue=queue,
                        execution_timeout=timedelta(seconds=args.timeout))
                    (case_out/(label+'-handle.json')).write_bytes(encoded({'id': handle.id, 'run_id': handle.result_run_id}))
                    try:
                        return await asyncio.wait_for(handle.result(), args.timeout+30)
                    except WorkflowFailureError:
                        raise
                    except BaseException:
                        await asyncio.wait_for(handle.cancel(), 15)
                        raise
                    finally:
                        history = await asyncio.wait_for(handle.fetch_history(), 15)
                        (case_out/(label+'-history.json')).write_text(history.to_json())
                        counts = {
                            'scheduled': sum(e.HasField('activity_task_scheduled_event_attributes') for e in history.events),
                            'completed': sum(e.HasField('activity_task_completed_event_attributes') for e in history.events),
                            'failed': sum(e.HasField('activity_task_failed_event_attributes') for e in history.events),
                        }
                        record.setdefault('history', {})[label] = counts
                        assert counts['scheduled'] == 1, counts
                if case == 'interrupted-evidence':
                    assembly_before, assembly_files = retain(store, 'assembly', case_out/'assembly-before-interruption')
                    assert assembly_files['document.json'] == raw
                    hook = EvidenceInterruption(store, processing.scratch, evidence_id, SOURCE,
                                                digest(raw), case_out/'interruption', timeout=args.interrupt_timeout)
                    observation, failure = await interrupted_call(hook, lambda: execute('interrupted'))
                    cause = application_failure(failure)
                    assert isinstance(failure, WorkflowFailureError), failure
                    assert isinstance(cause, ApplicationError) and cause.type == 'parser', cause
                    assert str(cause).endswith('execution_failed'), cause
                    assert record['history']['interrupted']['failed'] == 1
                    assert record['history']['interrupted']['completed'] == 0
                    assert not Path(observation['scratch']).exists(), 'Failed scratch was not cleaned'
                    record['interruption'] = observation
                    record['interrupted_failure'] = str(cause)
                    record['registrations_after_interruption'] = absent_complete(store)
                    assert store.resolve(evidence_id) is None
                    assert store.resolve('assembly') == assembly_before
                    record['evidence_absent_after_interruption'] = True
                    record['child_reaped_and_scratch_removed'] = True
                    record['assembly_registration_unchanged'] = True
                    assert producer_manifest() == producer
                    (case_out/'interrupted-failure.json').write_bytes(encoded(record))
                    # Same accepted plan/request, production code and worker. The
                    # next actual Activity must spawn a new evidence interpreter.
                try:
                    result = await execute('initial')
                except WorkflowFailureError as error:
                    cause = application_failure(error)
                    record['failure'] = str(cause)
                    (case_out/'failure.json').write_bytes(encoded(record))
                    assert case not in ('valid', 'split', 'interrupted-evidence'), record
                    assert isinstance(cause, ApplicationError) and cause.type == 'integrity', record
                    if gate: assert 'representation_release_gate' in str(cause)
                    # A gate must have completed real rendering before validation rejects it.
                    _, failed_files = retain(store, evidence_id, case_out/'evidence')
                    if gate:
                        assert failed_files['source.pdf'] == source
                        assert json.loads(failed_files['content-evidence.json'])['source'] == request
                    assert record['history']['initial']['failed'] == 1
                    record['registrations'] = absent_complete(store)
                    record['complete_registration_absent'] = True
                else:
                    assert case in ('valid', 'split', 'interrupted-evidence'), (case, result)
                    _, final_files = retain(store, result['operation'], case_out/'final')
                    final = json.loads(final_files['processing-result.json'])
                    assert final['processing_complete'] and not final['quality_accepted'] and not final['canonical_accepted']
                    assert final['content_evidence'] == evidence_id
                    _, assembly = retain(store, final['assembly'], case_out/'assembly')
                    assert assembly['document.json'] == raw
                    _, evidence_files = retain(store, evidence_id, case_out/'evidence')
                    assert evidence_files['source.pdf'] == source
                    content = json.loads(evidence_files['content-evidence.json'])
                    assert content['source'] == request and content['document_sha256'] == digest(raw)
                    _, bindings = retain(store, final['relationships'], case_out/'relationships')
                    binding = json.loads(bindings['relationships.json'])
                    assert binding['content_evidence'] == evidence_id
                    report = binding['relationships']
                    validate(report, doc, request, final['parsed_result'], final['assembly'], case_profile['content_evidence']['relationships'])
                    assert len(report['resolved']) == 4 and not report['unresolved']
                    candidate = copy.deepcopy(report['candidates'])
                    candidate['relationships'] = [{**r, 'disposition': 'candidate'} for r in report['resolved']]
                    verdicts = score(json.loads(assembly['document.json']), candidate)
                    assert len(verdicts) == 4 and all(v['structure_pass'] for v in verdicts), verdicts
                    assert len(binding['representation_evidence']) == 4
                    evidence_registration = store.resolve(evidence_id)
                    entries = {f['name']: f for f in evidence_registration['files']}
                    views = []
                    for relation, item in zip(report['resolved'], binding['representation_evidence']):
                        assert item['relationship'] == relation['id']
                        assert item['review_id'] == relation['representation']['review_id']
                        assert len(item['views']) == 1+len(relation['representation']['isolated_symbols'])
                        for view in item['views']:
                            entry = entries[view['page_artifact']]
                            assert entry['sha256'] == view['page_sha256']
                            views.append({**view, 'key': entry['key']})
                    retry = await execute('retry')
                    assert retry['operation'] == result['operation']
                    assert all(record['history'][label]['completed'] == 1
                               for label in ('initial', 'retry'))
                    retried = Enrichment(processing).read(retry['operation'], 'processing-result.json')
                    assert retried == final
                    if case == 'interrupted-evidence':
                        complete = [i for i in registration_operations(store) if i.startswith('pdf-complete-')]
                        assert complete == [result['operation']], complete
                        record['single_complete_registration'] = complete[0]
                    record.update(final=result['operation'], relationships=final['relationships'],
                                  oracle_scores=verdicts, representation_views=views, retry_same_final=True)
                    if case == 'valid': original_files = evidence_files
                assert producer_manifest() == producer, 'Source changed during qualification'
                record['verified'] = True
                (case_out/'accepted.json').write_bytes(encoded(record))
                metadata['results'].append(record)
                (out/'runtime.json').write_bytes(encoded(metadata))
                print(case, 'PASS', flush=True)
    metadata['verified'] = True
    (out/'accepted.json').write_bytes(encoded(metadata))


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('producer', 'pdf', 'out', 'prefix', 'temporal', 'endpoint', 'bucket', 'topology'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--capacity-approved', action='store_true')
    parser.add_argument('--timeout', type=int, default=900, help='Per-workflow server deadline in seconds')
    parser.add_argument('--total-timeout', type=int, default=7200)
    parser.add_argument('--case', choices=['matrix', 'interrupted-evidence'], default='matrix')
    parser.add_argument('--interrupt-timeout', type=int, default=30,
                        help='Maximum seconds to observe and interrupt a partially rendered owned child')
    args = parser.parse_args()
    if not __debug__:
        parser.error('Do not use python -O; verification uses assertions')
    if not args.capacity_approved or args.timeout <= 0 or args.total_timeout <= 0 or args.interrupt_timeout <= 0:
        parser.error('Coordinated capacity acknowledgement and positive timeouts are required')
    async def bounded():
        from pdf_processing.execution import stop_fresh_children
        try:
            await asyncio.wait_for(run(args), args.total_timeout)
        finally:
            await stop_fresh_children()
    with open(os.environ.get('PDF_QUALIFICATION_LOCK', '/tmp/data-ingestion-pdf-qualification.lock'), 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(bounded())


if __name__ == '__main__':
    cli()
