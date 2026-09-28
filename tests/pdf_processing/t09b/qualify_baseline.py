"""Complete business/output qualification before retaining object settings."""
import base64
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text())


def approved_outputs():
    q04 = HERE.parent / 'q04'
    records = [
        load(q04 / 'pod-topology-v34/first-window-evidence/INDEPENDENT-VERIFICATION.json'),
        load(q04 / 'pod-topology-v35/first-window-evidence/INDEPENDENT-VERIFICATION.json'),
    ]
    outputs = {
        row['fixture']: row
        for record in records
        for row in record['workflows']
        if row['mode'] == 'fresh' and row['fixture'] in ('06', '07', '08', 'native')
    }
    for fixture, output in outputs.items():
        output['checks'] = load(HERE / 'reference-checks' / f'{fixture}.json')
    return outputs


def verify_output(result, expected):
    assert hashlib.sha256((result / 'document.json').read_bytes()).hexdigest() == expected['document_sha256']
    assert load(result / 'checks.json') == expected['checks']


def qualify(runtime: Path, objects: Path, controller: Path, *, phase='t09b-calibration-a6',
            expected_groups=29, expected_recycles=1, expected_generations=2,
            expected_recycle_at=20):
    state = runtime / 'evidence/state' / phase
    expected = approved_outputs()
    comparisons = []
    business = []
    for index, fixture in enumerate(('06', '07', '08', 'native', '06')):
        result = state / f'warm-{index}-{fixture}'
        verify_output(result, expected[fixture])
        assert load(result / 'result.json')['processing_complete'], fixture
        assert load(result / 'accepted.json')['verified'], fixture
        events = load(result / 'history.json')['events']
        assert not any(event['eventType'] in (
            'EVENT_TYPE_ACTIVITY_TASK_FAILED', 'EVENT_TYPE_ACTIVITY_TASK_TIMED_OUT',
            'EVENT_TYPE_WORKFLOW_EXECUTION_CANCEL_REQUESTED') for event in events), fixture
        completed = events[-1]
        assert completed['eventType'] == 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED', fixture
        payload = completed['workflowExecutionCompletedEventAttributes']['result']['payloads'][0]
        outcome = json.loads(base64.b64decode(payload['data']))
        assert outcome['status'] == 'complete' and outcome['processing_complete'] is True
        assert outcome['error'] is None
        business.append({'fixture': result.name, 'terminal_time': completed['eventTime'],
                         'business': {key: outcome[key] for key in (
                             'status', 'processing_complete', 'canonical_accepted',
                             'registered_pages', 'registered_components', 'error')}})
        comparisons.append({'fixture': result.name, 'full_document_equal': True,
                            'full_checks_equal': True, 'processing_complete': True})
    proof = load(state / 'warm-proof.json')
    assert proof['groups'] == expected_groups
    assert proof['recycles'] == expected_recycles
    assert len(proof['pids']) == expected_generations
    measurement = runtime / 'evidence/state' / (phase + '-measurement')
    contract = load(measurement / 'measurement-contract.json')
    assert contract['workload_succeeded'] and contract['qualification_complete']
    assert contract['group_requests'] == expected_groups
    assert contract['request_recycle'] == expected_recycle_at
    assert contract['parser_generations'] == expected_generations
    assert contract['process_lifecycle']['status'] == 'PASS'
    assert contract['resource_gate']['status'] == 'PASS'
    assert contract['automatic_retry'] is False
    assert load(runtime / 'evidence/workload-exit.json')['returncode'] == 0
    observer = load(objects / 'trial-cleanup.json')
    assert observer['primary_error'] is None and not observer.get('object_observer_error')
    assert observer['host_memory_low_override'] is False
    assert observer['maximum_object_full_avg10'] == 0
    assert observer['object_psi_policy'] == {
        'mode': 'approved_sustained_pressure_qualification',
        'stop_full_avg10_above': 0,
        'cumulative_full_total_stop': False,
        'memory_events_max': 'recorded_boundary_event_not_immediate_stop',
        'node_full_psi_avg10': 'runtime_telemetry_not_immediate_stop',
        'diagnostic_only': True,
    }
    cleanup = load(runtime / 'outer-cleanup.json')
    assert cleanup['primary_error'] is None
    assert cleanup['disposition'] == 'CLEANED_WITH_WORKLOAD_EVIDENCE_RETAINED'
    assert cleanup['final_identity_and_health'] is True
    attribution = [json.loads(line) for line in
                   (controller / 'node-psi-attribution.jsonl').read_text().splitlines()]
    assert attribution[0]['kind'] == 'start' and attribution[-1]['kind'] == 'end'
    assert attribution[-1]['stopped_by_signal'] is True
    assert attribution[0]['time'] <= load(runtime / 'evidence/supervisor-ownership.json')['started_at']
    assert attribution[-1]['time'] >= load(runtime / 'evidence/workload-exit.json')['finished_at']
    trace = [json.loads(line) for line in
             (controller / 'object-stall-trace.jsonl').read_text().splitlines()]
    assert trace[0]['kind'] == 'start' and trace[-1]['kind'] == 'end'
    for stats in trace[-1]['buffer_stats'].values():
        fields = dict(line.split(':', 1) for line in stats.splitlines())
        assert all(int(fields[key]) == 0 for key in
                   ('overrun', 'commit overrun', 'dropped events'))
    result = {'status': 'PASS_DIAGNOSTIC_ONLY', 'comparisons': comparisons,
              'groups': expected_groups, 'recycle_at': expected_recycle_at,
              'parser_generations': expected_generations,
              'object_full_psi_delta_us': observer['object_observer']['full_psi_delta_us'],
              'object_max_events_delta': observer['object_observer']['max_events_delta'],
              'maximum_object_full_avg10': observer['maximum_object_full_avg10'],
              'host_memory_low_override': False,
              'complete_auxiliary_attribution': True, 'direct_trace_loss': 0}
    (controller / 'temporal-reconciliation.json').write_text(json.dumps(business, indent=2) + '\n')
    from reconcile_traffic import reconcile_run
    server = [json.loads(line) for line in (controller / 'native-traffic.jsonl').read_text().splitlines()]
    lifecycle = load(controller / 'native-trace-lifecycle.json')
    assert lifecycle['remote_stopped'] is True
    traffic = reconcile_run(runtime / 'evidence/state', phase, server, 't09a', lifecycle)
    (controller / 'traffic-reconciliation.json').write_text(json.dumps(traffic, indent=2) + '\n')
    assert traffic['complete'], traffic['errors']
    result['traffic_complete'] = True
    from storage_cost import summarize
    storage = summarize(state / 'worker-1/storage.jsonl')
    (controller / 'storage-cost.json').write_text(json.dumps(storage, indent=2) + '\n')
    result['buffering_scope'] = 'publication inputs only; full buffering calibration remains pending'
    (controller / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
