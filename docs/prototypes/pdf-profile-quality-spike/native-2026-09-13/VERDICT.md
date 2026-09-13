# Native v1: promising structure preservation; quality contract remains open

The eight-page native sample supports keeping the pinned Docling OCR-off path as the v1 candidate for born-digital papers and selected book chapters. It preserves the sampled table geometry, selected cell associations, and typed figure/caption/source relationships. **It does not yet establish an accepted completeness or multilingual/PPT support contract.**

Scanned documents, historical documents, faulty-layer repair and automatic OCR selection are deferred under the user's revised scope. They are not retroactively passed, and their prior failures are not treated as current v1 adoption blockers. PPT-export PDF remains pending a source sample. English examples do not imply English-only product scope or prove other languages.

## Predeclared sample

Source SHA-256 hashes and physical/printed page mappings are in [plan.json](plan.json), frozen before inference at `ad2e08ab9cfddb97a6fe1fc6f1b20fe231e482cc236645b60c5795e7928ef6c6`.

| Source | Physical PDF pages | Printed pages | Selected evidence |
|---|---|---|---|
| WikiSkill, 2608.27454v1 | 4, 5, 8 | 4, 5, 8 | Framework diagram/caption, equation1, benchmark table with merged model groups |
| YOLO26, 2509.25164v5 | 3, 5 | 3, 5 | Model-history table, architecture diagram/caption |
| AIMA3rd, Chapter3 “Solving Problems by Searching” | 86, 87, 104 | 67, 68, 85 | Pseudocode Figure3.1, Romania map Figure3.2, body/inline math and depth-first subsection |

All source bytes match supplied hashes and selected pages contain native text. Visual rendering was checked separately: filename/category/native-text presence alone was not taken as proof reliable mapping. The chosen prose is single-column with book margin notes; **multi-column prose is not covered**. Eight pages only were converted, one at a time, plus four manual crops. No whole-book inference or alternate-profile matrix was run.

## Structure and evidence observations

- WikiSkill table is **26×8**, with all five model cells correctly spanning five rows. Three predeclared Avg. values (`38.5`, `47.4`, `68.1`) occur at their expected row/column coordinates.
- YOLO table is **15×4**; all three selected model/framework cell associations pass. These six checks plus geometry/spans are stronger than keyword presence but do not exhaustively validate every table cell.
- All four selected captioned regions have an associated typed item: **three PictureItems and one CodeItem**. Captions resolve to Figure2, Figure3, Figure3.1 and Figure3.2 on the correct source pages. [review.json](review.json) records source-region overlaps and actual boxes. The pseudocode figure is properly represented as code with a caption, not a missing picture. Selection must respect item types rather than assuming every captioned region is a PictureItem.
- Both selected displayed equations are detected as formula items with correct page provenance and bounding boxes, but their `text` is empty. Manual source-region PNGs visibly preserve both equations, with hashes in [formula-regions.json](formula-regions.json). This proves source evidence remains recoverable, **not** that the parser has delivered a usable mathematical representation or that a production final result already includes these manually created crops. No formula interpretation/enrichment was attempted.
- Figure-crop OCR recovers **15/16** exact predeclared labels. `Skill Proposer` becomes `Skil Proposer`; the error remains a failure. These are manually selected 3x page-render controls, not a test of automatic selection or complete diagram transcription.

## Completeness and reading order remain qualified

The run included two full short paragraph checks and ordering probes, not just keyword anchors. Raw results are preserved in [scores.json](scores.json), with explicit probe review in [review.json](review.json).

One paragraph was mis-transcribed during preregistration: magnified source and native text say “elements define a problem and”; the expected paragraph said “elements of a problem”. That oracle is invalid and excluded rather than rewritten to manufacture a pass. It is not a demonstrated faulty text layer.

The other exact paragraph check differs in dash representation, footnote marker inclusion and the epsilon glyph variant. These differences are recorded; this spike does not impose a new normalization policy or substitute semantic equivalence for the declared exact check. They show why the final completeness/representation contract needs review. A successful short-anchor result cannot replace that contract.

Ordering probes generally find their expected sequence, but YOLO's Figure3 anchor also appears as a body cross-reference, so that first-occurrence pass cannot establish the caption's location. Caption association is checked separately. Book margin notes are exported before body content; no complete paragraph-plus-margin-note ordering oracle has been approved. Full-page, cross-page and multi-column completeness remain unqualified.

## Runtime and boundaries

Pinned Linux image `sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`; network disabled; all **17** fixed model hashes match. [environment.json](environment.json) contains exact runtime/packages/options/model identity. OCR is off during parsing; table structure plus page/picture image generation are on at scale1. Manual crop OCR uses the pinned RapidOCR ONNX models at scale3. No model search, silent language conversion or automatic OCR selection occurred.

The runtime is the older pinned prototype Linux image, not proof of equivalence with every later worker build. This is direct parser validation, not checkpoint recovery, full request completion, K8s lifecycle or canonical delivery. The crop coordinates and derived evidence are diagnostics; production artifact registration and interface semantics are outside this spike.

## Reviewable next decisions

1. Retain native OCR-off as a supported **candidate**, with selected component enrichment evaluated independently.
2. Decide acceptable normalization/footnote/margin-note treatment and a reviewed completeness oracle before freezing the quality gate. Do not count the two paragraph probes as validated completeness.
3. Ensure final delivery preserves formula source references/regions even where formula text is empty; this need does not require formula interpretation in v1.
4. Obtain a PPT-export sample and representative language/multi-column cases before making those coverage claims. Neither an absent sample nor deferred scan behavior should be marked passed.

Overall adoption verdict: **inconclusive pending these review/coverage decisions**. The diagnostic is complete; no T06 implementation, issue change/closure, push or production deployment occurred.
