"""T09b baseline supervisor using the retained Q04 deadlines and cleanup engine."""
import inspect
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'q04'))
import pod_workload_p as base

PHASE = 't09b-calibration-a3'
RUN_ID = 't09b-calibration-20260928-a3'
MANIFEST = 'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json'


def build_measurement_argv(args, run_id, authorization_sha256):
    return [args.python, str(args.workspace / 'tests/pdf_processing/t09b/baseline_window.py'),
            '--bundle', str(args.bundle), '--state', str(args.state),
            '--capacity', str(args.capacity), '--name', PHASE,
            '--expected-run-id', run_id, '--expected-prefix', args.prefix,
            '--integration-manifest', str(args.workspace / MANIFEST),
            '--authorization-scope-sha256', authorization_sha256,
            '--attribution-interval-seconds', '0.25', '--attribution-gap-seconds', '1',
            '--capacity-approved']


def cleanup_markers(state):
    roots = sorted(root for root in (state / PHASE).glob('worker-*') if root.is_dir())
    missing = [root.name for root in roots if not (root / 'stopped.json').is_file()]
    stopped = [json.loads((root / 'stopped.json').read_text())
               for root in roots if root.name not in missing]
    complete = bool(roots) and not missing and all(
        row.get('parser_absent') and row.get('scratch_absent') for row in stopped)
    return dict(worker_absent=complete, owned_children_absent=complete,
                scratch_absent=complete, worker_generations=len(roots),
                missing_stopped_markers=missing, stopped=stopped)


base.PHASE = PHASE
base.RUN_ID = RUN_ID
base.WORKFLOW_QUEUE = PHASE + '-workflows'
base.ACTIVITY_QUEUE = PHASE + '-08'
base.EVIDENCE_ROOT = Path('/q04-evidence') / RUN_ID
base.build_measurement_argv = build_measurement_argv
base.cleanup_markers = cleanup_markers
# Preserve the historical runner. Its single embedded manifest path is the only
# run-body difference; fail if that seam changes instead of silently adapting it.
source = inspect.getsource(base.run)
old = 'tests/pdf_processing/q04/pod-topology-v15/RUNTIME-INTEGRATION-MANIFEST.json'
if source.count(old) != 1:
    raise RuntimeError('historical supervisor manifest seam changed')
exec(compile(source.replace(old, MANIFEST), __file__, 'exec'), vars(base))

if __name__ == '__main__':
    raise SystemExit(base.main())
