# Discover canonical changes through a cursor feed, not a broker

Projections discover accepted revisions, deletions and membership changes by
polling an append-only change feed with a monotonic sequence, exposed through
the governed read API, keeping their own durable cursors. This feed is the only
correctness mechanism: missed, duplicate and out-of-order delivery are all
resolved by re-reading from the cursor and applying events idempotently.
Notifications (NATS, PostgreSQL LISTEN/NOTIFY) may be added later as wake-up
hints only; they must derive from the same feed via an outbox and carry no
correctness responsibility. A platform consumer SDK wraps polling, cursor
persistence, the commit-visibility watermark and idempotent dispatch, so each
projection implements only its handler.

A broker was considered and deliberately deferred, not rejected. The
authoritative facts are committed in PostgreSQL transactions (admission owns
deletion and rebind; Canonical owns acceptance), so a broker cannot be written
atomically with them: the dual-write problem forces an outbox table plus a
relay in front of any broker — NATS's own JetStream reference architectures
keep PostgreSQL as the transactional source of truth with exactly this shape.
A JetStream durable consumer is itself a server-side cursor over a replayable
log, so moving to it changes the transport, not the consumer contract. The
feed contract is therefore transport-neutral: upgrading means adding a relay
behind the existing outbox and repointing consumers, with sequence, thin
events and idempotent application unchanged.

Revisit thresholds for introducing a broker: sustained event rates of hundreds
per second, consumer count around ten or more, a requirement for sub-10-second
end-to-end change latency, or a company platform mandate. Until one of these
holds, the pilot targets (10-minute searchable, 10–30-second polling) leave no
latency budget that a broker would buy.

Implementation guards carried to the implementation tickets: a consumer cursor
must not advance past sequence numbers whose transactions have not yet
committed (snapshot-xmin watermark, since PostgreSQL assigns sequence values
before commit), and the feed table is partitioned by month so retention drops
whole partitions.

Confirmed on 2026-10-22 during the
[publication grilling](https://github.com/davidlinnnn/data-ingestion/issues/55).
This applies [#58 Q18](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843984257)
(notifications are not the sole correctness mechanism) and follows the
[admission outbox decision](https://github.com/davidlinnnn/data-ingestion/issues/31)
that rejected a separate broker for dispatch. External references: the
[NATS JetStream wallet-backbone case](https://nats.io/blog/brosettlement-building-a-wallet-event-backbone-with-nats-jetstream/)
(PostgreSQL as source of truth, outbox, relay after commit), the
[dual-write problem](https://milanjovanovic.tech/blog/outbox-pattern-dual-write-problem),
[ordering pitfalls in PostgreSQL outboxes](https://event-driven.io/en/ordering_in_postgres_outbox/)
and [at-least-once outbox delivery](https://oneuptime.com/blog/post/2026-07-22-transactional-outbox-duplicate-events/markdown).
Event schema, log topology per writer and reporting transport remain with the
[#55](https://github.com/davidlinnnn/data-ingestion/issues/55) resolution.
