"""Pod replacement identity is a Kubernetes UID boundary, not a PID inequality."""

import json
from pathlib import Path
import tempfile
import unittest

from candidate.pod_loss_window_bf import SCOPE, verify_drain
from consumer import canonical, sha


class PodLossProofTest(unittest.TestCase):
    def test_frozen_scope_matches_reviewed_manifest(self):
        manifest = json.loads((Path(__file__).with_name('pod-topology-v57') /
            'RUNTIME-INTEGRATION-MANIFEST.json').read_text())
        self.assertEqual(manifest['authorization_scope'], SCOPE)
        self.assertEqual(manifest['authorization_scope_sha256'],
                         sha(canonical(SCOPE).encode()))

    def test_distinct_pods_can_reuse_worker_pid(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / 'evidence' / 'state' / 'pod-loss-bf'
            root.mkdir(parents=True)
            target = root / 'drain-native'
            target.mkdir()
            (root / 'worker-1').mkdir()
            (root / 'worker-2').mkdir()
            values = {
                target / 'accepted.json': {'verified': True,
                    'result': {'status': 'complete', 'processing_complete': True,
                               'registered_pages': 51, 'selected_components': 7,
                               'registered_components': 7},
                    'accepted': {'document_sha256': 'document',
                                 'checks': {'full_reference_graph_sha256': 'graph'}}},
                target / 'drain.json': {'scope': 'owned_pod',
                    'old_pod_uid': 'old', 'new_pod_uid': 'new'},
                target / 'drain-proof.json': {'retried_range': [6, 10],
                    'attempt': 2, 'retained': ['group-1']},
                target / 'history.json': {'events': [
                    {'eventType': 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED'}]},
                root / 'worker-1/host.json': {'pod': {'uid': 'old'},
                                               'ready': {'pid': 7}},
                root / 'worker-2/host.json': {'pod': {'uid': 'new'},
                                               'ready': {'pid': 7}},
                root.parents[1] / 'pod-loss-control/2-drain.reply.json': {
                    'run_id': 'q04-bf', 'kind': 'drain', 'generation': 2,
                    'status': 'PASS', 'old_pod_uid': 'old', 'pod_uid': 'new',
                    'old_runtime_absent': True, 'old_scratch_absent': True},
            }
            for path, value in values.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            self.assertEqual(verify_drain(root,
                {'native_document_sha256': 'document',
                 'native_graph_sha256': 'graph'})['new_pod_uid'], 'new')
