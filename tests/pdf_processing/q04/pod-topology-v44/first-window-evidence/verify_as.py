"""Independent readback of the retained AS terminal evidence."""

import hashlib
import json
from pathlib import Path


RAW = Path('/private/tmp/q04-relationship-pod-cgroup-20260925-as')
EVIDENCE = RAW / 'evidence'
STATE = EVIDENCE / 'state/relationship-pod-cgroup-as'
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
    assert len(listed) == len(inventory) == 95
    for row in inventory:
        path = EVIDENCE / row['path']
        assert not path.is_symlink()
        raw = path.read_bytes()
        assert len(raw) == row['bytes'] and digest(raw) == row['sha256']

    outcomes = {}
    for mode in ('fresh-native', 'recovery-native', 'replay-native'):
        row = read(STATE / mode / 'accepted.json')
        result, accepted = row['result'], row['accepted']
        assert row['verified'] and result['status'] == 'complete'
        assert result['processing_complete'] and result['registered_pages'] == 51
        assert result['registered_components'] == result['selected_components'] == 7
        assert accepted['document_sha256'] == '70673bdc5cb548d37c81efa91bb1c5460f71f94148bdb5d1218a319c6af9f152'
        assert accepted['checks']['full_reference_graph_sha256'] == '9f1b0ef9ed561df0c4a5748d5c49554e8f5ad3bb38764d94a51d3433f4d94972'
        history = read(STATE / mode / 'history.json')['events']
        assert sum(x['eventType'] == 'EVENT_TYPE_ACTIVITY_TASK_FAILED' for x in history) == 0
        assert sum(x['eventType'] == 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED' for x in history) == 1
        outcomes[mode] = {'pages': 51, 'components': 7, 'worker_generation': row['worker_generation'],
                          'history_events': len(history)}
    assert outcomes['fresh-native']['worker_generation'] == 1
    assert outcomes['recovery-native']['worker_generation'] == outcomes['replay-native']['worker_generation'] == 2

    failed = read(STATE / 'interrupted-native/result.json')
    assert failed['status'] == 'failed' and not failed['processing_complete']
    assert failed['error'] == {'category': 'parser', 'code': 'execution_failed'}
    history = read(STATE / 'interrupted-native/failure-history.json')['events']
    assert sum(x['eventType'] == 'EVENT_TYPE_ACTIVITY_TASK_FAILED' for x in history) == 1
    assert sum(x['eventType'] == 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED' for x in history) == 1
    assert read(STATE / 'interrupted-native/publication-outcome.json')['ok']
    hook = read(STATE / 'worker-1/interruption/observation.json')
    assert hook['command'][-1] == 'pdf_processing.evidence'
    assert hook['progress'] == 'first_page_decoded' and hook['partial_files']
    assert read(STATE / 'phase-complete.json')['status'] == 'PASS required relationship interruption recovery and replay'
    cleanup = read(EVIDENCE / 'cleanup-complete.json')
    assert cleanup['worker_generations'] == 2
    assert all(cleanup[key] for key in ('worker_absent', 'owned_children_absent', 'scratch_absent'))
    gate = read(EVIDENCE / 'state/relationship-pod-cgroup-as-measurement/all-sample-resource-gate.json')
    assert gate['status'] == 'PASS' and gate['samples_evaluated'] == 895
    assert all(not gate[key] for key in ('incomplete_sample_indexes', 'process_attribution_incomplete_sample_indexes',
                                        'memory_violations', 'oom_violations', 'psi_violations', 'summary_errors'))
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
    trace = sorted(p for p in listed if '/ocr-trace/' in p)
    report = {'status': 'PASS', 'terminal_inventory_files': len(inventory),
              'workflows': outcomes, 'interrupted_history_events': len(history),
              'required_interruption_hook': 'first_page_decoded',
              'resource_samples': gate['samples_evaluated'], 'controller_samples': controller['samples'],
              'host_samples': probe['terminal']['value']['samples'],
              'outer_cleanup': outer['disposition'], 'retained_pvc_uid': outer['retained_evidence_claim']['pvc_uid'],
              'ocr_phase_trace': 'PRESENT' if trace else 'MISSING; AQ process-level stall phase remains unknown'}
    OUT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
