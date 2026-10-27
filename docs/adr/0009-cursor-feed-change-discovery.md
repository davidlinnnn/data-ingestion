# Discover canonical changes through a cursor feed, not a broker

Projections discover changes to a Document's current revision (including
withdrawal), deletions and changes to which products a Document or a whole
Source belongs in by reading one append-only
Change Feed through the governed read API. The feed
lives in the admission database and each entry is written in the same
transaction as the fact it records, so the feed table is itself the
transactional outbox. Facts owned by other components, such as the current
canonical revision and governance withdrawal, enter the feed in the transaction
that records them in that database, through status intake or the shared block
record. Entries carry identities, not content. The platform keeps
one cursor per consuming projection: a projection reports its position only
after each event's effect is durable (applied, or handed to durable execution),
and the platform rejects reports that would move a cursor backwards. Missed,
duplicate and out-of-order delivery are all resolved by re-reading from the
cursor and applying events idempotently, so this feed is the only correctness
mechanism. Notifications may later be added as wake-up hints only, derived from
the same feed.

Each projection runs one logical reader that reads a batch, hands each event to
its durable execution layer under a deterministic identity, and reports its
position. Parallelism and autoscaling belong to that execution layer and follow
its backlog; for Temporal-based projections the reader is a singleton workflow
and workers scale on task-queue backlog. A platform consumer SDK wraps reading,
position reporting and idempotent hand-off, so a projection implements only its
handler. The reader must not run inside request-serving web workers, where every
worker process would start its own reader.

A broker such as NATS JetStream was considered and deferred, not rejected. It
removes nothing: the authoritative facts commit in PostgreSQL, so the
dual-write problem still requires this outbox plus a relay, and the API path
stays for bootstrap, resynchronisation and replay beyond a stream's retention,
so a broker is always a second transport. It adds a second access-control
surface, because entry identities reveal that a Document exists in a Resource.
Its strongest feature, a durable consumer shared by many workers, duplicates
what the execution layer already provides for work that runs for minutes to
hours (distribution, redelivery, backlog-based scaling), and parallel pulls lose
per-document order. Throughput is not a reason either: the near-term target of
10,000 document updates a day averages 0.12 events a second, and the enterprise
horizon of 100,000 a day averages about 1.2 and peaks around 12, on the order of
ten million entries over a 90-day retention. These are estimates, not
measurements, and are expected to sit far below what one PostgreSQL primary
handles; production load validation under
[#88](https://github.com/davidlinnnn/data-ingestion/issues/88) measures them.
Polling load grows with the number of consumers, not Documents. The costs that grow with volume are processing and
vector storage, which a broker does not change.

Revisit when at least one trigger holds and a named operator runs the cluster:
measured feed traffic becomes a primary load on the admission database;
consumers sit outside the platform's network or trust boundary, need
cross-region replication, can only subscribe to a broker, or cannot run a
durable execution layer; producers or consumers from a second domain need a
shared event backbone (more projections reading this feed do not count); or a
company mandate requires one. A managed broker service satisfies the operator
requirement but is not itself a trigger. Lower latency is not a trigger either:
long-polling on the same endpoint comes first. The upgrade is additive: a relay
publishes from the existing feed table, with no schema change and no change to
consumer logic.

Implementation guards carried to the implementation tickets (the feed and its read API: [#126](https://github.com/davidlinnnn/data-ingestion/issues/126); the projection side: [#127](https://github.com/davidlinnnn/data-ingestion/issues/127)): the feed is ordered
and paged by transaction ID and then sequence, and never returns entries from
transactions at or above the snapshot xmin. A sequence-only cursor is unsafe even
with that filter, because a transaction can take a lower sequence value and
commit after one that took a higher value, and the cursor would skip it (see
the PostgreSQL outbox ordering reference below). A prototype against
PostgreSQL 18.4 lost about one event in ten that way. The cost of the filter is
that one long-running transaction holds back the whole feed until it ends, so
the admission database sets `transaction_timeout` (PostgreSQL 17 and later) and
`idle_in_transaction_session_timeout`, and operations alert on the age of the
oldest snapshot xmin. Consumers treat the cursor as opaque, events
for one Document may arrive in any order, and handling is level-triggered: each
event means "re-read the current state". A state read that follows a feed
position must observe state at least as new as that position. The feed is
partitioned by month and kept for 90 days; a cursor older than the retention
receives `cursor_expired` and resynchronises through the same bootstrap path a
new projection uses, which fixes its feed starting point before it enumerates
documents. That resynchronisation also reconciles every Document the
projection still stores but the enumeration did not return, and a state read
for a deleted Document answers "deleted", so a deletion that fell inside the
expired gap is not left behind.

Confirmed on 2026-10-22 and revised on 2026-10-24 (platform-held cursors, a
single feed in the admission database, revised revisit thresholds) and on
2026-10-26 (long-transaction guards and resynchronisation after validation)
during the
[publication grilling](https://github.com/davidlinnnn/data-ingestion/issues/55).
The ordering evidence is in the
[validation record](../research/canonical-consumption-validation-2026-10-26/README.md).
This applies [#58 Q18](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843984257)
(notifications are not the sole correctness mechanism) and follows the
[admission outbox decision](https://github.com/davidlinnnn/data-ingestion/issues/31)
that rejected a separate broker for dispatch. External references: the
[NATS JetStream wallet-backbone case](https://nats.io/blog/brosettlement-building-a-wallet-event-backbone-with-nats-jetstream/)
(PostgreSQL as source of truth, outbox, relay after commit), the
[dual-write problem](https://milanjovanovic.tech/blog/outbox-pattern-dual-write-problem),
[ordering pitfalls in PostgreSQL outboxes](https://event-driven.io/en/ordering_in_postgres_outbox/),
[at-least-once outbox delivery](https://oneuptime.com/blog/post/2026-07-22-transactional-outbox-duplicate-events/markdown);
server-held positions in [JetStream consumers](https://docs.nats.io/using-nats/jetstream/model_deep_dive)
and [Kafka consumer offsets](https://docs.redpanda.com/docs/development/consumer-offsets),
against the consumer-held [Kinesis KCL lease table](https://docs.aws.amazon.com/streams/latest/dev/kcl-dynamoDB.html);
long-polling change feeds in [CouchDB](https://docs.couchdb.org/en/3.5.1/api/database/changes.html)
and [Consul blocking queries](https://developer.hashicorp.com/consul/api-docs/features/blocking);
the [KEDA Temporal scaler](https://keda.sh/docs/2.21/scalers/temporal/) and
Temporal's [continue-as-new pattern](https://docs.temporal.io/design-patterns/continue-as-new).
The event schema, serving-fact reporting and repair are in the
[#55 design record](../design/knowledge-platform-canonical-consumption.md).
