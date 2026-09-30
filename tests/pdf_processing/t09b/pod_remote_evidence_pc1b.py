from pathlib import Path
source=Path(__file__).with_name('pod_remote_evidence.py').read_text().replace('A6','PC1B').replace('a6','pc1b')
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())

for generation in (1,2,3):
    ledger = f'state/{PHASE}/worker-{generation}/storage.jsonl'
    base.STREAM_FILES.add(ledger)
    base.FINAL_REQUIRED.update((ledger, f'state/{PHASE}/worker-{generation}/storage-summary.json', f'state/{PHASE}/worker-{generation}/stopped.json'))
base.FINAL_REQUIRED = {path for path in base.FINAL_REQUIRED if not any(f'warm-{i}-{sid}' in path for i,sid in enumerate(('06','07','08','native','06')))}
for index,sid in enumerate(('07','08','native')):
    base.FINAL_REQUIRED.update(f'state/{PHASE}/warm-{index}-{sid}/{name}' for name in ('accepted.json','result.json','document.json','checks.json','history.json'))
IncrementalEvidenceMirror.finalize = inherited._failure_aware_finalize()
