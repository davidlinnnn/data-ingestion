# Read-only reassessment after the accepted handoff clarification

Scope source: `docs/design/pdf-v1-scope-2026-09-13.md` in the root checkout, read after the user accepted formula evidence, typed-content and Traditional Chinese evidence reuse. This memo adds no measurements, normalization rules or adoption pass. Prior failed/excluded probes and verdicts remain unchanged.

## Coverage and ownership

| Area | Established by existing S2 evidence | Remaining decision or check |
|---|---|---|
| English native papers/book chapter | Eight visually selected pages, source hashes, physical/printed mapping, native runtime/model identity; sampled 26×8 and15×4 tables, rowspans and six coordinate-bound values | **Contract review:** completeness, footnotes/margin notes and representation differences. **T06:** actual request-to-result qualification; S2 does not prove whole-page or cross-page completeness. |
| Formula occurrence/source evidence | Both occurrences have result-local typed references, physical pages and BOTTOMLEFT boxes; source PDFs/hash and pinned renderer exist; manual3x crops are readable; local parsed JSON also embeds72dpi page PNGs | **T06 real-result check:** bind exact parsed-result version, typed ID, immutable source revision/digest, coordinates/rotation and readable resolvable evidence with integrity. Validate resolution after worker replacement. A manual crop or72dpi page image alone is not a production-delivery pass. LaTeX is deferred. |
| Pictures and captions | Three selected PictureItems retain caption references and source regions | **T04/T06:** selected required OCR must appear durably in the final result with attribution; candidate crop recognition is not that handoff. |
| Captioned algorithm | AIMA Figure3.1 is CodeItem `#/texts/11`, with caption `#/texts/12`, source bbox and parsed code content | **T06:** preserve actual type/content/caption/source and check code completeness. No coercion to PictureItem or universal CodeItem OCR. |
| Traditional Chinese native plus screenshots | Earlier NCCU pages3–4 and NDHU pages6–7 preserve nine native-prose anchors; separate manual-crop diagnostics support eleven valid anchors | Supplemental language evidence only. **T04/T06:** exported screenshot-only anchors were0/9 despite crop control11/11; prove actual enriched result delivery. Native/crop anchors do not establish full-page TC completeness or paper/book domain equivalence. |
| Required enrichment completion | Existing S2 shows why selected picture work is distinct from parsing | **T04:** current required OCR barrier. **T06/future profile integration:** frozen required-work plan, reject unsupported required methods, durable valid result before complete; old requests retain semantics. No generic plugin implementation or new formula worker now. |
| PPT-export, multi-column prose, untested languages | No representative PPT or multi-column prose sample in this bounded native run | **Missing sample/coverage**, not a passing assumption or a reason to invent thresholds. Obtain samples and perform bounded qualification when available. |
| Government scans, historical pages, faulty-layer repair | Earlier diagnostics remain traceable with original limitations | Deferred scope, not passed or current v1 blocker. No new scan/OCR-selection spike is required by these clarifications. |

References: [native plan](plan.json), [native scores](scores.json), [typed relationships and invalid-probe review](review.json), [manual formula source regions](formula-regions.json), [TC/raw real-source scores](../real-2026-09-13/scores.json), [TC valid-subset/confound summary](../real-2026-09-13/summary.json), [real-source verdict](../real-2026-09-13/VERDICT.md).

## Exact local references are not global component IDs

Static inspection of existing local parsed JSON confirms:

- WikiSkill source revision `2608.27454v1.pdf`, source SHA `65afc6e12f6f707483fe1b79a97ab67c03abf4b4992f82fde03eb7b8d9ad4a69`: formula `#/texts/7` in physical page5, within parsed JSON SHA `56844edaaabd8455457d72b273b6eda6dac0e9fa87e97b764cf3b2076825f1de`.
- AIMA3rd source SHA `0609d012bf123d210c3587d1c1610074f5079217a996299123a2f7872f28a8e9`: formula `#/texts/15` in physical page86/printed67, within parsed JSON SHA `b30acfb79c293d16db5fc4a3b727dca8bc18f7b9d8ef84377daffa61a0346553`.

These references resolve only within those exact diagnostic results. They cannot be reused blindly in a differently assembled full-document result. Local source revision filenames and hashes are recorded, but production source-revision registration and retained-evidence ownership are not exercised here. Formula text is empty; text offsets are not a substitute for readable evidence. Both parser boxes use BOTTOMLEFT coordinates; manual crop plans use TOPLEFT points. Production must bind the conversion/rotation/render recipe instead of passing an unexplained bbox.

## What actually needs another executable S2 experiment?

**No new architecture-feasibility experiment is presently justified for the accepted handoff.** The needed next work is contract review and T04/T06 integration acceptance against real durable results, including fresh-worker evidence resolution and required-enrichment completion/failure semantics. That work is executable, but it should not be relabeled as an open-ended S2 spike.

Existing outputs can be re-assessed after a reviewed completeness oracle is defined; no model rerun is automatically necessary. The mis-transcribed AIMA paragraph, ambiguous caption-order probe, and dash/epsilon/footnote differences remain explicit. We do not erase meaningful minus signs, Greek letters, subscripts or superscripts to create a pass.

New PPT/multi-column/language samples will require bounded qualification runs. A genuinely new S2 feasibility question arises only if those cases or an integration failure reveal an unresolved method choice that existing evidence cannot answer. No model search, formula interpretation or automatic OCR-strategy exploration is proposed now.

Overall: retain the native strategy as a supported candidate. **Do not convert this clarification into overall adoption success or close the quality gate.**
