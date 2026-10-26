#!/usr/bin/env python3
"""Real PostgreSQL cursor experiment. Each run resets only this throwaway DB."""
import argparse
import collections
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
import threading
import time

import psycopg

DSN = os.environ['CODEX55_DSN']  # set by run_part_a.sh
ROOT = Path(__file__).resolve().parent


def writer(worker, seed, count, result_queue):
    rng = random.Random(seed * 1009 + worker)
    attempts = []
    try:
        with psycopg.connect(DSN) as conn:
            for i in range(count):
                uid = '%s-%s' % (worker, i)
                start = time.time()
                conn.execute('INSERT INTO documents VALUES (%s, 1)', (uid,))
                time.sleep(rng.uniform(0, .050))
                seq, xid = conn.execute(
                    "INSERT INTO feed(uid, kind) VALUES (%s, 'current_revision_changed') RETURNING seq, xid::text",
                    (uid,)).fetchone()
                is_long = worker < 3 and i == 25 + 20 * worker
                time.sleep(3.0 if is_long else rng.uniform(0, .200))
                rollback = rng.random() < .05
                if rollback:
                    conn.rollback()
                else:
                    conn.commit()
                attempts.append(dict(uid=uid, seq=seq, xid=int(xid), start=start,
                                     end=time.time(), rollback=rollback, long=is_long))
        result_queue.put(dict(worker=worker, attempts=attempts))
    except BaseException as exc:
        result_queue.put(dict(worker=worker, error=repr(exc), attempts=attempts))
        raise


def consume(mode, done, records, errors, polls):
    seq = 0
    xid = 0
    try:
        with psycopg.connect(DSN, autocommit=True) as conn:
            empty_after_done = 0
            while empty_after_done < 3:
                if mode == 'A':
                    rows = conn.execute('''SELECT seq, xid::text, uid FROM feed
                        WHERE seq > %s AND xid < pg_snapshot_xmin(pg_current_snapshot())
                        ORDER BY seq LIMIT 100''', (seq,)).fetchall()
                else:
                    rows = conn.execute('''SELECT seq, xid::text, uid FROM feed
                        WHERE (xid, seq) > (%s::xid8, %s)
                        AND xid < pg_snapshot_xmin(pg_current_snapshot())
                        ORDER BY feed.xid, feed.seq LIMIT 100''', (str(xid), seq)).fetchall()
                delivered_at = time.time()
                polls.append(dict(at=delivered_at, rows=len(rows)))
                for row_seq, row_xid, uid in rows:
                    records.append(dict(seq=row_seq, xid=int(row_xid), uid=uid, delivered_at=delivered_at))
                    seq, xid = row_seq, int(row_xid)
                if done.is_set() and not rows:
                    empty_after_done += 1
                else:
                    empty_after_done = 0
                time.sleep(.020)
    except BaseException as exc:
        errors.append(repr(exc))


def run(seed, writers, transactions):
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute('DROP TABLE IF EXISTS feed, documents')
        conn.execute('CREATE TABLE documents(uid text primary key, v int)')
        conn.execute('''CREATE TABLE feed(seq bigserial primary key,
            xid xid8 not null default pg_current_xact_id(), uid text, kind text)''')
        conn.execute('CREATE INDEX ON feed(xid, seq)')
        version = conn.execute('SELECT version()').fetchone()[0]
    done = threading.Event()
    records = {'A': [], 'B': []}
    polls = {'A': [], 'B': []}
    errors = []
    readers = [threading.Thread(target=consume, args=(m, done, records[m], errors, polls[m])) for m in records]
    for reader in readers:
        reader.start()
    ctx = mp.get_context('spawn')
    result_queue = ctx.Queue()
    processes = [ctx.Process(target=writer, args=(i, seed, transactions, result_queue)) for i in range(writers)]
    for process in processes:
        process.start()
    # Drain queues before join: large result messages can fill the multiprocessing pipe.
    results = [result_queue.get(timeout=300) for _ in processes]
    for process in processes:
        process.join(timeout=15)
        if process.exitcode != 0:
            errors.append('writer exit: %r' % process.exitcode)
    done.set()
    for reader in readers:
        reader.join(timeout=30)
        if reader.is_alive():
            errors.append('consumer did not drain')
    with psycopg.connect(DSN, autocommit=True) as conn:
        truth = [dict(seq=s, xid=int(x), uid=u, committed_at=float(t)) for s, x, u, t in conn.execute('''
            SELECT seq, xid::text, uid,
              extract(epoch from pg_xact_commit_timestamp(xid::text::xid)) FROM feed ORDER BY seq''')]
    errors.extend(r['error'] for r in results if 'error' in r)
    committed = {r['seq']: r for r in truth}
    summary = dict(seed=seed, attempted=writers * transactions, committed=len(truth), version=version, errors=errors)
    for mode in records:
        counts = collections.Counter(r['seq'] for r in records[mode])
        summary[mode + '_missed'] = len(set(committed) - set(counts))
        summary[mode + '_duplicated'] = sum(n - 1 for n in counts.values())
        summary[mode + '_unexpected'] = len(set(counts) - set(committed))
    ordered = [(r['xid'], r['seq']) for r in records['B']]
    summary['B_cursor_strictly_increasing'] = all(a < b for a, b in zip(ordered, ordered[1:]))
    deliveries = {r['seq']: r['delivered_at'] for r in records['B']}
    delays = {s: deliveries[s] - row['committed_at'] for s, row in committed.items() if s in deliveries}
    long_intervals = [a for r in results for a in r['attempts'] if a['long']]
    held = [delay for s, delay in delays.items() if any(a['start'] <= committed[s]['committed_at'] <= a['end'] for a in long_intervals)]
    ordinary = [delay for s, delay in delays.items() if not any(a['start'] <= committed[s]['committed_at'] <= a['end'] for a in long_intervals)]
    summary.update(B_max_delay_seconds=max(delays.values(), default=None),
                   B_max_delay_committed_during_long_seconds=max(held, default=None),
                   B_max_delay_other_seconds=max(ordinary, default=None),
                   committed_during_long=len(held), long_transactions=len(long_intervals),
                   long_rollback=sum(a['rollback'] for a in long_intervals))
    (ROOT / ('part-a-run-%s.json' % seed)).write_text(json.dumps(dict(
        summary=summary, committed=truth, deliveries=records, polls=polls, writers=results), indent=2))
    return summary


def write_results(summaries):
    lines = ['# Part A — PostgreSQL cursor experiment', '',
             'Status: COMPLETE (an observed failure remains a finding).', '',
             '8 writer processes × 400 transactions = 3,200 attempted transactions per run; '
             '5% randomized rollback, three 3-second transactions; two live consumers poll every 20 ms, batch 100. '
             'Delivery delay uses PostgreSQL commit timestamps (not insertion time).', '',
             '| Seed | Committed | A missed | A duplicated | B missed | B duplicated | B max delay (s) |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        lines.append('| {seed} | {committed} | {A_missed} | {A_duplicated} | {B_missed} | {B_duplicated} | {B_max_delay_seconds:.6f} |'.format(**s))
    lines += ['', '## Long transactions', '']
    for s in summaries:
        lines.append('- Seed {seed}: {committed_during_long} commits occurred while a 3-second transaction was open; '
                     'maximum B delay for these = {B_max_delay_committed_during_long_seconds:.6f}s, '
                     'other commits = {B_max_delay_other_seconds:.6f}s; long transaction rollbacks = {long_rollback}.'.format(**s))
    lines += ['', 'Long-lived transactions hold back xmin, so newer committed rows wait until that horizon advances. '
              'The observed tail latency is a consequence of the ordering policy. '
              'The delays for other commits can also include ordinary xmin waits and polling/backlog drain.', '',
              'Raw evidence: `part-a-run-<seed>.json` contains every attempted transaction, every committed row, '
              'every delivered row and every poll. Seeds reproduce random sleep/rollback choices; OS scheduling remains nondeterministic.', '',
              'PostgreSQL: `' + summaries[0]['version'] + '`', '',
              'Errors: `' + repr([s['errors'] for s in summaries]) + '`', '']
    (ROOT / 'part-a-results.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', nargs='+', type=int, default=[5501, 5502, 5503])
    parser.add_argument('--writers', type=int, default=8)
    parser.add_argument('--transactions', type=int, default=400)
    args = parser.parse_args()
    assert args.writers >= 8 and args.writers * args.transactions >= 3000
    summaries = []
    for seed in args.seeds:
        summary = run(seed, args.writers, args.transactions)
        summaries.append(summary)
        write_results(summaries)
        print(json.dumps(summary), flush=True)
    (ROOT / 'part-a-summary.json').write_text(json.dumps(summaries, indent=2))
    assert not any(s['errors'] for s in summaries), 'incomplete run; inspect errors'


if __name__ == '__main__':
    main()
