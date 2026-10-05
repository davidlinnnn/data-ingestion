"""Adapt the retained Q04 drain trial to a matched 10-page durable boundary."""
import inspect
import math
from pathlib import Path
import sys
import textwrap

sys.path.append(str(Path(__file__).resolve().parent.parent / 'q04'))
import q04_runtime
from consumer import require
from runtime_policy import Run as PolicyRun, check_sample


def ready_to_drain(progress, row):
    groups = [step for step in progress['steps'] if step['stage'] == 'group']
    current = row.get('parser', {})
    last_request = groups[-1].get('parser', {}).get('request_id') if groups else None
    return (progress['registered_pages'] == 10 and bool(last_request)
            and current.get('ready') and bool(current.get('request_id'))
            and current['request_id'] != last_request)


def drain_checks(attempts, retained, result, group_pages):
    require(group_pages in (5, 10), 'unreviewed recovery grouping')
    groups = [step['operation'] for step in result['steps'] if step['stage'] == 'group']
    require(result['pages'] == 51 and len(groups) == math.ceil(51 / group_pages),
            'recovery group coverage')
    require(retained == groups[:10 // group_pages], 'durable groups lost or changed')
    expected = {(start, min(start + group_pages - 1, 51)): (2 if start == 11 else 1)
                for start in range(1, 52, group_pages)}
    require(len(attempts) == len(expected)
            and {tuple(row['range']): row['attempt'] for row in attempts} == expected,
            'recovery retried wrong group or attempt')
    return {'retained': retained, 'durable_pages': 10,
            'retried_range': [11, 10 + group_pages], 'attempt': 2}


def mode_checks(mode, result, accepted, previous=None):
    require(mode == 'drain' and previous is None, 'recovery-only trial required')
    groups = [step for step in result['steps'] if step['stage'] == 'group']
    assembly = [step for step in result['steps'] if step['stage'] == 'assembly']
    require(len(assembly) == 1 and all(step['reused'] is False for step in groups + assembly),
            'unexpected recovery parse work')
    ocr = [step for step in result['steps'] if step['stage'] == 'component_ocr']
    require(len(ocr) == result['selected_components'] == result['registered_components']
            and all(step['reused'] is False for step in ocr), 'required recovery OCR coverage')


class Run(PolicyRun):
    pass


# Keep historical Q04 execution and its 5-page proof unchanged. Reuse its complete
# cancellation, history and cleanup path with only these reviewed recovery seams.
source = textwrap.dedent(inspect.getsource(q04_runtime.Run.trial))
changes = (
    ("progress['registered_pages'] == 5", 'ready_to_drain(progress, row)'),
    ("completed[0].get('parser', {})", "completed[-1].get('parser', {})"),
    (" and observed['psi_full_avg10'] <= self.config['window']['max_full_psi']", ''),
    ('drain_checks(attempts, retained, result)',
     "drain_checks(attempts, retained, result, profile['group_pages'])"),
)
for old, new in changes:
    if source.count(old) != 1:
        raise RuntimeError('retained recovery trial seam changed: ' + old)
    source = source.replace(old, new)
namespace = dict(q04_runtime.Run.trial.__globals__, ready_to_drain=ready_to_drain,
                 check_sample=check_sample, mode_checks=mode_checks,
                 drain_checks=drain_checks)
exec(compile(source, __file__, 'exec'), namespace)
Run.trial = namespace['trial']
