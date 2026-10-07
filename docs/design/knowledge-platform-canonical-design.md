# Canonical representation, acceptance and lifecycle

[Design index](README.md) · [Domain glossary](../../CONTEXT.md)

This checkpoint follows
[Design canonical representation, acceptance and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32).
The ticket remains in progress. Q1–Q9 establish acceptance, source/projection
responsibilities, evidence precision, parser-output disposition, accepted-revision
immutability, rule-based selection and post-acceptance invalidation principles.
Detailed representation, validation, selection, lifecycle mechanisms and Enrichment
version relationships remain open. Q10 confirms that adopting new Enrichment
produces a new Canonical Revision; automatic reprocessing scope remains under discussion.
The [confirmed logical design](knowledge-platform-logical-design.md) and
[resolved source handoff](knowledge-platform-source-handoff.md) continue to govern.

## Q1: minimum acceptance contract

Confirmed on 2026-10-06 in the [Q1 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6013869858).
A candidate Canonical Revision must provide all six parts before it can qualify
for Canonical Acceptance.

| Required information | Confirmed meaning |
|---|---|
| Identity and version lineage | Identify the Asset, exact Source Revision and attachment inputs, result version and producing method version. |
| Reusable content and structure | Preserve the text, structure and relationships required for agreed reuse. Format-specific distinctions may remain. |
| Traceable Source Evidence | Relate represented content to the fixed source observations and locations supporting it. Insufficient location precision or evidence support must be explicit and considered in acceptance. |
| Content attribution | Distinguish source content, OCR reconstruction and generated interpretation. Enrichment has attributable inputs, producing methods and versions. |
| Coverage and limitations | Expose coverage, missing or unsupported content and uncertainty, including whether the applicable acceptance rules permit those limitations. |
| Auditable acceptance basis | Bind the determination to the exact candidate, rule version, validation evidence and outcome attributable to automated rules or an authorized human. |

Acceptance means that this exact version meets agreed representation, evidence,
quality and governance conditions for agreed reuse. It does not establish source
truth, suitability for every use, latest-version selection or permanent access.
Wiki and Retrieval retain their own product-quality and publication conditions.

These are logical requirements. Information may be connected through fixed-version
references; this decision does not select fields or storage mechanisms. Existing
obligations for required processing completion, adopted evidence custody and
current governance continue to apply.

## Q2: complete-candidate acceptance boundary

Confirmed on 2026-10-06 in the [Q2/Q3 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6014492266).
For the initial document scope, one complete candidate produced from one Asset's
complete Capture Package is the unit of Canonical Acceptance. Components may be
individually addressed, cited and validated, but pages, paragraphs and other
components do not receive independent acceptance in this scope.

Main content and required attachments can jointly express necessary meaning:
an SOP's steps and an attachment's warnings must be evaluated together against
agreed reuse requirements. This boundary is recorded in
[ADR-0001](../adr/0001-complete-candidate-canonical-acceptance.md).

The same Source Revision may produce different candidates through different
methods or deliberate reprocessing; there is no one-to-one restriction. Independent
Enrichment acceptance and version relationships remain open. A complete candidate
does not imply lossless representation: Q1 and Q3 govern necessary content and
permitted limitations.

## Q3: acceptance with explicitly permitted limitations

Confirmed in the same [Q2/Q3 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6014492266).
The initial scope permits acceptance with disclosed limitations only where
explicit acceptance rules allow them. A limitation that prevents an agreed reuse
requirement from being met cannot be excused by attaching a warning.

For example, a chart may have reliable trend interpretation and traceable evidence
without reliably represented exact values. Rules for agreed trend-and-citation
requirements may allow acceptance with those values explicitly unavailable.
Requirements to answer exact-value questions cannot pass on that basis. This is a
policy example, not an adopted pilot, numeric threshold, model or processing profile.

Judgment exceptions continue through authorized human handling. Missing required
source inputs, incomplete required work, insufficient necessary evidence or
unsatisfied governance cannot be waived as an accepted limitation. This decision
does not select a new status name or grading schema.

## Q4: canonical relationships and projection citations

Confirmed on 2026-10-06 in the [Q4 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6015964591),
after clarifying document relationships, source locations and Docling's bounded
capabilities. Canonical represents reusable document structure through content
components and explicit relationships, retaining necessary format distinctions.
The detailed component/relation inventory and fields still need three-format cases.

| Boundary | Confirmed responsibility |
|---|---|
| Parsing and required Enrichment | Produce observations of document structure, source locations and detected relationships, with attributable methods and limitations. |
| Canonical mapping and acceptance | Preserve, normalize and validate source-side structure and evidence. Retain Source References and their resolution results without treating an unresolved reference as a reliable target link. |
| Projection | Organize its own product and connect its generated statements, chunks/hits or graph product to the exact Canonical inputs and Source Evidence it used. |

A Source Reference is something the source actually says or encodes, such as an
attachment path, hyperlink, figure reference or bibliographic citation. Keeping
that reference and establishing its target are separate facts. Preserve unresolved
references and their limitations; Q1–Q3 govern acceptance for required uses.

An external URL remains source content even when its target is not captured.
It does not imply recursive acquisition or an established cross-document knowledge
relationship. Required attachments retain the confirmed Capture Package bindings.

Logical component links do not select a graph database or a universal knowledge
graph. Reusable derived understanding may later be adopted as Canonical Enrichment
under its own input/evidence/acceptance contract; Q4 does not adopt all cross-document
inference. Projection owners retain product-specific knowledge organization.

The trace runs from a Wiki statement or Retrieval hit through its Canonical
component/revision inputs to fixed sources and locations. Canonical owns the
source-side relationships; each projection owns how its output uses those inputs.
See [ADR-0002](../adr/0002-canonical-source-relationships-and-projection-citations.md)
for the responsibility boundary.

### Capability evidence and precision follow-up

Docling can represent parent/child relationships, reading order and provenance;
bounded retained PDF outputs include detected caption links. The inspected
Markdown backend reads explicit link targets. These observations do not establish
general figure-reference, bibliography, diagram-arrow or exact platform artifact
resolution. Docling object references alone do not establish semantic reference
resolution. The Q4 issue record links the inspected evidence; integration and
qualification gaps still need the reconciliation and processing handoff.

Q4 did not decide evidence precision. Q5 below confirms its governing principle;
concrete locator, partial/unmapped and resolver details remain open.

## Q5: source-location precision follows the agreed use

Confirmed on 2026-10-06 in the [Q5 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6016542202).
Source Evidence is the original source observation and location supporting
represented content, enabling inspection of its basis in a fixed source version.
It is distinct from a Source Reference and does not establish source truth.

Allow different source-appropriate location precision. Examples include PDF pages,
regions or table cells; Markdown line ranges or blocks; and PPTX slides or shapes.
These are design examples, not format qualification. Expose the actual fixed-source
location and supported content, including partial correspondence or uncertainty,
under the already confirmed Q1/Q3 requirements.

Sufficiency follows the agreed reuse requirements and applicable acceptance rules.
A page-level location may suffice for one use and fail a use requiring a specific
table cell. Do not imply finer precision than the evidence provides or waive
insufficient necessary evidence as an accepted limitation.

Concrete locator types/fields, partial-mapping representation, evidence-validity
checks and resolver contracts still need case-based design. Q6 below records the
confirmed treatment of output outside the common representation.

## Q6: disposition of parser output outside the common representation

Confirmed on 2026-10-06 in the [Q6 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6018564062).
Map content into existing common structures wherever they suffice. For populated
output not yet covered, assign an explicit disposition by content/field:

| Disposition | Confirmed meaning |
|---|---|
| Incorporate into the representation, extending by format where needed | Understand the meaning and required use; reuse existing structures first, adding a clearly defined format-specific representation only where needed. |
| Retain uninterpreted | Preserve necessary original output or fixed references and disclose that the content is not yet reliably understood. Retention does not establish semantic understanding. |
| Omit under explicit rules | Record the permitted omission, its scope and rationale. Unknown impact cannot silently be treated as permission to omit. |

Different parts of one document may have different dispositions; these are not
three whole-document acceptance states. The complete candidate still must meet
Q1–Q3's agreed reuse, necessary content, evidence and quality conditions. Keeping
raw data cannot compensate for required meaning that remains uninterpreted.

This does not require permanent retention of every parser intermediate. Protect
data necessary for acceptance validation or reuse under existing custody
obligations; physical mechanisms and retention periods remain with their owners.
The illustrative PPTX chart/animation example does not establish parser capability
or adopt a pilot requirement.

Common types, extension schemas, per-field mapping/omission rules and concrete
validation examples still need design and reconciliation.

## Q7: accepted revision contents remain fixed

Confirmed on 2026-10-07 in the [Q7/Q8 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035081526).
Once accepted, a Canonical Revision's content, structure/relationships,
source/evidence mappings and producing-method attribution remain fixed. Corrections
or reprocessing that change these create a new candidate requiring acceptance;
the same revision identity must not silently denote a different result.

For example, correcting OCR from "10" to the source's "100" produces C2 rather than
rewriting C1 already referenced by a Wiki or Retrieval product. This illustrates
version behavior and does not adopt a manual editing feature.

Catalog display metadata, current access and lifecycle eligibility are managed
separately; changing those facts need not rebuild the content revision. Immutability
does not promise indefinite custody or access, or prevent authorized lifecycle
actions. Q9 below governs a later finding that the original acceptance conditions
were not met.

## Q8: replacement follows declared selection rules

Confirmed in the same [Q7/Q8 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035081526).
Acceptance and current selection remain distinct. Replace a default selected
result according to predeclared source applicability, selected method,
compatibility, and current governance/lifecycle conditions. Completion order
alone does not establish precedence.

Where those rules establish eligibility and replacement, selection may update
automatically without per-result human approval. If applicability cannot be
established reliably, expose conflict or not-ready meaning and retain an old
selection only while it still qualifies. A problem with the replacement cannot
restore an ineligible old result.

For example, C1 uses selected method A while C2 uses evaluation method B. Passing
C2's applicable acceptance criteria does not make it replace C1 under rules still
selecting A. Existing exact-revision and source-target selection meanings remain;
this decision does not prescribe a single global current pointer for all consumers.

See [ADR-0003](../adr/0003-immutable-accepted-canonical-revisions.md) for the
immutability/selection boundary. Detailed source/method applicability, ordering,
competing-candidate handling and lifecycle mechanisms remain open; Q9 below
confirms the invalidation/re-evaluation principle.

## Q9: later discovery of failed original acceptance conditions

Confirmed on 2026-10-07 in the [Q9 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035318528).
If an accepted revision is later found not to have met its original acceptance
conditions, preserve the historical rules, evidence and acceptance determination.
Record the current invalidation reason, evidence, affected scope and accountable
decision; stop selecting the affected revision as a qualifying input.

Hand off the impact to Projection and governance owners to stop affected products
from serving as qualifying results, rather than waiting indefinitely for a corrected
revision. A fallback must itself remain eligible. Publication granularity,
enforcement, reconciliation and custody mechanisms remain with their existing owners;
this principle does not imply instantaneous platform-wide shutdown or physical purge.

Corrections to fixed content or evidence mappings produce a new candidate requiring
acceptance under Q7. If the invalidation judgment itself was mistaken and the content
is unchanged, record a new attributable re-evaluation without rewriting history;
a judgment change alone need not create a new content revision.

The illustrative case is an SOP warning required by the original rules but omitted
during processing. Later stricter requirements do not establish that the original
acceptance was wrong. The user expects this case to be rare; this is a judgment,
not a measured frequency. This round establishes the necessary handling principle,
not a dedicated complex workflow or automatic defect-detection system.

## Q10: adopting new Enrichment produces a new Canonical Revision

Confirmed on 2026-10-07 in the [Q10 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035463278).
The user accepts that adopting new Enrichment produces a new Canonical Revision.
Q2's complete-candidate acceptance and Q7's fixed accepted contents still apply.

The user's follow-up asks whether the platform can update Canonical Revisions when
Enrichment methods change without requiring the Source Owner to upload again.
The confirmed source handoff already distinguishes method-only reprocessing from
a new source observation. Automatic triggers, affected scope and rollout behavior
remain under discussion; the question does not authorize automatic full-history
reprocessing. Existing Q8 selection and major-breaking-production-release policies
continue to apply.

## Illustrative checks and evidence limits

The discussion used PDF formula symbols, an SOP Markdown warning in an attachment,
and dependencies conveyed by arrows in a PPTX diagram. If the agreed reuse needs
those meanings, parser success, captured image bytes or a text list alone may be
insufficient. These examples illustrate how requirements determine necessary
content and permitted loss; they do not select the pilot, a model or processing
profile, or require every capability for every document.

The qualified PDF core remains bounded integration evidence. This confirmation
does not establish a passing Canonical Acceptance run or qualified Markdown/PPTX
workers.

## Historical ADR reconciliation before closure

After the canonical design converges, complete the
[ticket's historical ADR reconciliation checkpoint](https://github.com/davidlinnnn/data-ingestion/issues/32#historical-adr-reconciliation-checkpoint)
before final shared-understanding confirmation, resolution, closure and map update.
The agent continuing this ticket owns the work. Present the inventory of confirmed
historical/current decisions and their existing-ADR, backfilled-ADR or
no-separate-ADR dispositions in the final review. This remains outstanding;
confirmed canonical rounds do not complete it automatically.

## Open decisions and handoff

Continue the linked decision ticket for shared and format-specific representation,
criteria and validation; version and lifecycle rules; Source Evidence and
independent Enrichment acceptance/version relationships; attachment-only updates
and old captures with refreshed preconditions. Research dispositions and the
PDF core reconciliation matrix remain
required before closure, with owned integration/migration and validation handoffs.

This checkpoint does not resolve the ticket or update the map's closed-decision
index. Later confirmed rounds extend it without treating illustrative cases as
adopted requirements.
