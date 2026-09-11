"""Collect measured run evidence without rerunning conversion."""
import collections
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parent
STORE=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'PROTOTYPE-wipe-me/temporal-store-final'
E=ROOT/'evidence'
ledger=[json.loads(x) for x in (STORE/'ledger.jsonl').read_text().splitlines()]
w=json.loads((STORE/'workflow-1.json').read_text())
events=[]
for p in STORE.glob('attempts/*/*/events.jsonl'):
    events += [{**json.loads(x),'directory':str(p.parent)} for x in p.read_text().splitlines()]
counts={}
for stage in ('PagePreprocessingModel','RapidOcrModel','LayoutModel','TableStructureModel','PageAssembleModel','checkpoint_commit'):
    c=collections.Counter(p for e in events if e['stage']==stage for p in e['pages'])
    counts[stage]={'total_page_inputs':sum(c.values()),'unique_pages':len(c),'repeated_page_inputs':sum(c.values())-len(c),'repeated_pages':{str(p):n for p,n in c.items() if n>1}}
registered=collections.Counter(e['operation'] for e in ledger if e['event']=='registered')
recovery=[]
for fail in (e for e in ledger if e['event']=='child_exit' and e['code']!=0):
    identity=Path(fail['directory']).parent.name
    later=next(e for e in ledger if e['event']=='completed' and e['identity']==identity and e['time']>fail['time'])
    recovery.append({'failed_exit_code':fail['code'],'identity':identity,'seconds_from_failure_to_registered_completion':later['time']-fail['time'], 'failed_attempt_has_complete_manifest':(Path(fail['directory'])/'complete.json').exists()})
ocr=json.loads((Path(w['ocr'])/'ocr.json').read_text())
checkpoint_files=[p for group in w['groups'] for p in (Path(group)/'checkpoints').iterdir()]
report={'workflow_seconds':w['seconds'],'reuse_workflow_seconds':json.loads((STORE/'workflow-2.json').read_text())['seconds'],
 'accepted_registrations':len(registered),'maximum_registrations_per_identity':max(registered.values()),
 'stage_counts_including_failed_attempts':counts,'recovery':recovery,
 'checkpoint_bytes':sum(p.stat().st_size for p in checkpoint_files),
 'ocr_seconds':ocr['seconds_including_engine_load'],'ocr_label_recall':ocr['label_recall'],
 'ocr_attempts':len([e for e in ledger if e['event']=='started' and e['kind']=='ocr']),
 'assembly_attempts':len([e for e in ledger if e['event']=='started' and e['kind']=='assembly']),
 'reuse_events':dict(collections.Counter(e['kind'] for e in ledger if e['event']=='reused')),
 'scope':'Local Temporal with subprocess exits and injected Activity exceptions. No worker-Pod loss, concurrent registration race, remote artifact store or Kubernetes durability test.'}
(E/'recovery-summary.json').write_text(json.dumps(report,indent=2))
for name in ('workflow-1.json','workflow-2.json','ledger.jsonl','history-1.json','history-2.json'):
    shutil.copyfile(STORE/name,E/('final-temporal-'+name))
for source,name in ((Path(w['ocr'])/'ocr.json','final-ocr.json'),(Path(w['ocr'])/'figure.png','figure.png'),(Path(w['parsed'])/'comparison.json','final-grouped-comparison.json')):
    shutil.copyfile(source,E/name)
(E/'final-page-events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
# Preserve each accepted group's resource metrics, and the assembly metrics.
(E/'final-group-metrics.json').write_text(json.dumps([json.loads((Path(g)/'metrics.json').read_text()) for g in w['groups']],indent=2))
print(json.dumps(report,indent=2))
