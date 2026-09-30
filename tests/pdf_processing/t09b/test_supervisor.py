import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import pod_workload as supervisor


class SupervisorTest(unittest.TestCase):
    def test_launch_contract_and_missing_cleanup_marker(self):
        from candidate.warm_pod_window_r import validate_scope
        here = Path(__file__).resolve().parent
        manifest_path = here / 'RUNTIME-INTEGRATION-MANIFEST.json'
        manifest = json.loads(manifest_path.read_text())
        args = SimpleNamespace(python='/runtime/python', workspace=here.parents[2],
                               bundle=Path('/inputs'), state=Path('/state'),
                               capacity=Path('/capacity.json'), prefix=manifest['identity']['prefix'])
        command = supervisor.build_measurement_argv(
            args, supervisor.RUN_ID, manifest['authorization_scope_sha256'])
        self.assertEqual(command[:2], ['/runtime/python', str(here / 'baseline_window.py')])
        self.assertEqual(command[command.index('--integration-manifest') + 1], str(manifest_path))
        self.assertEqual(command[command.index('--expected-run-id') + 1], supervisor.RUN_ID)
        validate_scope(SimpleNamespace(integration_manifest=manifest_path,
                       authorization_scope_sha256=manifest['authorization_scope_sha256'],
                       name=supervisor.PHASE, expected_run_id=supervisor.RUN_ID,
                       expected_prefix=args.prefix))
        parsed = supervisor.base.parser().parse_args([
            '--prefix', args.prefix, '--authorization-scope-sha256', 'scope'])
        self.assertEqual(parsed.workload_seconds, 825)
        self.assertEqual(parsed.run_id, supervisor.RUN_ID)
        self.assertEqual(parsed.workflow_queue, supervisor.PHASE + '-workflows')
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            phase = state / supervisor.PHASE
            worker = phase / 'worker-1'
            worker.mkdir(parents=True)
            (phase / 'worker-1.log').write_text('retained log')
            self.assertFalse(supervisor.cleanup_markers(state)['worker_absent'])
            (worker / 'stopped.json').write_text(json.dumps(dict(parser_absent=True, scratch_absent=True)))
            self.assertTrue(supervisor.cleanup_markers(state)['worker_absent'])
            self.assertEqual(supervisor.cleanup_markers(state)['worker_generations'], 1)
