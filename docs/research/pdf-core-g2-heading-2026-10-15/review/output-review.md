# Independent heading output review

The packaged heading stage recovers the frozen selected WikiSkill levels with the native outline: 9/9 G1-S02 and 4/4 G1-S03 depths and implied section parents are correct. It does not recover the C07 absolute hierarchy: all six section depths are one level too deep because the document title remains a `section_header`. This is useful bounded evidence for numbered/outline-assisted depth recovery, not a complete hierarchy qualification.

The [independent checker](check.py) reads saved artifacts and frozen expectations; it runs no inference and does not feed oracle data to the candidate. [Machine-readable results](output-review.json) include every expected-node observation, every stage delta, all selected-page nonheading controls, hashes, graph checks and mutation self-checks. Source evidence and bounds are in [source-review.md](source-review.md). Only the final immutable [WikiSkill](../runtime/wikiskill-final/input-manifest.json) and [controls](../runtime/controls-p1-final/input-manifest.json) artifact paths were evaluated. Their JSON and Markdown also equal the retained earlier successful assert-run artifacts.

## Selected expected headings

All expected heading strings, physical pages and selected relative order are correct before and after the stage. The improvement is in depth and the section parents inferred from reading order and lower heading levels.

| Lane | Expected nodes | Correct depths before | Correct depths after | Correct inferred parents after |
| --- | ---: | ---: | ---: | ---: |
| WikiSkill G1-S02, native outline | 9 | 2 | 9 | 9 |
| WikiSkill G1-S03, native outline | 4 | 2 | 4 | 4 |
| WikiSkill G1-S02, no-outline ablation | 9 | 2 | 9 | 9 |
| WikiSkill G1-S03, no-outline ablation | 4 | 2 | 0 | 0 |
| Synthetic G1-C07, six sections | 6 | 2 | 0 | 4 |

The native-outline WikiSkill [output](../runtime/wikiskill-final/document-fresh.json) has `3.2.1` and `3.2.2` under `3.2`, and `4.2.1` under `4.2` by inferred heading hierarchy. A.1 and A.2 are under A, while A and B are peers. The corresponding [Markdown](../runtime/wikiskill-final/document-fresh.md) exposes those heading levels.

The actual Docling graph stays flat for the selected headings: every selected node's `parent` remains `#/body`, with unchanged `children`. Only the four top-level selected nodes have the expected section parent in the actual graph (4/13). The other nine relationships are recoverable from level plus reading order; they are not stored heading-to-heading graph edges. An implementation requiring explicit semantic section edges still needs materialization from those fields.

Removing the outline is an ablation, not a new oracle. The [no-outline output](../runtime/wikiskill-final/document-no-outline.json) preserves the nine S02 depths, but A, A.1, A.2 and B all become level 4, each inferred below the earlier level-2 `References` heading (`#/texts/286`, physical page 15). Thus the selected appendix result depends on the native outline in this full-document replay. It cannot support a claim that numbering/style alone solved the appendix.

The controls [output](../runtime/controls-p1-final/document-fresh.json) retains seven `section_header` items with levels `1, 2, 3, 3, 3, 3, 2`. The title `Synthetic PDF controls` stays at level 1; Mathematical structures and Code and footnote become level 2; their four mathematical subsections become level 3. All six section depths therefore miss the frozen absolute levels, without any offset normalization. The four mathematical child relationships are implied correctly; the two top sections are instead implied below the misclassified title. Distinct title identification was already absent before the stage and remains absent after it.

## Bookmark location negative control

The wrong Experiments destination is genuine, not a zero-based/one-based confusion. An independent [raw PDFium check](bookmark-raw-check.json) reads its destination as zero-based index 5, hence physical page 6. The saved native [outline](../runtime/wikiskill-final/outline.json) also reports `page_no: 6`; the frozen visible heading is on physical page 7. Controls Methodology and Experimental Setup resolve to physical pages 4 and 7 respectively using the same conversion.

The candidate retains the Experiments heading provenance on physical page 7. The [packaged bookmark matcher](../runtime/source/heading_hierarchy_model-v2.132.0.py) requires a known bookmark page to match a known candidate page, so this destination cannot relocate the heading or directly match that page-7 node. Its correct final level is also present in the no-outline ablation. This demonstrates safe preservation for this wrong-destination example, not correctness for every bookmark defect.

## Complete mutation and preservation audit

The entire WikiSkill outline-assisted stage delta is 39 existing `section_header.level` changes; its no-outline delta is 44. The controls delta is six such changes. Independent deep comparisons agree exactly with each saved producer diff. No text, `orig`, label, provenance box/charspan/page, content layer, identity, table, picture, body/furniture/group edge, array order or other field changes occur in any lane. The complete before/after trees have no unresolved child, inconsistent parent, cycle, duplicate traversal or unreachable-item errors, and their traversal orders are identical. All stage output graphs and item counts are preserved.

Core loading is a separate change boundary. Original-to-runtime normalization has 3,678 raw field changes for WikiSkill and 147 for controls. Every difference is explained by reference serialization `$ref` to `cref` or added null defaults; recursively normalizing only those conventions leaves zero residual differences. Those changes are not credited to the heading stage. Source PDF, original document, every persisted parsed-page input and outline hashes match the manifests. Final runner/guard hashes also match the bounded execution records.

All 75 distinct nonheading text items on WikiSkill's selected pages and all 10 controls nonheading text items retain their roles and exact content. The selected WikiSkill pages have no extra heading roles before or after. Controls has one existing extra section-header role, its document title, before and after; the stage introduces zero new heading classifications. The algorithm label/body and following B content remain intact. Matrix/formula content stays formula content, the code comment stays code, and the footnote plus `[1]` marker stay separate from code. These checks establish preservation of the baseline representation. The controls baseline already flattened code indentation, and mathematical transcription was not certified here.

Fresh and persisted-input reload outputs are exactly equal as JSON and Markdown in both lanes. The checker deliberately corrupts a depth, an actual parent, a provenance page and tree order; each corruption is detected. This makes the preservation and oracle checks falsifiable without adding a candidate heading algorithm.

## Execution scope and verdict

These runs replay the exact packaged assembly heading stage over old assembled documents plus fresh native backend parsed pages and outline. They are not a new end-to-end Docling conversion or full-pipeline restart/recovery qualification. The recorded packages are Docling Slim 2.132.0, Core 2.99.0 and Parse 7.22.3; no model modules were loaded by the stage runner.

The bounded [WikiSkill execution](../runtime/wikiskill-final/bounded-execution.json), including capture, no-outline replay and reload, completed in 1.8861 seconds with peak sampled process-tree RSS 434,470,912 bytes. The bounded [controls execution](../runtime/controls-p1-final/bounded-execution.json), including capture and reload, completed in 0.8154 seconds with 134,316,032 bytes. These measurements are for the replay scope and sampling method, not fresh native conversion/model inference or full ingest.

Verdict: selected WikiSkill depth and inferred-parent recovery succeeds with the native outline while preserving content and evidence. C07 absolute style-only hierarchy and title role fail, actual heading-to-heading graph edges are not created, and appendix depth fails in the no-outline ablation. These limits preclude a broad claim that heading/hierarchy requirements are fully qualified.

Skipped: full-document semantic heading review, real scanned style recovery, and formula/algorithm/code fidelity certification. No oracle edits, package installs, model inference or remote writes were performed by this reviewer.
