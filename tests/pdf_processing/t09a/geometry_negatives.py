"""Focused production handoff failures through actual Temporal/store publication.

Uses valid completed parsing/selection from a tiny v3 request and a dedicated
workflow calling its finalization Activity; no parsing inference is repeated.
"""
import asyncio,json,uuid
from pathlib import Path
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
with workflow.unsafe.imports_passed_through():
    import boto3
    import pypdfium2 as pdfium
    from temporalio.client import Client
    from temporalio.worker import Worker
    from temporalio.exceptions import ActivityError, ApplicationError
    from pdf_processing.object_store import Store,digest
    from pdf_processing.processing import Processing,encoded

@workflow.defn
class Finalize:
    @workflow.run
    async def run(self,value:dict):
        try:
            return await workflow.execute_activity('pdf_processing_step_v1',value,start_to_close_timeout=timedelta(seconds=60),retry_policy=RetryPolicy(maximum_attempts=3))
        except ActivityError as error:
            assert isinstance(error.cause, ApplicationError)
            return {'error':error.cause.message,'non_retryable':error.cause.non_retryable}

async def main():
    Path('/tmp/t09a-results').mkdir(exist_ok=True)
    client=await Client.connect('temporal:7233')
    s3=boto3.client('s3',endpoint_url='http://objects:9000');store=Store(s3,'t09a','final')
    def read(identity,name):return json.loads(store.read_artifact(next(f for f in store.resolve(identity)['files'] if f['name']==name)))
    result=json.loads(Path('/negative/seed.json').read_text())['result']
    final=read(result['processing_result'],'processing-result.json');selection=read(final['selection'],'selection.json')
    original_plan=read(final['plan'],'plan.json')
    results={}
    # Each modified profile/plan is isolated and gets a new selection identity.
    # Shared parsing and OCR inputs remain immutable. These are adversarial adapter
    # inputs, not new qualified public profiles.
    for case in ('filename_collision','shared_item','duplicate_id','invalid_original_page','oversize_original','unmatched_region','missing_formula_region','ordinary_zero_width','combining_reversed','combining_outside','combining_zero_height','review_zero_width'):
        plan=json.loads(json.dumps(original_plan));profile=plan['profile'];review=profile['content_evidence']['reviews'][plan['request']['artifact']['sha256']]
        expected=None
        if case=='filename_collision':
            plan['request']['artifact']['name']='original.pdf'
        elif case=='shared_item':
            eq=next(x for x in review['regions'] if x['id']=='eq2')
            review['regions'].append({**eq,'id':'eq2-separate-reviewed-occurrence'})
        elif case=='duplicate_id':
            review['regions'].append(review['regions'][0]);expected='duplicate_review_id'
        elif case=='invalid_original_page':
            review['original_pages']['1']=0;expected='invalid_original_page_number'
        elif case=='oversize_original':
            path=Path('/tmp/t09a-huge.pdf');pdf=pdfium.PdfDocument.new();page=pdf.new_page(2000,2000);page.close();pdf.save(path);pdf.close()
            raw=path.read_bytes();key='final/sources/oversize-original.pdf';saved=s3.put_object(Bucket='t09a',Key=key,Body=raw)
            review['original_source']['artifact']={'name':'oversize.pdf','key':key,'version_id':saved['VersionId'],'sha256':digest(raw)}
            review['original_pages']['1']=1;expected='original_evidence_pixel_limit'
        elif case=='unmatched_region':
            review['regions'].append({'id':'unmatched','kind':'formula','page':1,'bbox':{'l':1,'t':1,'r':2,'b':2,'coord_origin':'TOPLEFT'}});expected='review_region_has_no_typed_content'
        elif case=='missing_formula_region':
            expected='formula_evidence_missing'
        elif case in ('ordinary_zero_width','combining_reversed','combining_outside','combining_zero_height'):
            expected='region_outside_page'
        elif case=='review_zero_width':
            review['regions'][0]['bbox']['r']=review['regions'][0]['bbox']['l'];expected='region_outside_page'
        processing=Processing(store,'/tmp/t09a-negative','/experiment/PROTOTYPE-wipe-me/hf',profile,plan['limits'])
        # Clone full linked inputs for finalization without changing actual source/OCR.
        plan_id='pdf-plan-v1:'+uuid.uuid4().hex;plan['producer']=processing.producer
        store.publish(plan_id,{'plan.json':encoded(plan)})
        parsed=read(selection['parsed_result'],'parsed-result.json');parsed['plan']=plan_id;parsed['source']=plan['request']
        changed_assembly=None
        doc=None
        if case in ('missing_formula_region','ordinary_zero_width','combining_reversed','combining_outside','combining_zero_height'):
            doc=read(selection['assembly'],'document.json')
            if case=='missing_formula_region':
                next(t for t in doc['texts'] if t.get('label')=='formula')['prov']=[]
            else:
                node=next(t for t in doc['texts'] if t.get('label')=='text' and t.get('prov'))
                node['text']='x' if case=='ordinary_zero_width' else '\u0338'
                box=node['prov'][0]['bbox']
                box['r']=box['l']
                if case=='combining_reversed':box['r']=box['l']-1
                if case=='combining_outside':box['l']=box['r']=-1
                if case=='combining_zero_height':box['b']=box['t']
            changed_assembly='negative-assembly:'+uuid.uuid4().hex
            store.publish(changed_assembly,{'document.json':encoded(doc)})
            parsed['assembly']=changed_assembly
        parsed_id='negative-parsed:'+uuid.uuid4().hex;store.publish(parsed_id,{'parsed-result.json':encoded(parsed)})
        selected={**selection,'plan':plan_id,'parsed_result':parsed_id,'source':plan['request']}
        if changed_assembly:
            assert doc is not None
            selected['assembly']=changed_assembly;selected['parsed_sha256']=digest(encoded(doc))
        selection_id='negative-selection:'+uuid.uuid4().hex;store.publish(selection_id,{'selection.json':encoded(selected)})
        outcomes=[]
        for outcome in final['enrichments']:
            manifest=store.resolve(outcome['operation']);files={f['name']:store.read_artifact(f) for f in manifest['files']}
            ocr=json.loads(files['ocr.json']);ocr.update(selection=selection_id,parsed_result=parsed_id,source=plan['request'])
            files['ocr.json']=encoded(ocr);identity='negative-ocr:'+uuid.uuid4().hex;store.publish(identity,files);outcomes.append(identity)
        queue='t09a-negative-'+uuid.uuid4().hex
        async with Worker(client,task_queue=queue,workflows=[Finalize],activities=[processing.run]):
            handle=await client.start_workflow(Finalize.run,{'stage':'finalize','plan':plan_id,'selection':selection_id,'outcomes':outcomes},id=queue,task_queue=queue)
            actual=await handle.result()
            if expected:assert actual=={'error':expected,'non_retryable':True},(case,actual)
            else:
                delivered=read(actual['operation'],'processing-result.json');evidence=read(delivered['content_evidence'],'content-evidence.json')
                ids=[x.get('review_id') for x in evidence['formula_occurrences']]
                assert 'eq2' in ids,ids
                if case=='shared_item':assert 'eq2-separate-reviewed-occurrence' in ids,ids
                if case=='filename_collision':assert evidence['source']['artifact']['name']=='original.pdf'
            history=await handle.fetch_history()
            attempts=[e.activity_task_started_event_attributes.attempt for e in history.events if e.HasField('activity_task_started_event_attributes')]
            assert attempts==[1],attempts
            results[case]={'result':actual,'attempts':attempts}
            print(case,'passed',flush=True)
    Path('/tmp/t09a-results/review-failures.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':asyncio.run(main())
