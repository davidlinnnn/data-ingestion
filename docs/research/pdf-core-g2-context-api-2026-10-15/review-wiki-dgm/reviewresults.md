# Source review — wiki + DGM

Whole-target result: **9/13 pass including minor differences**:7 strict pass,2 minor,4 material;0 unknown,0 technical. Every output exists and every complete target was reviewed. No context leakage or partial-target omission was found.

| Source | Jobs | Strict pass | Minor | Material | Full-target success |
|---|---:|---:|---:|---:|---:|
| WikiSkill |7|5|1|1|6/7|
| DGM |6|2|1|3|3/6|

The two material content/code errors are ReflACT→RefIACT (Wiki368) and {}→[] plus changed relative context indentation (DGM646). Two additional material typed-role defects occur in DGM648 and650. All13 block native roles are correct; appropriate segment roles fail in those2 targets.

The frozen source contract is unchanged: JSON SHA-256 `effca07ba2779bfd49e0610fead6d121f4feeba783575956dc852465c06b567f`. Output access was authorized after freeze. Candidate strings were never repaired. Schema/JSON success is not treated as source fidelity.

| Job | Status | Full source pass | Coverage |
|---|---|---|---|
|wikiskill/ordinary_paragraph--texts-357|pass|true|complete extent|
|wikiskill/ordinary_paragraph--texts-361|pass|true|complete extent|
|wikiskill/ordinary_paragraph--texts-362|minor|true|complete extent|
|wikiskill/ordinary_paragraph--texts-363|pass|true|complete extent|
|wikiskill/ordinary_paragraph--texts-366|pass|true|complete extent|
|wikiskill/ordinary_paragraph--texts-367|pass|true|complete extent|
|wikiskill/ordinary_paragraph--texts-368|material|false|complete extent|
|dgm/code_item--texts-646|material|false|complete extent|
|dgm/ordinary_paragraph--texts-648|material|false|complete extent|
|dgm/ordinary_paragraph--texts-649|pass|true|complete extent|
|dgm/code_item--texts-650|material|false|complete extent|
|dgm/ordinary_paragraph--texts-651|pass|true|complete extent|
|dgm/code_item--texts-652|minor|true|complete extent|

## wikiskill/ordinary_paragraph--texts-357

**pass**; full target source pass: true.

- Complete source wording from both physical pages20/21 appears exactly once in order inside one paragraph block. The visible fragment gap remains as an internal newline gap.

Output SHA-256 `872bab67d652182c3eb08ea437de33fe3802aa6f7c6813d56ba516c475e0ee0b`.

## wikiskill/ordinary_paragraph--texts-361

**pass**; full target source pass: true.

- Full prose is present. Ordered math has the sample/train sets with comma-k subscripts and subset relation, then iteration k. Limits 8,5,3 and15,000 and distinct trace purposes are intact.

Output SHA-256 `38f6d59ae01e8dc062e595c804cc37d253e7ee2cec12301e795bc945b8ecc118`.

## wikiskill/ordinary_paragraph--texts-362

**minor**; full target source pass: true.

- Complete bold-lead-in wording and opening bootstrap sentence are present. Both D_test and cardinality-of-D_test spans remain inline, with replacement sampling, margins, per-benchmark resampling and equal macro weights intact.
- Candidate writes 1, 000 instead of 1,000: numeric value is unchanged; minor typography under the frozen tolerance.

Output SHA-256 `750cf7f85f5072638055e128d68a7ed1afd1c5d998f0c1161d0ae35f99c2e65d`.

## wikiskill/ordinary_paragraph--texts-363

**pass**; full target source pass: true.

- Complete ordinary paragraph and all six inline math occurrences are faithful. M-star appears three times; strict p<0.05 once and non-strict p≥0.05 twice. All/one-or-more quantifiers, no-sole-winner condition, tie and bolding consequence remain.
- The visible top- newline ranked reflows faithfully; equivalent geq/spacing macros do not change math.

Output SHA-256 `332ea096a4b934a65b7dc60ae368c3627d95cd1a4f79133362afdab322c605d4`.

## wikiskill/ordinary_paragraph--texts-366

**pass**; full target source pass: true.

- Every source sentence and proper name/citation is present. Parallel success/error analysts, recursive hierarchical merge and validation acceptance chain are intact.

Output SHA-256 `01812e3ec14e01e1b000aed53cdfd0bd129a9c7933608a2e23cacf44722d9e68`.

## wikiskill/ordinary_paragraph--texts-367

**pass**; full target source pass: true.

- Every source sentence is present. Only failure traces remains, and SKILL.md is a code segment embedded at the correct prose position. Native fi les extraction artifact is correctly read as files from pixels.

Output SHA-256 `455044b66c9d05faf0e12869e815a62fcad4cf57632b61378936cd8d3f2ce065`.

## wikiskill/ordinary_paragraph--texts-368

**material**; full target source pass: false.

- Both page fragments are included completely and in order, with the rolls/out split joined. All six pipeline stages and remaining prose are present.
- The source proper name ReflACT is transcribed as RefIACT: lowercase l is changed to uppercase I. This is outside the original OpenAI/OpenAl tolerance and is a material proper-name error.

Output SHA-256 `5b3416141a4d649676e0718f9d9c5dd482f879c5493387c5e2f2adcb7487d6ac`.

## dgm/code_item--texts-646

**material**; full target source pass: false.

- All source diff/context lines are present and ordered, including removed lines, defaults/fields, tie-break criterion, logs and final stop condition. The whole block and segment use code role.
- Source test_details=test_stats.get('test_details', {}) becomes test_details=test_stats.get('test_details', []): dictionary default changes to list. This is a material code-literal error.
- Relative source indentation is not preserved: test_success and attempt are visually at the same context L0 in the source, but have4 and8 leading spaces in output. Source best_attempt is L1 relative to attempt L0, but both have8 spaces in output.
- The grey final-condition wrap marker is reproduced and explicitly described in uncertainties. That matches the frozen wrap ambiguity and does not excuse the literal/indentation errors.

Output SHA-256 `f06193c6ed0ec37ff7da210492d53976863b45457674e74acf14f2b42013cf05`.

## dgm/ordinary_paragraph--texts-648

**material**; full target source pass: false.

- Whole paragraph wording, all5 source command/parameter tokens, node associations, Figure3, 23.3% and40.5% are present. The preserved bench- newline mark is a meaning-preserving wrap/hyphenation difference.
- Only4 tokens are typed code segments: edit_type, edit_actions, edit, str_replace. The first source monospace edit after original is inside a text segment. The block native paragraph role is correct, but the full typed inline-code role requirement fails.
- The protected E04 selected token/binding/number content check passes; this does not convert the whole target to a full typed-role pass.

Output SHA-256 `fd8bc169b48fc6f028a9666d667bb44423b452faf6aa177dd7d693eeac936179`.

## dgm/ordinary_paragraph--texts-649

**pass**; full target source pass: true.

- Exact complete label, correct paragraph role, node6 and trailing colon; no adjacent code is included.

Output SHA-256 `ad6f929526fe6a102fbdb28d3abd1c03b173eed66def25756f8cbffd61bcaa60`.

## dgm/code_item--texts-650

**material**; full target source pass: false.

- All words in both instruction paragraphs, file/command/parameter names and uniqueness/no-write conditions are present. The two paragraphs remain separated. Source inconsistency with node labels is preserved.
- Block kind code honors the declared native role, but the only segment is text. The source is a native monospaced code item; the frozen requirement for appropriate typed code segments is unmet. This is a material role/delivery defect despite complete content.
- Grey wrap arrows and line endings are reproduced with lost hanging indentation; this alone is a minor layout issue under the source ambiguity.

Output SHA-256 `1933c1c3492867d60dae2e148a6e3f3986511727d1a301da9745f6d486b2d1c2`.

## dgm/ordinary_paragraph--texts-651

**pass**; full target source pass: true.

- Exact complete label, correct paragraph role, node24 and trailing colon; no adjacent code is included.

Output SHA-256 `5eb689d95facfb40fcbfcc834234b30c72188a72a939363342347287b1417980`.

## dgm/code_item--texts-652

**minor**; full target source pass: true.

- Complete instruction prose is present as one code block with one code segment. Every quoted identifier, action and atomic/surrounding-context/no-overwrite meaning is intact.
- Source hanging indentation of printer continuation arrows is omitted in the text representation. This is a minor layout difference for instruction prose, explicitly covered by the predeclared wrap ambiguity; there is no executable-code indentation change.

Output SHA-256 `fc980ad9f1b5e458396dda0208f38b610d6ace62819578650c6d3c468ea03452`.

## Protected bounded anchors

- E14/Wiki363: existing bounded F13 label preserved; new6/6 math plus full prose passes.
- Wiki362: existing opening-sentence label preserved; new complete opening and whole target pass with minor number spacing.
- E04/DGM648: all selected token strings, bindings and numbers pass with preserved wrap/hyphenation. Full typed source role fails because the first edit is text instead of code; the bounded positive does not become a whole-target pass.
- E13/SEAL30: preserved in the source contract, evaluated by the other shard.

Every job is sourcegradable. Frozen printer-wrap/source-example inconsistencies do not prevent any whole-target decision. No source ambiguity was added or relabeled after seeing failures.

Skipped new inference, holdout access and historical-method regrading. This replay shard supplies no unseen-document generalization or single-component causal claim.
