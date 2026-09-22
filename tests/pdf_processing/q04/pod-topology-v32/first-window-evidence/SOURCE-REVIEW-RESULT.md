# AG source-review result

Status: **REJECTED_FOR_AUTOMATIC_ORACLE_ADOPTION**.

This review used the exact inputs and hashes in
[SOURCE-REVIEW-REQUEST.md](SOURCE-REVIEW-REQUEST.md). It confirms that neither
Wiki06 nor native loses or adds a source-region fragment. Wiki06 has six
cross-page one-to-two text splits. Native has 29 changed fragment components:
23 one-to-two splits and six many-to-many regroupings.

The latter six components prevent a safe, bounded proof that the changed graph
preserves reading order, parent/child membership, captions, and table/picture
bindings. Source-fragment equality does not prove those graph relations. No
general split/merge normalization is adopted, no historical reference is
modified, and AG remains measurement-only for Wiki06 and native.

This is a fail-closed source-review result, not a claim that the source PDFs are
wrong or that the AG runtime failed. A future adoption must review each changed
component against the source pages and record an explicit limited disposition
before creating a new oracle and running fresh/restored/exact replay.
