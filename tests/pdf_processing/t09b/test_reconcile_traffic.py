import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from reconcile_traffic import reconcile, reconcile_ledgers, reconcile_run


class ReconciliationTest(unittest.TestCase):
    def test_missing_worker_generation_cannot_be_omitted(self):
        root = Path(__file__).parent / 'boto-correlated-evidence'
        evidence = json.loads((root / 'result.json').read_text())
        trace = dict(collector_stopped=True, ready_call_id='ready', final_call_id='final')
        records = [dict(evidence['records'][0], call_id='ready'), *evidence['records'],
                   dict(evidence['records'][0], call_id='final')]
        with TemporaryDirectory() as directory:
            state = Path(directory)
            worker = state / 'phase' / 'worker-1'
            worker.mkdir(parents=True)
            (worker / 'storage.jsonl').write_text((root / 'storage.jsonl').read_text())
            (worker.parent / 'worker-1.log').write_text('log')
            self.assertTrue(reconcile_run(state, 'phase', records, 't09a', trace)['complete'])
            self.assertFalse(reconcile_run(state, 'phase', records, 't09a', {})['complete'])
            self.assertFalse(reconcile_run(state, 'phase', evidence['records'], 't09a', trace)['complete'])
            (worker.parent / 'worker-2').mkdir()
            report = reconcile_run(state, 'phase', records, 't09a', trace)
            self.assertFalse(report['complete'])
            self.assertEqual(report['worker_generations'], 2)
            self.assertEqual(len(report['missing_ledgers']), 1)

    def test_unfinished_call_cannot_disappear_from_traffic_report(self):
        root = Path(__file__).parent / 'boto-correlated-evidence'
        evidence = json.loads((root / 'result.json').read_text())
        with TemporaryDirectory() as directory:
            ledger = Path(directory) / 'storage.jsonl'
            original = (root / 'storage.jsonl').read_text()
            ledger.write_text(original)
            self.assertTrue(reconcile_ledgers([ledger], evidence['records'], 't09a')['complete'])
            pending = json.loads(original.splitlines()[0])
            pending['call_id'] = 'interrupted'
            ledger.write_text(original + json.dumps(pending) + '\n')
            report = reconcile_ledgers([ledger], evidence['records'], 't09a')
            self.assertFalse(report['complete'])
            self.assertIn('incomplete storage ledger', report['errors'][-1])

    def test_attempt_counts_missing_transfers_and_observer_exclusion(self):
        call = {'role': 'workload', 'operation': 'get_object', 'call_id': 'id',
                'key': 'prefix/a', 'sdk_retries': 1, 'outcome': 'read_complete',
                'delivered_bytes': 4}
        good = {'call_id': 'id', 'method': 'GET', 'path': '/bucket/prefix/a',
                'status': 200, 'server_rx_bytes': 100, 'server_tx_bytes': 4}
        bad = dict(good, status=503, server_tx_bytes=0)
        observer = dict(good, call_id=None)
        report = reconcile([call], [bad, good, observer], 'bucket')
        self.assertTrue(report['complete'])
        self.assertEqual(report['server_rx_bytes'], 200)
        self.assertEqual(report['excluded_untagged_calls'], 1)
        tagged_observer = dict(observer, call_id='observer')
        observer_call = dict(call, role='observer', call_id='observer', sdk_retries=0)
        report = reconcile([call, observer_call], [bad, good, tagged_observer], 'bucket')
        self.assertTrue(report['complete'])
        self.assertEqual(report['excluded_observer_calls'], 1)
        self.assertEqual(report['server_rx_bytes'], 200)
        self.assertFalse(reconcile([call], [bad, good, tagged_observer], 'bucket')['complete'])
        self.assertFalse(reconcile([call], [good], 'bucket')['complete'])
        partial = dict(call, outcome='read_incomplete')
        self.assertFalse(reconcile([partial], [bad, good], 'bucket')['complete'])
        missing = dict(call, sdk_retries=0, outcome='call_failed',
                       error_type='NoSuchKey', delivered_bytes=0)
        absent = dict(good, status=404, server_tx_bytes=533)
        self.assertTrue(reconcile([missing], [absent], 'bucket')['complete'])
        self.assertFalse(reconcile([missing], [bad], 'bucket')['complete'])
        self.assertFalse(reconcile([dict(call, sdk_retries=None)], [good], 'bucket')['complete'])
        changed = dict(good, path='/bucket/other')
        self.assertFalse(reconcile([call], [bad, changed], 'bucket')['complete'])
