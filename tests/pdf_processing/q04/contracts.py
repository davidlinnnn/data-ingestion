"""Executable acceptance predicates used by runtime and local negative regressions."""
import math
from consumer import require


def mode_checks(mode, result, accepted, previous=None):
    groups = [s for s in result['steps'] if s['stage'] == 'group']
    assembly = [s for s in result['steps'] if s['stage'] == 'assembly']
    require(len(groups) == math.ceil(result['pages']/5) and len(assembly) == 1, 'missing parse work')
    upstream = groups+assembly
    if mode in ('fresh', 'warm', 'invalidation'):
        require(all(s['reused'] is False for s in upstream), 'fresh/method-changed work reused')
    elif mode in ('restored', 'replay', 'evidence'):
        require(all(s['reused'] is True for s in upstream), 'checked restoration missing')
    elif mode != 'drain':
        raise ValueError('unsupported mode')
    if previous is not None:
        old = previous['result']
        old_ops = [s['operation'] for s in old['steps'] if s['stage'] in ('group', 'assembly')]
        ops = [s['operation'] for s in upstream]
        if mode in ('restored', 'replay', 'evidence'):
            require(ops == old_ops, 'reuse operation identities changed')
        if mode == 'invalidation':
            require(not set(ops).intersection(old_ops), 'method change accepted old work')
        if mode != 'invalidation':
            require(accepted['document_sha256'] == previous['accepted']['document_sha256'], 'new fresh/restored output differs')
        if mode == 'replay':
            require(result['processing_result'] == old['processing_result'] and all(s['reused'] is True for s in result['steps']), 'exact replay repeated work')
        else:
            require(result['processing_result'] != old['processing_result'], 'new request reused complete identity')
            require(accepted['final']['content_evidence'] != previous['accepted']['final']['content_evidence'], 'new evidence identity missing')
    ocr = [s for s in result['steps'] if s['stage'] == 'component_ocr']
    require(len(ocr) == result['selected_components'] == result['registered_components'], 'required OCR work coverage')
    if mode != 'replay':
        require(all(s['reused'] is False for s in ocr), 'new request OCR was skipped')


def warm_checks(results):
    require([r['sid'] for r in results] == ['06', '07', '08', 'native', '06'], 'warm fixture sequence')
    groups = [s for r in results for s in r['result']['steps'] if s['stage'] == 'group']
    require(len(groups) == 29, 'warm group coverage')
    parser = [g['parser'] for g in groups]
    require(len({p['pid'] for p in parser[:20]}) == 1, 'early parser replacement')
    require(len({p['pid'] for p in parser[20:]}) == 1 and parser[19]['pid'] != parser[20]['pid'], 'missing planned recycle')
    require([p['restarts'] for p in parser] == [1]*20+[2]*9, 'unexpected parser restart')
    require([p['recycles'] for p in parser] == [0]*19+[1]*10, 'recycle count mismatch')
    return {'groups': 29, 'pids': [parser[0]['pid'], parser[20]['pid']], 'recycles': 1}


def drain_checks(attempts, retained, result):
    groups = [s['operation'] for s in result['steps'] if s['stage'] == 'group']
    require(len(groups) == 11 and retained and all(x in groups for x in retained), 'lost registered groups')
    expected = {(start, min(start+4, 51)): (2 if start == 6 else 1) for start in range(1, 52, 5)}
    require(len(attempts) == 11, 'unexpected group attempt history coverage')
    require({tuple(a['range']): a['attempt'] for a in attempts} == expected, 'drain retried wrong group or attempt')
    return {'retained': retained, 'retried_range': [6, 10], 'attempt': 2}


def validate_window(window, now):
    require(all(isinstance(window.get(k), str) and window[k] for k in ('approval_reference', 'owner')), 'explicit current capacity approval required')
    require(all(type(window[k]) in (int, float) and math.isfinite(window[k]) for k in ('starts_at', 'ends_at')), 'finite capacity window required')
    require(window['starts_at'] <= now < window['ends_at'], 'outside current capacity window')
    for name in ('admission_seconds', 'admission_available_bytes', 'min_available_bytes', 'max_cgroup_bytes', 'max_sample_gap_seconds', 'max_replacement_seconds', 'cleanup_seconds'):
        require(type(window[name]) in (int, float) and math.isfinite(window[name]) and window[name] > 0, 'invalid guard '+name)
    require(type(window['max_full_psi']) in (int, float) and math.isfinite(window['max_full_psi']) and window['max_full_psi'] >= 0, 'invalid PSI guard')
    require(window['cleanup_seconds'] >= 120, 'reserve at least 120 seconds for cleanup')
    require(window['admission_available_bytes'] >= window['min_available_bytes'], 'invalid admission threshold')
