"""PROTOTYPE (#240) experiment 5: does a tailer that copies a change stream into a feed collection skip, repeat or reorder committed changes?

Writers commit #236 experiment 1's transactions without any feed write: each
bumps a Document's revision counter and inserts a revision record (15% touch two
or three Documents). Two tailer processes compete for one lease document; the
holder reads the change stream on `revisions` and writes feed entries and its
resume token in one transaction fenced by the lease epoch. A projection reader
pages the feed by position, appends what it read, then saves its cursor.
Faults (--faults), each at a fixed time after the writers' schedule starts:

  kill    SIGKILL the lease holder and restart it, so two tailers run again
  stop    SIGSTOP the holder until the other one takes over, then SIGCONT it
  freeze  the holder SIGSTOPs itself inside its feed transaction, after the transaction's first
          write; it stays stopped until the other one has written to the feed (150 s cap)
  reader  SIGKILL the reader and restart it from its saved cursor
  oplog   SIGKILL both tailers, write filler until every member's oplog has dropped
          the resume point, restart them: the holder must recover from the documents

Positions (--position):
  seq      the tailer's own counter, saved with the token under the fence
  derived  the event's cluster time plus its index within that cluster time
  epochseq the tailer's counter behind the lease epoch: a new holder's positions never equal an old one's

Fence order (--fence):
  first    the lease update is the transaction's first write, before the inserts
  last     the inserts come first; a duplicate position counts as fenced

Positive controls (--control):
  nofence    the batch is written without the epoch check, positions from a shared counter
  norecover  on lost history the tailer reopens the stream at the current time
"""
import argparse
import json
import multiprocessing as mp
import os
import random
import signal
import time
from collections import Counter, defaultdict
from pathlib import Path

from pymongo import MongoClient, ReturnDocument, WriteConcern
from pymongo.errors import BulkWriteError, OperationFailure, PyMongoError
from pymongo.read_concern import ReadConcern

from exp1_feed_order import lines, percentile
from exp4_durability import uri

TTL, RENEW = 5.0, 1.0  # lease seconds; the holder renews (and saves an idle resume token) this often
FILL_LIMIT = 300  # seconds of filler after which the oplog fault gives up
FREEZE = []  # set by SIGUSR1: the holder stops itself inside its next feed transaction


class Fenced(Exception):
    pass


class LeaseLost(Exception):
    pass


def orphan_exit(parent):
    if os.getppid() != parent:  # the orchestrator died: pkill -f does not reach spawn children, so they leave by themselves
        os._exit(3)


def writer(major, run, worker, seed, count, docs, scale, rate, t0, parent, out):
    rng = random.Random(seed * 1009 + worker)
    client = MongoClient(uri(major), w='majority')
    db = client.kp240
    due = t0
    with open(out, 'w') as f:
        for i in range(count):
            orphan_exit(parent)
            if rate:  # an absolute schedule: a slow transaction does not lower the offered rate
                due += rng.expovariate(rate)
                time.sleep(max(0.0, due - time.time()))
            cid = '%s-%d-%d' % (run, worker, i)
            targets = sorted(rng.sample(range(docs), 1 if rng.random() < .85 else rng.choice((2, 3))))
            is_long = worker < 3 and i % 2000 == 25 + 20 * worker
            rollback = rng.random() < .05
            pause = rng.uniform(0, .050) * scale, (3.0 if is_long else rng.uniform(0, .200) * scale)
            tries, first = 0, time.time()
            while True:
                tries += 1
                start, changes = time.time(), []
                try:
                    with client.start_session() as s:
                        s.start_transaction(write_concern=WriteConcern('majority'))
                        for k, d in enumerate(targets):
                            doc = '%s-d%d' % (run, d)
                            rev = db.documents.find_one_and_update(
                                {'_id': doc}, {'$inc': {'rev': 1}}, upsert=True,
                                return_document=ReturnDocument.AFTER, session=s)['rev']
                            if k == 0:
                                time.sleep(pause[0])
                            rid = '%s.%d' % (cid, k)
                            db.revisions.insert_one({'_id': rid, 'doc': doc, 'rev': rev}, session=s)
                            changes.append((rid, doc, rev))
                        time.sleep(pause[1])
                        if rollback:
                            s.abort_transaction()
                        else:
                            s.commit_transaction()
                    break
                except PyMongoError as exc:
                    if not exc.has_error_label('TransientTransactionError') or time.time() - first > 120:
                        raise
            f.write(json.dumps(dict(cid=cid, changes=changes, start=start, end=time.time(), tries=tries,
                                    rollback=rollback, long=is_long, behind=first - due if rate else 0)) + '\n')
            f.flush()


def op_time(db, epoch, **fields):
    """A fenced, majority-acknowledged write on the lease; its operation time is now's cluster time."""
    with db.client.start_session() as s:
        r = db.lease.update_one({'_id': 'tailer', 'epoch': epoch}, {'$set': fields}, session=s)
        if r.matched_count == 0:
            raise Fenced()
        return s.operation_time


def position(mode, seq, last, ct, epoch):
    """The next position after (seq, last) for an event at cluster time ct; last is [time, inc, index]."""
    if mode == 'seq':
        return seq + 1, seq + 1, last
    if mode == 'epochseq':
        return '%06d%012d' % (epoch, seq + 1), seq + 1, last
    k = last[2] + 1 if last and (last[0], last[1]) == (ct.time, ct.inc) else 0
    last = [ct.time, ct.inc, k]
    return '%010d%010d%06d' % tuple(last), seq, last


def tailer(major, slot, mode, control, fence, parent, out):
    name = '%s:%d' % (slot, os.getpid())
    signal.signal(signal.SIGUSR1, lambda *_: FREEZE.append(1))
    client = MongoClient(uri(major), w='majority')
    db = client.kp240
    log = open(out, 'a')

    def note(**kw):
        log.write(json.dumps(dict(kw, tailer=name, t=time.time()), default=str) + '\n')
        log.flush()

    while True:
        orphan_exit(parent)
        now = time.time()
        st = db.lease.find_one_and_update(
            {'_id': 'tailer', 'expires': {'$lt': now}},
            {'$set': {'owner': name, 'expires': now + TTL}, '$inc': {'epoch': 1}}, return_document=ReturnDocument.AFTER)
        if st is None:
            time.sleep(.2)
            continue
        note(ev='acquired', epoch=st['epoch'])
        try:
            follow(db, st, name, mode, control, fence, note, parent)
        except Fenced:
            note(ev='fenced', epoch=st['epoch'])
        except LeaseLost:
            note(ev='lease_lost', epoch=st['epoch'])
        except Exception as e:  # a crash: log it and compete for the lease again, as a restarted pod would
            note(ev='error', epoch=st['epoch'], error=repr(e)[:300])
            time.sleep(1)


def follow(db, st, name, mode, control, fence, note, parent):
    epoch, seq, last = st['epoch'], st['seq'], st['last']
    renewed = time.time()

    def hold():  # the freeze fault: stop inside the open transaction, after its first write
        if FREEZE:
            FREEZE.clear()
            note(ev='frozen', epoch=epoch)
            os.kill(os.getpid(), signal.SIGSTOP)

    def save(s, entries, token):  # either order: a tailer that lost the lease commits nothing
        if fence == 'last':
            try:
                db.feed.insert_many(entries, session=s)
            except BulkWriteError as e:  # a newer holder already wrote this position
                if any(x['code'] == 11000 for x in e.details['writeErrors']):
                    raise Fenced()
                raise
            hold()
        r = db.lease.update_one({'_id': 'tailer', 'epoch': epoch}, {'$set': dict(
            token=token, start_at=None, seq=seq_after, last=last_after)}, session=s)
        if r.matched_count == 0:
            raise Fenced()
        if fence == 'first':
            hold()
            db.feed.insert_many(entries, session=s)

    while True:  # one pass per stream opening: the first, and again after a recovery
        kw = dict(resume_after=st['token']) if st['token'] else dict(start_at_operation_time=st['start_at'])
        try:
            with db.revisions.watch([{'$match': {'operationType': 'insert'}}], max_await_time_ms=100, **kw) as stream:
                while True:
                    orphan_exit(parent)
                    batch, opened = [], time.time()
                    while (ev := stream.try_next()) is not None:
                        batch.append(ev)
                        if len(batch) >= 100 or time.time() - opened > .050:
                            break
                    token = stream.resume_token
                    if batch:
                        at = time.time()
                        if control == 'nofence':  # no epoch check; a shared counter keeps positions from colliding
                            n = len(batch)
                            seq_after = db.lease.find_one_and_update(
                                {'_id': 'tailer'}, {'$inc': {'seq': n}}, return_document=ReturnDocument.AFTER)['seq']
                            seq_cur, last_cur = seq_after - n, last
                        else:
                            seq_cur, last_cur = seq, last
                        entries = []
                        for ev in batch:
                            pos, seq_cur, last_cur = position(mode, seq_cur, last_cur, ev['clusterTime'], epoch)
                            d = ev['fullDocument']
                            entries.append(dict(_id=pos, change=d['_id'], doc=d['doc'], rev=d['rev'], epoch=epoch,
                                                ct=ev['clusterTime'], txn='%s:%s' % (bytes(ev['lsid']['id']).hex() if 'lsid' in ev else None, ev.get('txnNumber')),
                                                src='stream', at=at))
                        seq_after, last_after = seq_cur, last_cur
                        if control == 'nofence':
                            try:
                                db.feed.insert_many(entries, ordered=False)
                            except BulkWriteError as e:  # the naive tailer's idempotence: drop what is already there
                                if any(x['code'] != 11000 for x in e.details['writeErrors']):
                                    raise
                            db.lease.update_one({'_id': 'tailer'}, {'$set': dict(token=token, start_at=None, last=last_after)})
                        else:
                            with db.client.start_session() as s:
                                s.with_transaction(lambda s: save(s, entries, token), write_concern=WriteConcern('majority'))
                        seq, last, st['token'] = seq_after, last_after, token
                    if time.time() - renewed > RENEW:
                        upd = {'expires': time.time() + TTL}
                        if not batch and token and token != st['token']:
                            upd['token'] = token  # an idle stream still moves its resume point forward
                            st['token'] = token
                        r = db.lease.update_one({'_id': 'tailer', 'epoch': epoch, 'owner': name}, {'$set': upd})
                        if r.matched_count == 0:
                            raise LeaseLost()
                        renewed = time.time()
        except OperationFailure as e:
            if e.code != 286:  # ChangeStreamHistoryLost
                raise
            note(ev='history_lost', epoch=epoch, error=str(e)[:200])
            t_rec = op_time(db, epoch, expires=time.time() + TTL)
            if control == 'norecover':  # what Atlas Triggers do: carry on from now, skipping the gap
                op_time(db, epoch, token=None, start_at=t_rec)
                note(ev='reopened', epoch=epoch, t_rec=[t_rec.time, t_rec.inc], backfilled=0)
            else:
                seq, last = recover(db, epoch, mode, seq, last, t_rec, note)
            st.update(token=None, start_at=t_rec)
            renewed = time.time()


def recover(db, epoch, mode, seq, last, t_rec, note):
    """Feed every revision committed by t_rec that the feed lacks, then reopen the stream at t_rec."""
    note(ev='recovery_start', epoch=epoch, t_rec=[t_rec.time, t_rec.inc])
    have = {e['change'] for e in db.feed.find({}, {'change': 1})}
    scanned, after = [], None
    while True:  # one snapshot at t_rec, paged by _id: each page is its own find at the same cluster time
        r = db.command('find', 'revisions', filter={'_id': {'$gt': after}} if after else {}, sort={'_id': 1},
                       limit=10000, singleBatch=True, readConcern={'level': 'snapshot', 'atClusterTime': t_rec})
        page = r['cursor']['firstBatch']
        if not page:
            break
        scanned += page
        after = page[-1]['_id']
    missing = sorted((d for d in scanned if d['_id'] not in have), key=lambda d: (d['doc'], d['rev']))
    note(ev='recovery_scanned', epoch=epoch, scanned=len(scanned), feed_had=len(have), missing=len(missing))
    if mode == 'derived':  # backfilled changes have no event: mint positions at t_rec, before every event the reopened stream brings
        last = [t_rec.time, t_rec.inc, -1]
    chunks = [missing[i:i + 500] for i in range(0, len(missing), 500)] or [[]]
    for i, chunk in enumerate(chunks):
        at, entries, seq_cur, last_cur = time.time(), [], seq, last
        for d in chunk:
            if mode != 'derived':
                pos, seq_cur, last_cur = position(mode, seq_cur, last_cur, None, epoch)
            else:
                last_cur = [last_cur[0], last_cur[1], last_cur[2] + 1]
                pos = '%010d%010d%06d' % tuple(last_cur)
            entries.append(dict(_id=pos, change=d['_id'], doc=d['doc'], rev=d['rev'], epoch=epoch, ct=None, txn=None,
                                src='backfill', at=at))
        with db.client.start_session() as s:
            def cb(s, entries=entries, seq_cur=seq_cur, last_cur=last_cur):
                r = db.lease.update_one({'_id': 'tailer', 'epoch': epoch}, {'$set': dict(
                    token=None, start_at=t_rec, seq=seq_cur, last=last_cur)}, session=s)
                if r.matched_count == 0:
                    raise Fenced()
                if entries:
                    db.feed.insert_many(entries, session=s)
            s.with_transaction(cb, write_concern=WriteConcern('majority'))
        seq, last = seq_cur, last_cur
        db.lease.update_one({'_id': 'tailer', 'epoch': epoch}, {'$set': {'expires': time.time() + TTL}})
    note(ev='reopened', epoch=epoch, t_rec=[t_rec.time, t_rec.inc], backfilled=len(missing))
    return seq, last


def reader(major, parent, out, cursor_file):
    """Appends what it read, then saves the cursor: a crash between the two re-reads a page, never skips one."""
    client = MongoClient(uri(major))
    feed = client.kp240.get_collection('feed', read_concern=ReadConcern('majority'))
    pos = json.loads(Path(cursor_file).read_text()) if Path(cursor_file).exists() else None
    with open(out, 'a') as f:
        f.write(json.dumps(dict(incarnation=os.getpid(), cursor=pos, at=time.time())) + '\n')
        while True:
            orphan_exit(parent)
            rows = list(feed.find({'_id': {'$gt': pos}} if pos is not None else {}).sort('_id', 1).limit(100))
            now = time.time()
            for r in rows:
                f.write(json.dumps(dict(pos=r['_id'], change=r['change'], doc=r['doc'], rev=r['rev'], src=r['src'],
                                        epoch=r['epoch'], wrote=r['at'], at=now)) + '\n')
                pos = r['_id']
            f.flush()
            os.fsync(f.fileno())
            if rows:
                tmp = Path(str(cursor_file) + '.tmp')
                tmp.write_text(json.dumps(pos))
                os.replace(tmp, cursor_file)
            else:
                time.sleep(.020)


def members(major):
    base = {7: 3707, 8: 3708, 9: 3709, 6: 3706}[major]
    return [MongoClient('localhost:%d%d' % (base, i), directConnection=True) for i in (1, 2, 3)]


def oldest_oplog(m):
    return m['local']['oplog.rs'].find({}, {'ts': 1}).sort('$natural', 1).limit(1).next()['ts']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--major', type=int, default=8)
    p.add_argument('--position', choices=['seq', 'derived', 'epochseq'], required=True)
    p.add_argument('--control', choices=['none', 'nofence', 'norecover'], default='none')
    p.add_argument('--fence', choices=['first', 'last'], default='first')
    p.add_argument('--faults', default='', help='comma list of fault@seconds, e.g. kill@20,stop@40,reader@60,oplog@80')
    p.add_argument('--seed', type=int, default=24001)
    p.add_argument('--writers', type=int, default=8)
    p.add_argument('--transactions', type=int, default=400, help='per writer')
    p.add_argument('--docs', type=int, default=2000, help='Documents the writers pick from')
    p.add_argument('--scale', type=float, default=1.0, help='multiplies the random sleeps (not the 3 s ones)')
    p.add_argument('--rate', type=float, default=0, help='per-writer transactions per second; 0 = unpaced')
    p.add_argument('--out', required=True, help='directory for the raw record')
    a = p.parse_args()
    faults = sorted((float(x.split('@')[1]), x.split('@')[0]) for x in a.faults.split(',') if x)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cursor_file, deliveries, tlog, flog = out / 'cursor.json', out / 'deliveries.jsonl', out / 'tailers.jsonl', out / 'faults.jsonl'
    for f in (cursor_file, deliveries, tlog, flog):
        f.unlink(missing_ok=True)
    flog.touch()
    client = MongoClient(uri(a.major), w='majority')
    version = client.server_info()['version']
    client.drop_database('kp240')
    client.drop_database('kp240_filler')
    db = client.kp240
    for c in ('documents', 'revisions', 'feed', 'lease'):
        db.create_collection(c)
    db.feed.create_index('change')
    if any(f == 'oplog' for _, f in faults):
        for m in members(a.major):  # the smallest oplog allowed, so the filler outruns it quickly
            m.admin.command('replSetResizeOplog', 1, size=990.0)
    with client.start_session() as s:
        db.lease.insert_one(dict(_id='tailer', epoch=0, owner=None, expires=0, seq=0, last=None, token=None), session=s)
        db.lease.update_one({'_id': 'tailer'}, {'$set': {'start_at': s.operation_time}}, session=s)
        run_start = s.operation_time

    run = os.urandom(4).hex()  # a per-run prefix: a stray writer from another run shows up as foreign, never as a collision
    ctx, parent = mp.get_context('spawn'), os.getpid()
    procs = {}

    def start(key, target, *args):
        procs[key] = ctx.Process(target=target, args=args)
        procs[key].start()
        (out / 'children.pid').write_text(' '.join(str(x.pid) for x in procs.values()))
        return procs[key]

    def fault_note(**kw):
        with open(flog, 'a') as f:
            f.write(json.dumps(dict(kw, t=time.time()), default=str) + '\n')

    def holder():
        owner = db.lease.find_one({'_id': 'tailer'})['owner']
        return next(k for k, pr in procs.items() if k.startswith('tailer') and owner and owner.endswith(':%d' % pr.pid)), owner

    def wait_epoch_change(epoch, limit=90):
        until = time.time() + limit
        while time.time() < until:
            e = db.lease.find_one({'_id': 'tailer'})['epoch']
            if e != epoch:
                return e
            time.sleep(.05)
        return None

    try:
        start('reader', reader, a.major, parent, deliveries, cursor_file)
        for slot in 'AB':
            start('tailer' + slot, tailer, a.major, slot, a.position, a.control, a.fence, parent, tlog)
        time.sleep(2)
        t0 = time.time() + 1
        writers = [start('writer%d' % w, writer, a.major, run, w, a.seed, a.transactions, a.docs, a.scale, a.rate, t0,
                         parent, out / ('writer-%d.jsonl' % w)) for w in range(a.writers)]
        pending = list(faults)
        while any(w.is_alive() for w in writers):
            time.sleep(.1)
            if not pending or time.time() - t0 < pending[0][0]:
                continue
            _, kind = pending.pop(0)
            epoch = db.lease.find_one({'_id': 'tailer'})['epoch']
            if kind == 'kill':
                key, owner = holder()
                os.kill(procs[key].pid, signal.SIGKILL)
                t = time.time()
                procs[key].join()
                start(key, tailer, a.major, key[-1], a.position, a.control, a.fence, parent, tlog)
                fault_note(fault='kill', victim=owner, epoch=epoch, at=t, next_epoch=wait_epoch_change(epoch))
            elif kind == 'stop':
                key, owner = holder()
                os.kill(procs[key].pid, signal.SIGSTOP)
                t = time.time()
                nxt = wait_epoch_change(epoch)
                time.sleep(2)  # the new holder writes for a while before the old one wakes
                os.kill(procs[key].pid, signal.SIGCONT)
                fault_note(fault='stop', victim=owner, epoch=epoch, at=t, next_epoch=nxt, resumed=time.time())
            elif kind == 'freeze':
                key, owner = holder()
                os.kill(procs[key].pid, signal.SIGUSR1)
                t, until = None, time.time() + 10
                while t is None and time.time() < until:
                    time.sleep(.05)
                    t = next((x['t'] for x in lines(tlog)[::-1] if x['ev'] == 'frozen' and x['tailer'] == owner), None)
                    t = t if t and t > until - 10 else None
                nxt = wait_epoch_change(epoch, limit=150) if t else None
                until = time.time() + 150
                while nxt and time.time() < until and not db.feed.find_one({'epoch': nxt}):
                    time.sleep(.05)
                time.sleep(2)
                os.kill(procs[key].pid, signal.SIGCONT)
                fault_note(fault='freeze', victim=owner, epoch=epoch, at=t, next_epoch=nxt, resumed=time.time())
            elif kind == 'reader':
                os.kill(procs['reader'].pid, signal.SIGKILL)
                t = time.time()
                procs['reader'].join()
                time.sleep(2)
                start('reader', reader, a.major, parent, deliveries, cursor_file)
                fault_note(fault='reader', at=t)
            elif kind == 'oplog':
                t = time.time()
                for slot in 'AB':
                    os.kill(procs['tailer' + slot].pid, signal.SIGKILL)
                    procs['tailer' + slot].join()
                with client.start_session() as s:  # every resume point the dead tailers could hold is at or before this
                    db.lease.find_one({'_id': 'tailer'}, session=s)
                    stopped_at = s.cluster_time['clusterTime']
                filler, pad, written = client.kp240_filler.filler, 'x' * (1 << 20), 0
                ms, n = members(a.major), 0
                # the oplog is truncated only behind the last checkpoint (every 60 s), so this runs for a minute or more;
                # replacing 16 documents keeps the filler collection small while every replacement lands in the oplog
                while not all(oldest_oplog(m) > stopped_at for m in ms):
                    if time.time() - t > FILL_LIMIT:
                        raise SystemExit('oplog fault: %d bytes of filler in %d s did not overwrite the resume point' % (written, FILL_LIMIT))
                    filler.replace_one({'_id': n % 16}, {'pad': pad}, upsert=True)
                    n, written = n + 1, written + (1 << 20)
                    time.sleep(.01)
                filled = time.time()
                client.drop_database('kp240_filler')
                for slot in 'AB':
                    start('tailer' + slot, tailer, a.major, slot, a.position, a.control, a.fence, parent, tlog)
                fault_note(fault='oplog', at=t, stopped_at=[stopped_at.time, stopped_at.inc], filler_bytes=written,
                           filled=filled, restarted=time.time(), oldest=[str(oldest_oplog(m)) for m in ms])
        errors = ['%s exit %s' % (k, pr.exitcode) for k, pr in procs.items() if k.startswith('writer') and pr.exitcode != 0]
        errors += ['fault %s@%s never ran' % (k, t) for t, k in pending]

        attempts = [x for w in range(a.writers) for x in lines(out / ('writer-%d.jsonl' % w))]
        committed = {rid: (doc, rev, x['end']) for x in attempts if not x['rollback'] for rid, doc, rev in x['changes']}
        deadline, size, still = time.time() + 180, -1, time.time()
        while time.time() < deadline:  # drain: every committed change read by the reader, or nothing new for 15 s
            got = {d['change'] for d in lines(deliveries) if 'change' in d}
            if set(committed) <= got:
                break
            if len(got) != size:
                size, still = len(got), time.time()
            elif time.time() - still > 15:
                break
            time.sleep(1)
    finally:
        for pr in procs.values():
            if pr.is_alive():
                os.kill(pr.pid, signal.SIGCONT)
                os.kill(pr.pid, signal.SIGKILL)
                pr.join()
    summary = dict(version=version, position=a.position, control=a.control, fence=a.fence, faults=a.faults, seed=a.seed,
                   writers=a.writers, transactions=a.transactions, docs=a.docs, scale=a.scale, rate_per_writer=a.rate,
                   wall_seconds=round(time.time() - t0, 1), errors=errors, run=run,
                   **check(db, run, attempts, committed, lines(deliveries), lines(tlog), lines(flog)),
                   **({} if any(f == 'oplog' for _, f in faults) else oplog_usage(client, run_start, len(committed))))
    (out / 'summary.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary), flush=True)


def oplog_usage(client, since, committed):
    """Oplog bytes written since the run began, by the namespace of the operation (a transaction's first one)."""
    rows = client['local']['oplog.rs'].aggregate([
        {'$match': {'ts': {'$gte': since}}},
        {'$group': {'_id': {'$ifNull': [{'$arrayElemAt': ['$o.applyOps.ns', 0]}, '$ns']},
                    'entries': {'$sum': 1}, 'bytes': {'$sum': {'$bsonSize': '$$ROOT'}}}}])
    by_ns = {r['_id']: [r['entries'], r['bytes']] for r in rows}
    side = lambda *ns: sum(by_ns.get(n, [0, 0])[1] for n in ns)
    return dict(oplog_by_ns=by_ns, oplog_bytes_per_change_writers=round(side('kp240.documents', 'kp240.revisions') / committed),
                oplog_bytes_per_change_tailer=round(side('kp240.feed', 'kp240.lease') / committed))


def check(db, run, attempts, committed, deliveries, tlog, flog):
    truth = {d['_id'] for d in db.get_collection('revisions', read_concern=ReadConcern('majority')).find({}, {'_id': 1})}
    feed = list(db.get_collection('feed', read_concern=ReadConcern('majority')).find().sort('_id', 1))
    ours = [e for e in feed if e['change'].startswith(run + '-')]
    per_change = Counter(e['change'] for e in ours)

    def order_violations(rows):  # per Document, revisions must come in commit order: 1, 2, 3, ...
        seen, bad = defaultdict(int), 0
        for r in rows:
            if r['rev'] <= seen[r['doc']]:
                bad += 1
            seen[r['doc']] = max(seen[r['doc']], r['rev'])
        return bad

    # the reader: positions strictly rise within one incarnation; a page re-read after a crash is a redelivery, not a duplicate
    first, regressions, prev, redelivered = {}, 0, None, 0
    for d in deliveries:
        if 'incarnation' in d:
            prev = d['cursor']
            continue
        if prev is not None and d['pos'] <= prev:
            regressions += 1
        prev = d['pos']
        if d['pos'] in first:
            redelivered += 1
        else:
            first[d['pos']] = d
    read = list(first.values())
    read_changes = Counter(d['change'] for d in read)
    delivered_at = {d['change']: d['at'] for d in read}
    wrote_at = {e['change']: e['at'] for e in ours}

    # fencing: an entry written under epoch e after epoch e+1 was acquired came from a tailer that had lost its lease
    acquired = {x['epoch']: x['t'] for x in tlog if x['ev'] == 'acquired'}
    zombie = sum(1 for e in ours if e['epoch'] + 1 in acquired and e['at'] > acquired[e['epoch'] + 1])
    failover = []
    for f in flog:
        if f['fault'] in ('kill', 'stop', 'freeze') and f.get('next_epoch'):
            firsts = [e['at'] for e in ours if e['epoch'] == f['next_epoch']]
            reads = [d['at'] for d in read if d['epoch'] == f['next_epoch']]
            # first_write_after is when the new holder formed its first batch, first_read_after when that batch was readable
            failover.append(dict(fault=f['fault'], acquired_after=round(acquired[f['next_epoch']] - f['at'], 2),
                                 first_write_after=round(min(firsts) - f['at'], 2) if firsts else None,
                                 first_read_after=round(min(reads) - f['at'], 2) if reads else None))
    txn_ct = defaultdict(set)
    for e in ours:
        if e['src'] == 'stream':
            txn_ct[e['txn']].add((e['ct'].time, e['ct'].inc))
    recovery = [x for x in tlog if x['ev'].startswith('recovery') or x['ev'] in ('history_lost', 'reopened')]
    lost = [x['t'] for x in tlog if x['ev'] == 'history_lost']
    reopened = [x['t'] for x in tlog if x['ev'] == 'reopened']
    backfill_read = [d for d in read if d['src'] == 'backfill']
    commit_end = {rid: end for rid, (_, _, end) in committed.items()}
    to_feed = [wrote_at[r] - commit_end[r] for r in committed if r in wrote_at]
    to_reader = [delivered_at[r] - commit_end[r] for r in committed if r in delivered_at]
    span = max(x['end'] for x in attempts) - min(x['start'] for x in attempts)
    behind = [x['behind'] for x in attempts]
    return dict(
        committed=len(committed), revisions_match_writers={t for t in truth if t.startswith(run + '-')} == set(committed),
        foreign_in_feed=len(feed) - len(ours), feed_entries=len(ours),
        feed_missed=len(set(committed) - set(per_change)), feed_duplicates=sum(n - 1 for n in per_change.values()),
        feed_unexpected=len(set(per_change) - set(committed)), feed_order_violations=order_violations(ours),
        read_missed=len(set(committed) - set(read_changes)), read_duplicates=sum(n - 1 for n in read_changes.values()),
        read_order_violations=order_violations(read), read_position_regressions=regressions, read_redelivered=redelivered,
        reader_incarnations=sum(1 for d in deliveries if 'incarnation' in d),
        epochs=len(acquired), fenced=sum(1 for x in tlog if x['ev'] == 'fenced'),
        lease_lost=sum(1 for x in tlog if x['ev'] == 'lease_lost'), tailer_errors=[x for x in tlog if x['ev'] == 'error'], zombie_entries_accepted=zombie, failover=failover,
        txn_with_split_cluster_time=sum(1 for v in txn_ct.values() if len(v) > 1),
        multi_change_txns=sum(1 for x in attempts if not x['rollback'] and len(x['changes']) > 1),
        recovery_seconds=round(reopened[0] - lost[0], 2) if lost and reopened else None,
        backfilled=sum(1 for e in ours if e['src'] == 'backfill'),
        backfill_read=len(backfill_read),
        backfill_read_window=[round(min(d['at'] for d in backfill_read) - lost[0], 2),
                              round(max(d['at'] for d in backfill_read) - lost[0], 2)] if backfill_read and lost else None,
        recovery_log=recovery, faults_log=flog,
        tries_max=max(x['tries'] for x in attempts), tries_mean=round(sum(x['tries'] for x in attempts) / len(attempts), 2),
        events_per_second=round(len(committed) / span, 2),
        behind_schedule_p50=percentile(behind, .5), behind_schedule_p99=percentile(behind, .99), behind_schedule_max=percentile(behind, 1),
        commit_to_feed_p50=percentile(to_feed, .5), commit_to_feed_p99=percentile(to_feed, .99), commit_to_feed_max=percentile(to_feed, 1),
        commit_to_read_p50=percentile(to_reader, .5), commit_to_read_p99=percentile(to_reader, .99), commit_to_read_max=percentile(to_reader, 1),
    )


if __name__ == '__main__':
    main()
