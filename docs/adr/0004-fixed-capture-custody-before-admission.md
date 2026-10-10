# Fix complete captured inputs and custody before durable admission

Durable processing admission requires a finite, complete Capture Package with fixed
artifact versions, integrity information and accountable custody through the
agreed queueing, suspension and retry period. Resolving live latest content during
execution, unprotected expiring inputs or silently partial packages cannot provide
that guarantee; capture readiness does not require synchronous parsing or imply
Canonical Acceptance. Retain original inputs and adopted evidence under applicable
reprocessing, evidence and erasure obligations, independently of processing
checkpoint cleanup, without requiring another byte copy or indefinite retention.

Originally confirmed on 2026-09-30 in source-handoff
[Q3](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5909819124) and
[Q6](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5911948945);
retained-input obligations were confirmed on 2026-10-02 in
[Q10](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5953381014),
and complete-package admission was clarified on 2026-10-03 in
[Q9](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5966721936).
Retrospectively recorded on 2026-10-09; no new design decision is made here.
The accepted-dependency custody boundary was already confirmed on 2026-09-26 in
[overall Q20](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5844054630):
required adopted dependencies receive retention protection before acceptance completes;
processing owns its execution intermediates and projections own their products.
Exact admission transactions, custody mechanisms and numeric durations remain with
their existing owners.
