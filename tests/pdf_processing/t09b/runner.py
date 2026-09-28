"""T09b offline preparation and one guarded worker window; controller owns admission."""
import argparse
import json
from pathlib import Path
import shlex
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runtime_wiring import configure

runner = configure()
base = runner.base


def verify_object_monitor_a3():
    """Keep OOM/PSI fatal; record memory.max reclaim events for this diagnostic."""
    if runner.monitor is None or not runner.monitor.samples:
        raise ValueError('object-service telemetry missing')
    if runner.monitor.error is not None:
        raise runner.monitor.error
    first = runner.monitor.samples[0]
    for row in runner.monitor.samples[runner.checked_samples:]:
        if len(first['ancestors']) < 2 or len(row['ancestors']) < 2:
            raise ValueError('object-service Pod/container telemetry missing')
        if (row['object_full_avg10'] > 0
                or any(row['memory_events'][key] != 0
                       for key in ('oom', 'oom_kill', 'oom_group_kill'))):
            raise ValueError('object-service OOM/sustained-full-PSI qualification failure')
        for before, level in zip(first['ancestors'][:2], row['ancestors'][:2]):
            if (level['memory_max'] != str(runner.object_trial.TRIAL_BYTES)
                    or any(level['events_local'][key] != before['events_local'][key]
                           for key in ('oom', 'oom_kill', 'oom_group_kill'))):
                raise ValueError('object-service Pod/container memory contract changed')
        runner.checked_samples += 1


runner.OBJECT_PSI_POLICY = {
    **runner.OBJECT_PSI_POLICY,
    'memory_events_max': 'recorded_boundary_event_not_immediate_stop',
    'diagnostic_only': True,
}
runner.verify_object_monitor = verify_object_monitor_a3


def exact_command():
    return shlex.join([str(base.LOCAL_PYTHON), '-B', str(Path(__file__).resolve()),
                      '--execute', '--owner', 'main-session',
                      '--approval-reference', 'User authorized controlled T09b baseline',
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
        raise ValueError('T09b projected source changed')
    if json.loads(base.OFFLINE_MANIFEST.read_text()) != build_manifest():
        raise ValueError('T09b launch contract changed')
    return {'status': 'PASS_OFFLINE_ONLY', 'runtime_authorized': False}


runner.exact_command = base.exact_command = runner.ah.exact_command = exact_command
runner.offline_check = base.offline_check = offline_check
base.build_offline_manifest = build_manifest
# configure() already installs the T09b startup/evidence-race adapter.


if __name__ == '__main__':
    if sys.argv[1:] == ['--prepare']:
        runner.RECORD.mkdir(exist_ok=False)
        runner.topology.render(base.WORKER_YAML, runner.RECORD / 'SOURCE-MANIFEST.json')
        base.OFFLINE_MANIFEST.write_text(json.dumps(build_manifest(), indent=2) + '\n')
        print(json.dumps(offline_check()))
    else:
        raise SystemExit(base.main())
