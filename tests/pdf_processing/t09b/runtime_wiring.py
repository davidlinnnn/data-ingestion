"""Bind the retained guarded runner to T09b paths without starting a runtime.

Call in a dedicated interpreter: historical engines use module globals. The outer
controller must still supply reviewed offline admission, trace ownership and
post-run reconciliation before invoking the returned engine.
"""
from pathlib import Path
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'q04'))
sys.path.insert(0, str(HERE))


def configure():
    # Seed topology before the guarded engine defines its keyword defaults.
    # Rebinding module globals afterward does not update Python default values.
    modules = []
    for name in ('topology', 'pod_remote_evidence'):
        spec = importlib.util.spec_from_file_location('t09b_' + name, HERE / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules.append(module)
        if name == 'topology':
            previous = sys.modules.get('pod_topology_dh')
            sys.modules['pod_topology_dh'] = module.base
            try:
                from sentinel import run_warm_pod_cgroup_dh as runner
            finally:
                if previous is None:
                    sys.modules.pop('pod_topology_dh', None)
                else:
                    sys.modules['pod_topology_dh'] = previous
    topology, evidence = modules
    base, ah = runner.base, runner.ah
    layout = topology.base
    identity = 't09b-calibration-20260928-a2'
    phase = layout.PHASE
    values = dict(PHASE=phase, RUN_IDENTITY=identity, PREFIX=layout.OBJECT_PREFIX,
                  OUT=Path('/private/tmp') / identity,
                  BUNDLE=Path('/private/tmp/q44-inputs-warm-20260928-db'),
                  EVIDENCE_DIRECTORY_NAME=layout.EVIDENCE_DIRECTORY_NAME,
                  EVIDENCE='/q04-evidence/' + layout.EVIDENCE_DIRECTORY_NAME,
                  WORKER_YAML=HERE / 'runtime-a2/WORKER.yaml',
                  OFFLINE_MANIFEST=HERE / 'runtime-a2/RUNNER-MANIFEST.json')
    for module in (runner, ah, base):
        for key, value in values.items():
            setattr(module, key, value)
    runner.topology = ah.pod_topology = base.pod_topology = layout
    runner.OBJECT_OUT = Path('/private/tmp') / (identity + '-object')
    runner.RECORD = HERE / 'runtime-a2'
    runner.object_monitor_bh.RUN_ID = identity
    for key in ('DEPLOYMENT', 'RUN_LABEL', 'NODE', 'NAMESPACE'):
        setattr(base, key, getattr(layout, key))
    runner.FINAL_REQUIRED = base.FINAL_REQUIRED = evidence.base.FINAL_REQUIRED
    runner.IncrementalEvidenceMirror = base.IncrementalEvidenceMirror = evidence.IncrementalEvidenceMirror
    runner.pull_once = base.pull_once = evidence.pull_once

    def preflight_argv():
        return [part.replace('/q04/pod_preflight_ah.py', '/t09b/pod_preflight.py')
                for part in runner._ah_preflight_argv()]

    def workload_argv():
        return [part.replace('/q04/pod_workload_ah.py', '/t09b/pod_workload.py')
                for part in runner._ah_workload_argv()]

    runner.preflight_argv = base.preflight_argv = preflight_argv
    runner.workload_argv = base.workload_argv = workload_argv
    runner.adapted_window = runner.adapt_failure_export_window()
    def admission_pending(*args, **kwargs):
        raise RuntimeError('T09b outer controller and offline admission are not integrated')

    # Do not expose inherited DH launch commands as if they admitted this run.
    runner.offline_check = base.offline_check = admission_pending
    runner.exact_command = ah.exact_command = base.exact_command = admission_pending
    return runner
