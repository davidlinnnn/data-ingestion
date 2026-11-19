"""PROTOTYPE (#236) experiment 4: acknowledged admission writes survive a primary failure.

Writers commit "document + request" transactions with write concern majority
while the primary is killed (SIGKILL, restarted later) or stepped down. After
all members are back, every acknowledged request must be readable with read
concern majority. Prints one line per fault and writes the raw record.
"""
import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

from pymongo import MongoClient, WriteConcern
from pymongo.read_concern import ReadConcern

HERE = Path(__file__).resolve().parent


def uri(major):
    base = {7: 3707, 8: 3708, 9: 3709, 6: 3706}[major]  # 6 = the scratch set, rs.sh s
    hosts = ','.join('localhost:%d%d' % (base, i) for i in (1, 2, 3))
    return 'mongodb://%s/?replicaSet=rs0' % hosts


def rs(*args):
    args = ['s' if a == 6 else a for a in args]  # the scratch set is 6 here, s in rs.sh
    return subprocess.run([str(HERE / 'rs.sh'), *map(str, args)], check=True,
                          capture_output=True, text=True).stdout.strip()


def writer(client, worker, stop, acks, errors):
    db = client.kp236
    n = 0
    while not stop.is_set():
        rid = 'w%d-%d' % (worker, n)
        n += 1
        started = time.time()

        def txn(session):
            db.documents.update_one({'_id': 'd%d' % worker}, {'$inc': {'v': 1}}, upsert=True, session=session)
            db.requests.insert_one({'_id': rid, 'document_uid': 'd%d' % worker, 'state': 'queued',
                                    'dispatch': {'available_at': started, 'attempts': 0}}, session=session)
        try:
            with client.start_session() as session:
                session.with_transaction(txn, write_concern=WriteConcern('majority'))
            acks.append((rid, started, time.time()))
        except Exception as exc:  # the write is unacknowledged; the experiment records it
            errors.append((rid, started, time.time(), type(exc).__name__, str(exc)[:200]))


def wait_healthy(client, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            states = [m['stateStr'] for m in client.admin.command('replSetGetStatus')['members']]
            if sorted(states) == ['PRIMARY', 'SECONDARY', 'SECONDARY']:
                return states
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError('replica set not healthy after %d s' % timeout)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--major', type=int, required=True)
    p.add_argument('--mode', choices=['kill', 'stepdown'], required=True)
    p.add_argument('--rounds', type=int, default=1)
    p.add_argument('--writers', type=int, default=4)
    p.add_argument('--down-seconds', type=float, default=15)
    p.add_argument('--out', default=None)
    a = p.parse_args()

    client = MongoClient(uri(a.major), w='majority')
    version = client.server_info()['version']
    client.drop_database('kp236')
    client.kp236.create_collection('documents')
    client.kp236.create_collection('requests')
    wait_healthy(client)

    stop = threading.Event()
    acks, errors, faults = [], [], []
    threads = [threading.Thread(target=writer, args=(client, w, stop, acks, errors), daemon=True) for w in range(a.writers)]
    for t in threads:
        t.start()
    time.sleep(3)
    for r in range(a.rounds):
        old = rs('primary', a.major)
        print('round %d: fault on %s' % (r, old), flush=True)
        t_fault = time.time()
        if a.mode == 'kill':
            rs('kill', a.major, old)
            time.sleep(a.down_seconds)
            rs('start', a.major, old)
        else:
            rs('stepdown', a.major)
        wait_healthy(client)
        # a stepped-down member cannot run for 10 s (rs.sh); wait it out so the next round has a choice
        time.sleep(3 if a.mode == 'kill' else 12)
        faults.append(dict(round=r, old_primary=old, new_primary=rs('primary', a.major), at=t_fault))
        print('round %d: %s -> %s' % (r, old, faults[-1]['new_primary']), flush=True)
    stop.set()
    for t in threads:
        t.join()

    # Rolled-back writes on a rejoined member surface only after it catches up; read from the primary.
    requests = client.kp236.get_collection('requests', read_concern=ReadConcern('majority'))
    present = {d['_id'] for d in requests.find({}, {'_id': 1})}
    acked = {rid for rid, _, _ in acks}
    errored = {rid for rid, *_ in errors}
    ends = [f['at'] for f in faults[1:]] + [max(end for _, _, end in acks)]
    for f, until in zip(faults, ends):  # a round's window ends where the next fault starts
        done = sorted(end for _, _, end in acks if f['at'] < end <= until)
        before = max((end for _, _, end in acks if end <= f['at']), default=f['at'])
        window = [before] + done
        f['max_ack_gap_seconds'] = round(max(b - a_ for a_, b in zip(window, window[1:])), 3) if len(window) > 1 else None
        f['errors'] = sum(1 for _, s, e, *_ in errors if f['at'] - 1 <= e <= until)
        f['failed_over'] = f['old_primary'] != f['new_primary']
        print(json.dumps(f), flush=True)
    summary = dict(version=version, mode=a.mode, rounds=a.rounds, writers=a.writers,
                   acked=len(acked), acked_missing=len(acked - present),
                   errored=len(errored), errored_but_present=len(errored & present),
                   present=len(present), error_types=sorted({e[3] for e in errors}),
                   max_ack_gap_seconds=max((f['max_ack_gap_seconds'] or 0) for f in faults),
                   rounds_without_failover=sum(1 for f in faults if not f['failed_over']))
    print(json.dumps(summary), flush=True)
    if a.out:
        Path(a.out).write_text(json.dumps(dict(summary=summary, faults=faults, errors=errors,
                                               acks=acks, missing=sorted(acked - present)), indent=1))
    assert summary['acked_missing'] == 0, 'acknowledged writes lost'
    assert summary['rounds_without_failover'] == 0, 'a fault did not move the primary'


if __name__ == '__main__':
    main()
