from pathlib import Path
source = Path(__file__).with_name('pod_remote_evidence.py').read_text()
for old, new in {'A6': 'RB1', 'a6': 'rb1'}.items(): source = source.replace(old, new)
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
from pod_remote_evidence_be import FINAL_REQUIRED as recovery_required
base.FINAL_REQUIRED = {name.replace('process-drain-pod-cgroup-be', PHASE) for name in recovery_required}
for generation in (1, 2):
    ledger = f'state/{PHASE}/worker-{generation}/storage.jsonl'
    base.STREAM_FILES.add(ledger)
    base.FINAL_REQUIRED.update((ledger, f'state/{PHASE}/worker-{generation}/storage-summary.json'))
base.FINAL_REQUIRED.update({f'state/{PHASE}/drain-native/{name}' for name in ('result.json','document.json','checks.json','recovery-cost.json','replacement-vm.json')})
IncrementalEvidenceMirror.finalize = inherited._failure_aware_finalize()
base.FINAL_REQUIRED.add(f'state/{PHASE}/worker-1/drain-signal.json')
