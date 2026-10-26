# Model semantics and boundaries

`part_b.py` is a plain-Python deterministic discrete-event model, not a projection implementation. No design rule is changed after a baseline failure. Each seed has one workload, shared by the design and all six variants. The workload RNG is separate from the interleaving/failure RNG. Variants may consume scheduling randomness differently as their work diverges. The per-run workload hash allows comparison.

## What an event means

Time units are logical milliseconds. Platform mutations, feed delivery, an attempt's read, a Build-store transaction, an accepted fact report, and snapshot start/end are separate atomic events. A heap orders events by `(time, insertion_order)`. Safety is evaluated after **every** event. Included writes additionally check S2 and S3 inside the commit event, against the current platform state.

There are eight documents in two sources and two resources. Revision IDs are increasing integers allocated on canonical creation; canonical rollback reuses a previous ID. Source updates advance the source revision and create a canonical revision. Method refreshes create a canonical revision without changing the source revision. Deletion is permanent in this workload; withdrawal can be reinstated. Each source profile is a set of projections. A deleted/withdrawn document has no current revision. Rebind emits `inclusion_changed`; deletion emits both `current_revision_changed` and `document_deleted`. Events carry just the kind and identity.

The baseline read sees the actual platform state, including at least the delivered feed position. This is a permissible strong instance of the required read guarantee. The block table is represented by an immediate predicate: deleted, withdrawn, or the write targets a resource other than the current binding. This represents moved-out blocks without modeling a separate storage layer for them. The currently bound resource is unblocked upon rebind/reinstatement when otherwise eligible.

One reader per projection advances through the append-only feed and signals each live Build that subscribed at or before the event. A Build's bootstrap position is fixed at creation before enumeration. Enumeration and feed delivery run concurrently. Per-projection UID gates serialize the same document across Builds as well as within each Build. A running UID has one dirty bit; signals cause exactly one additional run, and further signals during that run can cause another. Queued signals coalesce before the next read. Failed attempts requeue and read again. Superseded attempts finish without committing; their own already-pending or subsequent feed event causes reconciliation.

Retrieval commits one document per attempt. Wiki groups 1–5 eligible UIDs from one Build into a transaction. Each member is validated at the same commit boundary; superseded members are excluded, and valid members commit atomically. Transactions on other UIDs remain concurrent. Slow completions take 25–85 ticks instead of 1–9; 12% of attempts fail and retry. Removal writes are allowed for blocked/deleted documents: S2/S3 refer to writing an **included** revision, since rejecting removal would prevent deletion from ever converging.

## Facts, snapshots, heartbeat

Each successful changed fact gets a new Build-wide counter value. Counters are shared across UIDs/resources and survive removal. The store retains its last version per key even when the content is removed. Reports get 1–3 copies, independently delayed 1–40 ticks or, in 10% of copies, 90–180 ticks. Delivery attempts fail with 12% probability and retry; duplicates, old deliveries and retired-Build deliveries are acknowledged. Reports for retired Builds cannot recreate their facts. Cursor reports also retry and use `max(old, reported)` on the platform.

Each fact is keyed by `(Build, uid, resource)`; the projection is determined by the Build ID, so this is equivalent to the specified four-part key. Accepted versions replace equal/older versions; older reports are ignored. Equal versions are idempotent for an uncorrupted fact. Removed facts carry a 30-day expiry. The model never reaches 30 days, so expiry itself is **not tested**.

A heartbeat compares the actual store's included count against the platform's included-fact count per live Build every 17 ticks. Only a count mismatch starts a repair. One repair per Build runs at a time. Start marks all its platform facts unconfirmed and atomically records the Build counter and a store view. Snapshot entries re-report the stored per-key versions; network delivery and retries interleave with commits and deltas. The snapshot ends after all entries have been accepted at least once. Accepted entries and delta deliveries interleaved with the active snapshot confirm facts. There is no additional pre-watermark-report exclusion rule in the supplied protocol. An unconfirmed fact is replaced by a removed tombstone at the start watermark, respecting the highest-version rule. N2 deletes it instead. This uses an atomic start view, a stronger snapshot consistency guarantee than an arbitrary live paginated scan; the supplied design does not specify the snapshot isolation mechanism. Snapshot entries are single logical reliable transfers; duplicate/delayed ordinary deltas are randomized. No repair is forced merely because a revision differs.

The corruption workload drops two existing included facts near t=240 and alters one existing fact's **revision** to `-999` near t=445. The latter preserves the included count. There is no hidden full-content audit that would repair this. The count check cannot detect all possible alterations; that limitation is an intended subject of the experiment, not silently treated as repaired. A snapshot triggered for another reason may happen to repair an alteration.

## Builds, readiness, deletion

Both projections start with one consistent serving Build. Each creates a second Build, bootstraps it, switches to it, optionally switches back, and retires the non-serving Build. Retained Builds keep consuming. The workload supplies external candidate approval; the design does not specify approval criteria, so the model does not invent them. A switch waits for enumeration to finish. Retirement clears the store and all its facts and prevents late reports from recreating them.

`source_profile_changed` starts one source pass per projection with a second dirty bit. Pages signal each UID to eligible non-retired Builds; completion waits for that pass's queued/running source work across those Builds. It reports the profile sequence observed at pass start. Repeated signals coalesce into one further pass. Backfill reports retry and only advance. The readiness calculation selects only the serving Build and applies membership and backfill sequence gates. Readiness has no separate user-requested invariant in this experiment; those paths have internal assertions, not a claim of a full readiness proof.

S1 implements the literal supplied predicate for every UID: **no included fact in any non-retired Build ⇒ no non-retired store contains the UID**. Counts also separately record the narrower case where the document actually is deleted. This prevents an ordinary reinclusion/report gap from being confused with an actual deletion-enforcement counterexample. Blocks affect admission/serving but do not magically erase content from a Build store.

L1 compares complete `(uid, resource) → revision` maps to the inclusion rule. L2 compares each live Build's store to the included subset of platform facts, including exact revisions; tombstones are metadata for absence. L3 compares the platform's reported cursor, not just the reader's local cursor, to the feed tail.

## Controls (one mutation at a time)

- N1: replace outgoing versions with a per-document counter; after assigning a removal version, reset that document counter to zero. Initial facts also use per-document versions. Keep the Build counter for snapshot watermarks, so the unrelated snapshot protocol is unchanged. This deliberately mixes incompatible version domains, illustrating the rejected version scheme.
- N2: delete unconfirmed keys at sweep instead of leaving watermark tombstones.
- N3: drop signals received while a UID is running; queued work still coalesces.
- N4: enumerate first; only then fix the feed start at the current tail and subscribe the new Build. Earlier events do not get replayed to it.
- N5: keep the block check but replace current-revision equality with `written_revision >= last_committed_revision`. Rollback remains in the workload.
- N6: return the complete historical platform state at `max(0, delivered_feed_position - 2)` instead of a fresh read. The commit check still sees the true current state.

Controls retain baseline failures. Tables report both raw failures and cases that fail where the same seed's baseline passed. No control is adjusted to manufacture a failure. Failure in a control is evidence for that workload; zero additional violations is not a proof that the mutation is safe.

## Quiescence, bounds and reproduction

Quiescence means no feed deliveries, reports/retries, source passes, bootstrap pages or attempts remain. The last heartbeat follows all pending work. Liveness is checked only then. A seed stops at 30,000 events if the protocol still cannot quiesce; its liveness result is **UNKNOWN**, never a pass. A repeated identical repair state can also stop a seed after 12 occurrences beyond t=1000. The event budget is a model execution bound, not a design timeout.

The first witness per invariant uses the smallest seed in the tested range, 0–999; this is not a claim of a globally minimal workload. The report gives a shortened causal trace, and replay can write the complete trace. JSONL records include each seed's workload hash, counters, witnesses and final mirror mismatches.

This does not represent real Wiki rendering/search indexing, physical transactions/locks, process crashes and recovery of durable outboxes, topology changes, authorization, a replica implementation, unbounded partitions, database failover, transaction-ID wraparound, 30-day tombstone expiry, or a formal proof over every interleaving. Random finite retries do not prove fairness over infinite executions. Part A separately exercises the real PostgreSQL feed ordering.
