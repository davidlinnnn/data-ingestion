"""Read-only inventory of retained Temporal executions; run inside coordinator."""
import asyncio
import json
from temporalio.client import Client

NAMES=['pdf-integration-0913','pdf-s1-warm-lifecycle']+[f'pdf-t{n:02}-validation' for n in range(1,9)]+['pdf-t09a-validation']

async def main():
    rows=[]
    for namespace in NAMES:
        row={'namespace':namespace,'open':[]}
        try:
            async with asyncio.timeout(15):
                client=await Client.connect('temporal.'+namespace+'.svc.cluster.local:7233')
                async for execution in client.list_workflows(query='ExecutionStatus="Running"'):
                    detail=await client.get_workflow_handle(execution.id).describe()
                    row['open'].append({'workflow_id':execution.id,'run_id':execution.run_id,
                        'pending_activities':[{'id':a.activity_id,'state':a.state,'attempt':a.attempt} for a in detail.raw_description.pending_activities]})
            row['query_status']='complete'
        except Exception as error:row['query_status']=type(error).__name__
        rows.append(row)
    print(json.dumps(rows))

if __name__=='__main__':asyncio.run(main())
