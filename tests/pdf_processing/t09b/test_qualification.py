import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from qualify_baseline import qualify


class QualificationTest(unittest.TestCase):
    def test_failed_traffic_never_leaves_overall_pass(self):
        outcome = dict(status='complete', processing_complete=True, error=None,
                       canonical_accepted=True, registered_pages=1, registered_components=1)
        event = dict(eventType='EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED', eventTime='time',
                     workflowExecutionCompletedEventAttributes={'result': {'payloads': [
                         {'data': base64.b64encode(json.dumps(outcome).encode()).decode()}]}})
        values = {
            'document.json': {}, 'checks.json': {}, 'result.json': outcome,
            'accepted.json': {'verified': True}, 'history.json': {'events': [event]},
            'warm-proof.json': dict(groups=29, recycles=1, pids=[1, 2]),
            'measurement-contract.json': dict(workload_succeeded=True, qualification_complete=True,
                group_requests=29, request_recycle=20, parser_generations=2,
                process_lifecycle={'status': 'PASS'}, resource_gate={'status': 'PASS'}, automatic_retry=False),
            'workload-exit.json': dict(returncode=0, finished_at=2),
            'supervisor-ownership.json': {'started_at': 1},
            'trial-cleanup.json': dict(primary_error=None, host_memory_low_override=False,
                object_observer=dict(max_events_delta=0, full_psi_delta_us=0), maximum_object_full_avg10=0,
                object_psi_policy=dict(mode='approved_sustained_pressure_qualification',
                    stop_full_avg10_above=0, cumulative_full_total_stop=False)),
            'outer-cleanup.json': dict(primary_error=None,
                disposition='CLEANED_WITH_WORKLOAD_EVIDENCE_RETAINED', final_identity_and_health=True),
            'native-trace-lifecycle.json': {'remote_stopped': True},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'node-psi-attribution.jsonl').write_text(
                '{"kind":"start","time":0}\n{"kind":"end","time":3,"stopped_by_signal":true}\n')
            (root / 'object-stall-trace.jsonl').write_text(
                '{"kind":"start"}\n{"kind":"end","buffer_stats":{}}\n')
            (root / 'native-traffic.jsonl').write_text('')
            with patch('qualify_baseline.load', side_effect=lambda path: values[path.name]), \
                 patch('reconcile_traffic.reconcile_run', return_value={'complete': False, 'errors': ['missing']}):
                with self.assertRaises(AssertionError):
                    qualify(root, root, root)
            self.assertFalse((root / 'qualification.json').exists())
            self.assertTrue((root / 'traffic-reconciliation.json').exists())
