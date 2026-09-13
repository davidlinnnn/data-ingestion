"""Submit a new captured version and validate full durable result through real services."""
import asyncio
import hashlib
from collections import Counter
import json
import sys
import time
import uuid
from pathlib import Path
import boto3
from temporalio.client import Client
from pdf_processing.object_store import Store, digest
from pdf_processing.processing_workflow import PDFProcessing

async def main():
    sid, trial = sys.argv[1:3]
    root = Path('/tmp/t09a-results'); root.mkdir(exist_ok=True)
    s3 = boto3.client('s3',endpoint_url='http://objects:9000'); store = Store(s3,'t09a','final')
    entry = next(x for x in json.loads(Path('/tmp/t09a-fixtures/manifest.json').read_text()) if x['id']==sid)
    def read(identity, name):
        manifest = store.resolve(identity)
        assert manifest is not None
        return store.read_artifact(next(f for f in manifest['files'] if f['name']==name))
    saved_request = root/(trial+'-request.json')
    if saved_request.exists(): request = json.loads(saved_request.read_text())
    else:
        data = Path('/tmp/t09a-fixtures',sid+'.pdf').read_bytes(); assert digest(data)==entry['review']['source_sha256']
        key = 'final/sources/'+sid+'.pdf'
        if '--source-from' in sys.argv:
            previous = json.loads((root/(sys.argv[sys.argv.index('--source-from')+1]+'-request.json')).read_text())
            assert previous['artifact']['sha256']==digest(data)
            artifact = previous['artifact']
        else:
            saved = s3.put_object(Bucket='t09a',Key=key,Body=data)
            artifact = {'key':key,'name':sid+'.pdf','version_id':saved['VersionId'],'sha256':digest(data)}
        request = {'version':3,'completion':'required_evidence_v1','profile':'native-v1','request_id':uuid.uuid4().hex,
            'source_revision':entry['source_revision'], 'artifact':artifact}
        saved_request.write_text(json.dumps(request))
    client = await Client.connect('temporal:7233')
    started = time.time()
    if '--attach' in sys.argv:
        active = json.loads((root/'active.json').read_text())
        assert active['trial']==trial and active['sid']==sid
        handle = client.get_workflow_handle(active['workflow_id'])
    else:
        handle = await client.start_workflow(PDFProcessing.run,{'request':request,'activity_queue':'t09a-pdf'},id='t09a-'+trial+'-'+uuid.uuid4().hex,task_queue='t09a-workflows')
    (root/'active.json').write_text(json.dumps({'trial':trial,'sid':sid,'workflow_id':handle.id,'started':started}))
    result_task = asyncio.create_task(handle.result())
    with (root/(trial+'-progress.jsonl')).open('a',buffering=1) as f:
        while not result_task.done():
            try:
                progress = await handle.query(PDFProcessing.progress)
                f.write(json.dumps({'time':time.time(),'status':progress['status'],'registered_pages':progress['registered_pages'],
                    'registered_components':progress.get('registered_components'),'steps':len(progress['steps'])})+'\n')
            except Exception as error: f.write(json.dumps({'time':time.time(),'query_error':type(error).__name__})+'\n')
            await asyncio.sleep(2)
    result = await result_task
    metadata = {'trial':trial,'sid':sid,'workflow_id':handle.id,'request':request,'started':started,'finished':time.time(),'result':result,
        'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (root/(trial+'.json')).write_text(json.dumps(metadata,indent=2))
    assert result['status']=='complete', result.get('error')
    assert result['processing_complete'] and result['canonical_accepted'] is False
    final = json.loads(read(result['processing_result'],'processing-result.json'))
    report = json.loads(read(final['content_evidence'],'content-evidence.json'))
    raw = read(final['assembly'],'document.json'); doc = json.loads(raw)
    assert digest(raw)==report['document_sha256']
    assert report['source']==request and report['parsed_result']==final['parsed_result']
    assert digest(read(final['content_evidence'],'source.pdf'))==request['artifact']['sha256']
    assert digest(read(final['content_evidence'],'original-source.pdf'))==entry['original_sha256']
    assert len(report['pages'])==len(entry['inventory'])
    for page in report['pages'].values():
        assert digest(read(final['content_evidence'],page['artifact']))==page['sha256']
        assert page['original_physical_page']==entry['review']['original_pages'][str(page['physical_page'])]
    assert len({x['ref'] for x in report['items']})==len(report['items'])
    for enrichment in final['enrichments']:
        manifest = store.resolve(enrichment['operation']); assert manifest
        for artifact in manifest['files']: store.read_artifact(artifact)
    (root/(trial+'-document.json')).write_bytes(raw)
    (root/(trial+'-evidence.json')).write_text(json.dumps(report))
    baseline_trial = 'evidence-08' if sid=='08' and (root/'evidence-08-document.json').exists() else 'fresh-'+sid
    baseline = root/(baseline_trial+'-document.json')
    checks = {'durable_complete_dependencies':True,'document_sha256':digest(raw),'pages':len(report['pages']),
        'typed_items':len(report['items']),'types':dict(Counter(x['actual_type'] for x in report['items'])),
        'required_ocr':len(final['enrichments']),'formula_occurrences':len(report['formula_occurrences']),
        'representation_observations':len(report['representation_observations'])}
    if trial != baseline_trial and baseline.exists():
        checks['fresh_reference_trial'] = baseline_trial
        checks['fresh_full_document_equal'] = json.loads(baseline.read_text())==doc
    if '--expect-reuse' in sys.argv:
        assert all(step['reused'] for step in result['steps'] if step['stage'] in ('group','assembly'))
        checks['all_group_assembly_reused']=True
    metadata.update(checks=checks,final=final)
    history = await handle.fetch_history()
    metadata['history'] = dict(Counter(e.event_type for e in history.events))
    (root/(trial+'.json')).write_text(json.dumps(metadata,indent=2))
    print(json.dumps({'trial':trial,'elapsed':metadata['finished']-started,'checks':checks}),flush=True)
    assert checks.get('fresh_full_document_equal',True), 'full typed JSON differs from fresh'

if __name__=='__main__': asyncio.run(main())
