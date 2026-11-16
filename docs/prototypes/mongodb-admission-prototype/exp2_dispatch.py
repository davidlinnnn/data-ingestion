"""PROTOTYPE (#236) experiment 2: dispatcher claim without a separate outbox.

The dispatch fields live in the request document. Dispatchers claim one
request at a time with an atomic find_one_and_update that sets a lease, start
the "workflow" (a collection keyed by request_id standing in for Temporal's
workflow ID with REJECT_DUPLICATE; a duplicate counts as success), then mark
the request dispatched. A fake worker completes workflows after a random time.
Before claiming, a dispatcher counts in-flight requests (live lease, or
dispatched and not done) against a global budget; the count and the claim are
not atomic, so the expected overshoot is at most (dispatchers - 1).

Two dispatchers are SIGKILLed: one after a claim and before the start, one
after the start and before the mark. Their leases must expire and another
dispatcher must finish the request.
"""
import argparse
import json
import multiprocessing as mp
import os
import random
import signal
import time
from pathlib import Path

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

from exp4_durability import uri


def in_flight(db, now):
    return db.requests.count_documents({'state': {'$ne': 'done'}, '$or': [
        {'dispatch.lease_until': {'$gt': now}}, {'dispatch.dispatched_at': {'$ne': None}}]})


def dispatcher(major, me, budget, lease, crash, log):
    db = MongoClient(uri(major), w='majority').kp236
    rng = random.Random(me)
    claims = 0
    with open(log, 'a') as f:
        def event(**e):
            f.write(json.dumps(dict(owner=me, at=time.time(), **e)) + '\n')
            f.flush()
        while True:
            now = time.time()
            if in_flight(db, now) >= budget:
                time.sleep(.005)
                continue
            r = db.requests.find_one_and_update(
                # not on state: a workflow can finish before its dispatcher marks it; re-starting is a duplicate
                {'dispatch.dispatched_at': None, 'dispatch.available_at': {'$lte': now},
                 '$or': [{'dispatch.lease_until': None}, {'dispatch.lease_until': {'$lte': now}}]},
                {'$set': {'dispatch.lease_until': now + lease, 'dispatch.owner': me}, '$inc': {'dispatch.attempts': 1}},
                sort=[('priority', 1), ('dispatch.available_at', 1)], return_document=ReturnDocument.AFTER)
            if r is None:
                if db.requests.count_documents({'dispatch.dispatched_at': None}) == 0:
                    return
                time.sleep(.010)
                continue
            claims += 1
            rid = r['_id']
            event(kind='claim', rid=rid, lease_until=now + lease)
            if crash == ('claimed', claims):
                os.kill(os.getpid(), signal.SIGKILL)
            time.sleep(rng.uniform(0, .005))  # the Temporal start call
            try:
                db.workflows.insert_one({'_id': rid, 'started_at': time.time(), 'by': me,
                                         'complete_at': time.time() + rng.uniform(.05, .3)})
                event(kind='start', rid=rid)
            except DuplicateKeyError:
                event(kind='start_duplicate', rid=rid)
            if crash == ('started', claims):
                os.kill(os.getpid(), signal.SIGKILL)
            done = db.requests.update_one({'_id': rid, 'dispatch.owner': me},
                                          {'$set': {'dispatch.dispatched_at': time.time()}})
            event(kind='mark' if done.modified_count else 'mark_lost', rid=rid)


def completer(major, stop_when):
    """The fake Temporal worker: a workflow finishes at complete_at and records the outcome."""
    db = MongoClient(uri(major), w='majority').kp236
    while True:
        now = time.time()
        for w in db.workflows.find({'complete_at': {'$lte': now}, 'done_at': None}):
            db.workflows.update_one({'_id': w['_id']}, {'$set': {'done_at': now}})
            db.requests.update_one({'_id': w['_id']}, {'$set': {'state': 'done', 'done_at': now}})
        if db.requests.count_documents({'state': {'$ne': 'done'}}) == 0:
            return
        time.sleep(.010)


def max_overlap(segments):
    points = sorted([(s, 1) for s, e in segments] + [(e, -1) for s, e in segments])
    level = peak = 0
    for _, d in points:
        level += d
        peak = max(peak, level)
    return peak


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--major', type=int, required=True)
    p.add_argument('--requests', type=int, default=1000)
    p.add_argument('--dispatchers', type=int, default=2)
    p.add_argument('--budget', type=int, default=20)
    p.add_argument('--lease', type=float, default=5.0)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = out / 'events.jsonl'
    log.unlink(missing_ok=True)

    client = MongoClient(uri(a.major), w='majority')
    version = client.server_info()['version']
    client.drop_database('kp236')
    db = client.kp236
    db.requests.create_index([('dispatch.dispatched_at', 1), ('priority', 1), ('dispatch.available_at', 1)])
    t0 = time.time()
    db.requests.insert_many([{'_id': 'r%04d' % i, 'state': 'queued', 'priority': i % 3,
                              'dispatch': {'available_at': t0, 'lease_until': None, 'owner': None,
                                           'attempts': 0, 'dispatched_at': None}} for i in range(a.requests)])

    ctx = mp.get_context('spawn')
    crashes = {0: ('claimed', 100), 1: ('started', 150)}  # 4 dispatchers make about 250 claims each  # (phase, n-th claim of that dispatcher)
    procs = {}

    def spawn(i, crash):
        procs[i] = ctx.Process(target=dispatcher, args=(a.major, 'd%d-%d' % (i, len(restarts)), a.budget, a.lease, crash, log))
        procs[i].start()

    restarts = []
    for i in range(a.dispatchers):
        spawn(i, crashes.get(i))
    comp = ctx.Process(target=completer, args=(a.major, None))
    comp.start()
    while comp.is_alive():
        for i, pr in list(procs.items()):
            if not pr.is_alive() and pr.exitcode == -signal.SIGKILL:
                restarts.append(dict(dispatcher=i, at=time.time(), crash=crashes.get(i)))
                print('dispatcher %d killed (%s); restarting it' % (i, crashes.get(i)), flush=True)
                crashes.pop(i, None)
                spawn(i, None)
        time.sleep(.1)
        if time.time() - t0 > 600:
            raise SystemExit('timed out')
    for pr in procs.values():
        pr.join(timeout=30)

    events = [json.loads(x) for x in log.read_text().splitlines()]
    wf = list(db.workflows.find())
    reqs = list(db.requests.find())
    # an in-flight segment per claim: until done if this claim's owner marked it, else until its lease ended
    marked = {(e['rid'], e['owner']) for e in events if e['kind'] == 'mark'}
    done_at = {r['_id']: r['done_at'] for r in reqs}
    segments = [(e['at'], done_at[e['rid']] if (e['rid'], e['owner']) in marked else e['lease_until'])
                for e in events if e['kind'] == 'claim']
    crashed = [e for e in events if e['kind'] == 'claim' and (e['rid'], e['owner']) not in marked
               and not any(x['kind'] == 'mark_lost' and x['rid'] == e['rid'] and x['owner'] == e['owner'] for x in events)]
    redispatch = [dict(rid=e['rid'], first_owner=e['owner'],
                       reclaimed_after=round(min(x['at'] for x in events if x['kind'] == 'claim' and x['rid'] == e['rid'] and x['at'] > e['at']) - e['at'], 3))
                  for e in crashed]
    summary = dict(
        version=version, requests=a.requests, dispatchers=a.dispatchers, budget=a.budget, lease_seconds=a.lease,
        wall_seconds=round(time.time() - t0, 1), restarts=restarts,
        workflows=len(wf), requests_with_one_workflow=len({w['_id'] for w in wf} & {r['_id'] for r in reqs}),
        all_dispatched=all(r['dispatch']['dispatched_at'] for r in reqs), all_done=all(r['state'] == 'done' for r in reqs),
        start_calls=sum(1 for e in events if e['kind'] in ('start', 'start_duplicate')),
        start_duplicates=sum(1 for e in events if e['kind'] == 'start_duplicate'),
        claims=sum(1 for e in events if e['kind'] == 'claim'), mark_lost=sum(1 for e in events if e['kind'] == 'mark_lost'),
        crashed_claims=redispatch, in_flight_peak=max_overlap(segments),
        in_flight_overshoot=max(0, max_overlap(segments) - a.budget),
    )
    (out / 'summary.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary), flush=True)
    assert summary['workflows'] == a.requests == summary['requests_with_one_workflow'] and summary['all_dispatched']
    assert summary['in_flight_overshoot'] <= a.dispatchers - 1


if __name__ == '__main__':
    main()
