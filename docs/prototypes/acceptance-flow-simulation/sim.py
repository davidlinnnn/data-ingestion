"""Simulation of the #57 acceptance flow on the platform-database side: Canonical Acceptance (B1),
a late result for a deleted Document (B4), current-revision selection (B5), failed requests (B7),
adoption with a declared refresh scope and the sweep (B8), rollback by re-adoption (B6).

No Temporal, no database: requests end in any order, a report may arrive twice, and every event
interleaves at random. `World.check` asserts the invariants once nothing is left to do.

Three sweep rules are compared:
  v1  the rule as first written: a later adoption's scope covers the revision (scopes add up)
  v2  the latest adoption's scope only, and never a revision made by the adopted version
  v3  v2, plus a withdrawn version stays in scope until no Document is served from it

Run with the project's Python: python sim.py [random runs] [seed]
"""

import random
import sys
from dataclasses import dataclass, field

CAP = 3  # requests the sweep opens per (Document, Source Revision, adoption) before it gives up


@dataclass
class Adoption:
    seq: int
    version: int
    scope: object  # "none", "all", or a frozenset of profile versions (Documents made by them)


@dataclass
class Request:
    rid: int
    doc: int
    srv: int  # the Source Revision's per-Document order
    version: int
    seq: int
    initiator: str  # source, platform (refresh), operator (re-run of a failed Source Revision)
    state: str = "active"  # succeeded, failed, void (ended, formed no acceptance)
    retryable: bool = False


@dataclass
class Revision:
    rid: int
    srv: int
    version: int
    seq: int


@dataclass
class Doc:
    uid: int
    poison: frozenset  # profile versions under which this Document fails every time
    rejects: set = field(default_factory=set)  # Source Revisions the Source broke: always rejected
    latest: int = 1
    deleted_with: int | None = None  # revisions held when it was deleted
    current: Revision | None = None
    revisions: list = field(default_factory=list)
    outcome: dict = field(default_factory=dict)  # srv -> pending, accepted, failed, rejected


class World:
    def __init__(self, rule="v3", cap=CAP, block=False):
        self.rule, self.cap, self.block = rule, cap, block
        self.adoptions = [Adoption(1, 1, "none")]
        self.withdrawn: set[int] = set()
        self.docs: list[Doc] = []
        self.requests: list[Request] = []
        self.pointer_changes = 0  # one feed event each
        self.late_promotions = 0  # a withdrawn version's revision became current
        self.voided = 0
        self.gave_up: set[tuple] = set()  # (doc, srv, adoption seq) the sweep stopped trying
        self.opened: dict[tuple, int] = {}  # requests the sweep opened, by the same key

    # --- admission -------------------------------------------------------------------------
    @property
    def adopted(self) -> Adoption:
        return self.adoptions[-1]

    def active(self, doc: int, srv: int | None = None) -> list[Request]:
        return [
            r for r in self.requests
            if r.doc == doc and r.state == "active" and (srv is None or r.srv == srv)
        ]  # fmt: skip

    def request(self, doc: Doc, srv: int, initiator: str) -> Request:
        if existing := self.active(doc.uid, srv):  # the partial unique index of spec §3
            return existing[0]
        a = self.adopted
        r = Request(len(self.requests), doc.uid, srv, a.version, a.seq, initiator)
        self.requests.append(r)
        doc.outcome.setdefault(srv, "pending")
        return r

    def submit(self, poison=frozenset()) -> Doc:
        doc = Doc(len(self.docs), frozenset(poison))
        self.docs.append(doc)
        self.request(doc, 1, "source")
        return doc

    def update(self, doc: Doc, rejected=False) -> None:
        if doc.deleted_with is None:
            doc.latest += 1
            if rejected:
                doc.rejects.add(doc.latest)
            self.request(doc, doc.latest, "source")

    def source_retry(self, doc: Doc) -> None:  # spec §6.4: same content, latest outcome failed
        if doc.deleted_with is None and doc.outcome.get(doc.latest) == "failed":
            self.request(doc, doc.latest, "source")

    def delete(self, doc: Doc) -> None:
        if doc.deleted_with is None:
            doc.deleted_with = len(doc.revisions)

    def adopt(self, version: int, scope, withdraw: int | None = None) -> None:
        assert version not in self.withdrawn, "a withdrawn version is not adopted again"
        self.adoptions.append(Adoption(self.adopted.seq + 1, version, scope))
        if withdraw is not None:
            self.withdrawn.add(withdraw)

    # --- acceptance (B1, B4, B5, B7) -------------------------------------------------------
    def report(self, r: Request, transient=False) -> None:
        if r.state != "active":
            return  # a repeated report, or the reconciler after the report, changes nothing
        doc = self.docs[r.doc]
        if r.srv in doc.rejects:  # a source cause: re-run once per adoption, like a dead failure
            r.state, doc.outcome[r.srv] = "failed", "rejected"
            return
        if transient or r.version in doc.poison:
            r.state, r.retryable = "failed", r.version not in doc.poison
            if r.initiator != "platform":
                doc.outcome[r.srv] = "failed"
            return
        if doc.deleted_with is not None or (self.block and r.version in self.withdrawn):
            r.state = "void"  # B4, and the variant that never accepts a withdrawn version
            self.voided += 1
            return
        r.state = "succeeded"
        rev = Revision(r.rid, r.srv, r.version, r.seq)
        doc.revisions.append(rev)
        doc.outcome[r.srv] = "accepted"
        cur = doc.current
        if cur is None or (rev.srv, rev.seq) > (cur.srv, cur.seq):  # B5, evaluated once
            doc.current = rev
            self.pointer_changes += 1
            self.late_promotions += rev.version in self.withdrawn

    # --- the sweep (B8) --------------------------------------------------------------------
    def covers(self, rev: Revision) -> bool:
        a = self.adopted
        if self.rule == "v1":
            return any(
                x.seq > rev.seq and (x.scope == "all" or (x.scope != "none" and rev.version in x.scope))
                for x in self.adoptions
            )  # fmt: skip
        if rev.version == a.version:
            return False
        if self.rule == "v3" and rev.version in self.withdrawn:
            return True
        return a.scope == "all" or (a.scope != "none" and rev.version in a.scope)

    def given_up(self, doc: Doc, srv: int) -> bool:
        key = (doc.uid, srv, self.adopted.seq)
        dead = any(
            r.doc == doc.uid and r.srv == srv and r.seq == key[2] and r.state == "failed" and not r.retryable
            for r in self.requests
        )  # fmt: skip
        if dead or self.opened.get(key, 0) >= self.cap:
            self.gave_up.add(key)
            return True
        return False

    def target(self, doc: Doc) -> tuple[int, str] | None:
        """The Source Revision the sweep opens a request for, with the initiator, or None."""
        revs = [x for x in doc.revisions if x.srv == doc.latest]
        if revs:
            best = max(revs, key=lambda x: x.seq)
            if self.covers(best) and not self.given_up(doc, doc.latest):
                return doc.latest, "platform"
            return None
        last = [r for r in self.requests if r.doc == doc.uid and r.srv == doc.latest][-1]
        if last.state in ("failed", "void") and not self.given_up(doc, doc.latest):
            return doc.latest, "operator"
        cur = doc.current  # the latest content cannot be made now: the served content stays in scope
        if cur and self.covers(cur) and not self.given_up(doc, cur.srv):
            return cur.srv, "platform"
        return None

    def sweep(self, batch: int | None = None) -> int:
        made = 0
        for doc in self.docs:
            if batch is not None and made >= batch:
                break
            if doc.deleted_with is not None or self.active(doc.uid):
                continue
            if found := self.target(doc):
                key = (doc.uid, found[0], self.adopted.seq)
                self.opened[key] = self.opened.get(key, 0) + 1
                self.request(doc, *found)
                made += 1
        return made

    # --- driving ---------------------------------------------------------------------------
    def finish(self, rng: random.Random | None = None) -> None:
        pending = [r for r in self.requests if r.state == "active"]
        if rng:
            rng.shuffle(pending)
        for r in pending:
            self.report(r)

    def settle(self, rng: random.Random | None = None, limit=200) -> None:
        """Ends every request and sweeps until a sweep opens nothing."""
        for _ in range(limit):
            self.finish(rng)
            if not self.sweep():
                return
        raise AssertionError("the sweep never reaches a fixed point")

    def check(self) -> tuple[int, int]:
        """Asserts the invariants at rest. Returns the Documents served from a withdrawn version:
        (not counted by the sweep, counted because the redo failed)."""
        assert not any(r.state == "active" for r in self.requests) and not self.sweep()
        assert all(n <= self.cap for n in self.opened.values()), "the sweep exceeded its cap"
        stuck = counted = 0
        for doc in self.docs:
            for srv, outcome in doc.outcome.items():
                has = any(x.srv == srv for x in doc.revisions)
                assert (outcome == "accepted") == has, "outcome accepted iff a revision exists"
            if doc.deleted_with is not None:
                assert len(doc.revisions) == doc.deleted_with, "acceptance after deletion"
                continue

            def gone(srv: int, uid=doc.uid) -> bool:
                return (uid, srv, self.adopted.seq) in self.gave_up

            cur = doc.current
            revs = [x for x in doc.revisions if x.srv == doc.latest]
            if revs:
                best = max(revs, key=lambda x: x.seq)
                assert cur is best, "current is not the best revision of the latest content"
                assert not self.covers(best) or gone(doc.latest), "in scope, not redone, not counted"
            else:
                assert gone(doc.latest), "latest content neither accepted nor a counted failure"
                assert not (cur and self.covers(cur)) or gone(cur.srv), "served content left in scope"
            if cur and cur.version in self.withdrawn:
                stuck += not gone(cur.srv)
                counted += gone(cur.srv)
        return stuck, counted


# --- fixed cases -------------------------------------------------------------------------------
def case_f1(rule: str) -> int:
    """@2 declared all, 5 of 50 refreshed, then back to @1: requests the rollback opens."""
    w = World(rule=rule)
    for _ in range(50):
        w.submit()
    w.settle()
    w.adopt(2, "all")
    w.sweep(batch=5)
    w.finish()
    before = len(w.requests)
    w.adopt(1, frozenset({2}), withdraw=2)
    w.settle()
    if rule != "v1":
        assert w.check() == (0, 0)
    return len(w.requests) - before


def case_all_then_none() -> int:
    """@2 declared all, 5 of 50 refreshed, then @3 declared none: requests opened afterwards."""
    w = World()
    for _ in range(50):
        w.submit()
    w.settle()
    w.adopt(2, "all")
    w.sweep(batch=5)
    before = len(w.requests)
    w.adopt(3, "none")
    w.settle()
    w.check()
    return len(w.requests) - before


def case_scenario7(first: int) -> tuple:
    """S2 in flight under @1 and S3 in flight under @2; `first` is the one that ends first."""
    w = World()
    doc = w.submit()
    w.settle()
    w.update(doc)
    w.adopt(2, "all")
    assert w.sweep() == 0, "the sweep leaves a Document with an active request alone"
    w.update(doc)
    s2, s3 = w.active(doc.uid)
    for r in (s2, s3) if first == 2 else (s3, s2):
        w.report(r)
    w.settle()
    w.check()
    return doc.current.srv, doc.current.version, len(w.requests)


def case_f2() -> tuple:
    """The latest Source Revision failed under @1, then @2 is adopted with scope none."""
    w = World()
    a = w.submit(poison={1})  # a: a first submission that fails under @1
    b, c = w.submit(), w.submit()
    w.settle()
    b.poison, c.poison = frozenset({1}), frozenset({1, 2})
    w.update(b)  # b: an update that fails under @1
    w.update(c)  # c: an update that fails under @1 and @2
    w.settle()
    before = (a.current, b.current.srv, c.current.srv)
    w.adopt(2, "none")
    w.settle()
    w.check()
    return before, [(d.current.srv, d.current.version) for d in (a, b, c)]


def case_f3(cap: int, transient: bool) -> int:
    """A refresh that fails on every try: requests opened over 50 sweep runs."""
    w = World(cap=cap)
    doc = w.submit()
    w.settle()
    doc.poison = frozenset() if transient else frozenset({2})
    w.adopt(2, "all")
    for _ in range(50):
        w.sweep()
        for r in w.active(doc.uid):
            w.report(r, transient=transient)
    return len(w.requests) - 1


def case_dropped(rule: str) -> int:
    """A rollback's redo is 5 of 20 done when @3 is adopted with scope none: Documents left on @2."""
    w = World(rule=rule)
    for _ in range(20):
        w.submit()
    w.settle()
    w.adopt(2, "all")
    w.settle()
    w.adopt(1, frozenset({2}), withdraw=2)
    w.sweep(batch=5)
    w.adopt(3, "none")
    w.settle()
    return w.check()[0]


def case_f11(block: bool) -> tuple:
    """A rollback while @2 work is in flight: a refresh of an old Document, and a new Document."""
    w = World(block=block)
    old = w.submit()
    w.settle()
    w.adopt(2, "all")
    w.sweep()
    new = w.submit()
    w.adopt(1, "none", withdraw=2)
    w.finish()
    seen = (old.current.version, new.current.version if new.current else None)
    w.settle()
    assert w.check() == (0, 0)
    return w.late_promotions, seen, (old.current.version, new.current.version), w.pointer_changes


def case_rejected_latest() -> tuple:
    """Review B, H1: current made by @2 on S1, S2 rejected, then @2 withdrawn: S1 is redone."""
    w = World()
    w.adopt(2, "none")
    doc = w.submit()
    w.settle()
    w.update(doc, rejected=True)
    w.settle()
    w.adopt(1, "none", withdraw=2)
    w.settle()
    assert w.check() == (0, 0)
    return doc.current.srv, doc.current.version, doc.outcome[2]


def case_b4() -> tuple:
    """Deletion before the result arrives, and after acceptance with a refresh in flight."""
    w = World()
    a, b = w.submit(), w.submit()
    w.delete(a)
    w.report(w.requests[1])
    w.adopt(2, "all")
    w.sweep()
    w.delete(b)
    w.settle()
    w.check()
    return len(a.revisions), len(b.revisions), w.voided, w.pointer_changes


# --- random runs -------------------------------------------------------------------------------
def random_run(rng: random.Random, rule: str, block: bool) -> World:
    w = World(rule=rule, block=block)
    top = 1
    for _ in range(rng.randint(10, 80)):
        live = [d for d in w.docs if d.deleted_with is None]
        active = [r for r in w.requests if r.state == "active"]
        roll = rng.random()
        if roll < 0.18 or not w.docs:
            poison = set()
            if rng.random() < 0.15:
                poison = {rng.randint(1, top + 1)} if rng.random() < 0.8 else set(range(1, 99))
            w.submit(poison)
        elif roll < 0.33 and live:
            w.update(rng.choice(live), rejected=roll < 0.20)  # no extra draw: the stream is kept
        elif roll < 0.63 and active:
            r = rng.choice(active)
            w.report(r, transient=rng.random() < 0.15)
            if rng.random() < 0.1:
                w.report(r)
        elif roll < 0.68 and live:
            w.delete(rng.choice(live))
        elif roll < 0.74 and live:
            w.source_retry(rng.choice(live))
        elif roll < 0.80:
            top += 1
            w.adopt(top, rng.choice(["none", "all", frozenset({w.adopted.version})]))
        elif roll < 0.86:
            bad = w.adopted.version
            good = [v for v in range(1, top + 1) if v != bad and v not in w.withdrawn]
            if good:
                scope = rng.choice(["none", "all", frozenset({bad})])
                w.adopt(rng.choice(good), scope, withdraw=bad if rng.random() < 0.7 else None)
        else:
            w.sweep(batch=rng.choice([None, 1, 3]))
    w.settle(rng)
    return w


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 57
    print(f"F1  requests a rollback opens, 5 of 50 refreshed: v1 {case_f1('v1')}, v3 {case_f1('v3')}")
    print(f"F1  all unfinished, then none: requests opened afterwards: {case_all_then_none()}")
    print(f"S7  (current srv, version, requests): S2 first {case_scenario7(2)}, S3 first {case_scenario7(3)}")
    print(f"F2  (before the fix, after it): {case_f2()}")
    print(
        "F3  requests for a refresh that always fails, 50 sweep runs:"
        f" no cap {case_f3(10**9, True)}, service down {case_f3(CAP, True)}, content {case_f3(CAP, False)}"
    )
    print(f"F4  Documents left on a withdrawn version: v2 {case_dropped('v2')}, v3 {case_dropped('v3')}")
    for block in (False, True):
        print(f"F11 block={block}: (late promotions, seen, final, feed events) {case_f11(block)}")
    print(f"B4  (revisions of a, of b, void results, feed events): {case_b4()}")
    print(f"H1  latest rejected, served version withdrawn: (current srv, version, S2) {case_rejected_latest()}")

    rng = random.Random(seed)
    total = {"documents": 0, "requests": 0, "gave up": 0, "served faulty, redo failed": 0}
    for i in range(runs):
        w = random_run(rng, "v3", block=i % 2 == 1)
        stuck, counted = w.check()
        assert stuck == 0
        total["documents"] += len(w.docs)
        total["requests"] += len(w.requests)
        total["gave up"] += len(w.gave_up)
        total["served faulty, redo failed"] += counted
    print(f"v3: {runs} random runs, seed {seed}: every invariant held; {total}")

    rng = random.Random(seed)
    bad = sum(random_run(rng, "v2", block=False).check()[0] > 0 for _ in range(runs))
    print(f"v2: {bad} of {runs} random runs end with a Document served from a withdrawn version")


if __name__ == "__main__":
    main()
