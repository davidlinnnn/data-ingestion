import copy
import json
from pathlib import Path
import unittest
import tempfile

from sentinel import aima_attribution_telemetry_o as telemetry

ROOT = Path('/private/tmp/q04-aima-pod-cgroup-20260920-n/failure-evidence/state')


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.rows = [json.loads(line) for line in (ROOT/'aima-pod-cgroup-n-measurement/resource-attribution.jsonl').read_text().splitlines()]

    def test_real_n_process_handoff_does_not_depend_on_late_workflow_query(self):
        result = telemetry.evaluate_handoff_contract(self.rows, ROOT/'aima-pod-cgroup-n')
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['handoffs'][0]['warm_pid'], 132)
        self.assertEqual(result['handoffs'][0]['fresh_pid'], 187)
        self.assertFalse(result['sub_sample_order_measured'])

    def test_missing_exit_and_live_warm_at_birth_fail(self):
        for mutation in ('exit', 'overlap', 'identity'):
            with self.subTest(mutation=mutation):
                rows = copy.deepcopy(self.rows)
                if mutation == 'exit':
                    rows[308]['process_events'] = [e for e in rows[308]['process_events'] if e['event'] != 'exit_observed']
                elif mutation == 'overlap':
                    rows[308]['processes'].append(next(p for p in rows[307]['processes'] if p['pid'] == 132))
                else:
                    next(e for e in rows[308]['process_events'] if e['event'] == 'exit_observed')['start_ticks'] += 1
                self.assertFalse(telemetry.evaluate_handoff_contract(rows, ROOT/'aima-pod-cgroup-n')['complete'])

    def test_actual_collector_stop_classifies_only_confirmed_exits(self):
        for mutation in (None, 'denied', 'peak', 'tied_peak'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                rows = copy.deepcopy(self.rows)
                if mutation == 'denied':
                    next(p for p in rows[395]['processes'] if p['status'] != 'complete')['reason'] = 'PermissionError'
                if mutation == 'peak': rows[395]['memory_current'] = 3 * 1024**3
                if mutation == 'tied_peak': rows[395]['memory_current'] = max(r['memory_current'] for r in rows)
                supplied = iter(rows)
                def sampler(**kwargs):
                    row = next(supplied)
                    row['runtime_observations'] = [dict(o, key=str(row['monotonic'])+o['label']) for o in row['observations']]
                    return row
                root = Path(tmp)
                collector = telemetry.StrictAttributionCollector(root/'rows.jsonl', root/'summary.json',
                    root_pid=103, observation_root=ROOT/'aima-pod-cgroup-n', sampler=sampler)
                collector.identity = rows[0]['cgroup']
                collector._stream = collector.spool.open('w')
                collector._final_stream = collector.output.open('xb')
                for _ in rows[:-1]: collector._capture()
                outcome = collector.stop(expect_cancel=True, require_handoff=True, require_no_warm_fresh_overlap=True)
                report = json.loads(collector.summary.read_text())
                self.assertEqual(outcome.qualification_complete, mutation is None, report)
                self.assertFalse(outcome.attribution_complete)
                self.assertFalse(report['process_attribution_complete'])
                if mutation is None:
                    self.assertEqual(report['classified_cgroup_transition_sample_indexes'], [395, 414])


if __name__ == '__main__':
    unittest.main()
