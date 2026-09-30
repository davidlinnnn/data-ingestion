"""Full output/resource/traffic gates for three serial process-cold workers."""
import inspect
import qualify_baseline as base
from storage_cost import summarize_ledgers

source = inspect.getsource(base.qualify)
changes = (("enumerate(('06', '07', '08', 'native', '06'))", "enumerate(('07', '08', 'native'))"),
           ("storage = summarize(state / 'worker-1/storage.jsonl')",
            "storage = summarize_ledgers([state / f'worker-{i}/storage.jsonl' for i in (1,2,3)])"))
for old,new in changes:
    if source.count(old) != 1: raise RuntimeError('process-cold qualification seam changed')
    source = source.replace(old,new)
namespace = dict(vars(base), summarize_ledgers=summarize_ledgers)
exec(compile(source,__file__,'exec'),namespace)


def qualify(runtime,objects,controller):
    phase=base.load(runtime/'evidence/state/config.json')['workflow_queue'].removesuffix('-workflows')
    for i in (1,2,3):
        stopped=base.load(runtime/'evidence/state'/phase/f'worker-{i}/stopped.json')
        assert stopped['parser_absent'] and stopped['scratch_absent']
    return namespace['qualify'](runtime,objects,controller,phase=phase,
        expected_groups=17,expected_recycles=0,expected_generations=3,expected_recycle_at=None)
