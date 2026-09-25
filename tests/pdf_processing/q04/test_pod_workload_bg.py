"""Split-Pod supervisor keeps Activity scratch ephemeral and cleanup exact."""

import json
from pathlib import Path
import tempfile
import unittest

import pod_workload_bg as bg


class PodWorkloadBGTest(unittest.TestCase):
    def test_budget_adoption_selects_pod_emptydir_scratch(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / 'state'
            state.mkdir()
            config = {'run_id': 'q04-init', 'parser_budgets': bg.base.PARSER_BUDGETS,
                      'profiles': {'08': {}}, 'queues': {'08': 'old'}}
            (state / 'config.json').write_text(json.dumps(config))
            bg.base.run.__globals__['adopt_budget'](state, root / 'budget.json',
                evidence_root=root, run_id=bg.RUN_ID,
                workflow_queue=bg.WORKFLOW_QUEUE,
                activity_queue=bg.ACTIVITY_QUEUE)
            adopted = json.loads((state / 'config.json').read_text())
            self.assertEqual(adopted['pod_namespace'], 'pdf-t09a-validation')
            self.assertEqual(adopted['queues']['08'], bg.ACTIVITY_QUEUE)

    def test_cleanup_requires_controller_absence_proof(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / 'state'
            (state / bg.PHASE).mkdir(parents=True)
            self.assertFalse(bg.cleanup_markers(state)['worker_absent'])
            control = root / 'pod-loss-control'
            control.mkdir()
            (control / '0-stop.reply.json').write_text(json.dumps({
                'run_id': bg.RUN_ID, 'kind': 'stop', 'status': 'PASS',
                'activity_pods_absent': True, 'worker_absent': True,
                'emptydirs_absent': True}))
            self.assertFalse(bg.cleanup_markers(state)['worker_absent'])
            worker = state / bg.PHASE / 'worker-2'
            worker.mkdir()
            (worker / 'stopped.json').write_text(json.dumps({
                'parser_absent': True, 'scratch_absent': True}))
            self.assertTrue(bg.cleanup_markers(state)['worker_absent'])
