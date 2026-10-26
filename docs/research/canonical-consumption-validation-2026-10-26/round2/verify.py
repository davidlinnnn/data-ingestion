#!/usr/bin/env python3
"""Recompute REPORT.md, validate coverage/hashes and replay required witnesses."""
import sys
sys.dont_write_bytecode = True
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import phase2
from model import ROOT, INVARIANTS, workload
from scenarios import EXPECTED, check_expected
from smoke import ROUND1_HASH

DATA = phase2.DATA
LATE = ('late_landings', 'late_S2', 'late_S3', 'late_transactions',
        'already_invalid_landings', 'S2_at_write', 'S3_at_write')


def stats(values):
    return None if not values else dict(mean=sum(values)/len(values),
        p95=sorted(values)[math.ceil(.95*len(values))-1], max=max(values))


def fmt_stats(values):
    s = stats(values)
    return '—' if s is None else '%.3f / %d / %d' % (s['mean'], s['p95'], s['max'])


def table(headers, rows):
    return ['| ' + ' | '.join(headers) + ' |',
            '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + [
                '| ' + ' | '.join(map(str, row)) + ' |' for row in rows]


def seed_list(values):
    return ', '.join(map(str, sorted(values))) or '—'


def metric(row, name):
    return row['model']['metrics'].get(name, 0)


def has(row, invariant):
    if invariant == 'S1_flipback':
        return metric(row, 'fact_based_flip_backs') > 0
    return invariant in row['evaluation']['violations']


def expected_label(name, variant, expected):
    if name == 'SC24' and variant == 'N-viewexp':
        return 'FAIL S1_flipback or L2'
    text = 'FAIL ' + ', '.join(expected) if expected else 'PASS'
    if name == 'SC18':
        text += '; already-invalid ' + ('≥1' if variant == 'V4-Rb' else '=0')
    if name == 'NC2' and variant == 'N2':
        text += '; masked by V4 fence'
    if name == 'NC2' and variant == 'N-fence':
        text += '; masked by tombstone'
    return text


def load():
    metadata = json.loads((DATA/'metadata.json').read_text())
    assert metadata['python'] == sys.version, 'Replay with the recorded Python version'
    assert metadata['end'], 'Batch runner has not completed'
    manifest = json.loads((ROOT/'phase1d-manifest.json').read_text())
    assert hashlib.sha256((ROOT.parent/'part_b.py').read_bytes()).hexdigest() == ROUND1_HASH
    assert metadata['phase1d_hashes'] == manifest
    for name, sha in manifest.items():
        assert hashlib.sha256((ROOT/('phase1d-'+name)).read_bytes()).hexdigest() == sha
    for name in ('model.py', 'scenarios.py', 'MAPPING.md', 'test_model.py', 'smoke.py'):
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == manifest[name]
    expected_groups = [g for groups in phase2.PLAN.values() for g in groups]
    groups = {}
    hashes = {}
    for variant, w in expected_groups:
        path = DATA/'raw'/(variant+'-'+w+'.jsonl')
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        by_seed = {r['model']['seed']: r for r in rows}
        assert len(rows) == len(by_seed) == 1000, path
        assert set(by_seed) == set(range(1000)), path
        for seed, row in by_seed.items():
            r = row['model']
            assert (r['variant'], r['workload']) == (variant, w)
            assert row['evaluation'] == phase2.acceptance(r)
            assert set(r['violations']) <= set(INVARIANTS), (variant,w,seed,r['violations'])
            sha = hashlib.sha256(json.dumps(workload(seed, w)).encode()).hexdigest()
            assert r['workload_hash'] == sha, (variant, w, seed)
            assert hashes.setdefault((w, seed), sha) == sha
            assert metric(row, 'flip_backs') == sum(metric(row, k) for k in
                ('fact_based_flip_backs', 'restore_gate_flips', 'flip_backs_liveness_gate'))
            if w == 'W-drift':
                d = row['drift']
                assert d is not None and metric(row, 'silent_rewinds') == 1
                assert not metric(row, 'snapshots_restore') and not metric(row, 'restore_gate_flips')
                if d['repair_latency'] is not None:
                    assert d['repair_latency'] == d['repair_completion_time'] - d['time'] >= 0
            else:
                assert row['drift'] is None
        groups[(variant, w)] = by_seed
    assert len(groups) == len(expected_groups)
    assert sum(s['completed'] for name,s in metadata['sets'].items()
               if name != 'deterministic') == sum(len(rows) for rows in groups.values())
    assert all(s['completed'] == s['expected'] for s in metadata['sets'].values())
    scripts = [json.loads(line) for line in (DATA/'deterministic.jsonl').read_text().splitlines()]
    assert len(scripts) == sum(map(len, EXPECTED.values()))
    assert {(r['scenario'], r['variant']) for r in scripts} == {
        (n,v) for n,matrix in EXPECTED.items() for v in matrix}
    for row in scripts:
        n,v = row['scenario'],row['variant']
        assert row['expected'] == sorted(EXPECTED[n][v])
        assert row['matches_expected'] == check_expected(n,v,row['model'])
    return metadata, groups, scripts, hashes


class ForensicSimulation(phase2.ObservedSimulation):
    """Capture the state at a first violation without altering any transition."""
    def __init__(self, *args, **kwargs):
        self.contexts = {}
        self.event = None
        super().__init__(*args, **kwargs)

    def step(self):
        self.event = [self.q[0][2], deepcopy(self.q[0][3]) if self.q[0][2] == 'action' else None]
        return super().step()

    def fail(self, invariant, detail):
        first = invariant not in self.witnesses
        super().fail(invariant, detail)
        if first:
            uid = detail.get('uid')
            self.contexts[invariant] = dict(time=self.time, event=deepcopy(self.event),
                document=deepcopy(self.docs.get(uid)),
                stores={b['id']: repr({k:v for k,v in b['store'].items() if k[0] == uid})
                        for b in self.builds.values() if self.live(b['id'])},
                stored_entries=[dict(build=b['id'],uid=k[0],resource=k[1],revision=rev,
                                     fact_version=b['versions'][k]) for b in self.builds.values()
                                if self.live(b['id']) for k,rev in b['store'].items() if k[0]==uid],
                facts=[dict(build=bid, uid=u, resource=r, fact=deepcopy(f))
                       for (bid,u,r),f in self.facts.items() if u == uid and self.live(bid)])


def excerpt(trace, size, invariant=None, landing=False):
    marker = ('VIOLATION ' + invariant + ' ') if invariant else None
    candidates = [i for i,line in enumerate(trace) if
                  (marker and marker in line) or (landing and 'LANDING' in line and 'valid_at_check=False' in line)]
    center = candidates[0] if candidates else len(trace)-1
    start = min(max(0, center-size+5), max(0,len(trace)-size))
    result = trace[start:start+size]
    assert len(result) == size
    return result


def requests(groups):
    cases = []
    for variant in ('V1','V2','V3','V4','N-fence'):
        rows = groups[(variant,'W-drift')]
        for seed,row in rows.items():
            if row['drift']['status'] == 'recovered_without_repair_completion':
                cases.append(dict(role='stream_recovery',variant=variant,workload='W-drift',
                                  seed=seed,invariant='L2',lines=20))
    measured = [r for r in groups[('V4','W-drift')].values()
                if r['drift']['repair_latency'] is not None]
    maximum = max(r['drift']['repair_latency'] for r in measured)
    seed = min(r['model']['seed'] for r in measured if r['drift']['repair_latency']==maximum)
    cases.append(dict(role='latency_max',variant='V4',workload='W-drift',seed=seed,
                      invariant='L2',lines=30))
    for w in phase2.WORKLOADS:
        rows = groups[('V4',w)]
        for invariant in INVARIANTS + ['UNKNOWN']:
            seeds = [s for s,r in rows.items() if
                     (r['model']['unknown'] is not None if invariant == 'UNKNOWN' else
                      invariant in r['evaluation']['violations'])]
            if seeds:
                cases.append(dict(role='V4_failure', variant='V4', workload=w,
                                  seed=min(seeds), invariant=invariant, lines=30))
    targets = {'V4-Ra': ('L1','L5'), 'V4-Rb': ('already_invalid_landings',),
               'N2': ('S1_flipback','L2'), 'N12': ('S1_flipback','L2'),
               'N-viewexp': ('S1_flipback','L2')}
    for v,properties in targets.items():
        unique = detection(groups,v,properties)['unique']
        if unique:
            s = min(unique)
            inv = next(i for i in properties if detects(groups[(v,'W-real')][s],(i,)))
            cases.append(dict(role='control',variant=v,workload='W-real',seed=s,
                              invariant=inv,lines=20))
    for w in phase2.WORKLOADS:
        for invariant in INVARIANTS:
            if w == 'W-drift' and invariant == 'S1_flipback':
                continue
            unique = [s for s,r in groups[('N-fence',w)].items()
                      if has(r,invariant) and not has(groups[('V4',w)][s],invariant)]
            if unique:
                cases.append(dict(role='fence_candidate',variant='N-fence',workload=w,
                                  seed=min(unique),invariant=invariant,lines=30))
    # The brief requires a trace and explanation for every S1 under silent drift.
    for (v,w),rows in groups.items():
        if w == 'W-drift':
            for seed,row in rows.items():
                if has(row,'S1'):
                    cases.append(dict(role='drift_S1',variant=v,workload=w,seed=seed,
                                      invariant='S1',lines=20))
    return sorted(cases,key=lambda c:(c['role'],c['variant'],c['workload'],c['invariant'],c['seed']))


def detects(row, properties):
    return any(metric(row,i)>0 if i == 'already_invalid_landings' else has(row,i) for i in properties)


def detection(groups, variant, properties):
    raw = {s for s,r in groups[(variant,'W-real')].items() if detects(r,properties)}
    baseline = {s for s,r in groups[('V4','W-real')].items() if detects(r,properties)}
    return dict(raw=raw, shared=raw & baseline, unique=raw-baseline)


def build_evidence(groups, cases):
    phase2.ObservedSimulation = ForensicSimulation
    evidence = []
    cached = {}
    for case in cases:
        key = (case['variant'],case['workload'],case['seed'])
        if key not in cached:
            row,sim = phase2.record(case['seed'],case['variant'],case['workload'],full_trace=True)
            # JSONL canonicalizes tuple-bearing cycle witnesses to JSON arrays.
            assert json.loads(json.dumps(row)) == groups[(case['variant'],case['workload'])][case['seed']], key
            if case['role'] == 'latency_max':
                d = row['drift']
                marker = '%04d replacement %d atomic END %s' % (
                    d['repair_completion_time'],d['repair_id'],d['build'])
                assert any(line.startswith(marker) for line in sim.trace)
            stem = '%s-%s-seed%d' % key
            path = DATA/'traces'/(stem+'.txt')
            path.write_text('\n'.join(sim.trace)+'\n')
            cached[key] = (sim,path)
        sim,path = cached[key]
        out = dict(case,trace=str(path.relative_to(ROOT)),
                   excerpt=excerpt(sim.trace,case['lines'],case['invariant'],
                                   case['invariant']=='already_invalid_landings'),
                   context=sim.contexts.get(case['invariant']))
        evidence.append(out)
    (DATA/'evidence.json').write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
    return evidence


def describe_S1(case, row):
    context = case['context']
    witness = row['model']['witnesses']['S1']
    uid = witness['detail']['uid']
    stores = ', '.join(witness['detail']['stores'])
    timing = ('before the silent rewind' if context['time'] < row['drift']['time'] else
              'at/after the silent rewind')
    facts = ', '.join('%s/%s:%s@v%s' % (f['build'],f['resource'],
                     f['fact'].get('state','included' if f['fact']['included'] else 'removed'),
                     f['fact']['version']) for f in context['facts']) or 'no live fact'
    mechanism = ('V1 has no pending reservation covering its check/write/report interval. '
                 if case['variant']=='V1' else
                 'The retained mark-and-sweep protocol can tombstone an unconfirmed fact '
                 'at a newer watermark while its store entry survives. ')
    if context['time'] >= row['drift']['time'] and context['event'][0] == 'action':
        if context['event'][1][0] == 'silent_rewind':
            mechanism = 'The silent rewind changed mirror facts without changing the store. '
    versions = ', '.join('%s:%s@v%s' % (e['build'],e['resource'],e['fact_version'])
                         for e in context['stored_entries'])
    return (mechanism + 'At tick %d, %s is judged enforced while present in %s, %s. '
            'Atomic event: %s. Stored versions: %s. Live mirror: %s. The enforcement predicate has no '
            'included/pending blocker for this deleted document; the store still holds it.' %
            (context['time'],uid,stores,timing,json.dumps(context['event']),versions,facts))


def render(metadata, groups, scripts, hashes, evidence):
    rows_all = [r for rows in groups.values() for r in rows.values()]
    verdicts = Counter(r['evaluation']['verdict'] for r in rows_all)
    lines = ['# Ticket 55 round 2 — phase 2 report','',
        'Generated and checked by `verify.py` from the phase-2 JSONL and timing metadata. '
        'The phase-1d model, mapping and scenario expectations are unchanged. '
        'The approved W-drift acceptance exception is applied outside the model: '
        'raw fact-based flip-backs remain recorded, but do not fail that workload.','',
        '## What ran','',
        'Batch command: `'+metadata['command']+'`. Report commands: '
        '`prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/verify.py --write` '
        'and the same command without `--write` to check.','',
        'Python: `'+metadata['python'].replace('\n',' ')+'`; platform: `'+metadata['platform']+'`. '
        'Workers: %d. Seeds: %d–%d inclusive for every listed group. Protocol checks: %d.' %
        (metadata['workers'],metadata['seed_start'],metadata['seed_stop'],metadata['protocol_checks']),'',
        'Accepted totals: %d runs; %d PASS, %d FAIL, %d UNKNOWN. '
        'UNKNOWN is never counted as PASS. L1–L5 are checked only at quiescence; '
        'bound-hit repair costs are censored.' % (len(rows_all),verdicts['PASS'],verdicts['FAIL'],verdicts['UNKNOWN']),'']
    times = metadata['sets']
    main_wall = times['main_V4_priority']['wall_seconds'] + times['main_remaining']['wall_seconds']
    lines += table(['Set','Groups','Runs','Wall seconds'],[
        ['Main',len(phase2.PLAN['main']),sum(len(groups[g]) for g in phase2.PLAN['main']),'%.3f'%main_wall],
        *[[label,len(phase2.PLAN[label]),times[label]['completed'],'%.3f'%times[label]['wall_seconds']]
          for label in ('ablations','fence','controls')],
        ['Deterministic','defined scenario rows',len(scripts),'%.3f'%times['deterministic']['wall_seconds']]])
    lines += ['','Main includes the V4 priority pass followed by remaining variants. '
              'Wall times are elapsed set times across parallel workers, not summed worker times. '
              'Raw records are in `phase2/raw/`; deterministic records in `phase2/deterministic.jsonl`; '
              'timing/version data in `phase2/metadata.json`.','',
              'Workload hashes were recomputed from the frozen workload generator and compared '
              'for every variant/seed. The following digests summarize the ordered seed/hash pairs:','']
    lines += table(['Workload','Distinct seeds','SHA-256 of ordered seed/hash pairs'],[
        [w,len([k for k in hashes if k[0]==w]),hashlib.sha256(json.dumps(
            [(s,hashes[(w,s)]) for s in range(1000)]).encode()).hexdigest()] for w in phase2.WORKLOADS])
    lines += ['','Model and validation code hashes (the model/mapping remain frozen):','']
    lines += table(['File','SHA-256'],[[n,metadata['phase1d_hashes'][n]]
                                       for n in ('model.py','scenarios.py','MAPPING.md')] +
                   [['../part_b.py',ROUND1_HASH]] +
                   [[n,hashlib.sha256((ROOT/n).read_bytes()).hexdigest()]
                    for n in ('phase2.py','verify.py')])
    lines += ['','## Main invariants','',
        'Cells count seeds with at least one violation, not atomic-event counts. '
        '**S1_flipback† under W-drift is exposure only**, excluded from FAIL. '
        'Liveness-gate and restore-gate flips are separate metrics. '
        'Zero in a quiescence-only invariant is not a pass for a bound-hit seed.','']
    lines += table(['Variant','Workload',*[i+'†' if i=='S1_flipback' else i for i in INVARIANTS],'UNKNOWN','Quiescent','PASS'],[
        [v,w,*[sum(has(r,i) for r in groups[(v,w)].values()) for i in INVARIANTS],
         sum(r['model']['unknown'] is not None for r in groups[(v,w)].values()),
         sum(r['model']['quiescent'] for r in groups[(v,w)].values()),
         sum(r['evaluation']['verdict']=='PASS' for r in groups[(v,w)].values())]
        for v,w in groups])
    lines += ['','## W-drift exposure and repair latency','',
        'Latency is measured from the silent rewind to a completed repair for the affected Build '
        'whose included-fact map equals its store (the exact L2 predicate for that Build). '
        'Unrelated Builds or later events can still fail invariants; latency is not a PASS verdict. An already-running '
        'repair may qualify. Completion at the same tick has zero latency. A stream report can '
        'restore equality without any repair completing: that seed has an explicit null repair '
        'latency and is listed separately, not counted as unrepaired or assigned a fabricated '
        'completion. Statistics include only measured repair completions. Every seed has its '
        'observation/status in raw JSONL. Unrepaired/bound-hit observations are censored.','']
    drift_rows=[]
    for v in ('V1','V2','V3','V4','N-fence'):
        rs=list(groups[(v,'W-drift')].values());ds=[r['drift'] for r in rs]
        statuses=Counter(d['status'] for d in ds)
        drift_rows.append([v,sum(metric(r,'fact_based_flip_backs')>0 for r in rs),
            sum(metric(r,'fact_based_flip_backs') for r in rs),
            statuses['repair_completed'],fmt_stats([d['repair_latency'] for d in ds if d['repair_latency'] is not None]),
            statuses['recovered_without_repair_completion'],statuses['already_equal'],statuses['unrepaired_or_censored']])
    lines += table(['Variant','Exposed seeds','Fact flips','Repair samples','Latency mean / p95 / max',
                    'Stream-only recovery','Already equal','Unrepaired/censored'],drift_rows)
    lines += ['','Stream-only recovery seeds (with first L2-equality latency):','']
    lines += table(['Variant','Seed','First equality latency'],[
        [v,s,r['drift']['first_equality_time']-r['drift']['time']]
        for v in ('V1','V2','V3','V4','N-fence') for s,r in sorted(groups[(v,'W-drift')].items())
        if r['drift']['status']=='recovered_without_repair_completion'])
    lines += ['','Latency observation replay evidence:','']
    lines += table(['Case','Variant','Seed','Trace'],[
        [e['role'],e['variant'],e['seed'],'[full trace](%s)'%e['trace']]
        for e in evidence if e['role'] in ('stream_recovery','latency_max')])
    lines += ['','## Late landings','',
        'Mean / nearest-rank p95 / max per seed. Source-entry counts, with combined '
        'late landings counted once per initially valid source and page/document transactions '
        'reported separately. Already-invalid landings remain a metric, including the Rb ablation.','']
    lines += table(['Variant','Workload',*LATE],[
        [v,w,*[fmt_stats([metric(r,m) for r in groups[(v,w)].values()]) for m in LATE]]
        for v,w in groups])
    lines += ['','## Repair cost','',
        'Snapshot starts summed over Builds per seed. Transient share uses the existing '
        'next-heartbeat counterfactual, unchanged from phase 1d: only heartbeat-triggered starts '
        'are classified; shares below show both all-start and heartbeat-start denominators. '
        'Suppressing new repairs in the fork can change later RNG consumption.','']
    cost_rows=[]
    for (v,w),rr in groups.items():
        rs=list(rr.values());total=sum(metric(r,'snapshots') for r in rs)
        tr=sum(metric(r,'transient_snapshots') for r in rs);hb=sum(metric(r,'heartbeat_snapshots') for r in rs)
        cost_rows.append([v,w,fmt_stats([metric(r,'snapshots') for r in rs]),
                          '%d/%d (%.3f%%)'%(tr,total,100*tr/max(1,total)),
                          '%d/%d (%.3f%%)'%(tr,hb,100*tr/max(1,hb))])
    lines += table(['Variant','Workload','Snapshots mean / p95 / max','Transient / all starts',
                    'Transient / heartbeat starts'],cost_rows)
    lines += ['','## Fence redundancy','',
        'Each row compares paired workload seeds. S1_flipback under W-drift remains exposure, '
        'not a failure. A paired difference alone is not causal proof: protocol branches '
        'consume scheduler RNG differently. Any N-fence-only failure is a candidate requiring '
        'the trace below to establish that the omitted fence enabled it.','']
    fence_rows=[]
    for w in phase2.WORKLOADS:
        for i in INVARIANTS+['UNKNOWN']:
            a={s for s,r in groups[('V4',w)].items() if
               (r['model']['unknown'] is not None if i=='UNKNOWN' else has(r,i))}
            b={s for s,r in groups[('N-fence',w)].items() if
               (r['model']['unknown'] is not None if i=='UNKNOWN' else has(r,i))}
            fence_rows.append([w,i,len(a),len(b),len(b-a),len(a-b),len(a&b)])
    lines += table(['Workload','Invariant','V4','N-fence','N-fence only','V4 only','Both'],fence_rows)
    candidates=[e for e in evidence if e['role']=='fence_candidate']
    lines += ['','No sampled seed demonstrates that the replacement fence is necessary.'
              if not candidates else 'N-fence-only failure candidates exist; causal evidence follows.','']
    for e in candidates:
        lines += ['### Fence candidate: %s / %s / %s / seed %d'%(e['variant'],e['workload'],e['invariant'],e['seed']),
                  '', '[Full replay trace](%s).'%e['trace'],'','```text',*e['excerpt'],'```','']
    lines += ['','## Ablations and negative controls','',
        'Detection is per seed under W-real. Shared seeds satisfying the same target in V4 '
        'are subtracted from unique detection and explicitly listed. Rb targets already-invalid '
        'landings because S2/S3 are measurements; a failure is not expected from that metric. '
        'N2 can be masked by the retained fence. Random non-detection is distinct from the '
        'targeted deterministic control results. Ra and N2 have no unique random witness '
        'to excerpt. Ra is detected by SC16; N2 remains masked on NC2. The absence of a '
        'random Ra failure does not establish that the rule is optional.','']
    target_map={'V4-Ra':('L1','L5'),'V4-Rb':('already_invalid_landings',),
                'N2':('S1_flipback','L2'),'N12':('S1_flipback','L2'),
                'N-viewexp':('S1_flipback','L2')}
    detection_rows=[]
    for v,props in target_map.items():
        d=detection(groups,v,props)
        detection_rows.append([v,' or '.join(props),len(d['raw']),len(d['shared']),len(d['unique']),
                               min(d['unique']) if d['unique'] else '—',seed_list(d['shared'])])
    lines += table(['Variant','Expected target','Detected','Shared V4 seeds','Unique after subtraction',
                    'First unique seed','Subtracted seed list'],detection_rows)
    for e in evidence:
        if e['role']=='control':
            lines += ['','### %s first unique witness — seed %d'%(e['variant'],e['seed']),'',
                      '[Full replay trace](%s). Target: `%s`.'%(e['trace'],e['invariant']),
                      '','```text',*e['excerpt'],'```']
    lines += ['','## Deterministic matrix','']
    lines += table(['Scenario','Variant','Expected','Observed','Already invalid','Late landings','Match'],[
        [r['scenario'],r['variant'],expected_label(r['scenario'],r['variant'],r['expected']),
         r['model']['verdict']+(' '+','.join(r['model']['violations']) if r['model']['violations'] else ''),
         r['model']['metrics'].get('already_invalid_landings',0),
         r['model']['metrics'].get('late_landings',0),
         'yes' if r['matches_expected'] else '**NO**'] for r in scripts])
    lines += ['','## Every V4 failure','',
        'Failure classes are workload × accepted invariant (and UNKNOWN separately). '
        'All failing seed IDs remain in raw JSONL; the smallest seed of every class is '
        'replayed and compared identically, including metrics and latency observations. '
        'W-drift fact-based flip exposure is excluded only by the approved acceptance rule.','']
    failures=[e for e in evidence if e['role']=='V4_failure']
    if not failures:
        lines += ['**No V4 failures and no V4 UNKNOWNs.** No failure-class replay is required. '
                  'This does not count W-drift exposure as prevented; its measured exposure is above.']
    for e in failures:
        lines += ['','### %s / %s — smallest seed %d'%(e['workload'],e['invariant'],e['seed']),'',
                  '**Classification: finding requiring causal review.** No model change was made. '
                  '[Full replay trace](%s).'%e['trace'],'','```text',*e['excerpt'],'```']
    lines += ['','## Every S1 under W-drift','',
        'S1 remains a failure even under silent drift. Each case below has an identical '
        'full replay, a captured atomic-state context in `phase2/evidence.json`, and a trace. '
        'Pre-drift S1 cases cannot be attributed to the later corruption.','']
    drift_cases=[e for e in evidence if e['role']=='drift_S1']
    if drift_cases:
        lines += table(['Variant','Seed','Causal explanation','Trace'],[
            [e['variant'],e['seed'],describe_S1(e,groups[(e['variant'],e['workload'])][e['seed']]),
             '[full trace](%s)'%e['trace']] for e in drift_cases])
    else:
        lines += ['No S1 cases under W-drift.']
    lines += ['','## Harness handling and verification','',
        'No phase-1d protocol source, invariant implementation, cost metric or scenario expectation '
        'was changed for the batches. No new harness bug was found or fixed. W-drift acceptance '
        'and read-only latency observation live in `phase2.py`; all original model verdicts, '
        'violations and metrics are retained alongside accepted verdicts. Replay comparisons '
        'canonicalize tuple-bearing cycle witnesses through JSON before comparing with JSONL arrays; '
        'this verifier serialization correction affects no model transition or batch. Observer parity was '
        'checked against the original model for every main variant/workload combination.','',
        '`verify.py` recomputes every report table from raw JSONL, checks complete seed coverage '
        'and all workload/source hashes, validates acceptance and flip counters, regenerates '
        'witnesses, and compares replay results identically. The entire generated Markdown '
        'must match REPORT.md byte-for-byte.','',
        '## Limits','',
        '- Snapshot views, register operations, store mini-batches and replacement are atomic. '
        'The model does not represent torn snapshots, distributed transactions or database isolation anomalies.',
        '- The platform has an idealized immediate liveness flag. Failure detection time, '
        'false suspicions and partitions between independent detectors are not represented.',
        '- The population is eight documents, paired Wiki pages, two resources and two projections. '
        'This is not a scale or throughput benchmark.',
        '- Time is logical ticks. Queue boundaries and FIFO tie order idealize transport, '
        'storage and concurrent execution; no physical latency calibration is claimed.',
        '- There is no durable outbox. A projection crash can lose unsent confirmations; '
        'the pending-age and heartbeat paths must repair the mirror.',
        '- A restore rewinds mirror facts only; projection counters, stores, expiry metadata '
        'and Build fences remain. Silent corruption can make judgments wrong before detection.',
        '- The digest uses stable truncated SHA-256 XOR. The model does not inject hash collisions '
        'or Byzantine publishers.',
        '- Fault draws share scheduler RNG. The same workload hashes guarantee the same external '
        'actions, not identical fault realizations after variants take different branches.',
        '- Finite seeds and the event bound cannot prove the design or fence redundancy. '
        'Costs at repair-cycle bounds are censored. Undefined repair-completion latency is '
        'kept distinct from recovery without a repair and from unrepaired/censored runs.',
        '', 'No network, paid API calls, commits, pushes or GitHub operations. All writes are under round2/.','']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    metadata,groups,scripts,hashes=load()
    cases=requests(groups)
    evidence=build_evidence(groups,cases)
    text=render(metadata,groups,scripts,hashes,evidence)
    path=ROOT/'REPORT.md'
    if args.write:
        path.write_text(text)
    else:
        assert path.read_text()==text, 'REPORT.md differs from recomputed report'
    print('VERIFIED: %d random rows; %d deterministic rows; %d identical witness replays; report %s.'%
          (sum(len(r) for r in groups.values()),len(scripts),len({(e['variant'],e['workload'],e['seed']) for e in evidence}),
           'written' if args.write else 'matches'))


if __name__=='__main__':
    main()
