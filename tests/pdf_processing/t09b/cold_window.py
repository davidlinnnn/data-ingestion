"""Three serial first-request measurements with the retained warm execution engine."""
import inspect
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import baseline_window
from runtime_policy import Run

base = baseline_window.warm_pod_window_db.base
SEQUENCE = ('07', '08', 'native')
SCOPE = {'sequence': list(SEQUENCE), 'group_requests': 17, 'max_requests': 20,
         'expected_parser_generations': 3, 'automatic_retry': False,
         'measurement': 'one fresh worker per fixture; process-cold, host caches uncontrolled'}


class ColdRun(base.AttributedCandidateRun, Run):
    """Preserve attribution and owned cancellation with the approved runtime policy."""


def validate_scope(args):
    manifest = json.loads(args.integration_manifest.read_text())
    base.require(manifest['authorization_scope'] == SCOPE
                 and manifest['authorization_scope_sha256'] == args.authorization_scope_sha256
                 == base.sha(base.canonical(SCOPE).encode()), 'process-cold scope changed')
    base.require(manifest['identity'] == {'phase': args.name, 'run_id': args.expected_run_id,
                                        'prefix': args.expected_prefix}, 'process-cold identity changed')
    return manifest


async def cold_trials(run, host, collector):
    results = []
    for index, sid in enumerate(SEQUENCE):
        if index:
            await collector.process_transition('cold_previous_worker_shutdown', host.stop)
            await collector.process_transition('cold_next_worker_start', host.start)
        results.append(await run.trial(sid, 'warm', f'warm-{index}-{sid}', None))
    return results


def cold_checks(results):
    base.require([row['sid'] for row in results] == list(SEQUENCE), 'process-cold sequence changed')
    pids = []
    for row in results:
        steps = [step for step in row['result']['steps'] if step['stage'] == 'group']
        expected = (row['result']['pages'] + 4) // 5
        base.require(len(steps) == expected and all(not step['reused'] for step in steps),
                     'process-cold fresh group coverage changed')
        identities = {step['parser']['pid'] for step in steps}
        base.require(len(identities) == 1
                     and all(step['parser']['restarts'] == 1 and step['parser']['recycles'] == 0
                             for step in steps), 'process-cold parser was recycled or replaced')
        pids.append(next(iter(identities)))
    base.require(len(set(pids)) == 3, 'process-cold fixtures shared a parser')
    return {'groups': 17, 'pids': pids, 'recycles': 0}


original_lifecycle = base.validate_process_evidence

def validate_process_evidence(summary, proof):
    result = original_lifecycle(summary, proof)
    result['exits'] = len(proof['pids'])
    return result


source = inspect.getsource(base.run_window)
old = """                for index, sid in enumerate(SEQUENCE):
                    record = await warm_run.trial(
                        sid, "warm", f"warm-{index}-{sid}", first.get(sid)
                    )
                    results.append(record)
                    first.setdefault(sid, record)"""
changes = ((old, """                results = await cold_trials(warm_run, host, collector)
                first = {row['sid']: row for row in results}"""),
           ('"group_requests": 29', '"group_requests": 17'),
           ('"request_recycle": 20', '"request_recycle": None'),
           ('"parser_generations": 2', '"parser_generations": 3'),
           ('Wiki06-YOLO07-AIMA08-native-Wiki06', 'process-cold-YOLO07-AIMA08-native'))
for (old, new), count in zip(changes, (1, 2, 1, 1, 1)):
    if source.count(old) != count:
        raise RuntimeError('retained process-cold execution seam changed')
    source = source.replace(old, new)
namespace = dict(vars(base), SEQUENCE=SEQUENCE, cold_trials=cold_trials,
                 warm_checks=cold_checks, validate_scope=validate_scope,
                 AttributedCandidateRun=ColdRun, validate_process_evidence=validate_process_evidence)
exec(compile(source, __file__, 'exec'), namespace)
base.run_window = namespace['run_window']

if __name__ == '__main__':
    raise SystemExit(base.main())
