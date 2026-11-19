"""PROTOTYPE (#236) experiment 3: concurrent finalize of one Document.

N concurrent finalizes of the same Document. Each is one transaction: write
the document (the stand-in for PostgreSQL's row lock: a concurrent writer gets
a write conflict and retries), find the Source Revision by content, reuse an
active process request for it or insert one. A partial unique index on
(document_uid, source_revision_id) over active process requests backs it up.
A completer finishes active requests while finalizes run, so new requests keep
being created; a sampler reads every active request in one snapshot and
records the largest count per key.

  --variant guarded   document write + partial unique index (the design)
  --variant control   neither, revisions pre-created (positive control: expected to exceed one)
"""
import argparse
import collections
import json
import random
import threading
import time
from pathlib import Path

from pymongo import MongoClient, WriteConcern
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.read_concern import ReadConcern

from exp4_durability import uri

ACTIVE = {'kind': 'process', 'state': {'$in': ['queued', 'processing']}}


def finalize(client, variant, n, content, results):
    db = client.kp236
    tries, t0 = 0, time.time()
    while True:
        tries += 1
        try:
            with client.start_session() as s:
                s.start_transaction(write_concern=WriteConcern('majority'))
                if variant == 'guarded':
                    db.documents.update_one({'_id': 'doc'}, {'$inc': {'finalizations': 1}}, session=s)
                rev = 'rev-%s' % content
                if variant == 'guarded':  # the control only reads it: an upsert of one document also serializes
                    db.source_revisions.update_one({'_id': rev}, {'$setOnInsert': {'document_uid': 'doc'}},
                                                   upsert=True, session=s)
                active = db.requests.find_one(dict(ACTIVE, document_uid='doc', source_revision_id=rev), session=s)
                time.sleep(random.uniform(0, .010))  # the rest of the admission checks
                if active is None:
                    db.requests.insert_one({'_id': 'q%d-%d' % (n, tries), 'kind': 'process', 'state': 'queued',
                                            'document_uid': 'doc', 'source_revision_id': rev}, session=s)
                outcome = 'created' if active is None else 'reused'
                s.commit_transaction()
            break
        except DuplicateKeyError:
            # the index refused a second active request: retrying reads the one that won
            continue
        except PyMongoError as exc:
            if not exc.has_error_label('TransientTransactionError') or time.time() - t0 > 120:
                results.append(dict(n=n, error=repr(exc)[:200], tries=tries))
                return
    results.append(dict(n=n, content=content, outcome=outcome, tries=tries, seconds=round(time.time() - t0, 4)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--major', type=int, required=True)
    p.add_argument('--variant', choices=['guarded', 'control'], required=True)
    p.add_argument('--finalizes', type=int, default=100)
    p.add_argument('--contents', type=int, default=1, help='distinct contents among the finalizes')
    p.add_argument('--out', required=True)
    a = p.parse_args()

    client = MongoClient(uri(a.major), w='majority')
    version = client.server_info()['version']
    client.drop_database('kp236')
    db = client.kp236
    for c in ('documents', 'source_revisions', 'requests'):
        db.create_collection(c)
    db.documents.insert_one({'_id': 'doc', 'finalizations': 0})
    if a.variant == 'control':
        db.source_revisions.insert_many([{'_id': 'rev-%d' % c, 'document_uid': 'doc'} for c in range(a.contents)])
    if a.variant == 'guarded':
        db.requests.create_index([('document_uid', 1), ('source_revision_id', 1)], unique=True,
                                 partialFilterExpression=ACTIVE, name='one_active_process')

    stop = threading.Event()
    peaks = collections.Counter()

    def completer():
        while not stop.is_set():
            r = db.requests.find_one(ACTIVE)
            if r:
                time.sleep(random.uniform(.005, .030))
                db.requests.update_one({'_id': r['_id']}, {'$set': {'state': 'done'}})
            time.sleep(.002)

    def sampler():
        while not stop.is_set():
            with client.start_session() as s:
                s.start_transaction(read_concern=ReadConcern('snapshot'))  # one consistent read
                counts = collections.Counter(r['source_revision_id'] for r in db.requests.find(ACTIVE, session=s))
                s.commit_transaction()
            for k, c in counts.items():
                peaks[k] = max(peaks[k], c)

    side = [threading.Thread(target=completer), threading.Thread(target=sampler)]
    for t in side:
        t.start()
    results, rng = [], random.Random(23603)
    barrier = threading.Barrier(a.finalizes)

    def go(n):
        barrier.wait()
        finalize(client, a.variant, n, rng.randrange(a.contents), results)
    threads = [threading.Thread(target=go, args=(n,)) for n in range(a.finalizes)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    time.sleep(.2)
    stop.set()
    for t in side:
        t.join()

    final = collections.Counter(r['source_revision_id'] for r in db.requests.find(ACTIVE))
    tries = collections.Counter(r['tries'] for r in results)
    summary = dict(
        version=version, variant=a.variant, finalizes=a.finalizes, contents=a.contents,
        wall_seconds=round(time.time() - t0, 2), errors=[r for r in results if 'error' in r],
        created=sum(1 for r in results if r.get('outcome') == 'created'),
        reused=sum(1 for r in results if r.get('outcome') == 'reused'),
        requests=db.requests.count_documents({}),
        sampled_max_active_per_revision=max(peaks.values(), default=0), final_max_active=max(final.values(), default=0),
        tries_histogram=dict(sorted(tries.items())), tries_max=max(tries), seconds_max=max(r.get('seconds', 0) for r in results),
    )
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(dict(summary=summary, results=results), indent=1))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
