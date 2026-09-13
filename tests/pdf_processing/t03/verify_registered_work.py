"""Read-only accepted artifact evidence: page stages within each complete group."""
import json
import sys
from pathlib import Path
import boto3
from pdf_processing.object_store import Store
store=Store(boto3.client('s3',endpoint_url='http://objects:9000'),'t03','final')
reports={}
for path in Path(sys.argv[1]).glob('*.json'):
    evidence=json.loads(path.read_text())
    if 'markers' not in evidence: continue
    groups=[]
    for step in evidence['result']['steps']:
        if step['stage']!='group':continue
        registration=store.resolve(step['operation']);assert registration is not None
        metrics=json.loads(store.read_artifact(next(i for i in registration['files'] if i['name']=='metrics.json')))
        stages=metrics['page_stage_inputs']
        assert all(v==5 for k,v in stages.items() if k in ('PagePreprocessingModel','LayoutModel','TableStructureModel','PageAssembleModel')),stages
        groups.append({'operation':step['operation'],'accepted_stage_inputs':stages})
    assert len(groups)==2
    reports[evidence['mode']]={'groups':groups,'capture_starts':sum(m['event'].startswith('capture-') for m in evidence['markers']),
        'interrupted_native_work':'Exact instruction-level work before Pod kill is unobservable; capture starts and accepted stage inputs are recorded separately.'}
print(json.dumps(reports,indent=2))
