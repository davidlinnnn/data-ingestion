"""Necessary local launch, projection, runtime-contract and cleanup checks."""
import argparse
import json
from pathlib import Path
import shlex
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tests/pdf_processing/q04'))
from sentinel import run_warm_pod_cgroup_dh as run
import pod_workload_dh as workload
import pod_preflight_dh as preflight
from candidate.warm_v3_reference_db import verify_v3_bundle

assert run.offline_check()['status'] == 'PASS_OFFLINE_ONLY'
assert run.OUT.name == run.RUN_IDENTITY
assert run.OBJECT_OUT.name == 't09a-bounds-object-20260928-dh'
assert not run.OUT.exists() and not run.OBJECT_OUT.exists()
assert not Path('/private/tmp/t09a-normal-topology-20260928-dh').exists()
assert run.base.parser().parse_args(shlex.split(run.exact_command())[2:]).execute
args = workload.base.parser().parse_args(run.workload_argv()[2:])
assert args.run_id == run.RUN_IDENTITY and args.prefix == run.PREFIX
assert args.workflow_queue == run.topology.WORKFLOW_QUEUE
assert args.activity_queue == run.topology.ACTIVITY_QUEUE
assert args.workload_seconds == 825
assert run.OBJECT_PSI_POLICY == {
    'mode': 'approved_sustained_pressure_qualification',
    'stop_full_avg10_above': 0,
    'cumulative_full_total_stop': False,
}
review = preflight.verify_workload_imports_ah(
    workspace=ROOT, bundle=run.BUNDLE, prefix=run.PREFIX)
assert review['reviewed_contract']['group_requests'] == 29
verify_v3_bundle(run.BUNDLE)
assert 'sitecustomize' not in ''.join(run.topology.base.HARNESS_FILES)
assert run.topology.source_manifest()['producer'] == json.loads(
    (ROOT / 'tests/pdf_processing/t09a_bounds/normal-topology-db/SOURCE-MANIFEST.json').read_text())['producer']
controller = (Path(__file__).with_name('controller.py')).read_text()
compile(controller, str(Path(__file__).with_name('controller.py')), 'exec')
assert controller.count('\n    start_trace()') == 1
assert controller.count('\n        stop_trace()') == 1
assert 'q44-dh-object-stall' in controller and 'psi_call_trace.py' in controller
assert 'terminal_proofs(' in controller
with tempfile.TemporaryDirectory() as temp:
    state = Path(temp); root = state / workload.PHASE
    root.mkdir(); (root / 'worker-1.log').write_text('worker log')
    worker = root / 'worker-1'; worker.mkdir()
    assert not workload.cleanup_markers(state)['worker_absent']
    (worker / 'stopped.json').write_text(json.dumps({'parser_absent': True, 'scratch_absent': True}))
    assert workload.cleanup_markers(state)['worker_absent']
print('PASS: full launch argv, unchanged production projection/oracle, runtime contract, cleanup markers')
