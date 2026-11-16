"""PROTOTYPE (#236) experiment 1: does a cursor-read Change Feed skip committed events?

The #55 scenario on MongoDB: writer processes commit transactions that write a
document and a feed event, sleep between statements, roll back 5%, and a few
hold their transaction open for 3 s. One reader process follows the feed and
saves its cursor after each batch is written; it is SIGKILLed halfway and
restarted from the saved cursor. Modes:

  stream   change stream on the feed collection, cursor = resume token
  seq      sequence from $inc on a counter document inside the transaction
  control  sequence from $inc outside the transaction (expected to skip: positive control)
"""
import argparse
import json
import multiprocessing as mp
import os
import random
import signal
import time
from pathlib import Path

from pymongo import MongoClient, ReturnDocument, WriteConcern
from pymongo.errors import PyMongoError
from pymongo.read_concern import ReadConcern

from exp4_durability import uri


def feed_entry(client, mode, session, uid):
    db = client.kp236
    if mode == 'stream':
        db.feed.insert_one({'_id': uid}, session=session)
        return None
    seq = db.counters.find_one_and_update(
        {'_id': 'feed'}, {'$inc': {'seq': 1}}, upsert=True, return_document=ReturnDocument.AFTER,
        session=session if mode == 'seq' else None)['seq']
    db.feed.insert_one({'_id': uid, 'seq': seq}, session=session)
    return seq


def writer(major, mode, worker, seed, count, scale, rate, out):
    rng = random.Random(seed * 1009 + worker)
    client = MongoClient(uri(major), w='majority')
    db = client.kp236
    with open(out, 'w') as f:
        for i in range(count):
            uid = '%d-%d' % (worker, i)
            is_long = worker < 3 and i % 2000 == 25 + 20 * worker
            rollback = rng.random() < .05
            pause = rng.uniform(0, .050) * scale, (3.0 if is_long else rng.uniform(0, .200) * scale)
            tries, first = 0, time.time()
            while True:
                tries += 1
                start = time.time()
                try:
                    with client.start_session() as s:
                        s.start_transaction(write_concern=WriteConcern('majority'))
                        db.documents.update_one({'_id': uid}, {'$set': {'v': 1}}, upsert=True, session=s)
                        time.sleep(pause[0])
                        seq = feed_entry(client, mode, s, uid)
                        time.sleep(pause[1])
                        if rollback:
                            s.abort_transaction()
                        else:
                            s.commit_transaction()
                    break
                except PyMongoError as exc:
                    if not exc.has_error_label('TransientTransactionError') or time.time() - first > 120:
                        raise
            f.write(json.dumps(dict(uid=uid, seq=seq, start=start, end=time.time(), tries=tries,
                                    rollback=rollback, long=is_long)) + '\n')
            if rate:
                time.sleep(max(0.0, rng.expovariate(rate)))


def reader(major, mode, out, cursor_file):
    """Appends deliveries, then saves the cursor: a crash between the two re-delivers, never skips."""
    client = MongoClient(uri(major))
    cursor = json.loads(Path(cursor_file).read_text()) if Path(cursor_file).exists() else None
    feed = client.kp236.get_collection('feed', read_concern=ReadConcern('majority'))
    with open(out, 'a') as f:
        if mode == 'stream':
            with feed.watch([{'$match': {'operationType': 'insert'}}],
                            resume_after=cursor, max_await_time_ms=100) as stream:
                while True:
                    batch, opened = [], time.time()
                    while (ev := stream.try_next()) is not None:
                        batch.append(ev)
                        if len(batch) >= 100 or time.time() - opened > .050:
                            break
                    now = time.time()
                    for ev in batch:
                        f.write(json.dumps(dict(uid=ev['documentKey']['_id'], at=now)) + '\n')
                    f.flush()
                    os.fsync(f.fileno())
                    token = stream.resume_token
                    if token is not None:
                        Path(cursor_file).write_text(json.dumps(token))
        else:
            seq = cursor or 0
            while True:
                rows = list(feed.find({'seq': {'$gt': seq}}).sort('seq', 1).limit(100))
                now = time.time()
                for r in rows:
                    f.write(json.dumps(dict(uid=r['_id'], seq=r['seq'], at=now)) + '\n')
                    seq = r['seq']
                f.flush()
                os.fsync(f.fileno())
                Path(cursor_file).write_text(json.dumps(seq))
                time.sleep(.020)


def lines(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x]


def percentile(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 3) if xs else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--major', type=int, required=True)
    p.add_argument('--mode', choices=['stream', 'seq', 'control'], required=True)
    p.add_argument('--seed', type=int, default=23601)
    p.add_argument('--writers', type=int, default=8)
    p.add_argument('--transactions', type=int, default=400, help='per writer')
    p.add_argument('--scale', type=float, default=1.0, help='multiplies the random sleeps (not the 3 s ones)')
    p.add_argument('--rate', type=float, default=0, help='per-writer transactions per second; 0 = unpaced')
    p.add_argument('--no-restart', action='store_true')
    p.add_argument('--out', required=True, help='directory for the raw record')
    a = p.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    client = MongoClient(uri(a.major), w='majority')
    version = client.server_info()['version']
    client.drop_database('kp236')
    for c in ('documents', 'feed', 'counters'):
        client.kp236.create_collection(c)
    client.kp236.feed.create_index('seq')
    cursor_file, deliveries = out / 'cursor.json', out / 'deliveries.jsonl'
    for f in (cursor_file, deliveries):
        f.unlink(missing_ok=True)

    ctx = mp.get_context('spawn')
    start_reader = lambda: ctx.Process(target=reader, args=(a.major, a.mode, deliveries, cursor_file))
    rd = start_reader()
    rd.start()
    time.sleep(2)  # the stream must be open before the first write when there is no token yet
    writers = [ctx.Process(target=writer, args=(a.major, a.mode, w, a.seed, a.transactions, a.scale, a.rate,
                                                 out / ('writer-%d.jsonl' % w))) for w in range(a.writers)]
    t0 = time.time()
    for w in writers:
        w.start()
    restarted_at = None
    while any(w.is_alive() for w in writers):
        time.sleep(.5)
        if not a.no_restart and restarted_at is None and deliveries.exists() \
                and deliveries.stat().st_size and sum(1 for _ in open(deliveries)) >= a.writers * a.transactions // 2:
            os.kill(rd.pid, signal.SIGKILL)
            rd.join()
            restarted_at = time.time()
            time.sleep(2)
            rd = start_reader()
            rd.start()
            print('reader killed and restarted at %.1f s' % (restarted_at - t0), flush=True)
    errors = ['writer %d exit %s' % (i, w.exitcode) for i, w in enumerate(writers) if w.exitcode != 0]

    truth = {d['_id'] for d in client.kp236.get_collection(
        'feed', read_concern=ReadConcern('majority')).find({}, {'_id': 1})}
    deadline = time.time() + 60
    while time.time() < deadline:  # drain: stop when every committed event arrived or nothing new for 10 s
        got = lines(deliveries)
        if truth <= {d['uid'] for d in got}:
            break
        size = len(got)
        time.sleep(10)
        if len(lines(deliveries)) == size:
            break
    os.kill(rd.pid, signal.SIGKILL)
    rd.join()

    attempts = [x for w in range(a.writers) for x in lines(out / ('writer-%d.jsonl' % w))]
    committed = {x['uid']: x for x in attempts if not x['rollback']}
    got = lines(deliveries)
    delivered = {}
    for d in got:
        delivered.setdefault(d['uid'], d['at'])
    delays = [delivered[u] - x['end'] for u, x in committed.items() if u in delivered]
    long_end = [(x['start'], x['end']) for x in attempts if x['long']]
    summary = dict(
        version=version, mode=a.mode, seed=a.seed, writers=a.writers, transactions=a.transactions,
        scale=a.scale, rate_per_writer=a.rate, restarted=restarted_at is not None,
        wall_seconds=round(time.time() - t0, 1), errors=errors,
        committed=len(committed), in_db=len(truth), db_matches_writers=truth == set(committed),
        missed=len(set(committed) - set(delivered)),
        duplicated=len(got) - len(delivered), unexpected=len(set(delivered) - set(committed)),
        long_transactions=len(long_end),
        tries_max=max(x['tries'] for x in attempts), tries_mean=round(sum(x['tries'] for x in attempts) / len(attempts), 2),
        retried=sum(1 for x in attempts if x['tries'] > 1),
        delay_p50=percentile(delays, .5), delay_p99=percentile(delays, .99), delay_max=percentile(delays, 1),
    )
    (out / 'summary.json').write_text(json.dumps(summary, indent=1))
    (out / 'missed.json').write_text(json.dumps(sorted(set(committed) - set(delivered))))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
