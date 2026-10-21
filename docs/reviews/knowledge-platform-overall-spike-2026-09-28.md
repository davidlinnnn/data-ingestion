# Knowledge Platform overall design — fresh-context spike

[Reviews](README.md) · [Reviewed candidate](../design/knowledge-platform-overall-review.md)

**Date:** 2026-09-28. **Method:** an explicitly requested subagent with no inherited
conversation history independently read the candidate, synthesis, glossary,
Baseline and relevant issue records, then walked concrete counterexamples.
The parent checked findings against existing decisions and detailed-ticket scope.
This was a document/scenario review, not an executable prototype or runtime test.

**Subsequent disposition:** the user requested incorporation of this feedback and
confirmed the logical responsibilities, boundary meanings and handoff on
2026-09-28. The [overall review](../design/knowledge-platform-overall-review.md)
and synthesis now include the clarifications and validation cases; the Baseline's
query-responsibility wording was reconciled while its separate direction-review
status remains proposed. The findings, hashes and pending status below describe
the pre-incorporation snapshot, not the revised confirmed artifacts.

## Verdict and candidate binding

**The independent reviewer agrees with the logical skeleton.** There is no new
consequential human decision required before logical-level confirmation and no
reason found to reopen Q1–Q25. Two wording/ownership clarifications are recommended;
two further counterexamples belong to already-assigned detailed design work.
This does not replace the still-pending human confirmation or the separate
Architecture Direction Review, and it does not qualify production mechanisms.

Reviewed workspace inputs, unchanged by this spike:

- `docs/design/knowledge-platform-overall-review.md`, SHA-256
  `a6ca48aae88473c7158b35b8954a1d7ff1edc2e1435c4151d4a0d13633882a57`.
- `docs/design/knowledge-platform-logical-design.md`, SHA-256
  `735e75349cb8afbf90aa9f8e31c7b24a612bace21426abdb6d0d09acd89fa31f`.

Classification: **A** requires a new human decision before confirming this skeleton;
**B** clarifies already-established responsibility; **C** is a detailed design or
validation obligation already owned by an existing ticket. A has no findings.

## B — clarify two responsibilities

### Projection operations versus consumer orchestration

The [Baseline responsibility table](../../ARCHITECTURE-BASELINE.md#4-responsibilities-and-conceptual-relationships)
places query strategy, ranking, traversal and context assembly with External
Consumers. The accepted projection-owned API/product boundary in
[Q16](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843866759)
also permits a Retrieval product to define its native ranked retrieval operation.
Read literally, the Baseline wording could make that operation seem forbidden.

Counterexample: Retrieval supplies ranked top-k results; a consumer combines them
with another tool's results and reranks the combination. These are distinct roles,
not competing owners of the same operation.

Suggested wording: **A projection owns the semantics of its declared product
operations. An External Consumer owns application-level query orchestration,
additional ranking and context assembly over those interfaces.** This sharpens Q16
without creating a new service, exposing index internals or selecting an algorithm.
Reconcile the wording when updating the proposed direction material; the spike
does not silently rewrite that separate review's candidate.

### Durable domain decisions and their evidence

The [overall review](../design/knowledge-platform-overall-review.md#components-and-authoritative-state)
correctly excludes Temporal from being a perpetual domain/audit store, but leaves
ownership of validation reports and human decisions mainly in workflow prose.

Counterexample: request status has expired after its terminal-plus-30-day window,
and workflow history is no longer retained, while a Published View Version still
needs to identify its validation report and release decision. Canonical exception
acceptance may likewise need durable attribution beyond execution history.

Suggested responsibility-table additions:

- **Canonical owner:** retain canonical acceptance/exception decision facts and
  required supporting evidence for their applicable lifecycle/custody period.
- **Projection owner:** retain publication candidate identity, validation evidence
  and release/withdrawal decision facts for their applicable lifecycle/custody period.

These records must not rely solely on request retention or workflow history.
They need no new central audit service. Exact representation, retention and
governance/erasure handling remain with
[Select canonical persistence and artifact ownership](https://github.com/davidlinnnn/data-ingestion/issues/57)
and the domain owners. This makes Q19/Q23/Q24 responsibilities explicit; it does not
promise perpetual retention or override deletion obligations.

## C — retain two counterexamples for detailed validation

### Approved candidate changes during catch-up

1. A person approves candidate K1 based on report R1.
2. Source changes arrive while release is waiting.
3. Catch-up creates materially different candidate K2.
4. Reusing the K1/R1 approval to release K2 would authorize unreviewed output.

The candidate already rejects blanket approval for a changed candidate, and the
[confirmed Q23 handoff](https://github.com/davidlinnnn/data-ingestion/issues/55#issuecomment-5844076710)
assigns report validity, live-change catch-up and cutover to the projection decision.
This is not an overall omission. Preserve the test: changed candidate/evidence
requires the applicable renewed decision binding; a governance recheck may deny K1
but must not turn its approval into authority for K2. Do not choose a cutover or
approval protocol in this review.

### Old backup cannot prove current authorization

1. Backup at t0 contains an access grant.
2. Revocation is effective at t1.
3. After a failure at t2, only the t0 backup is available.
4. Treating the restored grant as proof of current authorization resurrects access.

The candidate already requires reconciliation before renewed serving.
[Define governance enforcement across canonical data and published views](https://github.com/davidlinnnn/data-ingestion/issues/56)
and the persistence decision own this case. Preserve the acceptance condition:
where current governance cannot be established, keep disclosure fail-closed.
How trustworthy current state is recovered and what recovery loss/time can be
tolerated remain those decisions, including the
[operating envelope](https://github.com/davidlinnnn/data-ingestion/issues/54).
No special backup architecture is selected here.

## Cases that did not expose a contradiction

- Removing a shared Asset from Corpus A need not remove it from B or rerun OCR.
- Eligible accepted C1 can remain usable while newer source S2 is pending;
  captured-S2 selection cannot silently fall back, and exact-C1 selection cannot
  silently substitute another revision.
- Fixed materialization inputs do not preserve authorization indefinitely.
- Temporal execution completion is distinct from processing business success,
  canonical acceptance and eligible publication.
- Membership-only scheduling, batch admission, ordering, publication units,
  outbox/CAS details, physical DB selection and enforcement mechanisms are already
  explicitly delegated. Their not-yet-designed state is not an overall blocker.

## Parent disposition

Accepted the independent findings as review feedback and checked that the relevant
responsibilities and detailed obligations already exist in the issue scopes.
The reviewed candidate and separate Baseline are left unchanged so this review's
binding stays clear. The B items supply precise wording for the next candidate
revision; C items strengthen existing validation scenarios. No issue is closed,
no dependency or infrastructure is added, and no new human question is introduced.
