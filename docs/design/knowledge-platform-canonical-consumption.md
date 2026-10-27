# Knowledge Platform canonical consumption and publication

The design result of
[Define canonical consumption and publication for Wiki and Retrieval](https://github.com/davidlinnnn/data-ingestion/issues/55),
confirmed with the user from 2026-10-22 to 2026-10-26 (grilling groups A–E,
an independent review, a simulation-based validation in two rounds with rulings
G1–G9, ruling J1 on the overlap with #85, and rulings K1 and K2 from a final
review). It builds on the
[admission specification](knowledge-platform-admission-spec.md) and
[admission design](knowledge-platform-admission.md) (#31),
[ADR-0003](../adr/0003-immutable-accepted-canonical-revisions.md),
[ADR-0006](../adr/0006-fixed-inputs-independent-projection-publication.md),
[ADR-0007](../adr/0007-derived-product-readers-within-input-intersection.md)
and the [authorization design](knowledge-platform-authorization.md) (#85).
Domain terms follow `CONTEXT.md`; this ticket adds **Build** and **Change Feed**.
The change-discovery decision is
[ADR-0009](../adr/0009-cursor-feed-change-discovery.md).

Vocabulary used below: a Source is an application (for example tKMS or
Note.AI); a Resource is a space or notebook under a Source and, in v1, also the
Corpus; a projection is Wiki or Retrieval (a knowledge graph later); a
Knowledge Profile is the list of projections a Source turns on.

Endpoint names in this document illustrate the contract. Full endpoint
specifications belong to the implementation tickets
[#97](https://github.com/davidlinnnn/data-ingestion/issues/97) (status and
report intake) and [#98](https://github.com/davidlinnnn/data-ingestion/issues/98)
(deletion and retry). Every obligation must be possible to meet at the HTTP
contract alone; the consumer SDK is a convenience (the Wiki backbone is
TypeScript).

## 1. Scope and owners

| Topic | Owner |
|---|---|
| Change discovery, inclusion rule, publication unit, serving facts, repair, deletion predicate, Build lifecycle, consumer obligations | this document |
| Admission, status vocabulary, readiness surface | #31 (closed), [admission specification](knowledge-platform-admission-spec.md), #97 |
| Deletion workflow, retry, enforcement alerting | #98 |
| Serving-time blocks, withdrawal, conformance of disclosure | #56 |
| Canonical revision selection, adoption, rollback | #80 |
| Retention and purge of canonical data and Builds | #57 |
| Consumer presentation (coverage, freshness, hidden pages, list shapes) | #76 |
| Operations: monitoring, alerts, restore runbook, database guards | #78 |
| Production load and scale validation | #88 |
| Authorization decisions and the Resource Service | #85, #113, #114 |

## 2. Decisions

### A. Change Feed

| ID | Decision |
|---|---|
| A1 | One append-only Change Feed in the admission PostgreSQL database, each entry written in the same transaction as the fact it records, so the feed table is the transactional outbox. Facts owned by other components (the current canonical revision through status intake; withdrawal and reinstatement through #56's shared block record) enter the feed in the transaction that records them in the admission database. Projections read it only through the governed read API and never connect to the database. [ADR-0009](../adr/0009-cursor-feed-change-discovery.md). |
| A2 | Thin events of four kinds: `current_revision_changed` (a new revision accepted, a method refresh, a canonical rollback, a governance withdrawal or reinstatement; the Document may end with no usable revision), `document_deleted`, `inclusion_changed` (per Document: rebind, or a rebind or narrowing of a copy's original), `source_profile_changed` (carries only `source_id`; its position doubles as `profile_seq`). Unknown kinds are logged and skipped and the cursor advances. |
| A3 | A projection reports a position only after each event's effect is durable (applied, or handed to durable execution). The cursor only moves forward. Changes that narrow access (deletion, withdrawal, moving out of a Resource) carry the highest priority; bulk refreshes must not hold up daily updates; coalescing events of one Document is allowed but never across a deletion. Events of one Document may arrive out of order; handling is level-triggered: every event means "re-read the current state". |
| A4 | 90-day retention, monthly partitions. An expired cursor receives `cursor_expired` and resynchronises through the same bootstrap as a new projection: fix the feed starting point first, then enumerate Documents (review m2). **R-a:** that bootstrap also reconciles every Document the projection still stores but the enumeration did not return, and a state read for a deleted Document answers `deleted`, not `404`. |
| A5 | Ordering and paging by (transaction ID `xid8`, sequence), returning only entries from transactions below the snapshot xmin; the cursor is opaque. A sequence-only cursor permanently skips a transaction that took a lower sequence and committed later; a PostgreSQL 18.4 prototype lost about one event in ten that way (review M1). Cost: one long transaction holds back the whole feed, so the admission database sets `transaction_timeout` and `idle_in_transaction_session_timeout` and operations alert on the oldest xmin age (G8). |
| A6 | A state read that follows a feed position must observe state at least as new as that position (read-your-feed; review m1). |
| A7 | The platform holds one cursor per projection. Each projection runs one logical reader (for Temporal, a singleton workflow; workers scale on backlog, for example with KEDA); the reader never runs inside request-serving web workers. |
| A8 | No broker now. NATS JetStream is deferred, not rejected; the revisit triggers and the additive relay upgrade are in ADR-0009. Throughput figures are estimates handed to #88 (10,000 updates a day average 0.12 events a second; 100,000 a day average about 1.2 and peak around 12). |
| A9 | Projection side: every event converges on `reconcile_doc(document_uid)`, serialised per uid (for a Wiki page, per uid of every source on the page); a run includes its registration, store write and confirmation, and a new event for a uid that is being reconciled triggers one more run after the current one (never dropped as "already running"; review m1). `source_profile_changed` starts one source-level reconciliation per affected projection: duplicates merge, the profile is re-read each pass, Documents are paged by key, and it runs at low priority. Bootstrap runs the same reconciliation for every Source. Recommended implementation, not an obligation: a fixed-ID `ReconcileSource` workflow with continue-as-new for Temporal-based projections. |

### B. Input scope and publication

| ID | Decision |
|---|---|
| B1 | **Inclusion rule:** Document D appears in product P of Resource R if and only if D is bound to R, P is in the Knowledge Profile of D's Source, and D has a usable current revision and is not deleted, withdrawn or blocked. In v1 a Document binds to exactly one Resource, and only to a Resource its own Source created (J1). Not offered: multiple bindings, cross-Source placement, changing a Document's Source. External responses use list shapes so multiple bindings stay additive. **Readiness:** the scalar value counts only projections whose backfill for the Source is complete; a newly added projection does not count until its owner reports "backfill of Source S complete at `profile_seq` P", and Documents keep their previous readiness; `serving[]` carries each projection's state (`ready`, `building`, `stale`) (review M7; supersedes #31 acceptance case 20). |
| B2 | **Rebind** (P0): within one Source, to another Resource, without reprocessing canonical data. Moving out of the old Resource has the same priority as deletion; #56's block extends to "this Document in this Resource" with deletion's targets; readiness counts only the current Resource. |
| B3 | **Cross-Source Document copy** (P0): the platform performs the copy. The copy is a new Document of the destination Source referencing the original's accepted Canonical Revision (no reprocessing, snapshot, no sync); re-import is a new revision of the copy. The platform records lineage and flattens it to the first original. Readers of a copy = destination readers ∩ original's readers. When the original is deleted or narrowed by a rebind, the platform blocks the original and every copy in the shared block record in the same step, then emits events for the copies. Index entries are independent per `document_uid` ("computation may be shared, stored entries may not"). A precomputed product containing a copy is checked **per page at query time**: a page is served only to users who can read all of its sources, including each copy's original (review M6). This amends ADR-0007. Copy as a feature needs its own design ticket on the map. |
| B4 | **Publication:** Wiki and Retrieval use one model. Products are published commit by commit inside a Build (one Document or a mini-batch). Each Document records (Source Revision, pipeline version). The external version of a product is its serving Build plus that Build's pipeline version. An incompatible method change, a storage or layout change, or a repair rebuild creates a new Build that replaces the old one at a switch. Coverage: intended = Documents enumerable by B1; actual = included facts; missing = the difference; ineligible = blocked or withdrawn (review m4). Presentation belongs to #76. |
| B5 | **Commit-time check** (review M3): before a store write (the platform performs it when it accepts the registration, §5.2), the revision being written must equal the platform's current revision for the Document, and the Document must not be deleted, withdrawn, blocked or moved out of the Resource; otherwise the result is dropped as superseded and later events reconcile again. This covers newer and older Source Revisions, method refreshes, canonical rollbacks and late results. **R-b:** a Wiki page's check covers every source of the page, not only the Document that triggered the rebuild. **Late landings:** the check and the store write are two steps, so a write can still land after its Document became ineligible. The contract does not promise that never happens; it promises that deletion is never judged enforced while such content is present (§5.2), is eventually removed, and that removal is eventually judged complete. Late landings are a metric (#78). **Wiki removal on deletion:** within the `applied` target, pages whose `sources[]` include D are hidden at query time; before `enforced`, they are regenerated from their remaining sources or deleted. Page sources are recorded by the pipeline, not trusted from model output. Pages that synthesise all sources (llm_wiki's `overview.md` and `index.md`) are the Wiki owner's to handle and are measured in the pilot; conformance tests that a failed preparation leaves no half-written page (review m9). Regenerating pages for a heavily cited Document may exceed 10 minutes (to #56/#31). |
| B6 | **Freshness** is the time of the Source Revision a product contains; a method-only recompute does not make a product fresher; a copy's freshness is its original revision's time. Wiki aggregate presentation belongs to #76. |

### C. Reporting and deletion

| ID | Decision |
|---|---|
| C1 | Projections push reports to the platform's HTTP report API under the same service identity as the feed reader; the durable execution layer retries until success; the platform is idempotent. To #88: admission PostgreSQL scenarios (daily and peak load, bulk refresh, partition drop and vacuum at 90-day retention, a long transaction holding the snapshot xmin). |
| C2 | **Serving facts** (supersedes #31 round 3's full inclusion list per product version; review m5): key (projection, Build, `document_uid`, `resource_id`); value `pending`, `included` or `removed`, Source Revision, Canonical Revision, `fact_version`. Pipeline version is a Build attribute (review n3). Each commit reports a delta. `fact_version` is monotonic per Build and never resets across removals (gaps allowed); the platform keeps the highest and acknowledges older ones with `2xx` (review M2). Details in §5. |
| C3 | **Deletion enforced** (level-triggered; supersedes spec §8's per-projection completion report): D is enforced when no non-retired Build of any projection holds an `included` or `pending` fact for D. No `delete_request_id`, not limited to required projections. A rebind's move-out is complete when no (D, old R) `included` or `pending` fact remains. Judgments are suspended under R-c and K2 (§5.6). **R-c:** while any non-retired Build has lost liveness, no enforcement judgment is made; a timeout raises an alert with its reason (for example a paused consumer). Withdrawal can use the same predicate (to #56). |
| C4 | Attempts keep #31's vocabulary; the attempt unit is (Document, revision, Build). Failures in a Build that is still building raise no attention. A B5 drop is `failed` with an owner reason such as `SUPERSEDED`. No `processing_failed` when the latest revision is already served (to #97). Deletion needs no attempt report. |

### D. Lifecycle and rebuilds

| ID | Decision |
|---|---|
| D1 | Turning a projection off for a Source removes its products; nothing is frozen. When a Resource's Wiki inputs are all removed, the whole Build retires. Platform-wide replacement: add the new projection, wait for ready, remove the old one, retire its Builds, purge (#57), delete its cursor and registration. Pause: stop the consumer, the cursor stays, blocks keep governance; a pause beyond 90 days resynchronises by bootstrap. A non-empty Resource cannot be deleted (#31 `409`); deleting an empty Resource retires its Wiki Build. |
| D2 | **Rebuild:** deploying an incompatible version starts a new Build automatically. The new Build is a new feed consumer: it fixes its cursor start, reads everything from the canonical read API (never copies from the old Build), and follows the feed. Mechanical switch gates: coverage not below the serving Build (at the pre-switch snapshot), caught up with the feed, no deleted, withdrawn or moved-out Documents. Quality is the owner's offline responsibility; the candidate references its validation evidence. In production, a method or storage change needs the Published View Owner's approval; repair rebuilds and non-production switches are automatic. Evidence binds to (Build, full pipeline version); any pipeline version change, compatible ones included, makes a new candidate; Document catch-up does not invalidate an approval; a failed gate at switch time needs re-approval; the switch record holds the cursor positions at evidence time and at switch time (review M5). The approval record is kept by the projection owner (#58 baseline). The owner's workflow checks the gates, obtains approval, switches, and reports `serving` with approval and evidence references; the platform re-runs the gates and rejects a failing switch (review m10). One pending candidate per Published View; a newer one replaces it. The old Build is retained 7 days by default and keeps following the feed; rollback is switching back; retention expiry retires it automatically. A Wiki may let its retained Build process only narrowing events and catch up after a rollback. Compatible changes recompute inside the Build; a Document rollback is a forward fix. |
| D3 | The canonical layer keeps #31's immutable per-Document revisions with adoption and platform refresh; no Builds there. Rollback retires the faulty adoption and selection falls back to the previous adopted revision of the same Source Revision without reprocessing (to #80). An incompatible canonical output change uses expand/contract: every projection declares support before canonical adopts it. |

### E. Product behaviour and scale

| ID | Decision |
|---|---|
| E1 | Contract obligations: (1) enrichment-derived content carries its status (all `unverified` in the first version) and a Canonical location reference back to the source image or table; (2) table-level status reaches results, and the Wiki generates no table-dependent comparisons or conclusions; (3) document-level known limitations reach citations; (4) original and generated content are distinguished. Owners verify quality offline with #32 shared cases, #54 Q4 representative questions and #82 table cases; code, formula, table and image each have a consumer check. |
| E2 | Physical layout is not part of the contract; the contract holds the PEP filtering semantics and #56 conformance. |
| E3 | Scale horizon: 10 million active Documents (the ceiling confirmed on #88; this record first said 1 million, corrected 2026-10-27); 10,000 updates a day near term, 100,000 later (to #88). |
| E4 | `min_readiness` is single-projection freshness (supersedes admission.md's cross-projection meaning; review m6): results carry `document_uid`, the served Source Revision and its time, and a stale flag; projections support a `latest_only` pre-filter. Naming and presentation belong to #76; cross-projection consistency rests on exact-revision citation (ADR-0003). |

### Validation and final rulings

| ID | Decision |
|---|---|
| G1 | Keep **register before write** (F1): see §5.2. |
| G2 | Keep the **count and digest heartbeat** (H1); its purpose is detecting silent drift of the platform's mirror. An announced restore is handled by G7. |
| G3 | Keep **R-a** (A4) although only a deterministic scenario detects its absence; without it a deletion inside an expired gap is left behind permanently. |
| G4 | Keep **R-b** (B5). |
| G5 | Adopt **snapshot-then-stream repair** with a view lifetime and the expiry fence on replacement entries (§5.4), replacing the mark-and-sweep repair of review M2. |
| G6 | No replacement fence: registration before write, W-stamped tombstones and the expiry fence already cover it, and no sampled run needed it. |
| G7 | Adopt the **restore runbook** (§5.6), generalised by K2 to any loss of committed writes in the admission database, with all enforcement judgments suspended until every Build is repaired. |
| G8 | Record the long-transaction cost and guards in ADR-0009 (A5). |
| G9 | Commit the curated validation evidence; keep raw outputs out of git with a hash manifest (§7). |
| K1 | The B5 check runs when the platform accepts a registration, in one step with recording `pending` and serialised with the C3 judgment (§5.2). |
| K2 | One rule for every loss of committed writes in the admission database (§5.6). |
| J1 | No cross-Source placement in v1. A placed Document would have two owners: its Source owns content and lifecycle while the Resource's maintainer owns its readers, unlike a copy, whose readers remain bounded by the original's (B3). The need is covered by copies, no first-release need is named, and mainstream products (Google Drive, Confluence, Notion) do not keep one document live in two spaces either. #85's `contributor` relation and endpoints, eviction and the maintainer's listing of other Sources' Documents are deferred and can be added later as additive changes. |

## 3. Governed reads

| Use | Endpoint (illustrative) | Returns | Errors and compatibility |
|---|---|---|---|
| Read the Change Feed | `GET /v1/feed?cursor=&limit=` | `events[]`, opaque `next_cursor` | `410 cursor_expired` beyond retention: bootstrap |
| Report position | `PUT /v1/consumers/{projection}/cursor` | — | `409 cursor_backwards` with the platform's position, which wins |
| Document state | `GET /v1/documents/{document_uid}/state?at_least=<cursor>` | `resource_id`; `current` (Source Revision, Canonical Revision, or `null`); `status` (`active`, `deleted`, `withdrawn`); `copy_of` (original uid, original Resource, original Canonical Revision, or `null`) | At least as new as `at_least`, otherwise `503` to retry; a deleted uid answers `status: deleted`, never `404` |
| List Sources | `GET /v1/sources` | `source_id` list | bootstrap |
| Source profile | `GET /v1/sources/{id}/profile` | `projections[]`, `profile_seq` | — |
| List a Source's Documents | `GET /v1/sources/{id}/documents?after=&limit=` | keyset-paged `document_uid` list | bootstrap and `ReconcileSource` |
| Canonical content and evidence | exact-revision reads of the canonical contract | Markdown, supplements, enrichment status, location references | withdrawn or deleted: fail closed; exact-revision references resolve within retention (ADR-0003) |
| Block check | defined by #56 | whether a Document, or a Document in a Resource, is blocked | shared by serving queries and the B5 check |

Event examples (identities only):

```json
{"position": "c1f…", "kind": "current_revision_changed", "document_uid": "doc_7f3",
 "source_id": "src_tkms", "priority": "normal", "occurred_at": "2026-10-26T09:12:00Z"}
{"position": "c1g…", "kind": "document_deleted", "document_uid": "doc_7f3",
 "source_id": "src_tkms", "priority": "narrowing", "occurred_at": "…"}
{"position": "c1h…", "kind": "inclusion_changed", "document_uid": "doc_7f3",
 "source_id": "src_tkms", "priority": "narrowing", "occurred_at": "…"}
{"position": "c1i…", "kind": "source_profile_changed", "source_id": "src_tkms",
 "priority": "background", "occurred_at": "…"}
```

Priorities: `narrowing` (deletion, withdrawal, moving out, a copy's original
narrowing) first; `normal` (source updates, reinstatement, canonical rollback);
`background` (method refreshes, profile backfill or removal) must not hold up
the other two.

## 4. Builds

A **Build** is one complete, independently built logical instance of a
Published View's data, produced by one compatible line of its method. Its
owner maps it to one or more physical indexes or collections. States:
`building`, `serving`, `retained`, `retired`; readiness counts only `serving`.
A Build is retired only when its owner reports `retired` after clearing its
data; the platform never retires one by itself, because data might still be
present (review m3). A Build that stops reporting is handled by liveness
(`status_unverified`) and alerting.

## 5. Report intake and the platform's mirror

The platform keeps, per Build, a mirror of the serving facts the projection
reported. Deletion judgments (C3) and readiness are computed from the mirror.
This section is the contract that keeps the mirror safe under delayed,
duplicated, reordered and lost reports, projection crashes, liveness loss,
expired cursors, database restores and silent corruption.

### 5.1 Reports

| Report | Content | Platform handling |
|---|---|---|
| Registration (before a store write) | `pending` fact with a new `fact_version` | The projection writes its store only after the platform accepts it; `pending` blocks enforcement and does not count toward readiness |
| Serving fact | `included` or `removed`, Source Revision, Canonical Revision, `fact_version`; the `included` confirmation of a successful write uses a **newly allocated** version | Highest `fact_version` wins; older ones `2xx` and ignored; `removed` tombstones kept 30 days |
| Build state | `building`, `serving`, `retained`, `retired`; `serving` carries approval and evidence references | Gates re-run on `serving`; failure `409 gate_failed` |
| Heartbeat | Per Build: count and digest of store entries plus unfinished registrations (§5.5) | Mismatch requests a repair |
| Repair view | Pages of a consistent view (§5.4) | Atomic replacement |
| Backfill complete | `(source_id, profile_seq)` | The projection starts counting toward scalar readiness |
| Attempt | #31 vocabulary, unit (Document, revision, Build) | Out-of-order `409` with the current position (#31) |

SDK operations: `report_facts` (registrations included), `report_build_state`,
`serve_snapshot`, `report_backfill_done(source, profile_seq)`.

The platform asks for a repair in its response to heartbeat and report calls
(for example a `repair_requested` field with a reason), so a projection learns
of it over HTTP alone; #97 fixes the shape.

### 5.2 Register before write

Before writing a Document's content into its store, a projection registers a
`pending` fact and waits for acceptance. A Wiki page registers one `pending`
fact per source of the page; the platform records all of them or rejects the
registration, never a part. The platform performs the B5 check
when it accepts the registration (for a Wiki page, on every source of the page,
R-b), in one step with recording `pending` and serialised with the C3 judgment
for the same Document. A registration that fails the check is rejected with a
terminal response, and the projection drops the result as `SUPERSEDED`; it does
not write. So no Document can be judged enforced between a passing check and
its `pending` fact. After the write succeeds, it reports
`included` with a freshly allocated `fact_version`, so a confirmation of a write
that landed after a repair view is newer than the view. A projection keeps its
unfinished registrations, and the last reported `fact_version` of each store
entry, durably across crashes; a repair view depends on both. Without registration,
a write that completed while its confirmation was still in flight is invisible
to the platform: if the Document is deleted then, the mirror holds nothing and
the deletion is judged complete while the content is still served (observed in
7 of 1,000 simulated runs without registration).

A `pending` fact older than `PENDING_MAX` and still unconfirmed makes the
platform request a repair. `PENDING_MAX` must exceed the longest store write
delay, including a liveness pause; #97 sets the value.

### 5.3 Tombstones and the expiry fence

A `removed` fact is a tombstone kept 30 days. A report retry must give up
before then and request a repair instead (review M2). After a tombstone
expires, the platform still remembers its version and expiry time per key and
rejects a report whose version is at or below the expired tombstone's and which
was issued (first created, or for a repair view, captured) before that expiry,
so a very late `included` cannot resurrect a deleted Document. A rejection is a
terminal response, not retried, and requests a repair.

### 5.4 Repair: snapshot then stream

A repair is requested by a heartbeat mismatch, a pending-age expiry, a report
retry giving up, a §5.3 rejection, a discarded view (steps 2 and 3), a loss of
committed writes (§5.6), or before a Build switch (review m8). A Build has at
most one view in transfer; a request during a transfer is satisfied by it,
except a loss of committed writes, which discards it and starts a fresh view.

1. **Consistent view.** The projection atomically reads W, the highest
   `fact_version` allocated in the Build, and captures its whole state for the
   Build: every store entry as `included` and every registered entry whose
   store write has not completed (in flight, or failed and awaiting retry) as
   `pending`. Allocating a version and recording what it was allocated for are
   atomic with respect to the capture, so every version at or below W is
   reflected in the view and every later allocation is above W. A
   non-transactional sequence needs care here. Pages may arrive out of order or
   duplicated; the platform deduplicates them.
2. **Lifetime.** A view must finish transferring within the report retry
   lifetime, measured from capture; otherwise the platform discards it and
   requests a fresh view.
3. **Expiry fence.** Each entry to be installed passes the §5.3 fence with its
   original version; if any entry is rejected, the whole view is discarded and
   a fresh view requested.
4. **Atomic replacement.** When every page has arrived, the platform replaces
   the Build's mirror in one step: facts with version above W are kept (they
   were produced after the view); keys in the view take the view's state,
   stamped W; keys absent from the view become `removed` tombstones stamped W.
   If one key appears both as a stored entry and as a newer unfinished
   registration, the registration wins.

No separate "replacement fence" is kept (G6). The earlier mark-and-sweep repair
turned unconfirmed facts into tombstones while their content stayed stored,
and repairs and write retries could overwrite each other indefinitely; both
showed in simulation (§7).

Implementation note for #97: the model assumed an atomic view. A real
implementation takes the view from one database snapshot or an equivalent, and
reads pages synchronously with retries so that transfer time stays well below
the lifetime.

### 5.5 Heartbeat

Each Build's heartbeat carries a count and a digest over the same set a repair
view would capture: its store entries plus its unfinished registrations, the
registration winning for a key with both, each with its revision. The digest is
the XOR of a stable hash of (`document_uid`, `resource_id`, Canonical Revision)
over that set. The platform computes the same over the mirror's `included` and
`pending` facts; tombstones are excluded. A mismatch requests a repair. Because
both sides count in-flight writes, they agree while writes are under way,
except during a registration's own round trip. The
simulation compared store entries alone, so in-flight writes caused harmless
extra repairs (about a quarter of them); at production write rates that would
trigger a whole-Build view on almost every heartbeat, which this definition
avoids without losing any drift the digest detects. The digest catches silent
drift that keeps the count unchanged, for example a bug rewriting the mirror
(G2). #97 fixes the hash.

### 5.6 Enforcement gates

- **Liveness (R-c):** while any non-retired Build has lost liveness, no
  enforcement judgment is made.
- **Lost writes (G7, K2):** after any event in which the admission database
  loses committed writes (a restore from backup, a point-in-time restore, or a
  failover that loses unreplicated commits), operations trigger the platform
  to request a repair of every Build and to suspend all enforcement judgments
  until those repairs complete. Only a view captured after the event ends the
  suspension; a view already in transfer is discarded. A restored mirror has lost the facts recorded
  after the restore point, so it cannot tell which Documents to gate. Without
  this, the heartbeat still repairs the mirror, but a deletion judged in the
  minutes before that repair can be judged enforced while content is present.
  Which events trigger it and the full procedure, in which the feed, cursors
  and blocks rewind too, are #78's runbook.

## 6. Scenario walkthroughs

| Scenario | Walk | Result |
|---|---|---|
| Source update (#32 V06, attachment updated alone) | New Source Revision accepted → canonical reports the current revision; the platform writes `current_revision_changed` (normal) in the same transaction → each projection runs `reconcile_doc` → B5 passes → `included` with the new revision | Retrieval first: `ready_stale`, then `ready` when the Wiki catches up; the E4 stale flag lets `latest_only` exclude the old Wiki page |
| Method-only change (#32 V07, OCR-1 → OCR-2) | Owner adopts → platform refresh (background) → new Canonical Revision → `current_revision_changed` → recompute inside the Build | Freshness unchanged (B6); old citations still resolve by exact revision (ADR-0003); a failed refresh alerts the owner and the old result keeps serving |
| Missing required input (#32 V05) | Canonical rejects the new Source Revision → current revision unchanged → no event | The previous eligible revision keeps serving; readiness `ready_stale` with attention `source_revision_rejected` |
| One projection fails | Wiki attempts exhaust retries → `failed` → `processing_failed` (track `llm-wiki`) | Retrieval unaffected; the Wiki keeps serving its previous version |
| One projection rebuilds | New Build: fix start → full read → follow feed → gates → switch → old Build retained 7 days, still following the feed | Rollback is switching back; failures while building raise no attention; deletion covers building and retained Builds |
| Late completion | A result for an older revision finishes after a newer one → B5 sees it is not current → dropped, `failed` with `SUPERSEDED` | No regression; a deleted Document's late result never lands as published (and a late landing is still removed, B5) |
| Source withdrawal (#32 V09) | #56 records the withdrawal and writes `current_revision_changed` (narrowing) in the same transaction → applied block → projections remove, the Wiki regenerates pages containing D → `removed` facts | Readiness `withdrawn`; no fallback to an older Source Revision; reinstatement is a new event at normal priority |
| Invalidated after acceptance (#32 V09) | Canonical finds the conditions no longer met → no current revision → `current_revision_changed` | Removed like a withdrawal; the accepted history is kept but no longer selected |
| Rebind | `inclusion_changed` (narrowing) → old Resource blocked at once, Wiki pages of the old Resource rewritten → included in the new Resource in normal order | Readiness counts the new Resource; move-out completes when no (D, old R) fact remains |
| Stale capture (#32 V08) | Admission rejects the stale capture by `source_version` → no Source Revision → no event | Projections see nothing |
| Major breaking release (Q23) | Deploy a new major → new Build → owner validation with evidence → gates → production approval → owner switches, reports `serving`, platform re-runs gates | Catch-up during the wait keeps the approval; a pipeline version change makes a new candidate; the switch record keeps both cursor positions |
| Canonical rollback | Retire the faulty adoption → selection falls back → `current_revision_changed` (normal) → recompute | No canonical reprocessing; B5's "equals current" lets the rollback land |
| Copy's original deleted | Original deleted → the platform blocks the original and every copy in one step → `document_deleted` for each | Copies unreadable within a minute; each projection removes them and each becomes enforced |

## 7. Validation

A discrete-event simulation (Codex, two rounds, gated by a reviewed rule
mapping and smoke tests) checked the reporting and repair protocol against
these faults: delay, duplication and reordering; store write failures; reports
lost in a crash; liveness loss; a pause beyond feed retention; an announced
restore (W-rewind); and silent drift (W-drift). Round 1 also measured the
feed ordering problem on PostgreSQL 18.4. Evidence:
[validation record](../research/canonical-consumption-validation-2026-10-26/README.md).

Invariants: S1, no Document judged enforced while any store still holds it;
S1 flip-back, no enforcement judgment reverses because of facts; S7, no
judgment while liveness is lost; L0, the run converges; L1 to L5, at quiescence
stores match the inclusion rule, the mirror equals the stores, cursors reach
the feed tail, no `pending` remains and every deletion is enforced.

| Design | W-real | W-rewind | W-drift |
|---|---|---|---|
| Adopted (§5) | 0 | 0 | 0 |
| Without registration | 20 | 9 | 250 |
| Registration with mark-and-sweep repair | 179 | 87 | 264 |
| The same plus the digest heartbeat | 224 | 130 | 156 |

Seeds out of 1,000 with at least one failure. The "Adopted" row still had a
replacement fence; the same design without it (§5, G6) also had 0 failures in
all three workloads, with drift-to-repair latency p95 125 and max 245 ticks.
The adopted design had no
unknown verdicts; under W-drift its fact flips before repair are counted as
exposure, not failures, because silent corruption of the mirror cannot be
prevented by any protocol (drift-to-repair latency p95 129, max 297 ticks).
All 33 deterministic scenario cells matched their expectations. A verifier
recomputed every table and replayed 125 witnesses identically, and the main
line recounted independently.

Each rule's absence was shown as follows (W-real unless noted):

| Scenario | Guarded by | Without it | Acceptance owner |
|---|---|---|---|
| SC15: write done, confirmation in flight, Document deleted | registration (§5.2) | judged enforced while present | #97, #98 |
| SC16: consumer paused beyond retention, Document deleted meanwhile | R-a (A4) | left behind (L5) | #98 |
| SC18: page {D, E}; E's update triggers a rebuild just after D is deleted | R-b (B5) | already-invalid source lands; 6 runs flipped, 958 runs had such landings | #56 conformance |
| SC19: an older `included` arrives after the tombstone expired | expiry fence (§5.3) | deleted Document resurrected (1 run) | #97 |
| SC20r: announced restore, equal count | lost-writes rule (§5.6) | judgment flips | #98, #78 |
| SC20u: silent drift, equal count | digest heartbeat (§5.5) | never repaired (L2) under W-drift: 176–245 runs | #97 |
| SC21: repair and write retry overwrite each other | snapshot-then-stream (§5.4) | repair never converges (L0): 130–163 runs | #97 |
| SC22: write succeeds, confirmation lost in a crash | pending age (§5.2) | `pending` stuck (L4) | #97 |
| SC23: view taken during a write; Document deleted; write lands later | view includes `pending`; fresh confirmation versions | — | #97, #98 |
| SC24: a view's last page arrives after a related tombstone expired | view lifetime and expiry fence (§5.4) | stale view resurrects a deleted fact (50 runs) | #97 |
| NC2: removal report lost, repair done, old `included` arrives | W-stamped tombstones | masked; kept as a regression test | #97 |

Limits: the view is atomic, liveness is an ideal flag, the population is eight
Documents, time is logical and there is no durable outbox. The evidence is
about protocol logic, not performance or scale (#88).

## 8. Superseded decisions

| Earlier decision | Replaced by |
|---|---|
| #31 round 3: report a full inclusion list once per product version | C2 deltas (a full list per commit is infeasible for 1 million Documents with tens of thousands of commits a day) |
| [Admission specification](knowledge-platform-admission-spec.md) §7.1 and #31 acceptance case 20 | B1 readiness backfill rule |
| Admission specification §6.1 rule 5 and the admission design's maintainer-granted placement | J1: no cross-Source placement in v1 |
| Admission specification §8, "each projection reports when it has finished" | C3 level predicate |
| The admission design's original cross-projection `min_readiness` | E4 |
| ADR-0007's precondition that all inputs of a Resource share its readers | B3 per-page query-time check when a Resource contains copies (ADR-0007 amended) |
| [#55 Q1 comment](https://github.com/davidlinnnn/data-ingestion/issues/55#issuecomment-6344459131): consumer-held cursor, sequence watermark, broker thresholds | A5, A7, A8 and ADR-0009 |
| [Authorization design](knowledge-platform-authorization.md) Q4, Q14, Q15, E2 and E3 as they concern `contributor` and eviction | J1 (deferred; the design carries an amendment note) |

## 9. Handoffs

| To | What |
|---|---|
| #126 | The Change Feed itself and the governed read API (§2 A1–A8, §3): the feed table and its ordering, the per-projection cursor, the Document state read, bootstrap enumeration, the in-transaction event-append function that #97, #98, #114 and #56 call, and the `source_profile_changed` producer. Added 2026-10-27: the record first left these with no implementation ticket |
| #127 | The projection side (§2 A7, A9, §4, §5) as a consumer SDK and a conceptual reference projection: single logical reader, `reconcile_doc`, registration before write, repair views, heartbeat, Build lifecycle, the pre-filtered query path, and the projection owner's checklist. Added 2026-10-27 |
| #97 | Readiness backfill rule and `serving[]`; registration with the B5 check in the same step (K1); serving facts with `pending`, fresh confirmation versions, tombstones and the expiry fence; `PENDING_MAX`; snapshot-then-stream repair (lifetime, expiry fence, atomic replacement); count and digest heartbeat; `processing_failed` suppression; Build states and gate re-run on `serving`; list shapes. Acceptance: SC15, SC19, SC20u, SC21, SC22, SC23, SC24, NC2 |
| #98 | C3 with `pending`; the B5 check at registration (K1); rebind move-out; R-c; the lost-writes suspension (K2); R-a; enforcement timeout alerts with reasons. Acceptance: SC15, SC16, SC20r |
| #56 | Resource-scoped block for rebind; copy blocks along lineage; withdrawal and reinstatement recorded in the admission database in the feed's transaction; withdrawal may use C3; conformance for B5 (with R-b, SC18) and the per-page copy check; Wiki derived-content deletion target flag |
| #57 | Custody and purge of canonical data shared by copies and originals; purge after Build retirement; the current canonical revision recorded in the admission database |
| #80 | Canonical rollback by retiring an adoption; expand/contract; current revision reported through status intake (into the feed in the same transaction) |
| #85, #86, #114 | Copy reader intersection; J1: `contributor`, eviction and the maintainer's document listing deferred; #114's scope shrinks; #86 G1 needs no `contributor` in v1 |
| #87 | Aspect 11: contributor grants and eviction deferred with J1 |
| #76 | Import hints, deletion notices, hidden pages and unreadable originals, freshness aggregation, coverage, `min_readiness` naming, list shapes |
| #78 | `transaction_timeout`, `idle_in_transaction_session_timeout` and oldest-xmin alerting; per-consumer lag; enforcement timeout alerts; lost-Build alerts; the lost-writes runbook (which restores and failovers trigger it; feed, cursor and block rewind); late-landing and repair-latency metrics |
| #88 | Scale horizon and admission PostgreSQL load scenarios (C1) |
| Map #52 | A design ticket for cross-Source Document copy (B3) |

## Sources

- #55 ticket and the handoff comments on it from #31, #84 and #85:
  <https://github.com/davidlinnnn/data-ingestion/issues/55>
- Change feed and outbox:
  [dual-write problem](https://milanjovanovic.tech/blog/outbox-pattern-dual-write-problem),
  [ordering in PostgreSQL outboxes](https://event-driven.io/en/ordering_in_postgres_outbox/),
  [gaps in PostgreSQL sequences](https://www.cybertec-postgresql.com/en/gaps-in-sequences-postgresql),
  [CouchDB changes feed](https://docs.couchdb.org/en/3.5.1/api/database/changes.html),
  [Kubernetes watch 410 and relist](https://oneuptime.com/blog/post/2026-09-03-kubernetes-watch-410-gone-relist-reconcile/view)
- Snapshot then stream and source-level reconciliation:
  [Debezium incremental snapshots](https://debezium.io/blog/2021/10/07/incremental-snapshots),
  [Debezium signalling](https://debezium.io/documentation/reference/configuration/signalling),
  [Elastic connector full and incremental syncs](https://www.elastic.co/docs/reference/search-connectors/content-syncs),
  [Temporal continue-as-new](https://docs.temporal.io/design-patterns/continue-as-new)
- Registration before write and anti-entropy:
  [Kubernetes finalizers](https://kubernetes.io/docs/concepts/overview/working-with-objects/finalizers/),
  [Cassandra repair](https://cassandra.apache.org/doc/latest/cassandra/managing/operating/repair.html)
- Builds and alias switching:
  [Qdrant embedding model migration](https://qdrant.tech/documentation/tutorials-operations/embedding-model-migration/),
  [Milvus aliases](https://help.aliyun.com/en/milvus/user-guide/manage-alias)
- Bindings, copies and document-level access:
  [Google Drive single-location files](https://support.google.com/drive/answer/10864219),
  [Confluence move and copy](https://support.atlassian.com/confluence-cloud/docs/move-copy-and-hide-pages/),
  [Notion teamspaces](https://www.notion.com/help/intro-to-teamspaces),
  [NotebookLM Drive syncing](https://workspaceupdates.googleblog.com/2026/05/keep-your-sources-up-to-date-with-automatic-Drive-syncing-in-NotebookLM.html),
  [Glean permissions](https://developers.glean.com/libraries/indexing-sdk/permissions),
  [Bedrock knowledge base ACLs](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-ds-custom-acl.html),
  [Azure AI Search document-level access](https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview)
