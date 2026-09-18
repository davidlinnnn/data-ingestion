# ACL retained split disposition proposal

Status: **decision proposal only**. ACL fixture 09 remains failed. This document
does not update a reference, normalize a graph, change continuation behavior, or
qualify fresh, restored, or replay.

## Decision input

The retained comparison proves one complete, provenance-preserving split. The
historical graph has one `#/texts/97` with two regions; the current graph has two
adjacent body text nodes, one for each of the same regions. Joining their strings
with one space and rebasing the second charspan exactly reconstructs the historical
node. After accounting for the extra node and reference renumbering, no collection
delta remains. This proof localizes the difference; it does not authorize a
consumer normalization or replace graph review with source-signature equality.

The current `column-edge-continuation-v1` behavior is internally consistent: the
right-column continuation starts at normalized top `0.3766`, outside its top-quarter
gate. The historical R3 method did not carry this continuation attestation. All
non-continuation method, package, model, option, platform and Python fields match.

## Option A: retain the conservative split and review a new reference

Create a new, explicitly versioned fixture-09 reference from the retained output
only after source review accepts the two-node representation. Keep exact graph
comparison. The acceptance record must identify the old and proposed graph hashes,
the two source regions, their full text and charspans, and the one-node-to-two-node
mapping. It must say that this is a fixture-09 disposition, not a general PDF
quality rule.

Benefits:

- preserves the already reviewed continuation implementation and producer identity;
- does not introduce a broader cross-column join based on one document;
- keeps graph equality strict against a reviewed, versioned expectation;
- limits the reference change to the observed fixture and makes future drift red.

Costs:

- the historical R3 graph remains historical evidence rather than the current
  expected graph;
- fixture-09 page-2 typed coverage must be reviewed as 69 nodes rather than 68;
- fresh, restored and exact replay still need execution against the same newly
  approved reference before ACL can pass.

Q01 is not reinterpreted by this option. Its eight source-anchored continuation
conditions and `continuation-oracle.json` remain unchanged because production
continuation code does not change. The Q04 specification's full-graph requirement
also remains unchanged; only the reviewed expected graph version changes.

## Option B: expand the continuation policy to reproduce the historical join

Change production continuation logic so the right-column fragment is joined to
the left-column fragment. A simple threshold expansion would need to admit at
least normalized top `0.3766`; a narrower rule would need additional source-backed
features beyond this single retained example.

Benefits:

- may reproduce the historical fixture-09 graph and retain its existing 68-node
  page-2 oracle;
- presents this paragraph as one semantic text node.

Costs and risk:

- changes the producer/method identity and invalidates group and assembly reuse;
- can create false cross-column joins outside ACL, including the class of false
  associations Q01 was introduced to reject;
- requires source-reviewed negative cases before a rule can be justified; this
  one positive sample is insufficient to select a safe boundary;
- requires fresh validation of all affected fixtures and old-request behavior,
  rather than a fixture-09 reference-only disposition.

Q01 would need all eight anchored edges rechecked, including the four rejected
associations, the required join, and the three inline joins. Q04 would need fresh
six-fixture full graphs, restored compatibility, exact replay, invalidation, and
old-request non-reinterpretation under the new method identity. Signature-set
equality would not satisfy any of those checks.

## Recommendation

Choose **Option A** for this retained result. The evidence supports the split as a
safe representation and does not support widening a global continuation rule.
Approve a new reference only through an explicit source-review record. Do not edit
the current frozen bundle or overwrite the R3 reference; produce a new bundle
version after review.

The directly affected acceptance artifacts are:

- `references/09.json`: version a proposed two-node graph; retain the old hash;
- `oracles/quality-oracle.json`: review fixture 09 processed page 2 as 69 ordered
  typed items and bind the two fragments independently;
- retained fixture-09 content evidence: verify the same six formula occurrences,
  equation 2 `TextItem`, two OCR components, source/page hashes, captions,
  provenance and all graph edges against the new reference.

No reference or source oracle for fixtures `native`, `06`, `07`, `08`, or `10`
changes under Option A. Q01's `continuation-oracle.json` also stays unchanged. The
required reuse sequence for fixture 09 is still: a new fresh result accepted by the
reviewed graph; restored output exactly equal to that fresh output; exact replay
with the same request/final identity and all recorded work reused. Existing old
requests remain bound to their original method/profile and must not be reinterpreted.
Passing those three cases would be bounded ACL evidence, not completion of #51.
