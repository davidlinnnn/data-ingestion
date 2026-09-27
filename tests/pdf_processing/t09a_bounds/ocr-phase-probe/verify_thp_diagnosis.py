"""Verify the retained THP differential and output equivalence without runtime."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
summary = json.loads((root / 'thp-comparison.json').read_text())
reference = None
for name in ('bx', 'by', 'bz', 'ca'):
    evidence = root / (name + '-evidence')
    rows = [json.loads(line) for line in (evidence / 'samples.jsonl').read_text().splitlines()]
    deltas = {key: int(rows[-1][key]['total']) - int(rows[0][key]['total'])
              for key in ('vm_psi', 'cgroup_psi')}
    assert deltas['vm_psi'] == summary[name]['vm_full_delta_us']
    assert deltas['cgroup_psi'] == summary[name]['cgroup_full_delta_us']
    cleanup = json.loads((evidence / 'independent-cleanup.json').read_text())
    assert cleanup == {'container_absent':True, 'held_deployments_off':32,
                       'object_memory':'512Mi', 'object_ready':True}
    if name == 'by':
        assert all(value > 0 for value in deltas.values())
        assert summary[name]['vmstat_delta']['compact_stall'] == 12
        continue
    assert deltas == {'vm_psi':0, 'cgroup_psi':0}
    for variant in ('observed', 'plain'):
        report = json.loads((evidence / variant / 'ocr.json').read_text())
        report.pop('seconds_including_engine_load')
        actual = report, (evidence / variant / 'figure.png').read_bytes()
        if reference is None: reference = actual
        assert actual == reference, (name, variant)
    assert json.loads((evidence / 'result.json').read_text())['status'] == 'PASS_DIAGNOSTIC_ONLY'
print('PASS: THP reversal, three successful controls, exact OCR/crop equality and cleanup')
