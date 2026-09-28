"""Summarize retained measurements without copying source text into the repo."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

RUN=sys.argv[1]
RAW=Path('/private/tmp/t09a-r2-20260914')/RUN
RESULTS=Path('/private/tmp/t09a-r3-results')/RUN
OUT=Path(__file__).parent/'evidence'/RUN
OUT.mkdir(parents=True,exist_ok=True)
def redacted(value):
    if isinstance(value,list):return [redacted(v) for v in value]
    if isinstance(value,dict):
        if value.get('name') in ('AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','MINIO_ROOT_USER','MINIO_ROOT_PASSWORD'):
            return {**value,'value':'<REDACTED>'}
        return {k:redacted(v) for k,v in value.items()}
    return value

def copy_metadata(path):
    (OUT/path.name).write_text(json.dumps(redacted(json.loads(path.read_text())),indent=2)+'\n')

rows=[];proofs=[];release=None;methods={}
for path in sorted(RAW.glob('*-controller.json')):
    record=json.loads(path.read_text());name=path.name.removesuffix('-controller.json')
    row={'trial':name,'controller_status':record['status'],'error':record.get('error')}
    metadata=RESULTS/(name+'.json')
    if metadata.exists():
        result=json.loads(metadata.read_text())
        proof={k:result[k] for k in ('trial','workflow_id','request','result','history','events') if k in result}
        if result.get('accepted_plan'):
            plan=result['accepted_plan'];details={k:plan[k] for k in ('profile','limits','producer','producer_contract','checkpoint_format')}
            if release is None:release=details
            assert details==release,'Effective release differs across trials'
            proof['native_stages']=[{k:v for k,v in stage.items() if k!='native_events'} for stage in result['retained_native_stage_observations']]
            for stage in proof['native_stages']:
                method=stage.pop('actual_method',None)
                if method is not None:
                    identity=hashlib.sha256(json.dumps(method,sort_keys=True).encode()).hexdigest()
                    stage['actual_method_sha256']=identity;methods[identity]=method
            proof['ocr_execution_metadata']=result['ocr_execution_metadata']
        proofs.append(proof)
        row.update(checks=result.get('checks'),elapsed=result['finished']-result['started'],
            workflow_id=result['workflow_id'],processing_status=result['result']['status'],
            verifier_sha256=result['verifier_sha256'])
    samples=[];streams={}
    for file in (RAW/(name+suffix+'-samples.jsonl') for suffix in ('','-old','-new')):
        if not file.exists():continue
        stream=[json.loads(line) for line in file.read_text().splitlines()]
        samples.extend(stream)
        if stream:streams[file.name]={'first':stream[0]['time'],'last':stream[-1]['time'],'memory_events_last':stream[-1]['memory_events']}
    samples.sort(key=lambda s:s['time'])
    if samples:
        row['resources']={'samples':len(samples),'peak_cgroup_bytes':max(int(s['memory_current']) for s in samples),
            'peak_sampled_process_rss_bytes':max((p['rss'] for s in samples for p in s['processes']),default=0),
            'peak_scratch_bytes':max(s['scratch']['bytes'] for s in samples),
            'memory_events_per_stream':streams}
    quality=RESULTS/(name+'-quality.json')
    if quality.exists():row['source_quality']=json.loads(quality.read_text())
    rows.append(row)
    copy_metadata(path)
for pattern in ('*cleanup.json','frozen-release.json','*injection.json'):
    for path in RAW.glob(pattern):copy_metadata(path)
(OUT/'execution-proofs.json').write_text(json.dumps(redacted(proofs),indent=2)+'\n')
(OUT/'actual-methods.json').write_text(json.dumps(methods,indent=2)+'\n')
(OUT/'release-details.json').write_text(json.dumps(redacted(release),indent=2)+'\n')
(OUT/'matrix.json').write_text(json.dumps(rows,indent=2)+'\n')
(OUT/'raw-evidence-hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.iterdir() if p.is_file()},indent=2)+'\n')
print(json.dumps(rows,indent=2))
