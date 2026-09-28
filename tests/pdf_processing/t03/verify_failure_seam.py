"""Production Processing failure mapping through real Temporal and object storage."""
import asyncio
import json
from pathlib import Path
import tempfile
import uuid
import boto3
from temporalio.client import Client
from temporalio.worker import Worker
from pdf_processing.object_store import Store,digest
from pdf_processing.processing import Processing,encoded
from pdf_processing.processing_workflow import PDFProcessing

async def main():
    client=await Client.connect('temporal:7233')
    profile=json.loads(Path('/driver/native-v1.json').read_text())
    good=boto3.client('s3',endpoint_url='http://objects:9000')
    bad=boto3.client('s3',endpoint_url='http://objects:9000',aws_access_key_id='invalid',aws_secret_access_key='invalid')
    results={}
    for case,connection in [('configuration',bad),('integrity',good),('second_read',good)]:
        prefix='failure-'+uuid.uuid4().hex
        store=Store(connection,'t03',prefix)
        request={'version':1,'profile':'native-v1','request_id':prefix,'source_revision':'test:v1',
            'artifact':{'key':prefix+'/sources/source.pdf','version_id':'specific-version','sha256':'0'*64,'name':'source.pdf'}}
        if case=='integrity':
            operation='pdf-plan-v1:'+digest(encoded(request['request_id']))
            good.put_object(Bucket='t03',Key=store.registry_key(operation),Body=b'{malformed')
        with tempfile.TemporaryDirectory() as scratch:
            processing=Processing(store,scratch,'/experiment/PROTOTYPE-wipe-me/hf',profile)
            if case=='second_read':
                operation='pdf-plan-v1:'+digest(encoded(request['request_id']))
                saved=store.publish(operation,{'plan.json':encoded({'request':request,'profile':profile,
                    'producer':processing.producer,'limits':processing.limits,'pages':1,'groups':[[1,1]]})})
                target=saved['files'][0]['key']
                class TamperBetweenReads:
                    reads=0
                    def __getattr__(self,name): return getattr(good,name)
                    def get_object(self,**args):
                        if args['Key']==target:
                            self.reads+=1
                            if self.reads==3:
                                good.put_object(Bucket='t03',Key=target,Body=b'{changed after resolution}')
                        return good.get_object(**args)
                store.client=TamperBetweenReads()
            async with Worker(client,task_queue=prefix,activities=[processing.run]):
                handle=await client.start_workflow(PDFProcessing.run,{'request':request,'activity_queue':prefix},
                    id=prefix,task_queue='t03-workflows')
                result=await handle.result()
                assert result['status']=='failed' and result['error']['category']==('integrity' if case=='second_read' else case),result
                assert result['registered_pages']==0
                history=await handle.fetch_history()
                starts=[e.activity_task_started_event_attributes.attempt for e in history.events
                        if e.HasField('activity_task_started_event_attributes')]
                assert starts==[1],starts
                results[case]={'workflow_id':handle.id,'result':result,'attempts':starts}
    print(json.dumps(results,indent=2))
if __name__=='__main__': asyncio.run(main())
