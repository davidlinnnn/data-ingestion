"""Checkpoint-fed evidence/finalization through actual Temporal + shared storage.

This deliberately seeds upstream fixtures. It does NOT qualify native parsing,
OCR engine execution, restored assembly, or an end-to-end PDFProcessing request.
No shared worker/deployment is changed; all writes use a fresh Q02 prefix.
"""
import asyncio
import copy
import fcntl
from datetime import timedelta
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
import uuid

import boto3
from temporalio import workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.client import WorkflowFailureError
from temporalio.worker import Worker, UnsandboxedWorkflowRunner
from pdf_processing.processing import Processing, encoded
from pdf_processing.enrichment import Enrichment
from pdf_processing.object_store import Store, digest
from pdf_processing.compatibility import dependencies
from fixtures import document, policy, mutate, FAILURES, SOURCE
from test_publication import profile, seed


@workflow.defn
class FinalBoundary:
    @workflow.run
    async def run(self, value: dict) -> dict:
        return await workflow.execute_activity('pdf_processing_step_v1', value,
            start_to_close_timeout=timedelta(minutes=3), heartbeat_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(maximum_attempts=1))


async def main():
    out = Path(os.environ['Q02_OUTPUT'])
    out.mkdir(parents=True, exist_ok=False)
    s3 = boto3.client('s3', endpoint_url=os.environ['Q02_ENDPOINT'])
    client = await Client.connect(os.environ['Q02_TEMPORAL'])
    bucket = os.environ['Q02_BUCKET']
    prefix_root = os.environ['Q02_PREFIX'].strip('/')
    assert prefix_root and s3.get_bucket_versioning(Bucket=bucket).get('Status') == 'Enabled'
    assert not s3.list_objects_v2(Bucket=bucket, Prefix=prefix_root+'/', MaxKeys=1).get('Contents')
    run_id = uuid.uuid4().hex
    results = []
    source = Path(os.environ.get('Q02_PDF', '/private/tmp/t09a-fixtures/08.pdf')).read_bytes()
    assert digest(source) == SOURCE
    from docling_core.types.doc import DoclingDocument
    # Match production save_as_json aliases/precision; raw retained replay is immutable.
    DoclingDocument.model_validate(document()).save_as_json(out/'document.json')
    doc = json.loads((out/'document.json').read_text())
    # Each scenario has independent immutable registrations. Valid scenario executes
    # the real supervised evidence child. Mutations are fault-injected registrations.
    original_files = None
    for case in ['valid', 'split', 'allowed_unknown', 'required_missing', 'missing_output', 'missing_ocr'] + FAILURES:
        prefix = f'{prefix_root}/{run_id}/{case}'
        store = Store(s3, bucket, prefix)
        prof = profile()
        prof['method']['packages']['pypdfium2'] = importlib.metadata.version('pypdfium2')
        if case == 'allowed_unknown':
            prof['content_evidence']['relationships'] = {'method': 'local-function-block-v1',
                'coverage': {'mode': 'unknown'}, 'unresolved': 'allow_unknown'}
        if case == 'required_missing':
            prof['content_evidence']['relationships']['coverage']['regions'][0]['required_count'] = 2
        saved = s3.put_object(Bucket=bucket, Key=store.prefix+'sources/source.pdf', Body=source)
        request = {'version': 3, 'completion': 'required_evidence_v1', 'profile': 'native-v1',
                   'request_id': uuid.uuid4().hex, 'source_revision': 'q02:retained-aima',
                   'artifact': {'sha256': SOURCE, 'key': store.prefix+'sources/source.pdf',
                                'version_id': saved['VersionId'], 'name': 'source.pdf'}}
        with tempfile.TemporaryDirectory(prefix='q02-runtime-') as tmp:
            processing = Processing(store, tmp, tmp, prof)
            processing.validate_request(request)
            plan, selection = seed(processing, doc, request)
            queue = 'q02-'+uuid.uuid4().hex
            # Actual source-backed child for successful and unresolved cases.
            if case not in ('valid', 'allowed_unknown', 'required_missing'):
                assert original_files is not None
                files = copy.deepcopy(original_files)
                from pdf_processing.relationships import build
                report = build(doc, request, 'parsed', 'assembly', prof['content_evidence']['relationships'])
                files['relationships.json'] = encoded(mutate(report, case, doc))
                content = json.loads(files['content-evidence.json'])
                content['source'] = request
                files['content-evidence.json'] = encoded(content)
                if case == 'missing_output': del files['relationships.json']
                evidence_id = 'pdf-evidence-v1:' + digest(encoded({'assembly': 'assembly', 'parsed_result': 'parsed',
                    'source': request, 'policy': prof['content_evidence'],
                    'dependencies': dependencies('evidence', prof, processing.producer)}))
                store.publish(evidence_id, files)
            if case == 'missing_ocr':
                selection['selected'] = ['#/pictures/required']
                store.publish('selected-ocr', {'selection.json': encoded(selection)})
            value = {'stage': 'finalize', 'plan': 'plan', 'selection': 'selected-ocr' if case == 'missing_ocr' else 'selection', 'outcomes': []}
            expected_success = case in ('valid', 'split', 'allowed_unknown')
            async with Worker(client, task_queue=queue, workflows=[FinalBoundary], activities=[processing.run],
                              workflow_runner=UnsandboxedWorkflowRunner(), max_concurrent_activities=1):
                handle = await client.start_workflow(FinalBoundary.run, value, id='q02-'+uuid.uuid4().hex, task_queue=queue, execution_timeout=timedelta(minutes=5))
                failure = None
                try:
                    result = await handle.result()
                except WorkflowFailureError as error:
                    cause = error
                    while getattr(cause, 'cause', None) is not None:
                        cause = getattr(cause, 'cause')
                    failure = str(cause)
                    result = None
                assert (result is not None) == expected_success, (case, failure)
                record = {'case': case, 'workflow_id': handle.id, 'run_id': handle.result_run_id,
                          'queue': queue, 'prefix': prefix, 'success': result is not None, 'failure': failure}
                if result:
                    final = Enrichment(processing).read(result['operation'], 'processing-result.json')
                    assert final['processing_complete'] and not final['quality_accepted'] and not final['canonical_accepted']
                    binding = Enrichment(processing).read(final['relationships'], 'relationships.json')
                    assert bool(binding['relationships']['unresolved']) == (case == 'allowed_unknown')
                    if case != 'allowed_unknown':
                        from oracle.score import score
                        candidate = copy.deepcopy(binding['relationships']['candidates'])
                        candidate['relationships'] = [{**r, 'disposition': 'candidate'} for r in binding['relationships']['resolved']]
                        assert all(r['structure_pass'] for r in score(doc, candidate)[:2])
                        record['independent_bfs_uniform_cost_oracle'] = True
                    record['relationship_artifact_sha256'] = next(f['sha256'] for f in store.resolve(final['relationships'])['files'] if f['name'] == 'relationships.json')
                    record.update(final=result['operation'], relationships=final['relationships'], content_evidence=final['content_evidence'])
                    if case == 'valid':
                        registration = store.resolve(final['content_evidence'])
                        original_files = {f['name']: store.read_artifact(f) for f in registration['files']}
                    # A retry revalidates all durable bytes at the same final boundary.
                    retry = await client.execute_workflow(FinalBoundary.run, value, id='q02-'+uuid.uuid4().hex, task_queue=queue, execution_timeout=timedelta(minutes=5))
                    assert retry['operation'] == result['operation']
                    record['retry_same_final'] = True
                else:
                    listing = s3.list_objects_v2(Bucket=bucket, Prefix=store.prefix+'registered/')
                    ids = []
                    for obj in listing.get('Contents', []):
                        raw_registration = store.get(obj['Key'])
                        assert raw_registration is not None, 'Listed registration disappeared'
                        ids.append(json.loads(raw_registration)['operation'])
                    assert not any(i.startswith('pdf-complete-') for i in ids)
                    record['complete_registration_absent'] = True
                history = await handle.fetch_history()
                record['activity_completions'] = sum(e.HasField('activity_task_completed_event_attributes') for e in history.events)
                record['activity_failures'] = sum(e.HasField('activity_task_failed_event_attributes') for e in history.events)
                results.append(record)
                (out/'runtime.json').write_bytes(encoded({'scope': __doc__, 'document_sha256': digest(encoded(doc)), 'producer': processing.producer, 'results': results}))
                print(case, 'PASS', flush=True)
    print('Runtime report:', out/'runtime.json')


if __name__ == '__main__':
    if os.environ.get('Q02_CAPACITY_APPROVED') != '1':
        raise SystemExit('Coordinate the runtime window before running the fault matrix')
    with open(os.environ.get('PDF_QUALIFICATION_LOCK', '/tmp/data-ingestion-pdf-qualification.lock'), 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(asyncio.wait_for(main(), timeout=int(os.environ.get('Q02_TIMEOUT_SECONDS', '1800'))))
