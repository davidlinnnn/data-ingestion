"""Bind the retained guarded runner to T09b paths without starting a runtime.

Call in a dedicated interpreter: historical engines use module globals. The outer
controller must still supply reviewed offline admission, trace ownership and
post-run reconciliation before invoking the returned engine.
"""
from pathlib import Path
import importlib.util
import json
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'q04'))
sys.path.insert(0, str(HERE))


def configure(*, topology_name='topology', evidence_name='pod_remote_evidence',
              identity='t09b-calibration-20260929-a6',
              bundle=Path('/private/tmp/q44-inputs-warm-20260928-db'),
              record_name='runtime-a6', preflight_name='pod_preflight.py',
              workload_name='pod_workload.py'):
    # Seed topology before the guarded engine defines its keyword defaults.
    # Rebinding module globals afterward does not update Python default values.
    modules = []
    for name in (topology_name, evidence_name):
        spec = importlib.util.spec_from_file_location('t09b_' + name, HERE / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules.append(module)
        if name == topology_name:
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
    phase = layout.PHASE
    values = dict(PHASE=phase, RUN_IDENTITY=identity, PREFIX=layout.OBJECT_PREFIX,
                  OUT=Path('/private/tmp') / identity,
                  BUNDLE=bundle,
                  EVIDENCE_DIRECTORY_NAME=layout.EVIDENCE_DIRECTORY_NAME,
                  EVIDENCE='/q04-evidence/' + layout.EVIDENCE_DIRECTORY_NAME,
                  WORKER_YAML=HERE / record_name / 'WORKER.yaml',
                  OFFLINE_MANIFEST=HERE / record_name / 'RUNNER-MANIFEST.json')
    for module in (runner, ah, base):
        for key, value in values.items():
            setattr(module, key, value)
    runner.topology = ah.pod_topology = base.pod_topology = layout
    runner.OBJECT_OUT = Path('/private/tmp') / (identity + '-object')
    runner.RECORD = HERE / record_name
    runner.object_monitor_bh.RUN_ID = identity
    for key in ('DEPLOYMENT', 'RUN_LABEL', 'NODE', 'NAMESPACE'):
        setattr(base, key, getattr(layout, key))
    runner.FINAL_REQUIRED = base.FINAL_REQUIRED = evidence.base.FINAL_REQUIRED
    runner.IncrementalEvidenceMirror = base.IncrementalEvidenceMirror = evidence.IncrementalEvidenceMirror
    runner.pull_once = base.pull_once = evidence.pull_once

    def startup_identity(channel, evidence_root=values['EVIDENCE']):
        return json.loads(channel.run(
            "from pathlib import Path;import json;"
            "p=Path(" + repr(evidence_root) + ");"
            "s=p/'supervisor-ownership.json';w=p/'ownership.json';"
            "s=json.loads(s.read_text()) if s.exists() else {};"
            "w=json.loads(w.read_text()) if w.exists() else {};"
            "print(json.dumps({'pid':s.get('pid'),'start_ticks':s.get('start_ticks'),"
            "'config_sha256':w.get('config_sha256')}))"
        ))

    def adapt_startup_guard():
        declarations = 'supervisor_identity_published = False'
        sample = '            verify_runtime_sample(row, baseline_oom)'
        sample_new = (
            '            try:\n'
            '                owner = startup_identity(sample_channel)\n'
            '                supervisor_start_confirmed |= all(\n'
            '                    owner.get(key) is not None for key in ("pid", "start_ticks")\n'
            '                )\n'
            '            except subprocess.CalledProcessError:\n'
            '                pass\n'
            '            if supervisor_start_confirmed and mirror is None:\n'
            '                base_runtime_guard(row, baseline_oom)\n'
            '            else:\n'
            '    ' + sample
        )
        stop = (
            '        if workload is not None and workload.poll() is None:\n'
            '            if pod_identity is not None and supervisor_identity_published:'
        )
        stop_new = (
            '        if (pod_identity is not None and sample_channel is not None\n'
            '                and not supervisor_start_confirmed):\n'
            '            try:\n'
            '                owner = startup_identity(sample_channel)\n'
            '                supervisor_start_confirmed = all(\n'
            '                    owner.get(key) is not None for key in ("pid", "start_ticks")\n'
            '                )\n'
            '            except subprocess.CalledProcessError as startup_error:\n'
            '                cleanup["startup_identity_error"] = repr(startup_error)\n'
            '        if workload is not None and workload.poll() is None:\n'
            '            if pod_identity is not None and supervisor_start_confirmed:'
        )
        failure_gate = (
            '        if (\n'
            '            pod_identity is not None\n'
            '            and not evidence_captured\n'
            '            and supervisor_identity_published\n'
            '        ):'
        )
        failure_gate_new = (
            '        if (\n'
            '            pod_identity is not None\n'
            '            and not evidence_captured\n'
            '            and supervisor_start_confirmed\n'
            '        ):'
        )
        classification = 'supervisor_identity_published=supervisor_identity_published'
        classification_new = 'supervisor_identity_published=supervisor_start_confirmed'
        contracts = (
            (declarations, declarations + '\n    supervisor_start_confirmed = False'),
            (sample, sample_new),
            (stop, stop_new),
            (failure_gate, failure_gate_new),
            (classification, classification_new),
        )
        inspector = runner.inspect

        def transformed_getsource(obj):
            source = inspector.getsource(obj)
            if any(source.count(old) != 1 for old, _ in contracts):
                raise RuntimeError('startup guard engine contract changed')
            for old, new in contracts:
                source = source.replace(old, new)
            return source

        runner.inspect = SimpleNamespace(getsource=transformed_getsource)
        try:
            adapted = runner.adapt_failure_export_window()
        finally:
            runner.inspect = inspector
        adapted.__globals__.update(
            startup_identity=startup_identity,
            base_runtime_guard=base.verify_runtime_sample,
        )
        return adapted

    def preflight_argv():
        return [part.replace('/q04/pod_preflight_ah.py', '/t09b/' + preflight_name)
                for part in runner._ah_preflight_argv()]

    def workload_argv():
        return [part.replace('/q04/pod_workload_ah.py', '/t09b/' + workload_name)
                for part in runner._ah_workload_argv()]

    runner.preflight_argv = base.preflight_argv = preflight_argv
    runner.workload_argv = base.workload_argv = workload_argv
    runner.adapted_window = adapt_startup_guard()
    def admission_pending(*args, **kwargs):
        raise RuntimeError('T09b outer controller and offline admission are not integrated')

    # Do not expose inherited DH launch commands as if they admitted this run.
    runner.offline_check = base.offline_check = admission_pending
    runner.exact_command = ah.exact_command = base.exact_command = admission_pending
    return runner
