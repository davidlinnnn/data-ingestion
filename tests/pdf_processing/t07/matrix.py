"""A real Temporal Activity worker per scenario, sharing isolated durable storage.

Run each scenario in a fresh interpreter; runtime variants live only in /tmp.
Only bounded metadata leaves the qualification namespace.
"""
import asyncio,copy,json,sys,uuid,tempfile
from pathlib import Path
import boto3
from temporalio.client import Client
from temporalio.worker import Worker
from pdf_processing.processing import Processing
from pdf_processing.processing_workflow import PDFProcessing
from pdf_processing.object_store import Store,digest
from pdf_processing.execution import Execution,SourceRequest,ChildFailure

OUT=Path('/tmp/t07-matrix');OUT.mkdir(exist_ok=True)
scenario=sys.argv[1]
launched_modules=[]
def audit(event, arguments):
    if event=='subprocess.Popen':
        argv=arguments[1]
        if isinstance(argv,(list,tuple)) and '-m' in argv:
            launched_modules.append(argv[argv.index('-m')+1])
sys.addaudithook(audit)

async def main():
    s3=boto3.client('s3',endpoint_url='http://objects:9000');store=Store(s3,'t07','final')
    client=await Client.connect('temporal:7233')
    profile=json.loads(Path('/driver/native-v1.json').read_text())
    if scenario=='baseline':
        import pypdfium2 as pdfium
        with pdfium.PdfDocument('/fixtures/multiple.pdf') as one:
            with pdfium.PdfDocument.new() as two:
                two.import_pages(one);two.import_pages(one);two.save('/tmp/t07-two.pdf')
        data=Path('/tmp/t07-two.pdf').read_bytes();key='final/sources/two.pdf'
        saved=s3.put_object(Bucket='t07',Key=key,Body=data)
        request={'version':3,'completion':'required_evidence_v1','profile':'native-v1',
            'request_id':uuid.uuid4().hex,'source_revision':'synthetic:two',
            'artifact':{'key':key,'name':'two.pdf','sha256':digest(data),'version_id':saved['VersionId']}}
        (OUT/'source.json').write_text(json.dumps(request))
    else:request=json.loads((OUT/'source.json').read_text())
    request={**request,'request_id':uuid.uuid4().hex}
    if scenario=='legacy-v1':
        request['version']=1;request.pop('completion')
    if scenario=='legacy-v2':
        request.update(version=2,completion='required_picture_ocr_v1')
    if scenario=='unauthorized':
        data=Path('/tmp/t07-two.pdf').read_bytes();key='outside/sources/two.pdf'
        saved=s3.put_object(Bucket='t07',Key=key,Body=data)
        request['artifact']={**request['artifact'],'key':key,'version_id':saved['VersionId']}
    if scenario=='ocr':
        profile['picture_ocr']={'render_scale':4}
        # Native parsing never constructs an OCR model with do_ocr=False.
        profile['method']['options']['ocr_options']['force_full_page_ocr']=True
    if scenario=='policy':profile['content_evidence']={'version':'typed-source-evidence-v1',
        'reviews':{request['artifact']['sha256']:{'source_sha256':request['artifact']['sha256'],'regions':[]}}}
    if scenario=='revision':request['source_revision']='synthetic:two:revision-b'
    if scenario=='bytes':
        data=Path('/fixtures/multiple.pdf').read_bytes();key='final/sources/changed.pdf'
        saved=s3.put_object(Bucket='t07',Key=key,Body=data)
        request['artifact']={'key':key,'name':'changed.pdf','sha256':digest(data),'version_id':saved['VersionId']}
    if scenario=='group-plan':profile['group_pages']=1
    if scenario=='parser':profile['method']['options']['images_scale']=2.0
    processing=Processing(store,'/tmp/t07-scratch','/experiment/PROTOTYPE-wipe-me/hf',profile)
    def read(identity,name):
        return json.loads(store.read_artifact(next(f for f in store.resolve(identity)['files'] if f['name']==name)))
    queue='t07-matrix-'+uuid.uuid4().hex
    async with Worker(client,task_queue=queue,activities=[processing.run],max_concurrent_activities=1):
        if scenario=='ocr':
            frozen=json.loads((OUT/'baseline.json').read_text())['request']
            refused=await client.execute_workflow(PDFProcessing.run,{'request':frozen,'activity_queue':queue},id=uuid.uuid4().hex,task_queue='t07-workflows')
            assert refused['status']=='failed' and refused['error']['code']=='worker_method_mismatch',refused
        result=await client.execute_workflow(PDFProcessing.run,{'request':request,'activity_queue':queue},id=uuid.uuid4().hex,task_queue='t07-workflows')
        report={'scenario':scenario,'request':request,'result':result,'producer':processing.producer,'profile':profile,
                'child_process_modules':list(launched_modules)}
        (OUT/(scenario+'.json')).write_text(json.dumps(report,indent=2))
        if scenario=='unauthorized':
            assert result['status']=='failed' and result['error']['code']=='invalid_source_reference',result
            print('Equal source bytes outside authorized prefix rejected: PASS');return
        if scenario=='legacy-v1':
            assert result['status']=='parsed_ready' and not result['processing_complete'],result
            assert all(s['reused'] for s in result['steps'])
            assert read(result['parsed_result'],'parsed-result.json')['source']==request
            print('v1 parsed_ready with compatible reuse: PASS');return
        if scenario=='parser':
            assert result['status']=='failed' and result['error']['code']=='worker_method_mismatch',result
            print('Unsupported parser change explicitly rejected without fallback: PASS');return
        assert result['status']=='complete',result
        final=read(result['processing_result'],'processing-result.json')
        assert final['source']==request and not final['canonical_accepted'] and final['processing_complete']
        assert final['provenance']['profile']==profile and final['provenance']['producer']==processing.producer
        if request['version']==3:
            evidence=read(final['content_evidence'],'content-evidence.json')
            assert evidence['source']==request
        else:
            assert final['version']==1 and 'content_evidence' not in final
        if scenario=='policy':
            assert evidence['formula_coverage']=='source_reviewed_regions'
            assert evidence['source_review']==profile['content_evidence']['reviews'][request['artifact']['sha256']]
        ocr=[read(x['operation'],'ocr.json') for x in final['enrichments']]
        assert ocr and all(x['source']==request for x in ocr)
        assert all(x['method']==read(final['selection'],'selection.json')['ocr_method'] for x in ocr)
        report['final']=final
        report['ocr']=[{k:x[k] for k in ('source_sha256','render_scale','crop_sha256','method','producer','outcome')} for x in ocr]
        if scenario!='baseline':
            baseline=json.loads((OUT/'baseline.json').read_text())
            should_reuse=scenario in ('ocr','unrelated','policy','legacy-v2')
            assert all(s['reused']==should_reuse for s in result['steps'] if s['stage'] in ('group','assembly')),result
            assert result['parsed_result']!=baseline['result']['parsed_result']
            assert result['processing_result']!=baseline['result']['processing_result']
            if should_reuse:
                assert 'pdf_processing.parse' not in launched_modules,launched_modules
                assert final['assembly']==baseline['final']['assembly']
                assert all('parser' not in s for s in result['steps'] if s['stage']=='group')
            if scenario=='ocr':
                assert launched_modules.count('pdf_processing.ocr')==4,launched_modules
                assert all(x['render_scale']==4 for x in ocr)
                assert all(not s['reused'] for s in result['steps'] if s['stage']=='component_ocr')
                assert all(x.get('qualification_implementation')=='t07-b' for x in ocr)
        duplicate=await client.execute_workflow(PDFProcessing.run,{'request':request,'activity_queue':queue},id=uuid.uuid4().hex,task_queue='t07-workflows')
        assert duplicate['processing_result']==result['processing_result'] and all(s['reused'] for s in duplicate['steps'])
        report['duplicate']=duplicate
        (OUT/(scenario+'.json')).write_text(json.dumps(report,indent=2))
    if scenario=='ocr':
        baseline=json.loads((OUT/'baseline.json').read_text())
        group=next(s['operation'] for s in baseline['result']['steps'] if s['stage']=='group')
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            root=Path(tmp);pdf=root/'two.pdf';processing.read_source(request,pdf)
            execution=Execution(SourceRequest(pdf,request['source_revision'],request['artifact']['sha256'],profile['method'],Path('/experiment/PROTOTYPE-wipe-me/hf')),store,root)
            execution.materialize(group,root/'saved')
            old_method=json.loads((root/'saved/method.json').read_text())
            old_compatibility=json.loads((root/'saved/compatibility.json').read_text())
            assert old_method!=profile['method']
            await execution.child('pdf_processing.parse',{'pdf':str(pdf),'out':str(root/'restored'),
                'model_cache':'/experiment/PROTOTYPE-wipe-me/hf','mode':'restore','checkpoint':str(root/'saved'),
                'start':1,'end':2,'expected_method':profile['method'],'checkpoint_compatibility':old_compatibility},root)
            metrics=json.loads((root/'restored/metrics.json').read_text())
            assert metrics['page_stage_inputs']=={'checkpoint_load':2,'document_assembly':0,'model_initialization':0},metrics
            expected=read(baseline['final']['assembly'],'document.json')
            assert json.loads((root/'restored/document.json').read_text())==expected
            # Real restore must reject a future format and an undeclared producer migration.
            failures=[]
            for label in ('format','migration'):
                if label=='format':
                    path=root/'saved/complete.json';original=path.read_bytes();v=json.loads(original);v['format']='unknown-v99';path.write_text(json.dumps(v))
                    compatibility=old_compatibility
                else:
                    path.write_bytes(original);compatibility={**old_compatibility,'contract':'undeclared-migration'}
                try:
                    await execution.child('pdf_processing.parse',{'pdf':str(pdf),'out':str(root/label),
                        'model_cache':'/experiment/PROTOTYPE-wipe-me/hf','mode':'restore','checkpoint':str(root/'saved'),
                        'start':1,'end':2,'expected_method':profile['method'],'checkpoint_compatibility':compatibility},root)
                except ChildFailure as error:failures.append({'case':label,'category':error.category,'code':error.code})
                else:raise AssertionError('Incompatible checkpoint accepted')
            report['restore']={'metrics':metrics,'full_document_equal':True,'old_method_sha256':digest(json.dumps(old_method,sort_keys=True).encode()),'negative':failures}
            (OUT/(scenario+'.json')).write_text(json.dumps(report,indent=2))
    print(scenario+': PASS',flush=True)

asyncio.run(main())
