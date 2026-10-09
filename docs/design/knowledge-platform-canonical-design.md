# Canonical representation, acceptance and lifecycle

[Design index](README.md) · [Domain glossary](../../CONTEXT.md)

This checkpoint follows
[Design canonical representation, acceptance and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32).
The ticket remains in progress. Q1–Q9 establish acceptance, source/projection
responsibilities, evidence precision, parser-output disposition, accepted-revision
immutability, rule-based selection and post-acceptance invalidation principles.
Q10–Q11 establish new Canonical Revisions for adopted Enrichment and automatic
reprocessing after platform method adoption within a declared scope. Q12–Q13
confirm attachment-change reuse and historical acceptance versus source-target
applicability. Revised Q14 confirms conceptual three-format/shared-Corpus consumer
cases here, with executable checks limited to decision-critical Canonical unknowns;
Wiki/Retrieval consumer implementation and effectiveness validation belong to
Projection. Detailed representation, validation, compatibility and lifecycle
mechanisms remain open.
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
methods or deliberate reprocessing; there is no one-to-one restriction. Q10–Q11
establish adoption of updated Enrichment through new complete candidates and scoped
automatic reprocessing; no separately selectable Enrichment contract has been
adopted. A complete candidate does not imply lossless representation: Q1 and Q3
govern necessary content and permitted limitations.

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

Q11 below resolves the follow-up about platform-initiated method updates without
requiring the Source Owner to upload again.

## Q11: automatic reprocessing after scoped platform method adoption

Confirmed on 2026-10-07 in the [Q11 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035858969).
Once the platform adopts a new Enrichment method, automatically reprocess affected
documents within a predeclared applicable scope. Do not require Source Owners to
re-upload or approve each document for a method update. An upstream model release
alone does not trigger replacement of all existing results.

Reprocessing requires retained, usable inputs and appropriate workload authority.
Keep the fixed Source Revision and issue a new processing request for the new
method. Reuse compatible artifacts, redo affected work and validate the complete
candidate for acceptance. Select the accepted new Canonical Revision only when
Q8's source, method, compatibility and current governance/lifecycle selection
conditions pass.
A failed update does not by itself invalidate an otherwise eligible old revision.

For example, S1 with parser P1 and Enrichment E1 yields C1. A new method can produce
E2 from the same S1 while reusing compatible P1, yielding a new accepted C2 without
rewriting C1. A newer result does not turn S1 into a newer source observation.
Wiki and Retrieval retain their own product quality and publication conditions.

Routine compatible updates follow the automatic policy. Major breaking production
migrations retain the [confirmed authorized release decision](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5844072563);
judgment exceptions and current governance remain applicable. This lets the
platform improve knowledge without shifting processing-method changes into repeated
Source Owner uploads, while preserving controlled adoption and selection.

Concrete scope representation, scheduling, batching, resource limits and rollout
mechanisms remain with their existing owners. This design confirmation does not
authorize actual full-history reprocessing or a production operation in this session.
See [ADR-0003](../adr/0003-immutable-accepted-canonical-revisions.md) for the combined
revision and selection boundary.

## Q12: reuse after an attachment-only change needs compatibility evidence

Confirmed on 2026-10-07 in the [Q12/Q13 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6036282074).
The source handoff already distinguishes M1 plus required attachment I1 from M1
plus I2 as separate Source Revisions. Reuse depends on an output's actual fixed
inputs and method compatibility, not merely on unchanged main-document bytes.

Main-only parsing can be reused where compatible. OCR, image interpretation and
downstream derived understanding that depend on a changed attachment must be
reprocessed or revalidated; an output without a sound compatibility basis cannot
be carried forward unchanged. The new complete candidate must still pass
[whole-candidate acceptance](../adr/0001-complete-candidate-canonical-acceptance.md).
Retain the producing-input/method attribution of reused outputs and validate the
new package/artifact/evidence associations. Relabeling an old result as supported
by a new attachment does not establish that support.

The initial implementation may use coarse safe recomputation, such as reusing
main-only parsing while redoing all Enrichment that read the changed attachment.
This does not require a fine-grained dependency graph, complex cache or a selected
recomputation algorithm.

| Reviewed design case | Expected result |
|---|---|
| The unchanged SOP says "follow the limit in the attachment"; I1 says 10, I2 says 100 | Main-only parsing may be reusable; the I1-derived "limit 10" cannot be silently carried into the new candidate. Recompute or validate affected understanding and its evidence. |
| Only the image/reference changes while the old derived limit remains | Fail the necessary-content/evidence checks for the complete candidate; changing the reference alone cannot justify acceptance. |

This records the basis for omitting recomputation while preserving whole-candidate
consistency. These are confirmed design cases, not executed processing tests.

## Q13: historical acceptance and requested-source applicability remain separate

Confirmed in the same [Q12/Q13 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6036282074).
An authorized, complete S1 input may produce a new accepted Canonical Revision if
it meets its applicable acceptance criteria. Acceptance and fulfillment of the
current requested source target are separately attributable facts.

In the reviewed source-handoff case, A captured S1; B captured reliably newer S2
and advanced platform state to P2. A then reads P2 and submits S1 with expected=P2.
Passing the platform-state precondition does not establish that S1 contains S2's
content. A new method or later completion similarly cannot promote S1 into a newer
source observation.

| Requested use / knowledge of source order | Expected result |
|---|---|
| Explicit S2 target | S1's accepted result does not fulfill the target; expose the unmet target rather than silently substituting S1. |
| Latest eligible accepted-result selection | An otherwise eligible S1 result may be selected under existing rules, with the S2 readiness/freshness gap exposed. |
| Historical or exact-version use | Preserve fixed lineage and apply current authorization/lifecycle rules; acceptance does not grant perpetual access. |
| No reliable source-order/applicability basis | Preserve the applicability conflict. Completion time, retries and refreshed preconditions do not establish precedence; do not assume which observation is newer. |

This extends the [acceptance/selection boundary](../adr/0003-immutable-accepted-canonical-revisions.md)
to the required old-capture/refreshed-precondition validation scenario. It does not
select a concurrency mechanism, require live-latest fetching during execution, or
require a person to approve every historical reprocessing request.

The attachment-only and refreshed-precondition design-case review is complete.
Concrete identifiers, compatibility rules and runnable validation remain part of
the outstanding contract and implementation handoff.

## Q14: shared Corpus cases and bounded canonical validation

Confirmed on 2026-10-07 in the [Q14 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6038695041).
The user clarified that Wiki builds an organized, interlinked knowledge base from
a Corpus. Single-document summaries and procedure explanations alone are insufficient
consumer cases. Retain the three-format fidelity cases as inputs to a shared
multi-document knowledge-organization case.

| Confirmed design case | Required meaning for reuse | Unacceptable loss for this use |
|---|---|---|
| PDF comparison table with notes | Values, units, headers/row-column correspondence and the target of qualifying notes | Misaligned values, lost units or omitted/misattached notes that erase a qualification |
| SOP Markdown with conditions and required attachment warnings | Step order, negation/condition scope and exact attachment relationships | Reordered steps, lost prohibitions or omitted necessary attachment warnings |
| PPTX branching flow diagram | Nodes, arrow direction, branch labels and necessary legend meaning | Text-only lists that lose branches, reversed direction or uncertain interpretation presented as certain |

All three need exact source versions and sufficient Source Evidence under Q5.
These are agreed design acceptance uses, not requirements that every document
contain each structure or proof of existing worker capability.

Use "document processing and recovery" as an illustrative shared Corpus: PDF
methods/comparisons/limits, SOP operation/retry conditions, and PPTX component/data
flows/failure branches. A Wiki topic may combine several sources; one source may
support several linked pages. This illustrative topic does not select the
first-adoption corpus.

| Shared consumer case | Canonical input obligation / projection check |
|---|---|
| Cross-document organization and synthesis | Preserve reusable content, context and each source's conditions so the projection can form topic/entity/concept pages. |
| Interlinked knowledge | Preserve source-side relationships and attributable inputs; distinguish source-explicit relationships from projection-derived page/concept links. |
| Differences and contradictions | Keep distinct source statements, scope and supporting evidence available; the projection must not erase differences or merge solely by matching names. |
| Incremental maintenance and traceability | Expose relevant revision/applicability/lifecycle facts and exact usable inputs; the projection can reevaluate affected products and retain the input lineage of each published version. |

Retrieval reuses the same canonical input set as a second consumer check; Wiki
specific organization must not be required to interpret the shared inputs.
Canonical Acceptance remains per complete document candidate. Corpus-wide synthesis,
page organization and interlinking do not become a prerequisite for accepting each
document or a requirement for a universal canonical knowledge graph.

### Validation and implementation ownership

The [Q14 scope revision](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6038854471) was confirmed
on 2026-10-07. Validate Wiki and Retrieval uses through conceptual walkthroughs of
the shared cases. This ticket does not implement either consumer, including a
reduced llm-wiki or RAG prototype.

Use the smallest necessary executable check only for a decision-critical Canonical
contract unknown that existing evidence cannot resolve, such as source-reference
resolution or preservation of necessary mapped fields. Reuse sufficient existing
evidence; an executable probe is not required for every conceptual consumer case.
The mapping-validation plan, PDF reconciliation and necessary evidence/gap handoffs
remain required.

Keep conceptual, synthetic and actual parser/consumer execution evidence distinct.
Conceptual walkthroughs do not prove generation quality, knowledge-link correctness,
retrieval effectiveness or incremental-publication behavior. Record the scope and
result of any contract probe; neither a synthetic fixture nor a passing contract
check qualifies an entire parser or consumer.

[Define canonical consumption and publication for Wiki and Retrieval](https://github.com/davidlinnnn/data-ingestion/issues/55)
owns llm-wiki/Retrieval implementation and effectiveness validation, including
composition/interlinking, retrieval, updates, product quality and publication.
Consumer implementation is not a prerequisite for this canonical decision. Use
this shared case set for both owners without reversing the existing dependency. Concrete processing capability
gaps retain their processing owner and affected validation.

The [inspected llm_wiki README at 48fd970e](https://github.com/nashsu/llm_wiki/blob/48fd970e206a02a6d2028d1dbfc41b7a0345bf0b/README.md#3-two-step-chain-of-thought-ingest)
is a use-pattern reference for concept/entity pages, links and incremental knowledge
maintenance. This reading did not inspect ingest code or execute the product;
documented features are not proof of claim-level or fixed-version evidence quality.
Direct adoption of that implementation is not decided here.

Current PDF evidence is bounded and does not establish all unit/note associations;
Markdown/PPTX lack corresponding qualified workers. The shared case requirements
feed the required reconciliation and owner-scoped integration work. Detailed
fixtures, canonical representation and the mapping-validation plan still need
design; execute a bounded contract check only where the revised scope requires it.
Q14 confirms the cases and validation boundary, not completed validation.

## Q15: references identify locations within an exact revision

Confirmed on 2026-10-07 in the [Q15 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6039615616).
References identify an exact Canonical Revision and a location/component within
that revision. A simple index or node reference may suffice; this decision does
not select an ID format or require a separate component identity system.

Initially, there is no guarantee of automatically matching the same component
across revisions. C1's `table-3` and C2's `table-3` do not establish identity by
sharing a label. Insertions, splits, merges or reparsing must not redirect an old
reference to new content. Q12 still permits artifact reuse with explicit
compatibility evidence; reuse does not imply general cross-revision matching.
Projection may initially reevaluate by document revision without a fine-grained
incremental-update contract here.

Historical references retain their original meaning, subject to current governance
and retention. If their fixed dependencies are unavailable, report that limitation
rather than substituting the current revision's content or evidence.

## Q16: minimum structure for the agreed consumer uses

Confirmed on 2026-10-07 in the [Q16 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6039900827).
Preserve necessary structure; source-grounded textual Enrichment may carry the
necessary meaning of a visual diagram when it meets the applicable acceptance
criteria. Initially, not every flow diagram must become a structured flow model,
and programmatic flow-graph operations are not guaranteed.

| Case | Confirmed minimum representation |
|---|---|
| PDF table | Cells, rows/columns and spans, with necessary header, unit and note associations; flattened text must not erase their correspondence. |
| SOP Markdown | Heading/step order and nesting, attachment relationships, and complete condition/prohibition text attached to its relevant step/context; no executable procedure rules are required initially. |
| PPTX flow diagram | Preserve reliably obtained nodes, directed connections and branch labels under Q6. For image-only meaning, attributable textual Enrichment may preserve the necessary sequence, conditions, branches and actions, with sufficient Source Evidence and validation. |

For the illustrative flow, "after processing, check quality; publish only on pass;
on failure, stop and notify the responsible person" preserves the required branches.
"This diagram shows quality checking and publication" does not. Neither example
is measured parser or Enrichment output.

Generated interpretation remains distinct from source-authored text/native structure.
Its source and producing method must be traceable. Already available necessary
structure is not discarded merely because a textual description also exists;
Q6 still governs its disposition. A generated description alone is not validation.
Uncertain required direction or branch meaning cannot pass the relevant acceptance
criterion merely by attaching a description or warning.

The trade-off is a sufficient shared representation for reading, citation and
knowledge organization without requiring a general executable workflow model.
A concrete future need for execution or programmatic graph analysis would require
a separate assessment. This does not assume every document needs human review.
This ticket owns acceptance meaning; the processing owner selects methods/profiles,
integration and affected validation. Existing PDF/Markdown/PPTX capability is not
established by this decision.

## Q17: changed-content evidence is an acceptance check

Confirmed on 2026-10-08 in the [Q17 clarification](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6061378937).
Treat support for changed text/interpretation as a case of the existing acceptance
rules, without introducing a separate old-locator reuse or migration mechanism.
A changed accepted result becomes a complete new candidate requiring acceptance;
the prior accepted Canonical Revision remains fixed.

An initial implementation may rerun the whole document's parsing, OCR and required
Enrichment, then build and validate the new candidate and its source mappings.
Q12-compatible artifact reuse remains optional, not an implementation prerequisite.
This does not mandate a full rerun for every change or require fine-grained update
or cache infrastructure; the processing owner retains execution/reuse strategy.

| Reviewed design case | Consequence under existing rules |
|---|---|
| Unchanged SOP main file with required attachment I1 replaced by I2 | The complete new Capture Package may be fully reprocessed into C2, with new source mappings and whole-candidate acceptance. C1 retains its original bindings. |
| Fixed source image says `100`; a new OCR method corrects the earlier `10` result | A new candidate may point to the same exact source and region after validating that it supports `100`. No cross-revision component matching or special locator migration is required. |
| An old source location remains accessible but does not support the new content | Accessibility alone is insufficient evidence. Missing necessary support prevents acceptance under Q1/Q3/Q5, even after a full rerun. |

These are reviewed design cases, not executed validation. Reuse
[ADR-0001](../adr/0001-complete-candidate-canonical-acceptance.md) and
[ADR-0003](../adr/0003-immutable-accepted-canonical-revisions.md); this clarification
does not warrant a separate ADR or new domain term.

## Q18: withdrawal before acceptance stops that acceptance

Confirmed on 2026-10-08 in the [Q18 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6061678555).
When a valid withdrawal is confirmed before Canonical Acceptance and its scope
covers the candidate's Canonical result, stop that acceptance. A late successful
processing/Enrichment result, even with passing content/quality checks, does not
create a new "accepted but withdrawn" result. Withdrawal of only one Published View
does not automatically expand to the Canonical candidate.

Record actual processing completion and validation outcomes separately where
permitted; they do not constitute Canonical Acceptance. Keep their records only
under applicable retention/erasure policy. If corresponding authorization is later
restored, explicitly reevaluate under the then-applicable acceptance and governance
rules. Restoration alone does not turn an earlier late success into acceptance.
Still-authorized, compatible candidates/artifacts may be reused; neither re-upload
nor a full rerun is mandatory.

This supplements the source-handoff rule that late success cannot undo withdrawal.
It does not rewrite acceptance facts established before withdrawal or treat
withdrawal as proof that original acceptance was wrong. Execution cancellation,
enforcement propagation/completion evidence, physical retention/purge and numeric
targets remain with the existing owners. No new status enumeration or cancellation
mechanism is selected, and this clarification does not add a separate ADR.

## Q19: multiple exchange-format proposal withdrawn

The user explicitly withdrew the proposal on 2026-10-08; see the
[Q19 withdrawal record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6062064816). Serving one
Canonical Revision in multiple exchange formats was proposed, not adopted.

First define one explicit Canonical schema with identifiable schema version;
field names remain fixed within that version. Source-content, parsing and Enrichment
updates follow the existing Canonical Revision/acceptance rules without automatically
changing the schema. Provider output changes belong in the mapping integration
rather than automatically changing the Canonical contract.

Decide future schema compatibility and migration from an actual proposed change.
Do not prebuild multiple read formats or a generic conversion framework for this
ticket. The required PDF reconciliation, provider-to-canonical mapping and owned
integration/migration gaps remain in scope. No separate ADR or new domain term is
introduced; concrete first-version fields and the three-format examples remain open.

## Q20: repeated attachment occurrences retain their own context

Confirmed on 2026-10-09 in the [Q20 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6074671955).
Each occurrence of a repeated attachment retains its own revision-scoped reference,
source location, original reference text and enclosing step/context. Multiple
occurrences may resolve to the same fixed artifact in the Capture Package.

In the SOP example, the quality warning at step 1 and publication warning at step 3
are separately addressable occurrences A/B, both targeting I1. I1 supports what
the image says; occurrence B additionally identifies its use at the publication
step. This does not require duplicated image bytes, cross-document attachment
identity/deduplication, cross-version matching, a new attachment service or a
particular OCR execution/reuse strategy. The complete candidate remains the unit
of acceptance.

Only this representation choice is confirmed. The remaining proposed contract
fields and examples still require review. Update the existing Source Reference
term without a separate ADR.

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

## Current contract review draft

The [contract and three-format review draft](knowledge-platform-canonical-contract-draft.md)
consolidates confirmed meanings into proposed fields and illustrative cases.
It is not an adopted schema or executable validation. Q20 confirms only the
repeated-attachment occurrence representation; the other draft shapes remain open. The preliminary PDF evidence
cross-check does not complete the required reconciliation or closure gates.

## Open decisions and handoff

Continue the linked decision ticket for shared and format-specific representation,
criteria and validation; detailed version and lifecycle rules; Source Evidence and
concrete artifact reuse/compatibility contracts. Q12–Q13 complete the required
attachment-only and old-capture/refreshed-precondition design-case review; executable
validation remains outstanding. Research dispositions and the PDF core
reconciliation matrix remain required before closure, with owned integration/migration
and validation handoffs.

This checkpoint does not resolve the ticket or update the map's closed-decision
index. Later confirmed rounds extend it without treating illustrative cases as
adopted requirements.
