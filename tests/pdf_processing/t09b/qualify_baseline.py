"""Complete business/output qualification before retaining object settings."""
import base64
import json
from pathlib import Path


def load(path):
    return json.loads(path.read_text())


def qualify(runtime: Path, objects: Path, controller: Path):
    state = runtime / 'evidence/state/t09b-calibration-a5'
    comparisons = []
    business = []
    for index, fixture in enumerate(('06', '07', '08', 'native', '06')):
        tag = 'ai' if fixture in ('06', 'native') else 'aj'
        reference = Path(f'/private/tmp/q04-matrix-pod-cgroup-20260924-{tag}/evidence/state/matrix-pod-cgroup-{tag}/fresh-{fixture}')
        result = state / f'warm-{index}-{fixture}'
        assert load(result / 'document.json') == load(reference / 'document.json'), fixture
        assert load(result / 'checks.json') == load(reference / 'checks.json'), fixture
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
    assert proof['groups'] == 29 and proof['recycles'] == 1 and len(proof['pids']) == 2
    measurement = runtime / 'evidence/state/t09b-calibration-a5-measurement'
    contract = load(measurement / 'measurement-contract.json')
    assert contract['workload_succeeded'] and contract['qualification_complete']
    assert contract['group_requests'] == 29 and contract['request_recycle'] == 20
    assert contract['parser_generations'] == 2
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
              'groups': 29, 'recycle_at': 20, 'parser_generations': 2,
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
    traffic = reconcile_run(runtime / 'evidence/state', 't09b-calibration-a5', server, 't09a', lifecycle)
    (controller / 'traffic-reconciliation.json').write_text(json.dumps(traffic, indent=2) + '\n')
    assert traffic['complete'], traffic['errors']
    result['traffic_complete'] = True
    result['buffering_scope'] = 'publication inputs only; full buffering calibration remains pending'
    (controller / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
