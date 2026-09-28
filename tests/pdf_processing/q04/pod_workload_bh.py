"""Coordinator-Pod supervisor for one native Activity Pod-loss qualification."""

import importlib.util
import inspect
import json
from pathlib import Path
import sys


_spec = importlib.util.spec_from_file_location(
    'q04_pod_workload_bh_engine', Path(__file__).with_name('pod_workload_p.py'))
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base
_spec.loader.exec_module(base)


PHASE = 'pod-loss-pod-cgroup-bh'
RUN_ID = 'q04-pod-loss-pod-cgroup-20260926-bh'
WORKFLOW_QUEUE = 'q04-pod-cgroup-bh-workflows'
ACTIVITY_QUEUE = 'q04-pod-cgroup-bh-native'
EVIDENCE_ROOT = Path('/q04-evidence/q04-pod-loss-pod-cgroup-20260926-bh')


def build_measurement_argv(args, run_id: str, authorization_sha256: str) -> list[str]:
    return [args.python, '-m', 'candidate.pod_loss_window_bh',
        '--bundle', str(args.bundle), '--state', str(args.state),
        '--capacity', str(args.capacity), '--name', PHASE,
        '--expected-run-id', run_id, '--expected-prefix', args.prefix,
        '--integration-manifest',
        str(args.workspace / 'tests/pdf_processing/q04/pod-topology-v59/RUNTIME-INTEGRATION-MANIFEST.json'),
        '--authorization-scope-sha256', authorization_sha256,
        '--capacity-approved']


def cleanup_markers(state: Path) -> dict:
    root = state / PHASE
    control = state.parent / 'pod-loss-control'
    reply_path = control / '0-stop.reply.json'
    reply = json.loads(reply_path.read_text()) if reply_path.exists() else {}
    stopped = [json.loads(path.read_text()) for path in sorted(root.glob('worker-*/stopped.json'))]
    complete = (len(stopped) == 1 and all(
                    row.get('parser_absent') is True
                    and row.get('scratch_absent') is True for row in stopped)
                and reply.get('run_id') == RUN_ID and reply.get('kind') == 'stop'
                and reply.get('status') == 'PASS'
                and reply.get('activity_pods_absent') is True
                and reply.get('worker_absent') is True
                and reply.get('emptydirs_absent') is True)
    return {
        'worker_absent': complete,
        'owned_children_absent': complete,
        'scratch_absent': complete,
        'worker_generations': len(list(root.glob('worker-*/ownership.json'))),
        'stopped': stopped,
        'pod_loss_cleanup': reply,
    }


def _patched(function, old: str, new: str):
    source = inspect.getsource(function)
    if source.count(old) != 1:
        raise RuntimeError('upstream supervisor contract changed')
    namespace = dict(vars(base))
    exec(compile(source.replace(old, new), str(base.__file__) + ':bh', 'exec'), namespace)
    return namespace[function.__name__]


base.PHASE = PHASE
base.RUN_ID = RUN_ID
base.WORKFLOW_QUEUE = WORKFLOW_QUEUE
base.ACTIVITY_QUEUE = ACTIVITY_QUEUE
base.EVIDENCE_ROOT = EVIDENCE_ROOT
base.build_measurement_argv = build_measurement_argv
base.cleanup_markers = cleanup_markers
base.adopt_budget = _patched(base.adopt_budget,
    'config["pod_namespace"] = None',
    'if config["trial_seconds"] != 180:\n'
    '        raise ValueError("baseline workflow deadline changed")\n'
    '    config["trial_seconds"] = 300\n'
    '    config["pod_namespace"] = "pdf-t09a-validation"')
base.run = _patched(base.run,
    'pod-topology-v15/RUNTIME-INTEGRATION-MANIFEST.json',
    'pod-topology-v59/RUNTIME-INTEGRATION-MANIFEST.json')
main = base.main


if __name__ == '__main__':
    raise SystemExit(main())
