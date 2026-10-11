# Use fixed shared inputs and publish each projection independently

Corpora reference reusable Assets, and each Materialization fixes its actual
Asset and Canonical Revision inputs rather than copying knowledge or silently
following changes during the run. Projections own their product APIs and publish
a coherent version within their declared publication unit independently, so Wiki
can publish while Retrieval is still building or has failed; no cross-projection
publication barrier is required. Fixed inputs and eligible old-version fallback
remain subject to current governance and custody, and neither a whole-Corpus
publication unit nor a universal serving gateway is implied.

Originally confirmed on 2026-09-26 in overall-design
[Q4–Q6](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843489434),
[Q16](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843866759) and
[Q17](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5844008136).
Retrospectively recorded on 2026-10-09; no new design decision is made here.
Snapshot resolution, publication units, switching and enforcement mechanisms remain
with the existing downstream owners. [ADR-0002](0002-canonical-source-relationships-and-projection-citations.md)
separately records source relationships and product citations.
