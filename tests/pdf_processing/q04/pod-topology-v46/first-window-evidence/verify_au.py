"""Independent readback of AU's retained terminal evidence."""

import hashlib
import json
from pathlib import Path

from candidate.telemetry_loss_window_au import verify_abort


RAW = Path('/private/tmp/q04-telemetry-loss-pod-cgroup-20260925-au')
EVIDENCE = RAW / 'evidence'
STATE = EVIDENCE / 'state/telemetry-loss-pod-cgroup-au'
OUT = Path(__file__).with_name('INDEPENDENT-VERIFICATION.json')


def read(path):
    return json.loads(path.read_text())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    terminal = read(EVIDENCE / 'durable-terminal-manifest.json')
    inventory = terminal['inventory']
    assert terminal['status'] == 'PASS_CANDIDATE' and terminal['workload_succeeded']
    assert terminal['inventory_sha256'] == digest(json.dumps(
        inventory, sort_keys=True, separators=(',', ':')).encode())
    listed = {row['path'] for row in inventory}
    observed = {str(p.relative_to(EVIDENCE)) for p in EVIDENCE.rglob('*') if p.is_file()}
    assert listed | {'durable-terminal-manifest.json'} == observed
    assert len(listed) == len(inventory)
    for row in inventory:
        path = EVIDENCE / row['path']
        assert not path.is_symlink()
        raw = path.read_bytes()
        assert len(raw) == row['bytes'] and digest(raw) == row['sha256']

    proof = verify_abort(STATE)
    business = proof['business_result']
    assert business['status'] == 'failed' and not business['processing_complete']
    assert business['registered_pages'] == 5 and business['pages'] == 51
    assert business['error']['code'] == 'activity_budget_exhausted'
    assert read(STATE / 'phase-complete.json')['status'] == 'PASS active worker telemetry-loss abort'
    cleanup = read(EVIDENCE / 'cleanup-complete.json')
    assert cleanup['worker_generations'] == 1
    assert all(cleanup[key] for key in ('worker_absent', 'owned_children_absent', 'scratch_absent'))
    gate = read(EVIDENCE / 'state/telemetry-loss-pod-cgroup-au-measurement/all-sample-resource-gate.json')
    assert gate['status'] == 'PASS'
    assert all(not gate[key] for key in ('incomplete_sample_indexes',
                'process_attribution_incomplete_sample_indexes', 'memory_violations',
                'oom_violations', 'psi_violations', 'summary_errors'))
    attribution = read(EVIDENCE / 'state/telemetry-loss-pod-cgroup-au-measurement/resource-attribution-summary.json')
    assert attribution['measurement_contract'] == 'guard_failure'
    assert attribution['cancel_observation_required'] and attribution['qualification_complete']
    controller = read(RAW / 'vm-controller-summary.json')
    assert controller['maximum_gap_seconds'] < 1
    assert controller['maximum_cgroup_bytes'] < 4 * 1024**3
    assert controller['minimum_available_bytes'] > 1610612736
    outer = read(RAW / 'outer-cleanup.json')
    assert outer['primary_error'] is None and outer['old_runtime_absent']
    assert outer['owned_objects_deleted_with_uid_preconditions'] and outer['post_cleanup_vm_oom_proof']
    assert outer['retained_evidence_claim']['phase'] == 'Bound'
    probe = read(Path(str(RAW) + '-node-pressure-cleanup.json'))
    assert probe['complete'] and probe['remote_absence']['value']['absent']
    report = {'status': 'PASS', 'terminal_inventory_files': len(inventory),
              'business_status': business['status'], 'registered_pages': business['registered_pages'],
              'injection_registered_pages': proof['registered_pages_at_injection'],
              'resource_samples': gate['samples_evaluated'], 'controller_samples': controller['samples'],
              'host_samples': probe['terminal']['value']['samples'],
              'retained_pvc_uid': outer['retained_evidence_claim']['pvc_uid'],
              'outer_cleanup': outer['disposition']}
    OUT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
