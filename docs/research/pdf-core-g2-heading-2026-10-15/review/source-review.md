# Frozen heading source review

Reviewed 2026-10-15 by the independent heading reviewer. This is a bounded source review and evaluation plan, not a full-document hierarchy oracle or an acceptance verdict.

The unchanged [G1 cases](../../../fixtures/pdf-core-g1-2026-10-14/cases.json) have SHA-256 `8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a`. The registry source bytes and all five relevant frozen page images were rehashed and agree with their recorded hashes. No source oracle was edited.

## Source observations

G1-S02 covers nine selected numbered headings on physical pages 4, 5 and 7 of [WikiSkill](../../../fixtures/agent-self-evolution-pilot-2026-10-11/01-2608.27454v1.pdf). Full-page visual inspection agrees with every frozen title, level and listed parent relationship:

| Physical page | Selected nodes, in source order |
| --- | --- |
| [4](../../evidence/pdf-core-g1-2026-10-14/structure/wikiskill-p04.png) | `3. Methodology` (1); `3.1. Three-Layer Knowledge Architecture` (2, parent 3) |
| [5](../../evidence/pdf-core-g1-2026-10-14/structure/wikiskill-p05.png) | `3.2. Evolutionary Agents and Wiki Orchestration` (2, parent 3); `3.2.1. Skill Provisioning for the Inference Agent` (3, parent 3.2); `3.2.2. Wiki Maintainer: Pattern Consolidation` (3, parent 3.2) |
| [7](../../evidence/pdf-core-g1-2026-10-14/structure/wikiskill-p07.png) | `4. Experiments and Results` (1); `4.1. Experimental Setup` (2, parent 4); `4.2. Main Results` (2, parent 4); `4.2.1. Skill Evolution Across Models and Tasks` (3, parent 4.2) |

The frozen bookmark observation records destination 6 for Experiments; the visible heading is on physical page 7. A candidate must retain page 7 as source evidence. Page 4's Figure 2 caption, body prose and inline bold layer labels, and page 7's inline bold Datasets/Baselines/Models labels are visually distinct from the selected standalone numbered heading sequence. These are useful regression controls, not newly added positive hierarchy expectations.

G1-S03 covers [physical page 19](../../evidence/pdf-core-g1-2026-10-14/structure/wikiskill-p19.png). `A. Method Details` and `B. Dataset Details and Splits` are peers at level 1. `A.1. Algorithm` and `A.2. Distribution of Accepted Skill Updates` are level 2 children of A. The boxed `Algorithm 1 WikiSkill evolution loop` label and its numbered steps are algorithm content, not a numbered document chapter. The algorithm and the paragraph below B must remain represented. This review does not certify complete algorithm transcription.

G1-C07 uses physical page 1 of the [synthetic controls PDF](../../../fixtures/pdf-core-g1-controls-2026-10-14/controls.pdf), SHA-256 `8ddae37b0461b3749402e44b4a40b0e65b3d6b9ad78cf2f03ed20d1950faba90`. Its [frozen full-page image](../../evidence/pdf-core-g1-2026-10-14/controls/controls-1.png), [generator](../../../fixtures/pdf-core-g1-controls-2026-10-14/generate.py) and [truth](../../../fixtures/pdf-core-g1-controls-2026-10-14/truth.json) agree: the title is `Synthetic PDF controls`; two level 1 headings are `Mathematical structures` and `Code and footnote`; four level 2 headings under Mathematical structures are `Inline expression`, `Matrix`, `Fraction`, and `Piecewise expression`. There is no numbering or PDF outline. The title is a separate role from level 1 sections in the frozen expectation; report any candidate title/level convention explicitly rather than silently shifting all levels.

Matrix entries, formulas and the code comment `# keep the boundary and block nesting` must not become headings. The trailing `[1]` marker and footnote `This fixture is synthetic and makes no empirical claim.` must survive separately from code. This source supports a synthetic style-only recovery claim; it does not establish recovery on scanned real documents.

## Saved native baseline

The reusable complete WikiSkill baseline is [native/document.json](../../paper-pdf-functional-2026-10-11/remaining-group5/01-2608.27454v1/native/document.json), with [method.json](../../paper-pdf-functional-2026-10-11/remaining-group5/01-2608.27454v1/native/method.json), [metrics.json](../../paper-pdf-functional-2026-10-11/remaining-group5/01-2608.27454v1/native/metrics.json) and [coverage.json](../../paper-pdf-functional-2026-10-11/remaining-group5/01-2608.27454v1/native/coverage.json). Metrics record the correct source SHA-256 `65afc6e12f6f707483fe1b79a97ab67c03abf4b4992f82fde03eb7b8d9ad4a69`; rehashing the document agrees with the recorded `4f0693659e6bb1dc8d13456f17a9d8c0a4b0604ed682cc4eee7d0bdaf63f4371`. It has 28 pages and 496 text items. The saved method is Docling 2.102.0 / Core 2.96.0 with OCR and enrichment disabled; metrics identify this artifact as restored from 28 checkpoints, so its 0.96-second conversion metric is restoration, not fresh model execution.

All 13 selected WikiSkill nodes already exist as `section_header` text items at the expected physical pages and in the expected relative order. All have `level: 1` and parent `#/body`; four expected level 1 nodes therefore have correct depth, while nine expected deeper nodes do not. This baseline establishes the hierarchy deficit without attributing it to source ambiguity.

| Case | Existing native references |
| --- | --- |
| G1-S02 | `#/texts/87`, `89`, `96`, `98`, `102`, `119`, `120`, `124`, `127` |
| G1-S03 | `#/texts/341`, `342`, `346`, `348` |

The newer [WikiSkill p4 native run](../../pdf-core-g2-images-2026-10-14/layout/runs/wikiskill-p4/document.json) covers only page 4. The saved [controls run](../../pdf-core-g2-images-2026-10-14/layout/runs/controls-p2/document.json) covers only page 2 and is not evidence for C07. No saved native page-1 controls artifact was found in the searched research artifacts. The root agent authorized a fresh CPU baseline for page 1.

## Evaluation contract

Evaluate each lane against its own exact normalized before/after artifacts, with immutable artifact hashes and method provenance. Record original saved document to compatible-Core load normalization separately from compatible-Core before to stage after. Neither loading changes nor a replacement method may be counted as heading-stage success.

For S02 and S03, report per expected node: exact normalized title presence, uniqueness, physical page, level, parent relationship and relative selected-node order. Score content presence separately from hierarchy. The source locators use PDF points with top-left origin, while the native baseline has bottom-left boxes; preserve native provenance exactly through heading recovery and declare any coordinate conversion used for comparison. Do not introduce a new overlap threshold. Check Experiments physical page 7 independently of the bookmark's destination.

For C07, report the title separately and all six section nodes with their expected levels and parents. Do not accept missing style evidence as a positive recovery result. If a method cannot recover a heading, the result is a visible miss rather than a reason to relax the frozen expectation.

Inspect the complete stage delta, not just matched headings. Verify preservation of item identities, text and original text, page numbers, provenance boxes/charspans, nonheading labels/content layers, tables/pictures, reference validity and multiplicity. Compare flattened content traversal order as well as arrays: legitimate hierarchy reparenting may change graph edges while preserving source reading order. Any permitted heading level/role/parent/children changes must be named explicitly; all other differences require explanation. No duplicate or dropped nodes are allowed.

Check false-heading controls directly in before/after output: ordinary body prose, captions, repeated page furniture, inline bold body labels, equations, matrix entries, Algorithm 1 label/steps and synthetic code/comment/footnote. Preserve the algorithm and B paragraph in S03 and code plus footnote in C07; structural recovery does not justify rewriting their content. Already-wrong native ordering or transcription should be recorded as baseline limitations, not silently repaired or attributed to the heading stage.

Limits: this review does not expand the frozen selected scope into a full-document hierarchy oracle, certify algorithm/formula transcription, or establish real scanned style recovery. No inference, package installation or remote write was performed by this reviewer.
