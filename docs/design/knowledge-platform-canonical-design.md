# Canonical representation, acceptance and lifecycle

[Design index](README.md) · [Domain glossary](../../CONTEXT.md)

This checkpoint follows
[Design canonical representation, acceptance and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32).
The ticket remains in progress. Q1–Q3 establish the minimum contract, the initial
complete-candidate acceptance boundary and explicitly permitted limitations;
detailed representation, criteria and lifecycle rules remain open.
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
