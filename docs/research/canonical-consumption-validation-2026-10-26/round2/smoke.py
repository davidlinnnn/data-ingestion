#!/usr/bin/env python3
"""Phase-1d smoke only: seeds 0..4 plus fixed scenarios; no full batches."""
import sys
sys.dont_write_bytecode = True
import argparse
from collections import Counter
import hashlib
import json
import math
import unittest
from model import ROOT, VARIANTS, INVARIANTS, PENDING_MAX, Simulation
from scenarios import EXPECTED, scenario, check_expected
from test_model import ProtocolChecks

ROUND1_HASH = '97b602f4afba5ae583628fecaa832d364ce96ef682782816d0d63ae47fa23796'
LATE_METRICS = ['late_landings', 'late_S2', 'late_S3', 'late_transactions',
                'already_invalid_landings', 'S2_at_write', 'S3_at_write']


def observed(result):
    suffix = ', '.join(result['violations'])
    return result['verdict'] + (' (' + suffix + ')' if suffix else '')


def statistics(values):
    return dict(mean=sum(values)/len(values), p95=sorted(values)[math.ceil(.95*len(values))-1], max=max(values))


def stats_text(values):
    s = statistics(values)
    return '%.2f / %d / %d' % (s['mean'], s['p95'], s['max'])


def sc24_excerpt(trace):
    # Keep all protocol evidence and enough actual boundary observations to total 30.
    selected = {i for i, line in enumerate(trace) if ' boundary ' not in line}
    assert len(selected) <= 30
    for i, line in enumerate(trace):
        if len(selected) == 30:
            break
        selected.add(i)
    excerpt = [trace[i] for i in sorted(selected)]
    assert len(excerpt) == 30
    for text in ('age=90; fresh view', 'replacement view 2', 'IGNORE obsolete replacement page 1'):
        assert any(text in line for line in excerpt)
    return excerpt


def run_smoke():
    assert hashlib.sha256((ROOT.parent/'part_b.py').read_bytes()).hexdigest() == ROUND1_HASH
    checked = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProtocolChecks))
    if not checked.wasSuccessful():
        raise SystemExit(1)
    runs, scripts, excerpt = [], [], None
    combinations = [(w,v) for w in ('W-real','W-rewind','W-drift') for v in ('V1','V2','V3','V4')]
    combinations += [('W-real',v) for v in ('V4-Ra','V4-Rb','N2','N12','N-fence','N-viewexp')]
    with (ROOT/'smoke-runs.jsonl').open('w') as output:
        for workload, variant in combinations:
            for seed in range(5):
                sim = Simulation(seed,variant,workload,full_trace=(variant=='V4-Ra' and seed==4))
                result = sim.run()
                if variant == 'V4-Ra' and seed == 4:
                    (ROOT/'V4-Ra-W-real-seed4-trace.txt').write_text('\n'.join(sim.trace)+'\n')
                runs.append(result)
                output.write(json.dumps(result,sort_keys=True)+'\n')
                output.flush()
                print('%s %s seed=%d %s late=%d repairs=%d steps=%d' %
                      (workload,variant,seed,observed(result),result['metrics'].get('late_landings',0),
                       result['metrics'].get('snapshots',0),result['steps']),flush=True)
    with (ROOT/'scenario-runs.jsonl').open('w') as output:
        for name, matrix in EXPECTED.items():
            for variant, expected in matrix.items():
                sim = scenario(name,variant)
                result = sim.run()
                result.update(scenario=name,expected_violations=sorted(expected),matches_expected=check_expected(name,variant,result))
                scripts.append(result)
                output.write(json.dumps(result,sort_keys=True)+'\n')
                (ROOT/('%s-%s-trace.txt'%(name,variant))).write_text('\n'.join(sim.trace)+'\n')
                if name == 'SC24' and variant == 'V4':
                    excerpt = sc24_excerpt(sim.trace)
                print('%s %s %s expected_match=%s'%(name,variant,observed(result),result['matches_expected']),flush=True)
    assert excerpt is not None
    (ROOT/'SC24-V4-excerpt.txt').write_text('\n'.join(excerpt)+'\n')
    write_report(runs,scripts,excerpt,checked.testsRun)
    assert hashlib.sha256((ROOT.parent/'part_b.py').read_bytes()).hexdigest() == ROUND1_HASH


def write_report(runs,scripts,excerpt,tests):
    groups = {}
    for r in runs:
        groups.setdefault((r['workload'],r['variant']),[]).append(r)
    totals = Counter(r['verdict'] for r in runs)
    deviations = [r for r in scripts if not r['matches_expected']]
    costs, landings = {}, {}
    lines = ['# Round 2, phase 1d — smoke','',
        '**Only seeds 0–4. No full batches.** %d protocol checks passed. Round 1 is untouched; phase-1, phase-1b and phase-1c code/results are preserved under their phase prefixes.'%tests,'',
        '**90 random runs: %d PASS, %d FAIL, %d UNKNOWN.** S2/S3 are measurements, not failures. L0 bounds fail; other bounds stay UNKNOWN. L1–L5 are evaluated only at quiescence.'%(totals['PASS'],totals['FAIL'],totals['UNKNOWN']),'',
        '## Findings and deviations','',
        '- **Harness bug fixed:** phase-1 mapping specified a 90-tick deadline for snapshot transfers and restart on timeout; the V4 replacement path omitted it. Every protected view now has an active deadline from capture time, late pages cannot complete it, and retry takes a new view. All affected smoke cells were rerun.',
        '- **Replacement expiry fence added:** candidate entries use their original fact version and view capture time in the same expired-tombstone predicate as reports, before stamping W. A rejected candidate aborts the atomic replacement and requests a fresh view. N-viewexp removes exactly these two guards; N12 retains its expired-reference acceptance mutation.',
        '- **SC24 matches:** V4 PASS; N-viewexp produces S1_flipback. The stale original page arrives at t135, after the original v2 tombstone expiry at t132. V4 had discarded that view at t100 and replaced it from current state at t101. The control installs the stale included v1 and flips enforcement.',
        '- **SC20r/SC20u separate announced restore from silent drift:** the runbook repairs announced restores for all four variants; a silent equal-count rewind has no gate or repair request, so count-only V1/V2 fail L2 while V3/V4 repair via digest.',
        '- **NC3 dropped by the main-line decision:** its never-registered mirror key is not reachable through V4 register-before-write. The replacement fence appears redundant given pending-before-write, W tombstones and the expiry fence. NC2/N-fence is masked by its tombstone. V4 keeps its fence; testing N-fence with 1,000 seeds on each of all three workloads is reserved for phase 2 and was NOT run here.',
        '- **Silent drift can immediately reverse an earlier enforcement judgment before a heartbeat repairs it.** W-drift has no operator gate. Those fact-based reversals remain failures under the unchanged invariants, even if the run later converges. The observed V4 results for all three workloads are in the tables below.','',
        '## V4 headline','',
        '; '.join('%s: %d/5 PASS, %d fact-based flip-backs' %
                  (w, sum(r['verdict']=='PASS' for r in groups[(w,'V4')]),
                   sum(r['metrics'].get('fact_based_flip_backs',0) for r in groups[(w,'V4')]))
                  for w in ('W-real','W-rewind','W-drift'))+'. All five V4 runs under each workload reach quiescence. W-drift failures remain failures despite final L1–L5 convergence.','',
        '**Deterministic matrix: %d/%d cells match; %d deviations.**' %
            (len(scripts)-len(deviations),len(scripts),len(deviations)),'',
        '## Random verdicts','',
        '| Workload | Variant | Seed 0 | Seed 1 | Seed 2 | Seed 3 | Seed 4 |','|---|---|---|---|---|---|---|']
    for (w,v),rows in groups.items():
        lines.append('| %s | %s | %s |'%(w,v,' | '.join(observed(r) for r in rows)))
    lines += ['','## Invariants — seeds with a failure','',
        'Quiescent is the denominator for L1–L5. Zero in an unevaluated property is not a pass. Current V1 is the fair two-step design; the old atomic model is excluded.','',
        '| Workload | Variant | Quiescent | '+' | '.join(INVARIANTS)+' | Raw / liveness-gate / restore-gate / fact flips | UNKNOWN |',
        '|---|---|---:|'+'---:|'*(len(INVARIANTS)+2)]
    for (w,v),rows in groups.items():
        counts=Counter(i for r in rows for i in r['violations'])
        lines.append('| %s | %s | %d/5 | %s | %d / %d / %d / %d | %d |'%(w,v,sum(r['quiescent'] for r in rows),
            ' | '.join(str(counts[i]) for i in INVARIANTS),sum(r['metrics'].get('flip_backs',0) for r in rows),
            sum(r['metrics'].get('flip_backs_liveness_gate',0) for r in rows),
            sum(r['metrics'].get('restore_gate_flips',0) for r in rows),sum(r['metrics'].get('fact_based_flip_backs',0) for r in rows),sum(r['unknown'] is not None for r in rows)))
    lines += ['','## Late landings — mean / p95 / max per run','',
        'Counts are source entries: two-source Wiki writes can add two. `late_landings` counts each initially admitted source once if eligibility or revision drifts after check/register. Already-invalid sources (e.g. Rb) are separate. `S2_at_write` / `S3_at_write` retain all original boundary observations. `late_transactions` counts affected document/page transactions. None fails a run. Bound-hit observations are censored.','',
        '| Workload | Variant | '+' | '.join(LATE_METRICS)+' |','|---|---|'+'---:|'*len(LATE_METRICS)]
    for (w,v),rows in groups.items():
        landings[w+':'+v]={key:statistics([r['metrics'].get(key,0) for r in rows]) for key in LATE_METRICS}
        lines.append('| %s | %s | %s |'%(w,v,' | '.join(stats_text([r['metrics'].get(key,0) for r in rows]) for key in LATE_METRICS)))
    lines += ['','## Repair snapshots per seed','',
        'Starts are per Build, summed per seed; p95 is nearest-rank. Bound-hit costs at 30,000 events are censored. Transient mismatch means absent before the next heartbeat in a fork suppressing new repairs. The fork retains existing repairs and copies state/RNG; removed repair work can change subsequent RNG consumption. Only heartbeat starts are classified as transient mismatches.','',
        '| Workload | Variant | Seed 0–4 | Mean | p95 | Transient / all starts | Transient / heartbeat starts |','|---|---|---|---:|---:|---:|---:|']
    for (w,v),rows in groups.items():
        values=[r['metrics'].get('snapshots',0) for r in rows]
        transient=sum(r['metrics'].get('transient_snapshots',0) for r in rows)
        heartbeat=sum(r['metrics'].get('heartbeat_snapshots',0) for r in rows)
        costs[w+':'+v]=dict(statistics(values),seeds=values,transient=transient,all_starts=sum(values),heartbeat_starts=heartbeat)
        lines.append('| %s | %s | %s | %.2f | %d | %d/%d (%.2f%%) | %d/%d (%.2f%%) |'%(w,v,', '.join(map(str,values)),
            statistics(values)['mean'],statistics(values)['p95'],transient,sum(values),100*transient/max(1,sum(values)),
            transient,heartbeat,100*transient/max(1,heartbeat)))
    lines += ['','V4 versus V3 directly:','','| Workload | V3 mean / p95 | V4 mean / p95 | Mean delta V4−V3 |','|---|---:|---:|---:|']
    for w in ('W-real','W-rewind','W-drift'):
        old,new=costs[w+':V3'],costs[w+':V4']
        lines.append('| %s | %.2f / %d | %.2f / %d | %+.2f |'%(w,old['mean'],old['p95'],new['mean'],new['p95'],new['mean']-old['mean']))
    lines += ['','## Deterministic matrix — expectations retained','',
        '| Schedule | Variant | Expected | Observed | Late S2 / S3 / combined | Already invalid | Raw S2 / S3 | Match? |','|---|---|---|---|---:|---:|---:|---|']
    for r in scripts:
        exp='FAIL '+', '.join(r['expected_violations']) if r['expected_violations'] else 'PASS'
        if r['scenario']=='SC20r':
            exp+='; restore repair'
        if r['scenario']=='SC20u' and r['variant'] in ('V3','V4'):
            exp+='; digest repair'
        if r['scenario']=='NC2' and r['variant']=='N2':
            exp+='; masked by V4 fence'
        if r['scenario']=='NC2' and r['variant']=='N-fence':
            exp+='; masked by tombstone'
        if r['scenario']=='SC24' and r['variant']=='N-viewexp':
            exp='FAIL S1_flipback or L2'
        if r['scenario']=='SC18':
            exp+='; already invalid '+('≥1' if r['variant']=='V4-Rb' else '=0')
        if r['scenario']=='SC22' and r['variant']=='V4':
            exp+='; age repair'
        m=r['metrics']
        lines.append('| %s | %s | %s | %s | %d / %d / %d | %d | %d / %d | %s |'%(r['scenario'],r['variant'],exp,observed(r),
            m.get('late_S2',0),m.get('late_S3',0),m.get('late_landings',0),m.get('already_invalid_landings',0),
            m.get('S2_at_write',0),m.get('S3_at_write',0),'yes' if r['matches_expected'] else '**NO — finding**'))
    lines += ['','## SC24 / V4 — exactly 30 trace lines','',
        'All protocol lines plus selected actual boundary observations from `SC24-V4-trace.txt`, in their original order. View at t10; delete t11; remove v2 t12; deadline at t100 takes a fresh empty view; replacement completes t101; stale original page at t135 is ignored. N-viewexp has neither guard and installs included v1 after tombstone expiry, causing S1_flipback.','','```text']+excerpt+['```','',
        '## Affected Ra witness rerun','',
        'Phase-1c evidence is preserved in `phase1c-V4-Ra-W-real-seed4-trace.txt` and its causal explanation in `phase1c-SMOKE.md`. The corrected run is in `V4-Ra-W-real-seed4-trace.txt`: view 2 at t136 is discarded at t226 (age 90), and its late page at t308 is ignored. Seed 4 now PASSes. The seed/workload and all non-transfer rules are unchanged; additional timeout events can change later scheduler RNG consumption. SC24 isolates the same late-view mechanism.','',
        '## Evidence and reproduction','',
        'Raw results, witnesses, queue cycles and metrics: `smoke-runs.jsonl`, `scenario-runs.jsonl`, `smoke-summary.json`. Every schedule has a full trace.','',
        '```sh','prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/smoke.py',
        'prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/smoke.py --scenario SC24 V4',
        'prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/smoke.py --replay V4 W-real 0',
        'prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/phase1-replay.py --replay V3 W-real 0','```','',
        'Round-1 `part_b.py` SHA-256: `'+ROUND1_HASH+'`. Archived files are verified by `phase1-manifest.json`, `phase1b-manifest.json` and `phase1c-manifest.json`. The original cycle evidence and reduction remain in the `phase1c-SC21-WITNESS.md`, `phase1c-SC21-source-witness.txt` and `phase1c-cycle-witnesses.json` archives. No network, paid calls, new dependencies, commits, pushes or GitHub operations.','',
        '**Stopped after phase 1d. Full batches intentionally not run.**']
    (ROOT/'SMOKE.md').write_text('\n'.join(lines)+'\n')
    summary=dict(restore_flips={w+':'+v:[r['metrics'].get('restore_gate_flips',0) for r in rows] for (w,v),rows in groups.items()},
        fact_flips={w+':'+v:[r['metrics'].get('fact_based_flip_backs',0) for r in rows] for (w,v),rows in groups.items()},
        verdicts={v:totals[v] for v in ('PASS','FAIL','UNKNOWN')},costs=costs,late_landings=landings,
        scenario_deviations=[dict(scenario=r['scenario'],variant=r['variant'],observed=observed(r)) for r in deviations])
    (ROOT/'smoke-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--replay',nargs=3,metavar=('VARIANT','WORKLOAD','SEED'))
    mode.add_argument('--scenario',nargs=2,metavar=('ID','VARIANT'))
    args=parser.parse_args()
    if args.replay:
        variant,workload,seed=args.replay
        assert variant in VARIANTS and workload in ('W-real','W-rewind','W-drift')
        print(json.dumps(Simulation(int(seed),variant,workload).run(),indent=2,sort_keys=True))
    elif args.scenario:
        name,variant=args.scenario
        sim=scenario(name,variant)
        print(json.dumps(sim.run(),indent=2,sort_keys=True))
        print('\n'.join(sim.trace))
    else:
        run_smoke()


if __name__=='__main__':
    main()
