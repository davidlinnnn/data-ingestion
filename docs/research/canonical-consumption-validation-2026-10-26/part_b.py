#!/usr/bin/env python3
"""Deterministic discrete-event model for ticket 55; no DB or third-party packages.

Time is integer milliseconds. The workload RNG is separate from scheduling RNG.
Safety is checked after every atomic event, including report loss/corruption.
See MODEL.md for abstraction boundaries and underspecified protocol choices.
"""
import argparse
from collections import Counter, deque
from copy import deepcopy
import hashlib
import heapq
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parent
VARIANTS = ['design', 'N1', 'N2', 'N3', 'N4', 'N5', 'N6']
INVARIANTS = ['S1', 'S2', 'S3', 'L1', 'L2', 'L3']
PROJECTIONS = ['retrieval', 'wiki']
DAY = 86400000


def workload(seed):
    r = random.Random(seed)
    actions = []
    def add(t, kind, *args):
        actions.append((t, kind, list(args)))
    # Every seed includes every requested scenario; relative timings vary.
    add(r.randint(20, 45), 'profile', 's1', 'wiki', True)
    add(r.randint(70, 100), 'profile', 's0', 'wiki', False)
    add(r.randint(130, 160), 'profile', 's0', 'wiki', True)
    for uid in ['d4', 'd5', 'd6', 'd7']:
        start = r.randint(25, 60)
        add(start, 'source_update', uid)
        add(start + r.randint(12, 25), 'method_refresh', uid)
        add(start + r.randint(30, 48), 'rollback', uid)
    add(r.randint(80, 140), 'delete', 'd0')
    add(r.randint(160, 220), 'delete', 'd3')
    t = r.randint(60, 85)
    add(t, 'withdraw', 'd1', True)
    add(t + r.randint(20, 45), 'withdraw', 'd1', False)
    add(r.randint(55, 90), 'rebind', 'd2', 'r1')
    add(r.randint(130, 175), 'rebind', 'd2', 'r0')
    for p in PROJECTIONS:
        add(r.randint(45, 80), 'build', p)
        add(r.randint(175, 210), 'switch', p)
        if r.random() < .5:
            add(r.randint(245, 275), 'switch_back', p)
        add(r.randint(330, 360), 'retire', p)
    for _ in range(28):
        uid = 'd' + str(r.randint(1, 7))
        kind = r.choice(['source_update', 'method_refresh', 'rollback', 'rebind', 'withdraw'])
        args = [uid]
        if kind == 'rebind':
            args.append(r.choice(['r0', 'r1']))
        elif kind == 'withdraw':
            args.append(r.choice([False, True]))
        add(r.randint(15, 300), kind, *args)
    # Both count-changing and count-preserving corruption are in the workload.
    add(235 + r.randint(0, 12), 'corrupt_drop')
    add(440 + r.randint(0, 12), 'corrupt_revision')
    return sorted(actions, key=lambda x: x[0])


class Simulation:
    def __init__(self, seed, variant='design', full_trace=False, actions=None):
        self.seed, self.variant = seed, variant
        self.r = random.Random(seed ^ 0x55A5A5)
        self.q, self.serial, self.time, self.steps = [], 0, 0, 0
        self.trace = [] if full_trace else deque(maxlen=20)
        self.full_trace = full_trace
        self.failures, self.witnesses = Counter(), {}
        self.metrics = Counter()
        self.unknown = None
        self.docs = {('d%d' % i): dict(uid='d%d' % i, source='s%d' % (i % 2),
                     resource='r0', source_revision=1, revision=i + 1,
                     previous=None, deleted=False, withdrawn=False)
                     for i in range(8)}
        self.next_revision = 8
        self.profiles = {'s0': set(PROJECTIONS), 's1': {'retrieval'}}
        self.profile_seq = {'s0': 0, 's1': 0}
        self.backfill_required = {('wiki', 's1'): None}
        self.backfill_complete = {(p, s): 0 for p in PROJECTIONS for s in self.profiles}
        self.feed, self.history = [], []
        self.record_history()
        self.projs = {p: dict(cursor=0, reported_cursor=0, poll=False,
                            dispatch=False, running={}, sources={}, candidate=None, original=p + '-0')
                      for p in PROJECTIONS}
        self.builds, self.facts = {}, {}
        self.snapshot_id = 0
        self.snapshots = {}
        self.repair_signatures = Counter()
        for p in PROJECTIONS:
            b = self.new_build(p, p + '-0', 'serving', initial=True)
            for uid in self.docs:
                desired = self.desired(uid, p)
                if desired is not None:
                    key = (uid, desired[0])
                    b['counter'] += 1
                    b['store'][key] = desired[1]
                    version = 1 if self.variant == 'N1' else b['counter']
                    b['versions'][key] = version
                    b['doc_counter'][uid] = 1
                    self.facts[(b['id'],) + key] = dict(included=True, revision=desired[1],
                        version=version, confirmed=True, expires=None)
                    b['last'][uid] = desired[1]
        self.actions = actions if actions is not None else workload(seed)
        self.workload_hash = hashlib.sha256(json.dumps(self.actions).encode()).hexdigest()
        for t, kind, args in self.actions:
            self.at(t, 'action', kind, args)
        self.at(17, 'heartbeat')

    def at(self, t, kind, *args):
        assert t >= self.time
        self.serial += 1
        heapq.heappush(self.q, (t, self.serial, kind, args))

    def later(self, delay, kind, *args):
        self.at(self.time + delay, kind, *args)

    def log(self, text):
        self.trace.append('%04d %s' % (self.time, text))

    def fail(self, invariant, detail):
        self.failures[invariant] += 1
        if invariant not in self.witnesses:
            self.witnesses[invariant] = dict(seed=self.seed, variant=self.variant,
                time=self.time, step=self.steps, detail=detail, trace=list(self.trace)[-20:])

    def record_history(self):
        self.history.append((deepcopy(self.docs), deepcopy(self.profiles)))

    def current(self, uid):
        d = self.docs[uid]
        return None if d['deleted'] or d['withdrawn'] else d['revision']

    def blocked(self, uid, resource):
        d = self.docs[uid]
        # A binding mismatch represents the immediate moved-out block for old R.
        return d['deleted'] or d['withdrawn'] or d['resource'] != resource

    def desired(self, uid, projection, snapshot=None):
        docs, profiles = snapshot if snapshot is not None else (self.docs, self.profiles)
        d = docs[uid]
        if d['deleted'] or d['withdrawn'] or d['revision'] is None or projection not in profiles[d['source']]:
            return None
        return (d['resource'], d['revision'])

    def emit(self, kind, identity):
        self.feed.append((kind, identity))
        self.record_history()
        self.log('feed %d %s %s' % (len(self.feed), kind, identity))
        for p, projection in self.projs.items():
            if not projection['poll']:
                projection['poll'] = True
                self.later(self.r.randint(1, 7), 'poll', p)

    def new_build(self, p, bid, state='building', initial=False):
        b = dict(id=bid, projection=p, state=state, store={}, versions={}, counter=0,
                 doc_counter={}, last={}, jobs={}, start=len(self.feed),
                 active=True, enumerated=initial, repair=None)
        self.builds[bid] = b
        return b

    def live(self, bid):
        return bid in self.builds and self.builds[bid]['state'] != 'retired'

    def action(self, kind, args):
        self.metrics['action_' + kind] += 1
        self.log('action %s %s' % (kind, args))
        if kind in ['source_update', 'method_refresh', 'rollback', 'delete', 'withdraw', 'rebind']:
            uid = args[0]
            d = self.docs[uid]
            if kind in ['source_update', 'method_refresh']:
                if kind == 'source_update':
                    d['source_revision'] += 1
                self.next_revision += 1
                d['previous'], d['revision'] = d['revision'], self.next_revision
            elif kind == 'rollback':
                if d['previous'] is not None:
                    d['revision'], d['previous'] = d['previous'], d['revision']
            elif kind == 'delete':
                d['deleted'] = True
            elif kind == 'withdraw':
                d['withdrawn'] = args[1]
            elif kind == 'rebind':
                d['resource'] = args[1]
            self.emit('inclusion_changed' if kind == 'rebind' else 'current_revision_changed', uid)
            if kind == 'delete':
                self.emit('document_deleted', uid)
        elif kind == 'profile':
            source, p, added = args
            if added:
                self.profiles[source].add(p)
                self.backfill_required[(p, source)] = len(self.feed) + 1
            else:
                self.profiles[source].discard(p)
            self.profile_seq[source] = len(self.feed) + 1
            self.emit('source_profile_changed', source)
        elif kind == 'build':
            p = args[0]
            bid = p + '-1'
            self.projs[p]['candidate'] = bid
            b = self.new_build(p, bid)
            if self.variant == 'N4':
                b['active'] = False
                b['start'] = None
            uids = list(self.docs)
            self.r.shuffle(uids)
            self.log('bootstrap %s start=%s' % (bid, b['start']))
            self.later(1, 'enumerate', bid, uids, 0)
        elif kind in ['switch', 'switch_back']:
            p = args[0]
            target = self.projs[p]['candidate'] if kind == 'switch' else self.projs[p]['original']
            if not target or not self.live(target):
                return
            if not self.builds[target]['enumerated']:
                self.later(5, 'action', kind, args)
                return
            for b in self.builds.values():
                if b['projection'] == p and b['state'] == 'serving':
                    b['state'] = 'retained'
            self.builds[target]['state'] = 'serving'
            self.log('serving %s' % target)
        elif kind == 'retire':
            p = args[0]
            for b in self.builds.values():
                if b['projection'] == p and b['state'] == 'retained':
                    b['state'] = 'retired'
                    b['store'].clear()
                    b['jobs'].clear()
                    for key in list(self.facts):
                        if key[0] == b['id']:
                            del self.facts[key]
                    self.log('retire %s' % b['id'])
            self.check_source_completion(p)
        elif kind.startswith('corrupt_'):
            candidates = [key for key, fact in self.facts.items() if fact['included'] and self.live(key[0])]
            self.r.shuffle(candidates)
            for key in candidates[:2 if kind == 'corrupt_drop' else 1]:
                if kind == 'corrupt_drop':
                    del self.facts[key]
                else:
                    self.facts[key]['revision'] = -999
                self.metrics[kind] += 1
                self.log('%s %s' % (kind, key))
        else:
            raise AssertionError(kind)

    def poll(self, p):
        projection = self.projs[p]
        projection['poll'] = False
        end = min(len(self.feed), projection['cursor'] + self.r.randint(1, 4))
        while projection['cursor'] < end:
            projection['cursor'] += 1
            seq = projection['cursor']
            kind, identity = self.feed[seq - 1]
            self.log('deliver %s feed=%d %s %s' % (p, seq, kind, identity))
            if kind == 'source_profile_changed':
                self.signal_source(p, identity)
            else:
                for b in list(self.builds.values()):
                    if b['projection'] != p or b['state'] == 'retired' or not b['active'] or seq <= b['start']:
                        continue
                    self.signal(b, identity)
        self.later(self.r.randint(1, 20), 'cursor_report', p, end)
        if end < len(self.feed):
            projection['poll'] = True
            self.later(self.r.randint(1, 7), 'poll', p)

    def cursor_report(self, p, position):
        if self.r.random() < .1:
            self.metrics['cursor_retry'] += 1
            self.later(self.r.randint(1, 15), 'cursor_report', p, position)
            return
        old = self.projs[p]['reported_cursor']
        self.projs[p]['reported_cursor'] = max(old, position)
        assert self.projs[p]['reported_cursor'] >= old

    def signal(self, b, uid):
        if b['state'] == 'retired':
            return
        job = b['jobs'].get(uid)
        if job is not None:
            if job['status'] == 'running':
                if self.variant == 'N3':
                    self.metrics['dropped_running_signal'] += 1
                    self.log('DROP signal %s %s' % (b['id'], uid))
                else:
                    job['dirty'] = True
                    self.metrics['rerun_signalled'] += 1
            return
        b['jobs'][uid] = dict(status='queued', dirty=False)
        self.request_dispatch(b['projection'])

    def request_dispatch(self, p):
        if not self.projs[p]['dispatch']:
            self.projs[p]['dispatch'] = True
            self.later(self.r.randint(1, 3), 'dispatch', p)

    def dispatch(self, p):
        projection = self.projs[p]
        projection['dispatch'] = False
        for b in self.builds.values():
            if b['projection'] != p or b['state'] == 'retired':
                continue
            eligible = [uid for uid, j in b['jobs'].items() if j['status'] == 'queued' and uid not in projection['running']]
            if not eligible:
                continue
            self.r.shuffle(eligible)
            limit = 1 if p == 'retrieval' else self.r.randint(1, 5)
            uids = eligible[:limit]
            batch = []
            for uid in uids:
                assert uid not in projection['running'], 'per-projection uid serialization'
                projection['running'][uid] = b['id']
                b['jobs'][uid].update(status='running', dirty=False)
                snap = None
                if self.variant == 'N6':
                    pos = max(0, projection['cursor'] - 2)
                    snap = self.history[pos]
                desired = self.desired(uid, p, snap)
                batch.append((uid, desired))
                self.log('read %s %s desired=%s delivered=%d' % (b['id'], uid, desired, projection['cursor']))
            self.metrics['attempts'] += 1
            if p == 'wiki':
                self.metrics['wiki_batch_%d' % len(batch)] += 1
            delay = self.r.randint(25, 85) if self.r.random() < .15 else self.r.randint(1, 9)
            if delay >= 25:
                self.metrics['slow_attempts'] += 1
            self.later(delay, 'finish', b['id'], batch, self.r.random() < .12)
            # Retrieval can start another uid while this uid is in flight.
            if len(eligible) > len(uids):
                self.request_dispatch(p)

    def finish(self, bid, batch, failed):
        b = self.builds[bid]
        projection = self.projs[b['projection']]
        if not self.live(bid):
            for uid, _ in batch:
                if projection['running'].get(uid) == bid:
                    del projection['running'][uid]
            self.request_dispatch(b['projection'])
            self.check_source_completion(b['projection'])
            return
        if failed:
            self.metrics['attempt_failures'] += 1
            self.log('attempt failed %s %s' % (bid, [x[0] for x in batch]))
        changes = []
        for uid, desired in batch:
            assert projection['running'].get(uid) == bid
            job = b['jobs'][uid]
            rejected = False
            if not failed and desired is not None:
                resource, revision = desired
                if self.variant == 'N5':
                    rejected = self.blocked(uid, resource) or revision < b['last'].get(uid, -1)
                else:
                    rejected = self.blocked(uid, resource) or revision != self.current(uid)
                if rejected:
                    self.metrics['superseded'] += 1
                    self.log('superseded %s %s wanted=%s current=%s blocked=%s' %
                        (bid, uid, desired, self.current(uid), self.blocked(uid, resource)))
            if not failed and not rejected:
                old = {key: rev for key, rev in b['store'].items() if key[0] == uid}
                wanted = {} if desired is None else {(uid, desired[0]): desired[1]}
                for key in old.keys() - wanted.keys():
                    del b['store'][key]
                    changes.append(self.changed(b, key, False, None))
                for key, revision in wanted.items():
                    if old.get(key) != revision:
                        # All checks are at this atomic mini-batch commit boundary.
                        if self.blocked(uid, key[1]):
                            self.fail('S2', dict(build=bid, uid=uid, resource=key[1], revision=revision,
                                                document=deepcopy(self.docs[uid])))
                        if revision != self.current(uid):
                            self.fail('S3', dict(build=bid, uid=uid, revision=revision, current=self.current(uid)))
                        b['store'][key] = revision
                        b['last'][uid] = revision
                        changes.append(self.changed(b, key, True, revision))
            del projection['running'][uid]
            if failed or job['dirty']:
                job.update(status='queued', dirty=False)
            else:
                del b['jobs'][uid]
        if changes:
            self.metrics['commits'] += 1
            self.log('commit %s %s' % (bid, [(c[1], c[2], c[3], c[4]) for c in changes]))
            for change in changes:
                self.send_report(change)
        self.request_dispatch(b['projection'])
        self.check_source_completion(b['projection'])

    def changed(self, b, key, included, revision):
        b['counter'] += 1
        version = b['counter']
        if self.variant == 'N1':
            version = b['doc_counter'].get(key[0], 0) + 1
            b['doc_counter'][key[0]] = version if included else 0
        b['versions'][key] = version
        return (b['id'], key, included, revision, version)

    def send_report(self, change):
        copies = self.r.randint(1, 3)
        self.metrics['report_copies'] += copies
        for _ in range(copies):
            delay = self.r.randint(90, 180) if self.r.random() < .1 else self.r.randint(1, 40)
            self.later(delay, 'report', change, None)

    def report(self, change, snapshot):
        bid, key, included, revision, version = change
        if self.r.random() < .12:
            self.metrics['report_retries'] += 1
            self.later(self.r.randint(1, 20), 'report', change, snapshot)
            return
        if self.live(bid):
            fullkey = (bid,) + tuple(key)
            current = self.facts.get(fullkey)
            if current is None or version >= current['version']:
                self.facts[fullkey] = dict(included=included, revision=revision, version=version,
                    confirmed=True, expires=None if included else self.time + 30 * DAY)
                self.log('fact %s included=%s rev=%s v=%d' % (fullkey, included, revision, version))
            else:
                self.metrics['old_reports_ignored'] += 1
        # Retired Build reports are acknowledged without recreating removed facts.
        if snapshot is not None and snapshot in self.snapshots:
            self.snapshots[snapshot]['pending'] -= 1
            self.maybe_sweep(snapshot)

    def enumerate(self, bid, uids, offset):
        if not self.live(bid):
            return
        b = self.builds[bid]
        for uid in uids[offset:offset + 2]:
            self.signal(b, uid)
        if offset + 2 < len(uids):
            self.later(self.r.randint(3, 9), 'enumerate', bid, uids, offset + 2)
        else:
            b['enumerated'] = True
            if self.variant == 'N4':
                b['start'], b['active'] = len(self.feed), True
                self.log('LATE bootstrap position %s start=%d' % (bid, b['start']))
            self.log('enumerated %s' % bid)

    def signal_source(self, p, source):
        projection = self.projs[p]
        state = projection['sources'].get(source)
        if state is not None:
            state['dirty'] = True
            self.metrics['source_pass_coalesced'] += 1
            return
        bids = [b['id'] for b in self.builds.values() if b['projection'] == p
                and b['state'] != 'retired' and b['active'] and b['start'] < projection['cursor']]
        state = dict(dirty=False, enumerated=False, profile_seq=self.profile_seq[source], builds=bids)
        projection['sources'][source] = state
        uids = [uid for uid, d in self.docs.items() if d['source'] == source]
        self.later(1, 'source_page', p, source, uids, 0)
        self.metrics['source_passes'] += 1

    def source_page(self, p, source, uids, offset):
        state = self.projs[p]['sources'][source]
        for uid in uids[offset:offset + 2]:
            for bid in state['builds']:
                if self.live(bid):
                    self.signal(self.builds[bid], uid)
        if offset + 2 < len(uids):
            self.later(self.r.randint(2, 6), 'source_page', p, source, uids, offset + 2)
        else:
            state['enumerated'] = True
            self.check_source_completion(p)

    def check_source_completion(self, p):
        for source, state in list(self.projs[p]['sources'].items()):
            busy = any(self.docs[uid]['source'] == source
                       for bid in state['builds'] if self.live(bid)
                       for uid in self.builds[bid]['jobs'])
            if state['enumerated'] and not busy:
                del self.projs[p]['sources'][source]
                if state['dirty']:
                    self.signal_source(p, source)
                else:
                    self.later(self.r.randint(1, 15), 'backfill_report', p, source, state['profile_seq'])

    def backfill_report(self, p, source, seq):
        if self.r.random() < .1:
            self.later(5, 'backfill_report', p, source, seq)
            return
        self.backfill_complete[(p, source)] = max(self.backfill_complete[(p, source)], seq)
        self.log('backfill complete %s %s profile_seq=%d' % (p, source, seq))

    def included_facts(self, bid):
        return {(uid, resource): fact['revision'] for (b, uid, resource), fact in self.facts.items()
                if b == bid and fact['included']}

    def heartbeat(self):
        for b in self.builds.values():
            if b['state'] == 'retired':
                continue
            if len(self.included_facts(b['id'])) != len(b['store']):
                self.metrics['heartbeat_mismatches'] += 1
                if b['repair'] is None:
                    self.start_snapshot(b)
        # No perpetual timer after quiescence: one final count check follows all work.
        if self.q:
            self.later(17, 'heartbeat')

    def start_snapshot(self, b):
        self.snapshot_id += 1
        sid = self.snapshot_id
        b['repair'] = sid
        watermark = b['counter']
        for key, fact in self.facts.items():
            if key[0] == b['id']:
                fact['confirmed'] = False
        # Atomic store view at the watermark; page/report delivery is asynchronous.
        entries = [(b['id'], key, True, rev, b['versions'][key]) for key, rev in b['store'].items()]
        self.snapshots[sid] = dict(build=b['id'], watermark=watermark, pending=len(entries), ready=False)
        self.metrics['snapshots'] += 1
        self.log('snapshot %d %s watermark=%d entries=%d' % (sid, b['id'], watermark, len(entries)))
        for entry in entries:
            self.later(self.r.randint(1, 35), 'report', entry, sid)
        self.later(self.r.randint(5, 20), 'snapshot_ready', sid)

    def snapshot_ready(self, sid):
        if sid in self.snapshots:
            self.snapshots[sid]['ready'] = True
            self.maybe_sweep(sid)

    def maybe_sweep(self, sid):
        state = self.snapshots.get(sid)
        if state is None or not state['ready'] or state['pending']:
            return
        bid, watermark = state['build'], state['watermark']
        if self.live(bid):
            for key, fact in list(self.facts.items()):
                if key[0] == bid and not fact['confirmed']:
                    if self.variant == 'N2':
                        del self.facts[key]
                        self.log('sweep DELETE %s old_v=%d' % (key, fact['version']))
                    elif fact['version'] <= watermark:
                        self.facts[key] = dict(included=False, revision=None, version=watermark,
                            confirmed=True, expires=self.time + 30 * DAY)
                        self.log('sweep tombstone %s v=%d' % (key, watermark))
            self.builds[bid]['repair'] = None
        del self.snapshots[sid]
        self.log('snapshot %d end' % sid)

    def safety(self):
        # The requested predicate is checked for every D. Also retain the narrower
        # deleted-only witness so an inclusion/reinstatement gap is distinguishable.
        included_uids = {key[1] for key, f in self.facts.items() if f['included'] and self.live(key[0])}
        actual = {}
        for b in self.builds.values():
            if b['state'] != 'retired':
                for uid, resource in b['store']:
                    actual.setdefault(uid, []).append((b['id'], resource))
        for uid in sorted(actual.keys() - included_uids):
            detail = dict(uid=uid, deleted=self.docs[uid]['deleted'], stores=actual[uid],
                          reason='no included fact in any non-retired Build')
            self.fail('S1', detail)
            if self.docs[uid]['deleted']:
                self.metrics['S1_deleted_checks'] += 1
                if 'S1_deleted' not in self.witnesses:
                    self.witnesses['S1_deleted'] = dict(seed=self.seed, variant=self.variant,
                        time=self.time, step=self.steps, detail=detail, trace=list(self.trace)[-20:])
        # Readiness uses only serving Build facts and source profile backfill gates.
        for p in PROJECTIONS:
            serving = [b for b in self.builds.values() if b['projection'] == p and b['state'] == 'serving']
            assert len(serving) == 1
            for source in self.profiles:
                required = self.backfill_required.get((p, source), 0)
                counted = p in self.profiles[source] and required is not None and self.backfill_complete[(p, source)] >= required
                if counted:
                    self.metrics['readiness_serving_only_checks'] += 1
                    assert serving[0]['state'] == 'serving'

    def liveness(self):
        for b in self.builds.values():
            if b['state'] == 'retired':
                continue
            wanted = {}
            for uid in self.docs:
                desired = self.desired(uid, b['projection'])
                if desired is not None:
                    wanted[(uid, desired[0])] = desired[1]
            if b['store'] != wanted:
                self.fail('L1', dict(build=b['id'], store=repr(b['store']), desired=repr(wanted)))
            facts = self.included_facts(b['id'])
            if facts != b['store']:
                self.fail('L2', dict(build=b['id'], facts=repr(facts), store=repr(b['store'])))
        for p, projection in self.projs.items():
            if projection['reported_cursor'] != len(self.feed):
                self.fail('L3', dict(projection=p, cursor=projection['reported_cursor'], feed=len(self.feed)))

    def run(self, max_steps=30000):
        while self.q and self.steps < max_steps:
            self.time, _, kind, args = heapq.heappop(self.q)
            self.steps += 1
            getattr(self, kind)(*args)
            self.safety()
            # A recurring failed repair is not declared a liveness pass. Stop a
            # fair, unchanged repeating state and report UNKNOWN with its state.
            if kind == 'heartbeat' and self.time > 1000:
                signature = repr(([(b['id'], b['store'], b['versions']) for b in self.builds.values()], self.facts))
                stable = hashlib.sha256(signature.encode()).hexdigest()
                self.repair_signatures[stable] += 1
                if self.repair_signatures[stable] >= 12:
                    self.unknown = 'Repeated identical repair state; no quiescence (12 occurrences).'
                    break
        if self.q and self.unknown is None:
            self.unknown = 'Event budget exhausted before quiescence.'
        if self.unknown is None:
            assert not any(b['jobs'] for b in self.builds.values() if b['state'] != 'retired')
            assert not any(p['sources'] for p in self.projs.values())
            assert not any(p['running'] for p in self.projs.values())
            self.liveness()
        return dict(seed=self.seed, variant=self.variant, steps=self.steps, time=self.time,
                    violations=dict(self.failures), witnesses=self.witnesses,
                    metrics=dict(self.metrics), unknown=self.unknown, workload_hash=self.workload_hash,
                    final_mismatches={b['id']: dict(store=repr(b['store']), facts=repr(self.included_facts(b['id'])))
                        for b in self.builds.values() if b['state'] != 'retired' and self.included_facts(b['id']) != b['store']})


def self_check():
    # Version ordering, duplicate delivery and tombstone retention are independent
    # of randomized workload coverage. Commit behavior is exercised by the seeds.
    s = Simulation(0, actions=[])
    bid = 'retrieval-0'
    key = ('d0', 'r0')
    s.r = random.Random(42)
    s.r.random = lambda: .5
    s.report((bid, key, False, None, 100), None)
    while s.q and any(e[2] == 'report' for e in s.q):
        t, _, kind, args = heapq.heappop(s.q)
        s.time = t
        getattr(s, kind)(*args)
    s.report((bid, key, True, 1, 99), None)
    assert s.facts[(bid,) + key]['included'] is False
    assert s.facts[(bid,) + key]['version'] == 100
    s.cursor_report('retrieval', 10)
    s.cursor_report('retrieval', 2)
    assert s.projs['retrieval']['reported_cursor'] == 10
    assert s.blocked('d0', 'r1') and not s.blocked('d0', 'r0')
    s.docs['d0']['withdrawn'] = True
    assert s.blocked('d0', 'r0') and s.desired('d0', 'retrieval') is None


def write_markdown(summary, path, title):
    lines = ['# ' + title, '',
             'Counts are seeds with ≥1 violation, not number of failing event boundaries. '
             'Liveness is evaluated only after quiescence. UNKNOWN is separate from zero violations.', '',
             '| Variant | Seeds | S1 | S2 | S3 | L1 | L2 | L3 | Nonquiescent / UNKNOWN |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for variant, s in summary.items():
        lines.append('| %s | %d | %s | %d |' % (variant, s['runs'],
            ' | '.join(str(s['failed_seeds'].get(i, 0)) for i in INVARIANTS), s['unknown_seeds']))
    for variant, s in summary.items():
        lines += ['', '## ' + variant, '', 'Deleted-document S1 witnesses: %d seeds. Quiescent runs: %d.' %
                  (s['deleted_S1_seeds'], s['runs'] - s['unknown_seeds']), '',
                  'Aggregate exercise counters: `' + json.dumps(s['metrics'], sort_keys=True) + '`', '']
        for invariant, witness in s['first_witnesses'].items():
            lines += ['### ' + invariant + ' — smallest failing seed in the tested range: ' + str(witness['seed']), '',
                      '`' + json.dumps(witness['detail'], sort_keys=True) + '`', '',
                      '```text'] + witness['trace'] + ['```', '']
        if s['first_unknown']:
            lines += ['UNKNOWN example: `' + json.dumps(s['first_unknown'], sort_keys=True) + '`', '']
    path.write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--variants', nargs='+', choices=VARIANTS, default=['design'])
    parser.add_argument('--seeds', type=int, default=1000, help='number of seeds, starting at --start')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--seed', type=int, help='replay exactly one seed')
    parser.add_argument('--trace', action='store_true')
    parser.add_argument('--output', default='part-b')
    args = parser.parse_args()
    self_check()
    seeds = [args.seed] if args.seed is not None else range(args.start, args.start + args.seeds)
    summary = {}
    with (ROOT / (args.output + '-runs.jsonl')).open('w') as out:
        for variant in args.variants:
            aggregate = dict(runs=0, failed_seeds=Counter(), violation_checks=Counter(), metrics=Counter(),
                             unknown_seeds=0, deleted_S1_seeds=0, first_witnesses={}, first_unknown=None)
            for seed in seeds:
                sim = Simulation(seed, variant, args.trace)
                result = sim.run()
                out.write(json.dumps(result, sort_keys=True) + '\n')
                aggregate['runs'] += 1
                aggregate['failed_seeds'].update(result['violations'].keys())
                aggregate['violation_checks'].update(result['violations'])
                aggregate['metrics'].update(result['metrics'])
                aggregate['deleted_S1_seeds'] += 'S1_deleted' in result['witnesses']
                for invariant, witness in result['witnesses'].items():
                    aggregate['first_witnesses'].setdefault(invariant, witness)
                if result['unknown']:
                    aggregate['unknown_seeds'] += 1
                    if aggregate['first_unknown'] is None:
                        aggregate['first_unknown'] = {k: result[k] for k in ['seed', 'unknown', 'final_mismatches']}
                if args.trace:
                    (ROOT / ('%s-%s-seed-%d-trace.txt' % (args.output, variant, seed))).write_text('\n'.join(sim.trace) + '\n')
                if aggregate['runs'] % 100 == 0:
                    print('%s %d/%d seeds failures=%s unknown=%d' %
                          (variant, aggregate['runs'], len(seeds), dict(aggregate['failed_seeds']), aggregate['unknown_seeds']), flush=True)
            summary[variant] = aggregate
            (ROOT / (args.output + '-summary.json')).write_text(json.dumps(summary, indent=2, sort_keys=True))
            write_markdown(summary, ROOT / (args.output + '-results.md'), 'Part B — ' + ', '.join(summary))
    print(json.dumps({v: {k: s[k] for k in ['runs', 'failed_seeds', 'unknown_seeds', 'deleted_S1_seeds']} for v, s in summary.items()}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
