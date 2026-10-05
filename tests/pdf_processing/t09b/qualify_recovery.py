"""Retain normal resource/traffic gates for a two-worker recovery result."""
import inspect
import json

import qualify_baseline as base
from storage_cost import summarize_ledgers


def recovery_business(runtime, phase):
    state = runtime / 'evidence/state' / phase
    target = state / 'drain-native'
    base.verify_output(target, base.approved_outputs()['native'])
    accepted = base.load(target / 'accepted.json')
    outcome = accepted['result']
    assert accepted['verified'] and outcome['status'] == 'complete'
    assert outcome['processing_complete'] and outcome['registered_pages'] == 51
    assert outcome['error'] is None
    events = base.load(target / 'history.json')['events']
    assert events[-1]['eventType'] == 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED'
    payload = events[-1]['workflowExecutionCompletedEventAttributes']['result']['payloads'][0]
    assert json.loads(base.base64.b64decode(payload['data'])) == outcome
    proof = base.load(target / 'drain-proof.json')
    size = accepted['profile']['group_pages']
    assert proof['durable_pages'] == 10 and proof['retried_range'] == [11, 10 + size]
    assert proof['attempt'] == 2 and len(proof['retained']) == 10 // size
    for generation in (1, 2):
        stopped = base.load(state / f'worker-{generation}/stopped.json')
        assert stopped['parser_absent'] and stopped['scratch_absent']
    return ([{'fixture': 'drain-native', 'terminal_time': events[-1]['eventTime'],
              'business': {key: outcome[key] for key in (
                  'status', 'processing_complete', 'canonical_accepted',
                  'registered_pages', 'registered_components', 'error')}}],
            [{'fixture': 'drain-native', 'full_document_equal': True,
              'full_checks_equal': True, 'processing_complete': True}])


source = inspect.getsource(base.qualify)
start = source.index('    expected = approved_outputs()')
end = source.index('    measurement = runtime', start)
source = source[:start] + '    business, comparisons = recovery_business(runtime, phase)\n' + source[end:]
for old in (
    "    assert contract['group_requests'] == expected_groups\n",
    "    assert contract['request_recycle'] == expected_recycle_at\n",
    "    assert contract['parser_generations'] == expected_generations\n",
    "    assert contract['process_lifecycle']['status'] == 'PASS'\n",
):
    if source.count(old) != 1:
        raise RuntimeError('retained recovery qualification seam changed')
    source = source.replace(old, '')
old = "storage = summarize(state / 'worker-1/storage.jsonl')"
if source.count(old) != 1:
    raise RuntimeError('retained storage qualification seam changed')
source = source.replace(old, "storage = summarize_ledgers([state / f'worker-{i}/storage.jsonl' for i in (1, 2)])")
namespace = dict(vars(base), recovery_business=recovery_business, summarize_ledgers=summarize_ledgers)
exec(compile(source, __file__, 'exec'), namespace)


def qualify(runtime, objects, controller):
    phase = base.load(runtime / 'evidence/state/config.json')['workflow_queue'].removesuffix('-workflows')
    size = base.load(runtime / 'evidence/state' / phase / 'drain-native/accepted.json')['profile']['group_pages']
    return namespace['qualify'](runtime, objects, controller, phase=phase,
        expected_groups=(51 + size - 1) // size, expected_recycles=0,
        expected_generations=2, expected_recycle_at=None)
