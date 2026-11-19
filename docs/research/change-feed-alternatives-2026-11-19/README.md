# Canonical-to-projection handoff: independent review

Date: 2026-11-19. The review of ADR-0009 that a team member's doubt asked for: is a cursor feed on PostgreSQL right for a cloud-native platform whose event rate may grow? Written by a reviewer agent with fresh context that was told the mechanism and the constraints, not the team's arguments, and read the ADR only after forming its view. Two of its findings were then reproduced (§9). Tags: **[V]** = verified from the cited source (URL in the text or in the Sources section); **[I]** = my inference; **[U]** = could not verify, or sources disagree.

## 1. Verdict

The design holds, but mostly for different reasons than ADR-0009 gives, and the doubt as raised ("high-concurrency events") points at the wrong weak spot. Judge two things separately. One is the **consumer contract**: thin, level-triggered events, a pull with an opaque cursor, a cursor the platform holds, and a re-list when the cursor expires. The other is the **PostgreSQL mechanism**: the xid8/xmin filter, monthly partitions and polling. The contract is the industry's standard shape for exactly this problem. Kubernetes list+watch with resourceVersion and 410-then-relist, the Cosmos DB change feed pull model with continuation tokens, DynamoDB Streams shard iterators and PgQ's per-consumer batches are all the same idea **[V]**. That makes the strongest argument for the design a cloud-native one, an argument the ADR never makes. The mechanism is a sound, known technique (PgQ has used it since 2006–2008; Dudycz documents the same xid8 trick) **[V]**. At the stated load it sits two to three orders of magnitude below where any public source reports discomfort **[I from V numbers]**. It lives only for the pilot, because PROD moves to MongoDB. Rate is not where this design breaks. The real risks are elsewhere. (1) Feed delay is coupled to the longest *writing* transaction on the whole PostgreSQL *instance*, and the guard is set per *database*. (2) The "per-Document commit order" promise rests on an assumption about when a writer gets its transaction id, and no writer exists yet that would make the assumption true or false. (3) The consumer side does the expensive work, and it is where 10x growth actually hurts. Its scaling story in the ADR leans on KEDA and backlog autoscaling, which the company does not allow. Switching to a broker today would add a stateful system nobody is assigned to run, and it would remove none of these three risks.

## 2. Alternatives compared

Ceilings are order-of-magnitude figures. "Fit" means fit to the real constraints: no operators, fixed pods, a small team, Temporal available, MongoDB in PROD.

| Option | Fit to constraints | What it removes | What it adds | Ops cost | Ceiling (events/s) |
|---|---|---|---|---|---|
| (a) Keep as is (PG pull feed, xid8/xmin, platform cursors) | Good. Plain Deployments, no new system. Pilot-only mechanism | – | – | Low: one partition job, two timeouts, an xmin-age alert | Writes: thousands/s on one primary for thin append-only rows **[I]**. Polling: consumers x poll rate, trivial |
| (b) CDC: logical decoding / Debezium (Server or embedded), or `pg_logical_emit_message` | Possible without operators (Debezium Server is a plain app) **[V]**, but PG-only, so thrown away at the MongoDB move | Polling. The xmin coupling (log order is commit order **[V Morling]**). Table growth with the WAL-message variant | A replication slot that can fill the disk when stalled or idle (Zalando hit this at scale) **[V]**. `wal_level=logical`. Debezium Server's support status differs between sources **[U]** | Medium-high: slot monitoring, `max_slot_wal_keep_size`, connector upgrades | Hundreds of thousands/s fleet-wide at Zalando **[V]** |
| (c) Broker (NATS JetStream via Helm, Kafka/Redpanda KRaft chart, RabbitMQ streams, managed queue) | JetStream installs from the Helm chart alone; NACK (CRDs) is optional **[V]**. Kafka without Strimzi is possible but heavy **[I]**. Still needs the outbox and a relay, and the HTTP path stays for bootstrap | Polling. Fan-out cost on the OLTP database. Push delivery. Replay load off the primary | A second stateful cluster with storage, upgrades and access control. A second transport. Duplicate access control for document identities | Medium (NATS) to high (Kafka), with no named operator | 10^4–10^6 |
| (d) Temporal as the transport (canonical layer starts or signals one workflow per projection x document) | Temporal is there **[V]** | The feed table and the cursors | Canonical layer coupled to every projection's task queue and workflow types. No replay or bootstrap for a new projection. Per-workflow limits: 10,000 signals per execution, a few signals/s per workflow, history of 51,200 events or 50 MB **[V]** | Low | High for starts, low per workflow. Breaks the contract, not the rate |
| (e) MongoDB change streams exposed straight to consumers (PROD) | Poor. Consumers need database credentials, and the resume token is tied to the pipeline and to oplog retention **[V]** | The tailer and the feed collection | Consumers coupled to storage schema and to oplog sizing. Each stream costs the server, with no index on the oplog **[V]**. Resume can scan the oplog **[V]** | Medium, and it lands on the DB owner | Fine for rate. Wrong trust boundary |
| (f) LISTEN/NOTIFY or long-poll as a wake-up hint on the feed | Long-poll: good. NOTIFY: acceptable at this rate | Poll latency and idle polls | NOTIFY takes an instance-wide lock at commit, which serialised Recall.ai's writes **[V]**. DBOS disputes how fundamental this is **[V]** | Low | Long-poll: same as (a). NOTIFY: a few thousand commits/s **[U]** |
| (g) HTTP-feed conventions (http-feeds spec / CloudEvents batch, Electric-style long-poll offsets, Nakadi cursors) | Good. A refinement of (a), not a replacement | – | Long-poll `timeout`, CloudEvents envelope, keep-alive "bookmark" positions **[V]** | Low | Same as (a) |

My recommendation **[I]**: (a) plus (g): add long-poll and a bookmark/heartbeat position so idle cursors keep moving. Plan (c) as an additive relay only when a trigger in §5 fires. Reject (d) and (e) as transports. Temporal is the right execution layer *behind* the reader, which is how Temporal's own guidance uses an external stream feeding Signal-With-Start or a start per event **[V]**.

## 3. Failure modes, with evidence

1. **One long transaction holds back the feed.** This is real, but narrower than the queue literature suggests. `pg_snapshot_xmin` is the "lowest transaction ID that was still active". Only transactions that have been *assigned* an xid, meaning those that have written something, carry one **[V PG docs: `pg_current_xact_id` assigns an id only when the transaction "has not performed any database updates" otherwise]**. So long read-only reports, backups and an operator's SELECT do not stall the feed. They do pin the vacuum horizon (PlanetScale) **[V]**, but this table does not need vacuum (see 2). Three gaps **[I]**:
   - xids are instance-wide. `observe()` already says it "counts every database of the instance". But the schema sets `transaction_timeout`/`idle_in_transaction_session_timeout` with `ALTER DATABASE` on the admission database only. If Temporal's PostgreSQL, or anything else, shares the instance, its writers stall the feed and no guard ends them. Either give the feed its own instance or set the timeouts at the instance or role level.
   - Prepared (2PC) transactions keep their xid with no time limit and are not ended by `transaction_timeout`. Confirm `max_prepared_transactions = 0`.
   - With the 60 s timeout, "bounded delay" really means "at most about 60 s plus the poll interval". Write that number into the contract.
2. **Vacuum/bloat.** This **mostly does not apply to `change_feed`**: it is append-only and retention is a `DROP TABLE` of a monthly partition, so dead tuples are never created (`feed.py retain()`). PgQ/PgQue rotate tables with TRUNCATE for the same reason **[V Percona]**. The Brandur/PlanetScale/Microsoft death-spiral evidence **[V]** is about claim-and-delete queues. It does apply to the **ingest-side outbox** (`dispatcher.py`: `FOR UPDATE SKIP LOCKED`, then `UPDATE … dispatched_at`), but at 0.12–1.2 rows/s it is far from the 800 jobs/s PlanetScale needed to force a spiral under competing load **[V]**.
3. **Polling load.** The cost is consumers x poll rate, each poll one index range scan on `(xid, seq)`. Five consumers polling once a second do negligible work **[I]**. Morling's objection to polling (load spikes, ordering gaps) **[V]** is answered by the xmin filter for ordering, and by the low rate for load.
4. **Single-reader ceiling.** The reader only hands events to Temporal, so its ceiling is the start rate of the Temporal client, hundreds per second or more **[I]**, against a 12/s peak. It is not the bottleneck. The bottleneck is work behind it: 12/s peak x tens of minutes of LLM work per event means tens of thousands of concurrent executions **[I arithmetic]**. With fixed pods and no KEDA, that becomes a long backlog. The cost goes to tokens and GPU, not to the feed.
5. **Head-of-line blocking by priority.** `priority` cannot reorder anything inside the feed: a reader consumes in `(xid, seq)` order **[V code]**. Prioritising is therefore only possible behind the reader, for example with separate task queues or Temporal task-queue priority. Priority and fairness went pre-release in 1.29, then public preview, and a 2026-05 Temporal blog post says GA for self-hosted **[V blog; exact server version for GA U]**. If a "narrowing" event (a deletion or an inclusion removal) waits behind hours of embedding work in one queue, the outcome is a governance problem, not a throughput one **[I]**.
6. **Hot partitions.** Not applicable to a single feed. They would appear with a partitioned broker keyed by Source **[I]**.
7. **xid8/sequence ordering.**
   - It is correct for "never skip" **[V Dudycz, PgQ slides]**. The well-known alternative is commit order from logical decoding (LSN) **[V Morling]**, which removes the xmin coupling but brings replication-slot risk **[V Zalando]**.
   - The subtle one: the order is the order of **xid assignment (first write)**, not commit order **[V Dudycz: "Ordering follows when a transaction started"]**. Take two transactions that write the same Document. If T_b wrote anything else before it blocked on the Document lock held by T_a, then T_b has the lower xid and commits *after* T_a. The feed then lists them against commit order. `feed.py`'s docstring promises "the changes of one Document in commit order". ADR-0009 instead says "events for one Document may arrive in any order". The two disagree **[V repo]**. Level-triggered reads make this harmless for state **[I]**, but a consumer that branches on `kind` could act on a stale kind. Either make every feed writer lock the Document row as its first write, or drop the per-Document order promise. No writer of `current_revision_changed` exists in `src/` yet **[V grep]**, so the choice is still free.
8. **Retention edge.** Partitions are keyed by `occurred_at` (transaction start) but ordered by xid, so the horizon taken from a dropped month can sit slightly above entries in the next month. The result is a spurious `cursor_expired`, which is the safe direction, bounded by the 60 s timeout **[I]**.
9. **Where Postgres-as-queue stops being comfortable (public numbers).** Microsoft: SKIP LOCKED is fine under about 100 concurrent workers, and WAL pressure appears at "thousands of jobs per second" **[V]**. PlanetScale: tuned clusters handle "tens of thousands of jobs per second" **[V]**. Graphile Worker self-reports 10k+ jobs/s **[V]**. All three describe update/delete queues, which are harder than an append-only feed **[I]**.

## 4. Strongest honest cases

**Against.**
- The ordering mechanism ties the delay of every projection to the behaviour of every writer on the instance. That is a global coupling, and it is invisible until it fires.
- It is a home-made protocol: a cursor format, retention, a horizon and bootstrap. Brokers and CDC give all of that already tested, and any later move (the MongoDB port is already scheduled) rewrites the mechanism.
- Polling with no wake-up adds latency for every consumer.
- "Thin events, consumer calls back" puts read load on the platform for every event, and Fowler notes the flow becomes hard to see **[V]**.
- The single feed has no per-consumer filtering, so every projection reads every event.
- The scaling story behind the reader in the ADR leans on backlog autoscaling (the KEDA Temporal scaler is cited) that the company does not allow.

**For.**
- It is the Kubernetes control-plane pattern: a list+watch of a database-backed versioned log, a bounded history window (etcd keeps 5 minutes by default), 410 Gone, then clear the cache and relist **[V k8s API concepts]**. Kubernetes controllers are level-triggered on keys, not events **[V secondary iximiuz; I]**.
- Cosmos DB's pull model and DynamoDB Streams are database-backed feeds that the cloud vendors themselves endorse **[V]**.
- An outbox is required whatever the transport **[V AWS, Azure]**. Here the outbox *is* the feed, so nothing extra is relayed.
- Level-triggered reconciliation tolerates loss, duplicates and reordering by construction.
- Load is 0.12–12/s against a ceiling in the thousands.
- It adds no stateful system for a small team with no operator to run one.
- The contract survives the MongoDB move unchanged (#240's tailer writes positions).

**On "cloud native"** **[V/I]**: none of the CNCF definition, 12-factor ("backing services" are attached resources) or the vendor guides calls a database-backed feed an anti-pattern **[I: I did not re-fetch the CNCF definition text]**. The credible anti-pattern is the *shared database* as an integration point, and consumers here go through an HTTP API, not the database **[I]**. The credible criticism is the Postgres-as-*queue* ceiling, which applies to the ingest outbox, not to this log. The Azure and AWS outbox guides do relay into a broker **[V]**, so a broker is the more common shape in the literature. It is not a requirement.

## 5. Thresholds: when to switch, and to what

- **Rate.** The feed is comfortable to roughly 1,000 events/s sustained **[I]**. That is 100x the horizon's peak and about 1,000x its average. The team's estimates would have to be wrong by about 100x before the feed write or read load matters. A 10x error, a 120/s peak, breaks the **consumer budget** (LLM and embedding capacity, fixed pods) long before it breaks the feed **[I]**. The doubt is justified for the consumers, not for the transport.
- **Consumer count.** Polling stays trivial into the tens of consumers. Above about 10–20, or with consumers that each want a filtered sub-stream, add server-side filtering by kind/Source, or a broker with subjects **[I]**.
- **Topology** (these are the real triggers; the ADR lists most of them):
  - consumers outside the trust boundary or in another region;
  - a second producing domain;
  - consumers that can only subscribe to a broker;
  - a need for sub-second push to many readers;
  - feed reads becoming a measurable share of primary load.
  The switch target is NATS JetStream from its Helm chart (no CRDs needed **[V]**), fed by a relay that reads the existing feed. It needs a named operator.
- **Migration path.** To a broker it is additive for handlers: a relay publishes from the feed, the SDK swaps its cursor source for a durable consumer, and handlers stay unchanged **[I]**. The HTTP feed stays for bootstrap and replay. The **MongoDB port is not additive** for the mechanism: positions become epoch/sequence from the tailer, and the xmin filter disappears. It is additive for consumers *only if* they treated the cursor as opaque and handled events level-triggered. That is the real reason to keep the contract this strict **[I]**.

## 6. Critique of ADR-0009

Holds up:
- The throughput arithmetic.
- A broker does not remove the outbox. Confirmed by the AWS and Azure guides, which still relay from an outbox **[V]**.
- A broker would be a second transport, because bootstrap and replay stay on HTTP.
- A second access-control surface.
- Level-triggered re-reads as the single correctness mechanism.
- The precise reason for rejecting a sequence-only cursor (an event lost about one time in ten in their prototype; consistent with Dudycz **[V]**).
- The revisit triggers: topology, not rate.
- Hints derived from the feed, never the source of truth (Kubernetes bookmarks have the same status **[V]**).

Weak or wrong:
- **"A broker removes nothing."** Overstated. It removes polling, the coupling of feed delay to writer transaction length, the hand-rolled cursor, retention and horizon code, and read load on the OLTP primary. What it does not remove is the outbox. The honest version: "it removes nothing we need at this load".
- **"Parallel pulls lose per-document order."** True for an unkeyed JetStream work queue. False for Kafka keyed partitions, and false for JetStream subject-per-key with ordered consumers **[I]**. It is not a general argument against brokers.
- **"Workers scale on task-queue backlog"**, citing the KEDA Temporal scaler. KEDA needs an operator, and the company runs fixed pods. The ADR needs a fixed-capacity story: size by the burst-drain deadline and prioritise narrowing events on their own queue.
- **"Events for one Document may arrive in any order"** contradicts `feed.py`'s promise of per-Document commit order (narrowed by #240), and neither text states the xid-assignment caveat in §3.7.
- **"The upgrade is additive"** is true for a broker relay. It is not true for the already-ruled MongoDB move, and the ADR carries no note that its mechanism section is pilot-only.
- `transaction_timeout` is presented as a database setting. The hazard is instance-wide.

Omits:
- The two strongest precedents: PgQ (the same snapshot technique, run at Skype) **[V]** and Kubernetes list/watch (the cloud-native argument) **[V]**.
- Logical decoding and `pg_logical_emit_message` as the known commit-order alternative, with the reason not to take it (slot and WAL risk, PG-only life) **[V]**.
- A bookmark or heartbeat so idle consumers' cursors do not age toward `cursor_expired` on a quiet feed (the Kubernetes and Nakadi keep-alive cursors) **[V]**.
- Coalescing: a document-keyed deterministic identity, rather than a position-keyed one, collapses repeated changes to one document while it sits in backlog. This is the workqueue-of-keys idea, and it is the biggest lever on consumer cost **[I]**. The ADR says "deterministic identity" without saying keyed by what.
- Priority is only meaningful behind the reader.
- The ingest-side outbox, which *is* the queue shape, carries the bloat risk.

## 7. Could not verify

- Official PG docs text for `transaction_timeout`: seen only through mirrors.
- The scope of the CNCF TOC definition and the 12-factor wording: not re-fetched.
- Kubernetes "level-triggered" phrasing: from a secondary source only.
- Debezium Server's GA versus "Developer Preview" status: Red Hat's build page says preview; the upstream status was not checked.
- No primary PgQ throughput figure: Skype quotes 10k+ TPS overall, not for PgQ.
- The NOTIFY lock threshold (about 5k commits/s): unconfirmed.
- Temporal start-rate ceiling for a self-hosted cluster on PostgreSQL: not measured.
- The exact server version at which priority/fairness became GA.
- My claim that the xmin of a snapshot spans every database of the instance: not quoted from the docs. Reproduced afterwards (§9).
- The per-Document reorder in §3.7: reasoned from the docs. Reproduced afterwards (§9).

## 8. Sources

- Dudycz, ordering in a Postgres outbox: https://event-driven.io/en/ordering_in_postgres_outbox/
- PostgreSQL snapshot functions: https://www.postgresql.org/docs/current/functions-info.html
- PgQ, PGCon 2008 slides: https://www.pgcon.org/2008/schedule/attachments/55_pgq.pdf ; PgQ 2009: https://www.pgcon.org/2009/schedule/attachments/91_pgq.pdf ; Percona on PgQ/PgQue: https://www.percona.com/blog/pgq-and-pgque-workflow-engines-you-might-need-in-postgresql/ ; SkyTools wiki: https://wiki.postgresql.org/wiki/SkyTools
- Kubernetes API concepts (watch, 410, bookmarks, 5 min): https://kubernetes.io/docs/reference/using-api/api-concepts/ ; level-triggered informers (secondary): https://labs.iximiuz.com/courses/kubelings-dbd840c8/module-07/watch-informers
- Cosmos DB change feed pull model: https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/change-feed-pull-model ; design patterns: https://learn.microsoft.com/en-us/azure/cosmos-db/change-feed-design-patterns ; Azure outbox with Cosmos: https://learn.microsoft.com/azure/architecture/databases/guide/transactional-outbox-cosmos
- DynamoDB Streams: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html ; AWS transactional outbox: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html
- MongoDB change streams production recommendations (8.2): https://www.mongodb.com/docs/v8.2/administration/change-streams-production-recommendations/ ; resume cost: https://alexbevi.com/blog/2022/03/02/performance-analysis-of-resuming-a-mongodb-change-stream/ ; https://jira.mongodb.org/browse/SERVER-58473
- Nakadi concepts / low-level API: https://zalando-nakadi.github.io/nakadi-manual/docs/using/concepts.html ; https://zalando-nakadi.github.io/nakadi-manual/docs/using/consuming-events-lola.html ; archived repo: https://github.com/zalando/nakadi
- HTTP feeds spec: https://github.com/http-feeds/http-feeds ; Electric HTTP API: https://electric-sql.com/docs/api/http
- Fowler, event-driven: https://www.martinfowler.com/articles/201701-event-driven.html
- Morling, revisiting the outbox: https://www.morling.dev/blog/revisiting-the-outbox-pattern/ ; replication slots: https://morling.dev/blog/mastering-postgres-replication-slots
- Zalando on Debezium at scale: https://engineering.zalando.com/posts/2025/12/contributing-to-debezium.html
- Debezium Server (Red Hat build): https://docs.redhat.com/en/documentation/red_hat_build_of_debezium/2.7.3/html/debezium_user_guide/debezium-server
- Brandur, Postgres queues: https://brandur.org/postgres-queues ; PlanetScale: https://planetscale.com/blog/keeping-a-postgres-queue-healthy ; Microsoft: https://techcommunity.microsoft.com/blog/adforpostgresql/potential-consequences-of-using-postgres-as-a-job-queue/4514332 ; Graphile Worker: https://worker.graphile.org/docs/performance
- Sequin HTTP pull consumers: https://github.com/sequinstream/sequin
- LISTEN/NOTIFY: https://www.recall.ai/blog/postgres-listen-notify-does-not-scale ; counterpoint: https://dbos.dev/blog/postgres-listen-notify-scalability
- NATS on Kubernetes (Helm, NACK optional): https://docs.nats.io/running-a-nats-service/nats-kubernetes/helm-charts ; https://docs.nats.io/learn/deployment/kubernetes
- Temporal limits: https://docs.temporal.io/workflow-execution/limits ; https://docs.temporal.io/kb/temporal-platform-limits-sheet/ ; Signal-With-Start: https://docs.temporal.io/design-patterns/signal-with-start ; signal-rate guidance (community): https://community.temporal.io/t/using-signals-to-build-a-workflowqueue-with-high-throughput/6193 ; priority/fairness: https://docs.temporal.io/develop/task-queue-priority-fairness ; https://temporal.io/blog/task-queue-priority-and-fairness-your-task-queue-your-way

## 9. Reproduction

Added after the review. [`check_findings.py`](check_findings.py) ran against PostgreSQL 17 in a
container published on port 55439 and printed:

```
(1) open writer in database b has xid 741; database a sees xmin 741; committed feed rows readable: 0
(2) feed order: ['first, committed last', 'second, committed first']; final state: first
both findings reproduced
```

1. A writing transaction left open in another database of the instance holds back the feed of
   this one (§3.1): the timeouts set on the admission database do not end it.
2. A transaction that wrote before it reached the Document is listed ahead of one that changed the
   same Document and committed earlier (§3.7). The state is the later commit's, so a reader that
   re-reads the state is right whichever event it handles last.

What followed: ADR-0009 and `kp_admission.feed` no longer promise an order between the events of
one Document, and the ADR's broker and sizing paragraphs were corrected.
