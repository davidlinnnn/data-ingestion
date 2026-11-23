# Make Canonical Acceptance one platform-database transaction over a write-once content object

Canonical Acceptance is the commit of one transaction in the platform database,
run when the final succeeded report of a `process` request is recorded (the
reconciler runs the same function when the report is lost). That transaction
ends the request, records the Canonical Revision, marks its Source Revision
`accepted`, moves the Document's current revision when the candidate wins, and
writes the change event. The revision's content is not in the database: the
processing workflow's last step writes it as one object, written once, at
`documents/{document_uid}/revisions/{canonical_revision_id}.json`, and hands
its key, digest and size to the platform as the candidate. The revision record
is the only statement of what is accepted, and it drives retention. The
revision's identifier is `crv_` and the request id's 32 hex digits, so one
request forms at most one revision and a redelivery lands on the same one.
Confirmed by the user between 2026-11-19 and 2026-11-22
([#57](https://github.com/davidlinnnn/data-ingestion/issues/57), rulings A2 and
B1 to B5); the contract is the admission specification §3 and §7.3, and the
reasons are in the
[design result](../design/knowledge-platform-canonical-persistence.md).

Three things follow. Processing completion, a registered Processing Result and
a written content object are not acceptance: a success forms none when the
Document is deleted, the report carries no candidate, the candidate's key is
not the revision's own, or the request's version has been withdrawn. The
platform, not canonical processing, selects the current revision, once, in that
transaction: a newer Source Revision wins, then a higher adoption sequence,
never completion time, so results arriving in any order leave the same current
revision (this narrows ADR-0003's selection rule to two comparisons). And
custody of the processing artifacts a revision refers to passes at that commit
with no storage operation: they stay where processing registered them, as
source files already do (ADR-0012), and the content refers to them by
references that hold no bucket, no Document prefix and no URL.

Readers get the bytes of a revision's content and of the artifacts it lists
from the platform's read API, by exact revision; no component outside the
platform holds storage credentials, and the platform issues no presigned URL
(user, 2026-11-22). Authorization is the platform's, storage cannot express
which reader may read which Document, and a deletion takes effect at the
platform's next read (a projection removes its own copy by cleanup, ADR-0014).

The trade-offs: an object can be written by a run whose transaction never
commits, so storage holds objects no record points at until the Document is
purged; a record can outlive its object when storage loses data, which the read
API reports as its own error; and image reads pass through the platform API
instead of going to storage directly. Rejected: writing the content into the
database inside the acceptance transaction (56 to 348 KB per Document estimated
from the Processing Result, larger in production; on MongoDB the commit would hold the feed counter while
the content replicates); a separate acceptance component between processing and
the platform; copying adopted artifacts into a Canonical area (23 MB per
Document at the median, 230 TB at ten million Documents); and letting readers
read the bucket.
