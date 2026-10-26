"""Fixed schedules. Expected results are assertions about observations, never knobs."""
from copy import deepcopy
import heapq
from model import Simulation, TTL


class FixedSchedule:
    """Explicit minimum delays for protocol follow-up; no scenario RNG."""
    def randint(self, low, high):
        return low

    def random(self):
        return .5

    def shuffle(self, values):
        return None


class ScriptedSimulation(Simulation):
    def __init__(self, variant, projection='retrieval', uids=('d0', 'd2')):
        super().__init__(0, variant, 'scripted', actions=[], full_trace=True,
                         faults=False, measure_transients=False)
        self.r = FixedSchedule()
        self.report_at = None
        self.drop_reports = False
        self.crash_confirmations = False
        self.crash_scheduled = False
        self.retry_not_before = 0
        self.first_view_page_at = None
        self.bid = projection + '-0'
        for uid, d in self.docs.items():
            if uid not in uids:
                d['withdrawn'] = True
        for b in self.builds.values():
            if b['id'] != self.bid:
                b['state'] = 'retired'
                b['store'].clear()
                b['pages'].clear()
            else:
                b['store'] = {k: v for k, v in b['store'].items() if k[0] in uids}
                b['pages'] = self.page_maps(b['store']) if projection == 'wiki' else {}
        self.facts = {k: v for k, v in self.facts.items() if k[0] == self.bid and k[1] in uids}
        self.saved['initial'] = deepcopy(self.facts)

    def send_report(self, change):
        if self.crash_confirmations:
            if not self.crash_scheduled:
                self.later(0, 'action', 'crash', [self.builds[change[0]]['projection']])
                self.crash_scheduled = True
            return super().send_report(change)
        if self.drop_reports:
            self.log('script crash loses unsent report %s' % (change,))
            self.metrics['crash_lost_reports'] += 1
            return
        t = self.report_at if self.report_at is not None and change[2] else self.time + 1
        self.at(max(t, self.time), 'report', dict(change=change, issued=self.time,
                epoch=self.projs[self.builds[change[0]]['projection']]['epoch'], snapshot=None))
        self.log('script report queued %s v=%d arrival=%d' % (change[1], change[-1], max(t, self.time)))

    def script_read(self, trigger, finish_at, write_delay=0, fail_write=None):
        b = self.builds[self.bid]
        p = self.projs[b['projection']]
        locked = self.family(trigger) if b['projection'] == 'wiki' else (trigger,)
        assert not any(uid in p['running'] for uid in locked)
        for uid in locked:
            p['running'][uid] = self.bid
        b['jobs'][trigger] = dict(status='running', dirty=False)
        wanted = {}
        for uid in locked:
            d = self.desired(uid, b['projection'])
            if d:
                wanted[(uid, d[0])] = d[1]
            self.log('SCRIPT read %s trigger=%s source=%s desired=%s' % (self.bid, trigger, uid, d))
        self.attempt_id += 1
        attempt = dict(id=self.attempt_id, trigger=trigger, locked=locked, wanted=wanted,
                       versions={}, registered=False, write_delay=write_delay)
        if fail_write is not None:
            attempt['fail_write'] = fail_write
        self.at(finish_at, 'finish', self.bid, attempt, False)

    def dispatch(self, p):
        if self.time < self.retry_not_before:
            self.at(self.retry_not_before, 'dispatch', p)
            return
        super().dispatch(p)

    def script_view(self, reserve=False):
        b = self.builds[self.bid]
        if reserve:
            b['counter'] += 1
            self.log('reserve unused fact_version %s v=%d' % (self.bid, b['counter']))
        self.force_snapshot(self.bid, 'scripted_witness')

    def start_replacement(self, b, reason):
        super().start_replacement(b, reason)
        if self.first_view_page_at is not None:
            sid = b['repair']
            self.q = [(self.first_view_page_at if kind == 'replacement_page' and args[0] == sid else t,
                       serial, kind, args) for t, serial, kind, args in self.q]
            heapq.heapify(self.q)
            self.log('SCRIPT replacement %d last page held until=%d' % (sid, self.first_view_page_at))
            self.first_view_page_at = None

    def step(self):
        kind = super().step()
        if self.name in ('SC21', 'SC24'):
            b = self.builds[self.bid]
            fact = self.facts.get((self.bid, 'd0', 'r0'), {})
            self.log('boundary %s counter=%d fence=%d store_v=%s mirror=%s/v%s unfinished=%d' %
                     (kind, b['counter'], b['fence'], b['versions'].get(('d0', 'r0')),
                      fact.get('state', 'included' if fact.get('included') else 'absent'),
                      fact.get('version'), len(b['intents'])))
        return kind

    def script_remove(self):
        b = self.builds[self.bid]
        for key in list(b['store']):
            if key[0] == 'd0':
                del b['store'][key]
                change = self.changed(b, key, False, None)
                self.log('SCRIPT store remove %s v=%d' % (key, change[-1]))
                if not self.drop_reports:
                    self.apply_fact(change)
                else:
                    self.metrics['crash_lost_reports'] += 1
        if b['projection'] == 'wiki':
            b['pages'] = self.page_maps(b['store'])

    def script_revision(self, uid, revision):
        self.next_revision = revision - 1
        self.action('source_update', [uid])


EXPECTED = {
    'SC15': {'V1': {'S1'}, 'V2': set(), 'V3': set(), 'V4': set()},
    'SC16': {'V3': set(), 'V4': set(), 'V4-Ra': {'L5'}},
    'SC18': {'V3': set(), 'V4': set(), 'V4-Rb': set()},
    'SC19': {'V3': set(), 'V4': set(), 'N12': {'S1_flipback'}},
    'SC20r': {v: set() for v in ('V1', 'V2', 'V3', 'V4')},
    'SC20u': {'V1': {'L2'}, 'V2': {'L2'}, 'V3': set(), 'V4': set()},
    'NC2': {'V3': set(), 'V4': set(), 'N2': set(), 'N-fence': set()},
    'SC21': {'V2': {'L0'}, 'V3': {'L0'}, 'V4': set()},
    'SC22': {'V3': {'L4'}, 'V4': set()},
    'SC23': {'V4': set()},
    'SC24': {'V4': set(), 'N-viewexp': {'S1_flipback', 'L2'}},
}


def scenario(name, variant):
    if name == 'SC24':
        s = ScriptedSimulation(variant, uids=('d0',))
        b = s.builds[s.bid]
        b['counter'] = 1
        s.first_view_page_at = 135
        s.at(10, 'script_view')
        s.at(11, 'action', 'delete', ['d0'])
        s.at(12, 'script_remove')
        s.external_end = 135
    elif name == 'SC21':
        # Phase-1 V2/seed-0: register v27; another key reaches v28;
        # snapshot sweeps before the delayed v27 write. No retry was lost.
        s = ScriptedSimulation(variant)
        b = s.builds[s.bid]
        b['counter'] = max(b['versions'][key] for key in b['store'])
        s.docs['d0']['revision'] = 50
        s.at(10, 'script_read', 'd0', 10, 5)
        s.at(11, 'action', 'withdraw', ['d2', True])
        s.at(11, 'script_read', 'd2', 11)
        s.at(12, 'script_view')
        s.external_end = 15
    elif name == 'SC22':
        s = ScriptedSimulation(variant, 'wiki')
        s.crash_confirmations = True
        s.at(10, 'script_read', 'd0', 10)
        s.external_end = 10
    elif name == 'SC23':
        s = ScriptedSimulation(variant, uids=('d0',))
        b = s.builds[s.bid]
        b['store'].clear()
        s.facts.clear()
        b['counter'] = 7
        s.at(10, 'script_read', 'd0', 10, 5)
        s.at(11, 'script_view', True)
        s.at(12, 'action', 'delete', ['d0'])
        s.external_end = 15
    elif name == 'SC18':
        s = ScriptedSimulation(variant, 'wiki')
        s.at(10, 'script_revision', 'd2', 50)
        s.at(10, 'script_read', 'd2', 12)
        s.at(11, 'action', 'delete', ['d0'])
        s.external_end = 12
    elif name == 'SC15':
        s = ScriptedSimulation(variant, uids=('d0',))
        s.builds[s.bid]['store'].clear()
        s.facts.clear()
        s.report_at = 12
        s.at(10, 'script_read', 'd0', 10)
        s.at(11, 'action', 'delete', ['d0'])
        # Keep the report-in-flight interval exact; removal is an independent event.
        s.at(14, 'script_remove')
        s.external_end = 14
    elif name == 'SC16':
        s = ScriptedSimulation(variant, uids=('d0',))
        s.at(1, 'action', 'pause', ['retrieval', 99])
        s.at(10, 'action', 'delete', ['d0'])
        s.external_end = 100
    elif name in ('SC19', 'NC2'):
        s = ScriptedSimulation(variant, uids=('d0',))
        b = s.builds[s.bid]
        b['counter'] = b['versions'][('d0', 'r0')] = 99
        s.facts[(s.bid, 'd0', 'r0')]['version'] = 99
        s.at(1, 'action', 'delete', ['d0'])
        s.at(1, 'script_remove')
        if name == 'NC2':
            s.drop_reports = True
            s.at(2, 'force_snapshot', s.bid, 'scripted_witness')
            arrival = 5
        else:
            arrival = 1 + TTL + 2
        s.at(arrival, 'report', dict(change=(s.bid, ('d0', 'r0'), True, 1, 99),
                                   issued=0, epoch=0, snapshot=None))
        s.external_end = arrival
    elif name in ('SC20r', 'SC20u'):
        s = ScriptedSimulation(variant)
        s.at(10, 'script_revision', 'd0', 50)
        s.at(10, 'script_read', 'd0', 10)
        s.at(20, 'action', 'rewind' if name == 'SC20r' else 'silent_rewind', [s.bid, 'initial'])
        s.external_end = 20
    else:
        raise ValueError(name)
    s.name = name
    s.workload_hash = 'scripted:' + name
    return s


def check_expected(name, variant, result):
    expected = EXPECTED[name][variant]
    actual = set(result['violations'])
    # A FAIL cell specifies necessary witnesses; additional failures are reported.
    match = (expected <= actual if expected else not actual) and result['unknown'] is None
    if name == 'SC24' and variant == 'N-viewexp':
        match = bool(expected & actual) and result['unknown'] is None
    if name == 'SC18':
        invalid = result['metrics'].get('already_invalid_landings', 0)
        match = match and (invalid >= 1 if variant == 'V4-Rb' else invalid == 0)
    if name == 'SC20r':
        match = match and result['metrics'].get('snapshots_restore', 0) > 0
    if name == 'SC20u':
        match = match and result['metrics'].get('snapshots_restore', 0) == 0
        if variant in ('V3', 'V4'):
            match = match and result['metrics'].get('snapshots_heartbeat', 0) > 0
    if name == 'SC22' and variant == 'V4':
        match = match and result['metrics'].get('snapshots_pending_age', 0) > 0
    return match
