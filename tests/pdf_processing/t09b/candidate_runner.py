"""Prepare or execute one guarded T09b group-10 B2 candidate."""
import json
from pathlib import Path
import shlex
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runtime_wiring import configure
from candidate_contract import IDENTITY, SCOPE

runner = configure(topology_name='candidate_topology',
                   evidence_name='candidate_pod_remote_evidence',
                   identity='t09b-calibration-20260929-b2', record_name='runtime-b2',
                   preflight_name='candidate_pod_preflight.py',
                   workload_name='candidate_pod_workload.py')
base = runner.base
original_runtime_sample = runner.base_verify_sample
inherited_scope = runner.authorization_scope


def authorization_scope():
    return {**inherited_scope(), 'group_requests': 16,
            'expected_parser_generations': 1, 'candidate_group_pages': 10}


runner.authorization_scope = base.authorization_scope = runner.ah.authorization_scope = authorization_scope


def integration_manifest():
    return {
        'schema_version': 1,
        'authorization_scope': SCOPE,
        'authorization_scope_sha256': base.sha256(base.canonical(SCOPE)),
        'identity': IDENTITY,
        'adoption': {
            'status': 'AUTHORIZED_BY_USER',
            'scope': 'One controlled T09b group-10 B2 candidate; existing resource guards; no retry.',
        },
    }


def verify_object_monitor():
    if runner.monitor is None or not runner.monitor.samples:
        raise ValueError('object-service telemetry missing')
    if runner.monitor.error is not None:
        raise runner.monitor.error
    first = runner.monitor.samples[0]
    for row in runner.monitor.samples[runner.checked_samples:]:
        if len(first['ancestors']) < 2 or len(row['ancestors']) < 2:
            raise ValueError('object-service Pod/container telemetry missing')
        if (row['object_full_avg10'] > 0 or any(row['memory_events'][key] != 0
                for key in ('oom', 'oom_kill', 'oom_group_kill'))):
            raise ValueError('object-service OOM/sustained-full-PSI qualification failure')
        for before, level in zip(first['ancestors'][:2], row['ancestors'][:2]):
            if (level['memory_max'] != str(runner.object_trial.TRIAL_BYTES)
                    or any(level['events_local'][key] != before['events_local'][key]
                           for key in ('oom', 'oom_kill', 'oom_group_kill'))):
                raise ValueError('object-service Pod/container memory contract changed')
        runner.checked_samples += 1


def verify_runtime_sample(row, baseline_oom):
    original_runtime_sample({**row, 'psi_full_avg10': 0}, baseline_oom)


runner.OBJECT_PSI_POLICY = {
    **runner.OBJECT_PSI_POLICY,
    'memory_events_max': 'recorded_boundary_event_not_immediate_stop',
    'node_full_psi_avg10': 'runtime_telemetry_not_immediate_stop',
    'diagnostic_only': True,
}
runner.verify_object_monitor = verify_object_monitor
runner.base_verify_sample = verify_runtime_sample
runner.base.verify_runtime_sample = verify_runtime_sample
runner.adapted_window.__globals__['base_runtime_guard'] = verify_runtime_sample


def exact_command():
    return shlex.join([str(base.LOCAL_PYTHON), '-B', str(Path(__file__).resolve()),
                      '--execute', '--owner', 'main-session',
                      '--approval-reference', 'User authorized controlled T09b validation',
                      '--authorization-scope-sha256', runner.ah.authorization_scope_sha256()])


def build_manifest():
    return dict(identity=runner.RUN_IDENTITY, authorization_scope=runner.authorization_scope(),
                workload_argv=runner.workload_argv(), preflight_argv=runner.preflight_argv(),
                sources={path.name: base.sha256(path.read_bytes())
                         for path in sorted(HERE.glob('*.py')) if not path.name.startswith('test_')},
                exact_single_run_command=exact_command(), automatic_retry=False)


def offline_check():
    layout = json.loads(base.WORKER_YAML.read_text())
    runner.topology.validate(layout)
    if json.loads((runner.RECORD / 'SOURCE-MANIFEST.json').read_text()) != runner.topology.source_manifest():
        raise ValueError('T09b candidate projected source changed')
    if json.loads(base.OFFLINE_MANIFEST.read_text()) != build_manifest():
        raise ValueError('T09b candidate launch contract changed')
    return {'status': 'PASS_OFFLINE_ONLY', 'runtime_authorized': False}


runner.exact_command = base.exact_command = runner.ah.exact_command = exact_command
runner.offline_check = base.offline_check = offline_check
base.build_offline_manifest = build_manifest


if __name__ == '__main__':
    if sys.argv[1:] == ['--prepare']:
        (HERE / 'CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json').write_text(
            json.dumps(integration_manifest(), indent=2) + '\n')
        runner.RECORD.mkdir(exist_ok=False)
        runner.topology.render(base.WORKER_YAML, runner.RECORD / 'SOURCE-MANIFEST.json')
        base.OFFLINE_MANIFEST.write_text(json.dumps(build_manifest(), indent=2) + '\n')
        print(json.dumps(offline_check()))
    else:
        raise SystemExit(base.main())
