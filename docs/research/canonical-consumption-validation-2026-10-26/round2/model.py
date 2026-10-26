#!/usr/bin/env python3
"""Round-2 discrete-event extension of the unchanged round-1 model (stdlib only)."""
import sys
sys.dont_write_bytecode = True
import importlib.util
from collections import Counter, deque
from copy import deepcopy
import hashlib
import heapq
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('round1_part_b', ROOT.parent / 'part_b.py')
round1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(round1)

VARIANTS = ['V1', 'V2', 'V3', 'V4', 'V4-Ra', 'V4-Rb', 'N2', 'N12', 'N-fence', 'N-viewexp']
INVARIANTS = ['S1', 'S1_flipback', 'S7', 'L0', 'L1', 'L2', 'L3', 'L4', 'L5']
RETENTION, TTL, RETRY_LIFETIME, HEARTBEAT = 60, 120, 90, 17
PENDING_MAX = 150
FAMILIES = [('d0', 'd2'), ('d1', 'd3'), ('d4', 'd6'), ('d5', 'd7')]


def workload(seed, name):
    actions = [a for a in round1.workload(seed) if not a[1].startswith('corrupt_')]
    actions += [(30, 'delete', ['d0']), (100, 'liveness_loss', ['wiki', 55]),
                (245, 'crash', ['retrieval']), (250, 'crash', ['wiki']),
                (95, 'block', ['d6', True]), (165, 'block', ['d6', False])]
    if seed % 2 == 0:
        actions.append((5, 'pause', ['retrieval', 120]))
    if name in ('W-rewind', 'W-drift'):
        actions.append((500, 'rewind' if name == 'W-rewind' else 'silent_rewind',
                        ['retrieval-live', 't200']))
    return sorted(actions, key=lambda a: a[0])


def digest(entries):
    """XOR stable 128-bit SHA-256 prefixes; no Python process-randomized hash."""
    value = 0
    for (uid, resource), revision in entries.items():
        raw = json.dumps([uid, resource, revision], separators=(',', ':')).encode()
        value ^= int.from_bytes(hashlib.sha256(raw).digest()[:16], 'big')
    return '%032x' % value


class Simulation(round1.Simulation):
    def __init__(self, seed=0, variant='V3', name='W-real', actions=None,
                 full_trace=False, faults=True, measure_transients=True):
        assert variant in VARIANTS
        super().__init__(seed, variant, full_trace, actions=[])
        self.name, self.faults = name, faults
        self.measure_transients = measure_transients
        self.suppress_snapshots = False
        self.trace = [] if full_trace else deque(maxlen=100)
        self.feed_times = []
        self.expired = {}
        self.enforcement_previous = {}
        self.moved_out = set()
        self.attempt_id = 0
        self.last_events = deque(maxlen=30)
        for p in self.projs.values():
            p.update(epoch=0, paused_until=0, lost_until=0)
        for b in self.builds.values():
            b['pages'] = self.page_maps(b['store']) if b['projection'] == 'wiki' else {}
        self.saved = {'initial': deepcopy(self.facts)}
        self.actions = actions if actions is not None else workload(seed, name)
        self.workload_hash = hashlib.sha256(json.dumps(self.actions).encode()).hexdigest()
        self.external_end = max([t for t, _, _ in self.actions] or [0])
        for t, kind, args in self.actions:
            self.at(t, 'action', kind, args)

    def new_build(self, *args, **kwargs):
        b = super().new_build(*args, **kwargs)
        b['pages'] = {}
        b['intents'] = {}
        b['fence'] = 0
        b['restore_scope'] = set()
        b['restoring'] = False
        return b

    def fail(self, invariant, detail):
        first = invariant not in self.witnesses
        super().fail(invariant, detail)
        if first:
            self.log('VIOLATION %s %s' % (invariant, json.dumps(detail, sort_keys=True)))

    @property
    def registered(self):
        return self.variant != 'V1'

    @property
    def digested(self):
        return self.variant not in ('V1', 'V2')

    @property
    def replacement(self):
        return self.variant not in ('V1', 'V2', 'V3')

    @property
    def fenced(self):
        return self.replacement and self.variant != 'N-fence'

    def family(self, uid):
        return next(pair for pair in FAMILIES if uid in pair)

    def page_maps(self, entries):
        pages = {}
        for (uid, resource), revision in entries.items():
            page = '%s:%s' % ('+'.join(self.family(uid)), resource)
            pages.setdefault(page, {})[(uid, resource)] = revision
        return pages

    def current(self, uid):
        d = self.docs[uid]
        return None if d['deleted'] or d['withdrawn'] else d['revision']

    def blocked(self, uid, resource):
        return super().blocked(uid, resource) or self.docs[uid].get('blocked', False)

    def desired(self, uid, projection, snapshot=None):
        answer = super().desired(uid, projection, snapshot)
        docs = snapshot[0] if snapshot else self.docs
        return None if docs[uid].get('blocked', False) else answer

    def emit(self, kind, identity):
        self.feed_times.append(self.time)
        super().emit(kind, identity)

    def action(self, kind, args):
        if kind in ('pause', 'liveness_loss'):
            p, duration = args
            field = 'paused_until' if kind == 'pause' else 'lost_until'
            self.projs[p][field] = self.time + duration
            self.log('%s %s until=%d' % (kind, p, self.time + duration))
            self.metrics[kind] += 1
            self.later(duration, 'recover', p)
        elif kind == 'crash':
            p = args[0]
            self.projs[p]['epoch'] += 1
            self.log('crash %s epoch=%d unsent reports lost' % (p, self.projs[p]['epoch']))
            self.metrics['crashes'] += 1
        elif kind == 'block':
            uid, blocked = args
            self.docs[uid]['blocked'] = blocked
            self.emit('current_revision_changed', uid)
        elif kind in ('rewind', 'silent_rewind'):
            bid, label = args
            if bid == 'retrieval-live':
                bid = next(b['id'] for b in self.builds.values()
                           if b['projection'] == 'retrieval' and b['state'] == 'serving')
            self.restore_mirror(bid, self.saved[label], announced=kind == 'rewind')
        else:
            if kind == 'rebind':
                uid, target = args
                if self.docs[uid]['resource'] != target:
                    self.moved_out.add((uid, self.docs[uid]['resource']))
            super().action(kind, args)
            for b in self.builds.values():
                if b['state'] == 'retired':
                    b['pages'].clear()
                    b['intents'].clear()

    def restore_mirror(self, bid, saved, announced=True):
        before = self.mirror_entries(bid)
        b = self.builds[bid]
        # Latch every pre/post-restore fact key, including removed tombstones.
        scope = {key[1] for key in self.facts if key[0] == bid}
        for key in list(self.facts):
            if key[0] == bid:
                del self.facts[key]
        for key, fact in saved.items():
            if key[0] == bid:
                self.facts[key] = deepcopy(fact)
                scope.add(key[1])
        self.metrics['mirror_rewinds'] += 1
        self.metrics['rewind_equal_counts'] += len(before) == len(self.mirror_entries(bid))
        self.log('rewind %s before=%s after=%s store unaffected' %
                 (bid, before, self.mirror_entries(bid)))
        if not announced:
            self.metrics['silent_rewinds'] += 1
            self.log('silent drift %s: no runbook or enforcement gate' % bid)
            return
        b['restore_scope'].update(scope)
        b['restoring'] = True
        if b['repair'] is not None:
            self.snapshots.pop(b['repair'], None)
            b['repair'] = None
            self.metrics['restore_superseded_repairs'] += 1
        self.log('restore gate %s scope=%s' % (bid, sorted(b['restore_scope'])))
        self.force_snapshot(bid, 'restore')

    def restore_complete(self, bid):
        b = self.builds[bid]
        if b['restoring']:
            b['restoring'] = False
            b['restore_scope'].clear()
            self.metrics['restore_repairs_completed'] += 1
            self.log('restore gate END %s' % bid)

    def restore_gated(self, uid):
        return any(self.live(b['id']) and b['restoring'] and uid in b['restore_scope']
                   for b in self.builds.values())

    def recover(self, p):
        self.log('recover %s' % p)
        if not self.projs[p]['poll']:
            self.projs[p]['poll'] = True
            self.later(0, 'poll', p)
        self.request_dispatch(p)

    def poll(self, p):
        projection = self.projs[p]
        until = max(projection['paused_until'], projection['lost_until'])
        if self.time < until:
            projection['poll'] = True
            self.at(until, 'poll', p)
            return
        cursor = projection['cursor']
        if cursor < len(self.feed) and self.time - self.feed_times[cursor] > RETENTION:
            self.resync(p)
            return
        super().poll(p)

    def resync(self, p):
        projection = self.projs[p]
        projection['poll'] = False
        projection['cursor'] = len(self.feed)
        self.cursor_report(p, len(self.feed))
        self.metrics['cursor_expired'] += 1
        enumerated = {uid for uid, d in self.docs.items() if not d['deleted']}
        self.log('cursor_expired %s FIX start=%d enumerate=%s' %
                 (p, len(self.feed), sorted(enumerated)))
        for b in self.builds.values():
            if b['projection'] != p or not self.live(b['id']):
                continue
            extras = {uid for uid, _ in b['store']} - enumerated
            uids = enumerated | (extras if self.variant != 'V4-Ra' else set())
            self.metrics['store_extras_reconciled'] += len(extras) if self.variant != 'V4-Ra' else 0
            self.log('resync %s extras=%s reconcile=%s' % (b['id'], sorted(extras), sorted(uids)))
            self.later(1, 'enumerate', b['id'], sorted(uids), 0)

    def cursor_report(self, p, position):
        if self.faults:
            super().cursor_report(p, position)
        else:
            self.projs[p]['reported_cursor'] = max(self.projs[p]['reported_cursor'], position)

    def dispatch(self, p):
        projection = self.projs[p]
        projection['dispatch'] = False
        if self.time < projection['lost_until']:
            return
        for b in self.builds.values():
            if b['projection'] != p or not self.live(b['id']):
                continue
            for trigger, job in list(b['jobs'].items()):
                locked = self.family(trigger) if p == 'wiki' else (trigger,)
                if job['status'] != 'queued' or any(u in projection['running'] for u in locked):
                    continue
                for uid in locked:
                    projection['running'][uid] = b['id']
                job.update(status='running', dirty=False)
                wanted = {}
                for uid in locked:
                    desired = self.desired(uid, p)
                    if desired is not None:
                        wanted[(uid, desired[0])] = desired[1]
                    self.log('read %s trigger=%s source=%s desired=%s' %
                             (b['id'], trigger, uid, desired))
                self.attempt_id += 1
                attempt = dict(id=self.attempt_id, trigger=trigger, locked=locked,
                               wanted=wanted, versions={}, registered=False)
                self.metrics['attempts'] += 1
                if p == 'wiki':
                    self.metrics['wiki_sources_%d' % len(wanted)] += 1
                slow = self.faults and self.r.random() < .15
                self.metrics['slow_attempts'] += slow
                delay = self.r.randint(25, 85) if slow else self.r.randint(1, 9)
                failed = self.faults and self.r.random() < .12
                self.later(delay, 'finish', b['id'], attempt, failed)

    def checked_sources(self, b, attempt):
        if b['projection'] == 'wiki' and self.variant == 'V4-Rb':
            return {key: rev for key, rev in attempt['wanted'].items()
                    if key[0] == attempt['trigger']}
        return attempt['wanted']

    def valid(self, key, revision):
        return not self.blocked(*key) and revision == self.current(key[0])

    def register(self, b, attempt):
        """One atomic platform event: checks plus accepted pending facts."""
        checked = self.checked_sources(b, attempt)
        accepted = True
        for key, revision in attempt['wanted'].items():
            b['counter'] += 1
            version = b['counter']
            attempt['versions'][key] = version
            if key in checked and not self.valid(key, revision):
                accepted = False
                self.metrics['superseded'] += 1
                self.log('register REJECT %s %s rev=%s current=%s' %
                         (b['id'], key, revision, self.current(key[0])))
            else:
                b['intents'][key] = dict(revision=revision, version=version, since=self.time)
                self.apply_fact((b['id'], key, True, revision, version), state='pending')
                self.log('register %s %s rev=%s v=%d pending' % (b['id'], key, revision, version))
        attempt['registered'] = True
        return accepted

    def finish(self, bid, attempt, failed=False):
        b = self.builds[bid]
        if not self.live(bid):
            self.complete_attempt(b, attempt, False)
            return
        lost_until = self.projs[b['projection']]['lost_until']
        if self.time < lost_until:
            self.at(lost_until, 'finish', bid, attempt, failed)
            return
        if failed:
            self.metrics['attempt_failures'] += 1
            self.log('attempt failed %s #%d retry' % (bid, attempt['id']))
            self.complete_attempt(b, attempt, True)
            return
        if b['projection'] == 'retrieval':
            old = {key: revision for key, revision in b['store'].items()
                   if key[0] in attempt['locked']}
            if old == attempt['wanted']:
                # V1 does not write/report a retrieval no-op; V2 adds no new write.
                self.clear_intents(b, attempt['locked'])
                self.complete_attempt(b, attempt, False)
                return
        self.clear_intents(b, attempt['locked'])
        attempt['admitted'] = {key: self.valid(key, rev) for key, rev in attempt['wanted'].items()}
        attempt['check_time'] = self.time
        if self.registered:
            accepted = self.register(b, attempt)
        else:
            accepted = all(self.valid(key, rev) for key, rev in self.checked_sources(b, attempt).items())
        if not accepted:
            self.metrics['superseded_pages'] += 1
            self.log('superseded page/uid %s #%d' % (bid, attempt['id']))
            self.clear_intents(b, attempt['locked'])
            self.complete_attempt(b, attempt, False)
            return
        if attempt['wanted']:
            delay = attempt.get('write_delay')
            if delay is None:
                delay = self.r.randint(15, 40) if self.faults and self.r.random() < .15 else self.r.randint(1, 6)
            fail_write = attempt['fail_write'] if 'fail_write' in attempt else self.faults and self.r.random() < .12
            self.log('%s accepted %s #%d write_delay=%d' %
                     ('register' if self.registered else 'check', bid, attempt['id'], delay))
            self.later(delay, 'write_attempt', bid, attempt, fail_write)
        else:
            self.write_attempt(bid, attempt, False)

    def write_attempt(self, bid, attempt, failed=False):
        b = self.builds[bid]
        if not self.live(bid):
            self.complete_attempt(b, attempt, False)
            return
        lost_until = self.projs[b['projection']]['lost_until']
        if self.time < lost_until:
            self.at(lost_until, 'write_attempt', bid, attempt, failed)
            return
        if failed:
            self.metrics['store_write_failures'] += 1
            self.log('store write FAILED after register %s #%d retry' % (bid, attempt['id']))
            self.complete_attempt(b, attempt, True)
            return
        wanted = attempt['wanted']
        old = {key: rev for key, rev in b['store'].items() if key[0] in attempt['locked']}
        changes = []
        late_transaction = False
        for key in sorted(old.keys() - wanted.keys()):
            del b['store'][key]
            changes.append(self.changed(b, key, False, None))
            self.log('store remove %s %s v=%d' % (bid, key, changes[-1][-1]))
        for key, revision in wanted.items():
            if old.get(key) != revision or attempt['registered'] or b['projection'] == 'wiki':
                ineligible = self.blocked(*key)
                drift = revision != self.current(key[0])
                was_valid = attempt.get('admitted', {}).get(key, True)
                self.metrics['S2_at_write'] += ineligible
                self.metrics['S3_at_write'] += drift
                self.metrics['late_S2'] += was_valid and ineligible
                self.metrics['late_S3'] += was_valid and drift
                self.metrics['late_landings'] += was_valid and (ineligible or drift)
                self.metrics['already_invalid_landings'] += not was_valid and (ineligible or drift)
                late_transaction |= was_valid and (ineligible or drift)
                if ineligible or drift:
                    self.log('LANDING %s %s S2=%s S3=%s valid_at_check=%s' %
                             (bid, key, ineligible, drift, was_valid))
                if attempt['registered']:
                    if self.replacement:
                        b['counter'] += 1
                        version = b['counter']
                        self.log('fresh confirmation %s %s register_v=%d confirm_v=%d fence=%d' %
                                 (bid, key, attempt['versions'][key], version, b['fence']))
                    else:
                        version = attempt['versions'][key]
                    b['versions'][key] = version
                    change = (bid, key, True, revision, version)
                else:
                    change = self.changed(b, key, True, revision)
                b['store'][key] = revision
                b['last'][key[0]] = revision
                changes.append(change)
                self.log('store write %s page=%s %s rev=%s v=%d' %
                         (bid, '+'.join(attempt['locked']), key, revision, change[-1]))
        if b['projection'] == 'wiki':
            b['pages'] = self.page_maps(b['store'])
        self.clear_intents(b, attempt['locked'])
        self.metrics['late_transactions'] += late_transaction
        if changes:
            self.metrics['commits'] += 1
            for change in changes:
                self.send_report(change)
        self.complete_attempt(b, attempt, False)

    def clear_intents(self, b, uids):
        for key in list(b['intents']):
            if key[0] in uids:
                del b['intents'][key]

    def complete_attempt(self, b, attempt, retry):
        projection = self.projs[b['projection']]
        for uid in attempt['locked']:
            if projection['running'].get(uid) == b['id']:
                del projection['running'][uid]
        job = b['jobs'].get(attempt['trigger'])
        if job is not None:
            if self.live(b['id']) and (retry or job['dirty']):
                job.update(status='queued', dirty=False)
            else:
                del b['jobs'][attempt['trigger']]
        self.request_dispatch(b['projection'])
        self.check_source_completion(b['projection'])

    def send_report(self, change):
        p = self.builds[change[0]]['projection']
        envelope = dict(change=change, issued=self.time, epoch=self.projs[p]['epoch'],
                        snapshot=None, delivery=dict(done=False))
        self.later(self.r.randint(1, 4) if self.faults else 0, 'outbox_send', envelope)
        self.later(RETRY_LIFETIME, 'sdk_deadline', envelope)
        self.log('outbox %s %s included=%s v=%d' % (change[0], change[1], change[2], change[4]))

    def force_snapshot(self, bid, reason):
        if self.live(bid) and not self.suppress_snapshots and self.builds[bid]['repair'] is None:
            self.start_snapshot(self.builds[bid], reason)

    def outbox_send(self, envelope):
        bid = envelope['change'][0]
        if not self.live(bid):
            return
        p = self.builds[bid]['projection']
        if envelope['epoch'] != self.projs[p]['epoch']:
            self.metrics['crash_lost_reports'] += 1
            self.log('DROP unsent/crashed report %s v=%d' % (bid, envelope['change'][-1]))
            envelope.get('delivery', {})['done'] = True
            return
        if envelope.get('delivery', {}).get('done'):
            return
        if self.time - envelope['issued'] >= RETRY_LIFETIME:
            self.metrics['sdk_giveups'] += 1
            self.log('SDK give up %s snapshot' % bid)
            self.force_snapshot(bid, 'sdk_giveup')
            return
        until = self.projs[p]['lost_until']
        if self.time < until:
            self.at(until, 'outbox_send', envelope)
            return
        copies = self.r.randint(1, 3) if self.faults else 1
        self.metrics['report_copies'] += copies
        for _ in range(copies):
            delay = (self.r.randint(90, 180) if self.r.random() < .1 else self.r.randint(1, 40)) if self.faults else 1
            # Copies share the SDK acknowledgment, but sent packets still arrive.
            self.later(delay, 'report', dict(envelope))

    def sdk_deadline(self, envelope):
        delivery = envelope['delivery']
        if delivery['done']:
            return
        delivery['done'] = True
        bid, sid = envelope['change'][0], envelope['snapshot']
        if not self.live(bid):
            return
        p = self.builds[bid]['projection']
        if sid is None and envelope['epoch'] != self.projs[p]['epoch']:
            return
        if sid is not None:
            if sid not in self.snapshots:
                return
            del self.snapshots[sid]
            self.builds[bid]['repair'] = None
            self.metrics['snapshot_aborts'] += 1
        self.metrics['sdk_giveups'] += 1
        self.log('SDK deadline %s v=%d snapshot path' % (bid, envelope['change'][-1]))
        self.force_snapshot(bid, 'sdk_giveup')

    def gc_tombstones(self):
        for key, fact in list(self.facts.items()):
            if not fact['included'] and fact.get('state') != 'pending' and fact['expires'] is not None and self.time >= fact['expires']:
                self.expired[key] = (fact['version'], fact['expires'])
                del self.facts[key]
                self.metrics['expired_tombstones'] += 1
                self.log('tombstone expired %s v=%d' % (key, fact['version']))

    def apply_fact(self, change, state=None, replacing=False, pending_since=None):
        bid, key, included, revision, version = change
        if not self.live(bid):
            return False
        if self.fenced and not replacing and version <= self.builds[bid]['fence']:
            self.metrics['fenced_reports_ignored'] += 1
            self.log('FENCE ignore %s %s v=%d <= %d' % (bid, key, version, self.builds[bid]['fence']))
            return False
        fullkey = (bid,) + tuple(key)
        current = self.facts.get(fullkey)
        if current is not None and version < current['version']:
            self.metrics['old_reports_ignored'] += 1
            return False
        state = state or ('included' if included else 'removed')
        self.facts[fullkey] = dict(included=state == 'included', state=state,
                                  revision=revision, version=version, confirmed=True,
                                  since=(self.time if pending_since is None else pending_since) if state == 'pending' else None,
                                  expires=self.time + TTL if state == 'removed' else None)
        if self.builds[bid]['restoring']:
            self.builds[bid]['restore_scope'].add(key[0])
        if self.replacement and state == 'pending':
            since = self.facts[fullkey]['since']
            self.at(max(self.time + 1, since + PENDING_MAX + 1), 'pending_expired', bid, key, version)
        self.log('fact %s %s rev=%s v=%d' % (fullkey, state, revision, version))
        return True

    def pending_expired(self, bid, key, version):
        fact = self.facts.get((bid,) + tuple(key))
        if (self.live(bid) and fact and fact.get('state') == 'pending'
                and fact['version'] == version and self.time - fact['since'] > PENDING_MAX):
            self.metrics['pending_age_requests'] += 1
            self.log('pending age %s %s v=%d age=%d' % (bid, key, version, self.time - fact['since']))
            self.force_snapshot(bid, 'pending_age')

    def report(self, envelope):
        change, sid = envelope['change'], envelope['snapshot']
        bid, key, _, _, version = change
        fullkey = (bid,) + tuple(key)
        if self.fenced and self.live(bid) and version <= self.builds[bid]['fence']:
            self.apply_fact(change)
            envelope.get('delivery', {})['done'] = True
            return
        if self.expired_reference(bid, key, version, envelope['issued']) and self.variant != 'N12':
            self.metrics['expired_reports_rejected'] += 1
            self.log('REJECT expired-tombstone report %s v=%d snapshot path' % (fullkey, version))
            self.force_snapshot(bid, 'expired_report')
        elif self.faults and self.r.random() < .12:
            self.metrics['report_retries'] += 1
            if envelope.get('delivery', {}).get('done'):
                return
            if sid is None:
                self.later(self.r.randint(1, 20), 'outbox_send', envelope)
            else:
                self.later(self.r.randint(1, 20), 'report', envelope)
            return
        else:
            self.apply_fact(change)
        envelope.get('delivery', {})['done'] = True
        if sid is not None and sid in self.snapshots:
            self.snapshots[sid]['pending'] -= 1
            self.maybe_sweep(sid)

    def expired_reference(self, bid, key, version, issued):
        fence = self.expired.get((bid,) + tuple(key))
        return bool(fence and version <= fence[0] and issued < fence[1])

    def included_facts(self, bid):
        return {(uid, resource): f['revision'] for (b, uid, resource), f in self.facts.items()
                if b == bid and f['included']}

    def ready_facts(self, bid):
        return self.included_facts(bid)

    def readiness(self, projection, source):
        serving = next((b for b in self.builds.values()
                        if b['projection'] == projection and b['state'] == 'serving'), None)
        required = self.backfill_required.get((projection, source), 0)
        if (serving is None or projection not in self.profiles[source] or required is None
                or self.backfill_complete[(projection, source)] < required):
            return 0
        return sum(self.docs[key[0]]['source'] == source for key in self.ready_facts(serving['id']))

    def mirror_entries(self, bid):
        return {(uid, resource): f['revision'] for (b, uid, resource), f in self.facts.items()
                if b == bid and (f['included'] or (self.registered and f.get('state') == 'pending'))}

    def mismatch(self, bid):
        store, mirror = self.builds[bid]['store'], self.mirror_entries(bid)
        return len(store) != len(mirror) or (self.digested and digest(store) != digest(mirror))

    def transient_without_repair(self, bid):
        # Trace storage does not affect transitions; omit it from the short fork.
        probe = deepcopy(self, {id(self.trace): deque(maxlen=0)})
        probe.suppress_snapshots = True
        probe.measure_transients = False
        deadline = self.time + HEARTBEAT
        # At a heartbeat, its successor has not yet been queued. Strictly before
        # the next boundary avoids inventing a tie order for that successor.
        while probe.q and probe.q[0][0] < deadline:
            probe.time, _, kind, args = heapq.heappop(probe.q)
            probe.gc_tombstones()
            getattr(probe, kind)(*args)
        return not probe.mismatch(bid)

    def heartbeat(self):
        for b in self.builds.values():
            if not self.live(b['id']) or self.time < self.projs[b['projection']]['lost_until']:
                continue
            self.metrics['heartbeats'] += 1
            if self.mismatch(b['id']):
                self.metrics['heartbeat_mismatches'] += 1
                if b['repair'] is None and not self.suppress_snapshots:
                    self.start_snapshot(b, 'heartbeat')
            if self.replacement and b['repair'] is None and not self.suppress_snapshots:
                if any(key[0] == b['id'] and fact.get('state') == 'pending'
                       and self.time - fact['since'] > PENDING_MAX for key, fact in self.facts.items()):
                    self.metrics['pending_age_requests'] += 1
                    self.start_snapshot(b, 'pending_age')
        if self.q:
            self.later(HEARTBEAT, 'heartbeat')

    def start_snapshot(self, b, reason='heartbeat'):
        if self.suppress_snapshots:
            return
        if reason == 'heartbeat':
            self.metrics['heartbeat_snapshots'] += 1
            if self.measure_transients:
                self.metrics['transient_snapshots'] += self.transient_without_repair(b['id'])
        if self.replacement:
            self.start_replacement(b, reason)
            return
        self.snapshot_id += 1
        sid = self.snapshot_id
        b['repair'] = sid
        watermark = b['counter']
        for key, fact in self.facts.items():
            if key[0] == b['id']:
                fact['confirmed'] = False
        entries = [(b['id'], key, True, rev, b['versions'][key]) for key, rev in b['store'].items()]
        self.snapshots[sid] = dict(build=b['id'], watermark=watermark, pending=len(entries), ready=False)
        self.metrics['snapshots'] += 1
        self.metrics['snapshots_' + reason] += 1
        self.log('snapshot %d %s reason=%s watermark=%d entries=%d' %
                 (sid, b['id'], reason, watermark, len(entries)))
        for entry in entries:
            envelope = dict(change=entry, snapshot=sid, issued=self.time, epoch=None,
                            delivery=dict(done=False))
            self.later(self.r.randint(1, 35) if self.faults else 1, 'report', envelope)
            self.later(RETRY_LIFETIME, 'sdk_deadline', envelope)
        self.later(self.r.randint(5, 20) if self.faults else 2, 'snapshot_ready', sid)

    def maybe_sweep(self, sid):
        state = self.snapshots.get(sid)
        if state is None or not state['ready'] or state['pending']:
            return
        bid, watermark = state['build'], state['watermark']
        if self.live(bid):
            for key, fact in list(self.facts.items()):
                if key[0] == bid and not fact['confirmed'] and fact['version'] <= watermark:
                    self.apply_fact((bid, key[1:], False, None, watermark))
                    self.log('sweep tombstone %s v=%d' % (key, watermark))
            self.builds[bid]['repair'] = None
            self.restore_complete(bid)
        del self.snapshots[sid]
        self.log('snapshot %d end' % sid)

    def start_replacement(self, b, reason):
        self.snapshot_id += 1
        sid, watermark = self.snapshot_id, b['counter']
        b['repair'] = sid
        entries = [dict(key=key, state='included', revision=rev, version=b['versions'][key], since=None)
                   for key, rev in b['store'].items()]
        entries += [dict(key=key, state='pending', **intent) for key, intent in b['intents'].items()]
        pages = [entries[i:i + 2] for i in range(0, len(entries), 2)] or [[]]
        self.snapshots[sid] = dict(build=b['id'], watermark=watermark, pages=len(pages),
                                   received={}, issued=self.time)
        if self.variant != 'N-viewexp':
            self.later(RETRY_LIFETIME, 'replacement_deadline', sid)
        self.metrics['snapshots'] += 1
        self.metrics['snapshots_' + reason] += 1
        self.log('replacement view %d %s W=%d store=%d unfinished=%d pages=%d' %
                 (sid, b['id'], watermark, len(b['store']), len(b['intents']), len(pages)))
        for index, page in enumerate(pages):
            for entry in page:
                self.log('view %d page=%d %s %s rev=%s original_v=%d' %
                         (sid, index, entry['key'], entry['state'], entry['revision'], entry['version']))
            for _ in range(self.r.randint(1, 3) if self.faults else 1):
                delay = (self.r.randint(90, 180) if self.r.random() < .1 else self.r.randint(1, 40)) if self.faults else 1
                self.later(delay, 'replacement_page', sid, index, page)

    def replacement_page(self, sid, index, page):
        state = self.snapshots.get(sid)
        if state is None:
            self.metrics['old_snapshot_pages_ignored'] += 1
            self.log('IGNORE obsolete replacement page %d index=%d' % (sid, index))
            return
        if self.variant != 'N-viewexp' and self.time - state['issued'] >= RETRY_LIFETIME:
            self.replacement_deadline(sid)
            return
        if index in state['received']:
            self.metrics['duplicate_snapshot_pages'] += 1
            return
        if self.faults and self.r.random() < .12:
            self.metrics['snapshot_page_retries'] += 1
            self.later(self.r.randint(1, 20), 'replacement_page', sid, index, page)
            return
        state['received'][index] = deepcopy(page)
        self.log('replacement page %d index=%d arrived records=%d' % (sid, index, len(page)))
        if len(state['received']) == state['pages']:
            self.finish_replacement(sid)

    def discard_replacement(self, sid, reason):
        state = self.snapshots.pop(sid)
        bid = state['build']
        self.builds[bid]['repair'] = None
        self.metrics['snapshot_aborts'] += 1
        self.metrics['replacement_aborts_' + reason] += 1
        self.log('DISCARD replacement %d %s reason=%s age=%d; fresh view' %
                 (sid, bid, reason, self.time - state['issued']))
        self.force_snapshot(bid, reason)

    def replacement_deadline(self, sid):
        if sid in self.snapshots:
            self.discard_replacement(sid, 'view_lifetime')

    def finish_replacement(self, sid):
        state = self.snapshots[sid]
        bid, watermark = state['build'], state['watermark']
        view = {}
        for index in sorted(state['received']):
            for entry in state['received'][index]:
                key = tuple(entry['key'])
                old = view.get(key)
                if old is None or entry['state'] == 'pending':
                    view[key] = entry
        if self.variant not in ('N-viewexp', 'N12'):
            for key, entry in view.items():
                if self.expired_reference(bid, key, entry['version'], state['issued']):
                    self.metrics['expired_replacement_entries_rejected'] += 1
                    self.log('REJECT expired-tombstone replacement entry %s %s original_v=%d view_time=%d' %
                             (bid, key, entry['version'], state['issued']))
                    self.discard_replacement(sid, 'expired_replacement')
                    return
        if self.live(bid):
            keys = {key[1:] for key in self.facts if key[0] == bid} | set(view)
            for key in sorted(keys):
                fact = self.facts.get((bid,) + key)
                if fact is not None and fact['version'] > watermark:
                    self.log('replacement KEEP >W %s %s v=%d W=%d' % (bid, key, fact['version'], watermark))
                    continue
                entry = view.get(key)
                if entry is not None:
                    self.apply_fact((bid, key, True, entry['revision'], watermark),
                                    state=entry['state'], replacing=True, pending_since=entry['since'])
                elif self.variant == 'N2':
                    self.facts.pop((bid,) + key, None)
                    self.log('replacement DELETE absent %s %s W=%d' % (bid, key, watermark))
                else:
                    self.apply_fact((bid, key, False, None, watermark), replacing=True)
            b = self.builds[bid]
            b['fence'] = max(b['fence'], watermark)
            b['repair'] = None
            self.restore_complete(bid)
            self.log('replacement %d atomic END %s fence=%d' % (sid, bid, b['fence']))
            self.metrics['replacements'] += 1
        del self.snapshots[sid]

    def any_lost(self):
        return any(self.live(b['id']) and self.time < self.projs[b['projection']]['lost_until']
                   for b in self.builds.values())

    def enforced(self, uid, resource=None):
        if self.any_lost() or self.restore_gated(uid):
            return False
        return not any(self.live(bid) and u == uid and (resource is None or r == resource)
                       and (fact['included'] or (self.registered and fact.get('state') == 'pending'))
                       for (bid, u, r), fact in self.facts.items())

    def safety(self):
        for uid, d in self.docs.items():
            judged = self.enforced(uid)
            if self.any_lost() and judged:
                self.fail('S7', dict(uid=uid))
            if d['deleted']:
                if judged and not self.enforcement_previous.get(uid, False):
                    self.log('ENFORCED %s true' % uid)
                if self.enforcement_previous.get(uid, False) and not judged:
                    self.metrics['flip_backs'] += 1
                    self.log('FLIP-BACK %s enforcement true->false' % uid)
                    if self.restore_gated(uid):
                        self.metrics['restore_gate_flips'] += 1
                        self.log('RESTORE-GATE FLIP %s (not a fact-based failure)' % uid)
                    elif self.any_lost():
                        self.metrics['flip_backs_liveness_gate'] += 1
                    else:
                        self.metrics['fact_based_flip_backs'] += 1
                        self.fail('S1_flipback', dict(uid=uid, reason='fact-based enforcement reversal'))
                self.enforcement_previous[uid] = judged
                stores = [b['id'] for b in self.builds.values() if self.live(b['id'])
                          and any(key[0] == uid for key in b['store'])]
                if judged and stores:
                    self.fail('S1', dict(uid=uid, stores=stores))
        for b in self.builds.values():
            if self.live(b['id']) and b['projection'] == 'wiki':
                assert b['pages'] == self.page_maps(b['store']), 'page/store atomicity'
                assert all(1 <= len(sources) <= 2 for sources in b['pages'].values())
                assert all(len({key[1] for key in sources}) == 1 for sources in b['pages'].values())

    def liveness(self):
        for b in self.builds.values():
            if not self.live(b['id']):
                continue
            wanted = {}
            for uid in self.docs:
                desired = self.desired(uid, b['projection'])
                if desired is not None:
                    wanted[(uid, desired[0])] = desired[1]
            if b['store'] != wanted or (b['projection'] == 'wiki' and b['pages'] != self.page_maps(wanted)):
                self.fail('L1', dict(build=b['id'], store=repr(b['store']), desired=repr(wanted)))
            if self.included_facts(b['id']) != b['store']:
                self.fail('L2', dict(build=b['id'], facts=repr(self.included_facts(b['id'])), store=repr(b['store'])))
        for p, state in self.projs.items():
            if state['cursor'] != len(self.feed) or state['reported_cursor'] != len(self.feed):
                self.fail('L3', dict(projection=p, cursor=state['cursor'], reported=state['reported_cursor'], tail=len(self.feed)))
        pending = [key for key, f in self.facts.items() if self.live(key[0]) and f.get('state') == 'pending']
        if pending:
            self.fail('L4', dict(pending=pending))
        for uid, d in self.docs.items():
            if (d['deleted'] or d['withdrawn']) and not self.enforced(uid):
                self.fail('L5', dict(uid=uid, scope='document'))
        for uid, resource in sorted(self.moved_out):
            if self.docs[uid]['resource'] != resource and not self.enforced(uid, resource):
                self.fail('L5', dict(uid=uid, resource=resource, scope='moved-out'))

    def step(self):
        self.time, _, kind, args = heapq.heappop(self.q)
        self.steps += 1
        self.last_events.append((self.time, kind))
        self.gc_tombstones()
        getattr(self, kind)(*args)
        self.safety()
        if self.time >= 200 and 't200' not in self.saved:
            self.saved['t200'] = deepcopy(self.facts)
        return kind

    def run(self, max_steps=30000):
        while self.q and self.steps < max_steps:
            self.step()
        if self.q:
            maintenance = {'heartbeat', 'report', 'outbox_send', 'snapshot_ready', 'force_snapshot',
                           'sdk_deadline', 'pending_expired', 'replacement_page', 'replacement_deadline'}
            kinds = Counter(event[2] for event in self.q)
            if self.time >= self.external_end and set(kinds) <= maintenance:
                self.fail('L0', dict(reason='repair/report cycle at execution bound',
                    queue=dict(kinds), cycle=list(self.last_events),
                    snapshot_version_obstructions=[dict(build=b['id'], key=key,
                        store_revision=revision, store_version=b['versions'][key],
                        fact=deepcopy(self.facts[(b['id'],) + key]))
                        for b in self.builds.values() if self.live(b['id'])
                        for key, revision in b['store'].items()
                        if self.facts.get((b['id'],) + key, {}).get('version', -1) > b['versions'][key]]))
            else:
                self.unknown = 'Execution bound before quiescence: ' + repr(dict(kinds))
        else:
            assert not any(b['jobs'] for b in self.builds.values() if self.live(b['id']))
            assert not any(p['running'] or p['sources'] for p in self.projs.values())
            self.liveness()
        result = dict(seed=self.seed, variant=self.variant, workload=self.name,
                      violations=dict(self.failures), witnesses=self.witnesses,
                      metrics=dict(self.metrics), unknown=self.unknown, steps=self.steps,
                      time=self.time, quiescent=not self.q, workload_hash=self.workload_hash,
                      trace_tail=list(self.trace)[-30:], final_mismatches={
                          b['id']: dict(store=repr(b['store']), facts=repr(self.included_facts(b['id'])))
                          for b in self.builds.values() if self.live(b['id'])
                          and self.included_facts(b['id']) != b['store']})
        result['verdict'] = 'FAIL' if self.failures else ('UNKNOWN' if self.unknown else 'PASS')
        return result
