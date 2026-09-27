"""Necessary post-run check: full JSON equality and real mixed-window results."""
import json
import gzip
from pathlib import Path

ROOT = Path(__file__).parent
WARM = Path("/private/tmp/t09a-bounds-20260928-db/evidence/state/bounds-pod-cgroup-db")
rows = []
for index, sid in enumerate(("06", "07", "08", "native", "06")):
    tag = "ai" if sid in ("06", "native") else "aj"
    fresh = Path(f"/private/tmp/q04-matrix-pod-cgroup-20260924-{tag}/evidence/state/matrix-pod-cgroup-{tag}/fresh-{sid}")
    warm = WARM / f"warm-{index}-{sid}"
    load = lambda path: json.loads(path.read_text())
    assert load(warm/"document.json") == load(fresh/"document.json"), sid
    assert load(warm/"checks.json") == load(fresh/"checks.json"), sid
    assert load(warm/"result.json")["processing_complete"], sid
    assert load(warm/"accepted.json")["verified"], sid
    rows.append({"fixture":warm.name,"reference":str(fresh),"processing_complete":True,
                 "full_document_equal":True,"full_checks_equal":True})
proof = load(WARM/"warm-proof.json")
assert proof["groups"] == 29 and proof["recycles"] == 1 and len(proof["pids"]) == 2
trial = load(ROOT/"first-window-evidence/object-trial-cleanup.json")
assert trial["primary_error"] is None
assert trial["object_psi_policy"]["mode"] == "functional_diagnostic"
assert trial["maximum_object_full_avg10"] == 0
assert trial["object_observer"]["max_events_delta"] == 0
assert load(ROOT/"first-window-evidence/independent-cleanup.json")["status"] == "PASS"
print("PASS: five full JSON/check comparisons; 29 groups, one recycle; diagnostic object guards and cleanup")

readiness = load(ROOT/'first-window-evidence/protection-readiness.json')
# The deadline starts before the first VM sample. Check the continuous object
# telemetry enclosing both readiness endpoints instead of subtracting VM samples.
objects = [json.loads(line) for line in gzip.decompress((ROOT/'first-window-evidence/object-pressure.jsonl.gz').read_bytes()).decode().splitlines()]
samples = [row for row in objects if row['kind'] == 'sample']
start = next(row for row in reversed(samples) if row['time'] <= readiness[0]['time'])
end = next(row for row in samples if row['time'] >= readiness[-1]['time'])
protection = [row for row in samples if start['time'] <= row['time'] <= end['time']]
assert end['time'] - start['time'] >= 125
assert max(b['time'] - a['time'] for a, b in zip(protection, protection[1:])) < 1
assert all(int(level['memory_low']) == 805306368 for row in protection for level in row['ancestors'])
assert load(ROOT/'first-window-evidence/independent-cleanup.json')['memory_low']['verified_restored']
print('PASS:125s protection persistence admission and manager/kernel restoration')

E=ROOT/'first-window-evidence'
(E/'fresh-output-comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
(E/'warm-proof.json').write_text(json.dumps(proof,indent=2)+'\n')

controller = load(E/'held-topology-controller.json')
assert controller['runner_exit_code'] == 0
assert len(controller['restoration_errors']) == 1
assert 'node attribution exit 1' in controller['restoration_errors'][0]
assert 'FileNotFoundError' in controller['restoration_errors'][0]
print('NOTE: outer controller exited 1: auxiliary node observer failed; do not label full harness PASS')

contract = load(E/'measurement-contract.json')
assert contract['workload_succeeded'] and contract['qualification_complete']
assert contract['group_requests'] == 29 and contract['request_recycle'] == 20
assert contract['parser_generations'] == 2 and contract['process_lifecycle']['status'] == 'PASS'
assert contract['resource_gate']['status'] == 'PASS'
assert not contract['automatic_retry']
assert load(E/'workload-exit.json')['returncode'] == 0
business = load(E/'temporal-reconciliation.json')
assert len(business) == 5
assert all(row['business']['processing_complete'] and row['business']['error'] is None
           and row['cancellation_time'] is None for row in business)
vm = [json.loads(line) for line in gzip.decompress((E/'vm-controller.jsonl.gz').read_bytes()).decode().splitlines()]
assert all(row['psi_full_avg10'] == 0 and row['vm_oom_kill'] == 0 for row in vm)
print('PASS: actual lifecycle contract, all terminal business results, complete VM guard samples')
