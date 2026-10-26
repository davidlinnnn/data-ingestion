#!/usr/bin/env python3
"""Approved full batches; the phase-1d transition model stays unchanged."""
import sys
sys.dont_write_bytecode = True
import concurrent.futures
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import time
import unittest

from model import ROOT, Simulation
from scenarios import EXPECTED, scenario, check_expected

DATA = ROOT / 'phase2'
WORKLOADS = ('W-real', 'W-rewind', 'W-drift')
PLAN = {
    'main': [(v, w) for v in ('V1', 'V2', 'V3', 'V4') for w in WORKLOADS],
    'ablations': [(v, 'W-real') for v in ('V4-Ra', 'V4-Rb')],
    'fence': [('N-fence', w) for w in WORKLOADS],
    'controls': [(v, 'W-real') for v in ('N2', 'N12', 'N-viewexp')],
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def acceptance(result):
    failures = dict(result['violations'])
    if result['workload'] == 'W-drift':
        failures.pop('S1_flipback', None)
    return dict(violations=failures, verdict='FAIL' if failures else
                ('UNKNOWN' if result['unknown'] else 'PASS'),
                fact_flip_exposure=result['metrics'].get('fact_based_flip_backs', 0))


class ObservedSimulation(Simulation):
    """Read-only latency observation; no RNG draws, protocol events or model edits."""
    def __init__(self, *args, **kwargs):
        self.drift = None
        super().__init__(*args, **kwargs)

    def equal(self, bid):
        return self.included_facts(bid) == self.builds[bid]['store']

    def restore_mirror(self, bid, saved, announced=True):
        super().restore_mirror(bid, saved, announced)
        if not announced:
            equal = self.equal(bid)
            self.drift = dict(build=bid, time=self.time, equal_at_drift=equal,
                              first_equality_time=self.time if equal else None,
                              repair_completion_time=None, repair_latency=None,
                              repair_id=None, repair_completions_without_L2=0)

    def observe_completion(self, sid, bid):
        if (self.drift is None or bid != self.drift['build'] or not self.live(bid)
                or self.drift['repair_completion_time'] is not None):
            return
        if self.equal(bid):
            self.drift.update(repair_completion_time=self.time,
                              repair_latency=self.time - self.drift['time'], repair_id=sid)
        else:
            self.drift['repair_completions_without_L2'] += 1

    def maybe_sweep(self, sid):
        state = self.snapshots.get(sid)
        bid = state['build'] if state else None
        super().maybe_sweep(sid)
        if state and sid not in self.snapshots and self.builds[bid]['repair'] is None:
            self.observe_completion(sid, bid)

    def finish_replacement(self, sid):
        bid = self.snapshots[sid]['build']
        completed = self.metrics.get('replacements', 0)
        super().finish_replacement(sid)
        if self.metrics.get('replacements', 0) > completed:
            self.observe_completion(sid, bid)

    def step(self):
        kind = super().step()
        if (self.drift and self.drift['first_equality_time'] is None
                and self.equal(self.drift['build'])):
            self.drift['first_equality_time'] = self.time
        return kind


def record(seed, variant, workload, full_trace=False):
    sim = ObservedSimulation(seed, variant, workload, full_trace=full_trace)
    result = sim.run()
    drift = deepcopy(sim.drift)
    if drift:
        drift['final_L2_equal'] = sim.equal(drift['build'])
        drift['status'] = ('repair_completed' if drift['repair_latency'] is not None else
                           'already_equal' if drift['equal_at_drift'] else
                           'recovered_without_repair_completion' if drift['final_L2_equal'] else
                           'unrepaired_or_censored')
    return dict(model=result, evaluation=acceptance(result), drift=drift), sim


def chunk(variant, workload, seeds):
    started = time.perf_counter()
    rows = [record(seed, variant, workload)[0] for seed in seeds]
    return rows, time.perf_counter() - started


def save_metadata(metadata):
    (DATA / 'metadata.json').write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')


def run_group(pool, groups, metadata, label, deadline):
    started, start_utc = time.perf_counter(), utc()
    futures = {}
    outputs = {}
    for variant, workload in groups:
        outputs[(variant, workload)] = (DATA / 'raw' / (variant + '-' + workload + '.jsonl')).open('w')
        for begin in range(0, 1000, 10):
            future = pool.submit(chunk, variant, workload, list(range(begin, begin + 10)))
            futures[future] = (variant, workload)
    count, worker_seconds = 0, 0
    try:
        for future in concurrent.futures.as_completed(futures):
            rows, seconds = future.result()
            worker_seconds += seconds
            stream = outputs[futures[future]]
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True) + '\n')
            stream.flush()
            count += len(rows)
            if count % 100 == 0:
                print('%s %d/%d rows wall=%.1fs' %
                      (label, count, len(groups)*1000, time.perf_counter()-started), flush=True)
            if time.perf_counter() > deadline:
                raise TimeoutError('Batch deadline reached; raw completed chunks are preserved')
    finally:
        for stream in outputs.values():
            stream.close()
        metadata['sets'][label] = dict(start=start_utc, end=utc(),
            wall_seconds=time.perf_counter()-started, worker_seconds=worker_seconds,
            groups=groups, completed=count, expected=len(groups)*1000)
        save_metadata(metadata)


def deterministic(metadata):
    started = time.perf_counter()
    count = 0
    with (DATA / 'deterministic.jsonl').open('w') as output:
        for name, matrix in EXPECTED.items():
            for variant, expected in matrix.items():
                sim = scenario(name, variant)
                result = sim.run()
                output.write(json.dumps(dict(scenario=name, variant=variant, model=result,
                    expected=sorted(expected), matches_expected=check_expected(name, variant, result)),
                    sort_keys=True) + '\n')
                (DATA/'traces'/(name+'-'+variant+'.txt')).write_text('\n'.join(sim.trace)+'\n')
                count += 1
    metadata['sets']['deterministic'] = dict(wall_seconds=time.perf_counter()-started,
                                            completed=count, expected=count)
    save_metadata(metadata)


def main():
    for directory in (DATA, DATA/'raw', DATA/'traces'):
        directory.mkdir(exist_ok=True)
    manifest = json.loads((ROOT/'phase1d-manifest.json').read_text())
    for name in ('model.py', 'scenarios.py', 'MAPPING.md'):
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == manifest[name]
    from test_model import ProtocolChecks
    checked = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(ProtocolChecks))
    assert checked.wasSuccessful()
    metadata = dict(start=utc(), python=sys.version, executable=sys.executable,
                    platform=platform.platform(), workers=12, seed_start=0, seed_stop=999,
                    command='prototype/55-validation/.venv/bin/python -B prototype/55-validation/round2/phase2.py',
                    phase1d_hashes=manifest, protocol_checks=checked.testsRun, sets={})
    save_metadata(metadata)
    deadline = time.perf_counter() + 3100
    deterministic(metadata)
    with concurrent.futures.ProcessPoolExecutor(max_workers=12) as pool:
        run_group(pool, [('V4', w) for w in WORKLOADS], metadata, 'main_V4_priority', deadline)
        run_group(pool, [(v,w) for v,w in PLAN['main'] if v != 'V4'], metadata, 'main_remaining', deadline)
        for label in ('ablations', 'fence', 'controls'):
            run_group(pool, PLAN[label], metadata, label, deadline)
    metadata['end'] = utc()
    save_metadata(metadata)
    print('COMPLETE: all requested batches', flush=True)


if __name__ == '__main__':
    main()
