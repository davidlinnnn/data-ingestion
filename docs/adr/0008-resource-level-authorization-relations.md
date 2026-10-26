# Keep authorization relations at the Resource level and the document binding in the platform

The authorization engine, built-in or company GAM, holds only relations on
Resources: who maintains, contributes to and reads each Resource. Which Resource
a Document belongs to stays in the platform's admission record, set by
submission, changed only through the Resource API's rebind and eviction, and
re-established by submission after an eviction. Eviction and the contributor
relation are deferred in v1 by
[#55](https://github.com/davidlinnnn/data-ingestion/issues/55), leaving rebind
as the only change. An
enforcement point first resolves the Document's binding, then asks the decision
interface about that Resource.

Writing a document tuple into the engine for every Document would let the
engine answer document-level questions on its own, and an auditor could explain
"why could Alice read D" in one place. It was rejected because:

- the binding would live in two systems without a shared transaction, so a
  failed half of a rebind could leave the previous Resource's readers able to
  read the Document;
- search would have to list readable Documents. OpenFGA's ListObjects defaults
  to 1000 results and 3 seconds, and SpiceDB warns about LookupResources beyond
  10k results, far below the 10M-document horizon. Listing readable Resources
  stays small;
- under company GAM (path 1) someone would have to write every document tuple
  into GAM. The platform writing them contradicts the confirmed rule that the
  platform does not write relations into GAM. Users writing them would bypass
  the attributable submission binding required by #53 Q12.

The cost is that explaining a decision needs two records: the binding with its
change history, and the decision. Per-document reader exceptions are not
supported. Adding them later means writing tuples only for the excepted
Documents, and ADR-0007's guarantee that a Resource's products share its
readers must then be re-evaluated.

Confirmed on 2026-10-26 in
[#85](https://github.com/davidlinnnn/data-ingestion/issues/85) Q1; see the
[authorization design](../design/knowledge-platform-authorization.md).
