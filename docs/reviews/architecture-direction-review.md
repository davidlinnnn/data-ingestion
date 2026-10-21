# Architecture direction review — candidate package

**Status:** Versioned review brief; all direction-review outcomes pending

**Candidate binding:** Preserved with the Knowledge Platform design checkpoint;
a formal direction-review record has not been assigned a candidate commit.
The separately [confirmed logical baseline](../design/knowledge-platform-logical-design.md)
retains its own decision authority and scope.

**Review scope:** Problem, direction, boundaries, principles, trade-offs, and next design questions

This brief prepares the material for a new commit-bound GitHub Review Record.
It records no approval and does not replace or relabel the [previous review record
for babda22](https://github.com/davidlinnnn/data-ingestion/issues/29).
That record and its earlier evidence remain tied to their original candidate and
review scope.

## Decision requested

Do the problem, Knowledge Platform direction, relationship to future Canonical
Experience, and next design questions provide a coherent basis for further work?

Agreement covers the proposed responsibilities and principles in the
[Baseline](../../ARCHITECTURE-BASELINE.md). It does not approve the detailed
mechanisms in the [historical design notes](../design/README.md), a delivery plan,
or an implementation of the future experience domain.

## Reading package

1. [HLD](../../HLD.md): current problem and evidence gaps, full loop, scope,
   responsibilities, scenarios, and trade-offs.
2. [Baseline](../../ARCHITECTURE-BASELINE.md): proposed principles, open questions,
   and the review criteria in §8.
3. [Glossary](../../CONTEXT.md) and [Knowledge Loop diagram](../diagrams/knowledge-loop.md):
   shared concepts and information flow.
4. [Scope review memo](hld-stage-scope-review.md): rationale for the change from
   the previous contract-heavy candidate; optional background.

## Candidate changes since babda22

- The review seeks direction alignment rather than completeness of all logical contracts.
- The HLD distinguishes the current pipeline diagnosis from operational evidence still needed.
- Future experience includes trace canonicalization into reusable trajectories.
- Improvement returns to four targets: agent behavior, projection methods or products,
  canonical processing methods, and source content.
- Agent business-system actions are distinguished from access to platform knowledge.
- Detailed identity, lifecycle, consistency, publication, taxonomy, and replay choices
  are preserved as non-normative candidates with open validation questions.

## Conceptual walkthroughs

These are walkthrough prompts, not claims that reviewers have executed them.

| Scenario | What the review should establish |
|---|---|
| Consumer method change and onboarding | Source understanding can be reused; method and publication responsibilities are explicit; operational examples support the problem diagnosis |
| Source update, permission revocation, or deletion | Evidence and affected products can be traced; disclosure responsibilities are clear; source detection and consistency questions remain visible |
| SOP execution and improvement | Trace and trajectory are distinct; observed outcomes are not invented; candidate evaluation and owner adoption are separate; a published SOP revision returns through normal ingestion |
| The same failure at four layers | A source error, OCR error, synthesis error, and tool-use error route to the appropriate owner and lifecycle |

## Reviewer outcomes

Use the [Baseline review criteria](../../ARCHITECTURE-BASELINE.md#8-architecture-direction-review).
Each reviewer records identity, perspective, date, outcome, rationale, blocking
objections, and follow-ups. Outcomes are **aligned**, **aligned with follow-ups**,
or **changes needed**.

| Perspective | Outcome | Reviewer, date, and rationale |
|---|---|---|
| Enterprise architecture | Pending | Not recorded |
| Security and data governance | Pending | Not recorded |
| AI consumer architecture | Pending | Not recorded |

No objections have been recorded in this brief; that is not evidence that a
review has found none. The [open design questions](../../ARCHITECTURE-BASELINE.md#7-open-design-questions)
are part of the candidate and remain unresolved.

## Establishing the Review Record

When the package is committed and shared for review, bind the GitHub issue to its
exact commit and link to that commit's HLD, Baseline, glossary, and diagram. Use
the title `Architecture direction review — <commit>` and these criteria. Preserve
the earlier record's scope and attribution; earlier walkthrough outcomes do not
carry over automatically.

Direction is agreed only when all three perspectives align and no blocking
objection remains. Subsequent logical designs record their own choices and
validation against that direction.
