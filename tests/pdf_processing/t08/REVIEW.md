# T08 two-axis review

Fixed base: `765d5483a61f8648f015e2f7f5538c54b62b6198`.
Initial reviewed commit: `38007e2`. Two independent read-only agents applied
`/code-review` to the complete routing, deployment, harness and documentation diff.

## Standards

No documented-standard violation. One nonblocking duplicated binding-construction
smell was corrected by a shared pure `release_binding` constructor used by both
manifest publication and worker validation. Recheck: no outstanding smell or
violation. The reviewer separately identified the malformed-request failure path,
which was also handled by the Spec review below.

## Spec

Two findings were corrected: malformed request values could raise AttributeError
before returning explicit failure; the Workflow now validates dictionary shape,
and the real negative matrix includes a malformed request. The queued-Activity
case formerly slept four seconds without proving an Activity was waiting; it now
polls with a bounded deadline and asserts an unstarted group Activity on the exact
old queue before starting its worker. Recheck: no remaining Spec findings.

The harness also deletes the old Workflow Pod during in-flight old parsing to
exercise Workflow replacement alongside Activity retry. Final runtime acceptance
is recorded separately in `evidence/VERDICT.md`; pending measurements were never
represented as a passing review result. Standards: 0 outstanding; Spec: 0 outstanding.

A later harness review of `9d9d83a` identified a cleanup failure path after forced
Pod deletion: runtime inspection could fail while the Pod object was already gone.
Fault targets are now recorded before deletion; retrying cleanup requires both
Pod absence and each tracked container's runtime absence, with bounded inspection
calls. Errors retain the flock. Both independent reviewers confirmed this
correction with no outstanding finding. Failed fault timing and scheduling trials
remain excluded in `evidence/EXPLORATORY.md`.

The phased scenario at `8e67d96` preserved the required interactions while avoiding
an unqualified simultaneous 14-Pod claim. Spec review requested actual Temporal
poller proof rather than Pod readiness alone. The final supplementary run requires
fresh poller identities matching current Pod names/UIDs on both Workflow and both
OCR queues before and after each method request; sealing checks all mappings.
The reviewer confirmed that correction. The main matrix, supplementary poller
cases, full suite and checked cross-release comparison subsequently passed.
