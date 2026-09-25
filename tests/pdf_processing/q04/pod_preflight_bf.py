"""Pre-inference gates for the split-coordinator Activity Pod-loss trial."""

import argparse
import importlib
import json
from pathlib import Path

import pod_preflight_be as be


PHASE = 'pod-loss-pod-cgroup-bf'
TOPOLOGY_PHASE = 'q04-pod-cgroup-bf'
RUN_ID = 'q04-pod-loss-pod-cgroup-20260925-bf'


def verify_workload_imports(*, workspace: Path, bundle: Path, prefix: str):
    modules = ('candidate.pod_loss_window_bf', 'pod_loss_bridge_bf',
               'pod_workload_bf', 'pod_init_p', 'worker_bc')
    for module in modules:
        importlib.import_module(module)
    from candidate.pod_loss_window_bf import validate_scope
    from candidate.warm_pod_window_r import validate_contract
    from q04_runtime import profiles

    inputs = json.loads((bundle / 'inputs.json').read_text())
    config = {'parser_budgets': {
        'startup_seconds': 120, 'no_progress_seconds': 180,
        'terminate_seconds': 5, 'reap_seconds': 5, 'max_requests': 20},
        'profiles': profiles(inputs, {fixture['id']: {
            'key': prefix + 'sources/' + fixture['id'] + '.pdf'}
            for fixture in inputs['fixtures']})}
    validate_contract(config, inputs)
    path = workspace / 'tests/pdf_processing/q04/pod-topology-v57/RUNTIME-INTEGRATION-MANIFEST.json'
    manifest = json.loads(path.read_text())
    validate_scope(argparse.Namespace(
        integration_manifest=path,
        authorization_scope_sha256=manifest['authorization_scope_sha256'],
        name=PHASE, expected_run_id=RUN_ID, expected_prefix=prefix))
    return {'status': 'PASS', 'modules': list(modules),
            'reviewed_contract': {'status': 'PASS', 'fixtures': ['native'],
                'modes': ['drain'], 'parser_max_requests': 20,
                'production_default_changed': False}}


be.PHASE = PHASE
be.TOPOLOGY_PHASE = TOPOLOGY_PHASE
be.RUN_ID = RUN_ID
be.base.PHASE = PHASE
be.base.TOPOLOGY_PHASE = TOPOLOGY_PHASE
be.base.RUN_ID = RUN_ID
be.base.verify_configuration_q = be.verify_configuration_at
be.base.verify_workload_imports_q = verify_workload_imports
main = be.base.main


if __name__ == '__main__':
    raise SystemExit(main())
