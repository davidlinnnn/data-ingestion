# Round3 independent review

Reviewed the frozen source images and the saved inputs, raw model text, official postprocess/DocTags output, and execution metadata. This review performed no model inference and changed no source oracle or production code.

## Method and evidence

`vlm/probe.py` uses the pinned Granite-Docling258M revision `982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe`, the installed Docling2.102.0 official Granite presets and Transformers engine, CPU/F32 with4Torch threads,1interop thread and batch1. Formula uses official `<formula>` prompt/postprocess. Whole-page jobs use `Convert this page to docling.` and the official DocTags→DoclingDocument parser. The source hashes and selected physical pages match G1. The Eq2 input PNG is byte-identical to round2.

The engine is called directly: full VlmPipeline lifecycle, detector/region selection, formula crop expansion, source remapping and Canonical Acceptance are outside scope. Whole-page inputs are144dpi source renders; the model processor may internally resize/tile them. The parser uses supplied raster dimensions for its isolated page1 geometry; these coordinates are not source PDF points. SkillOpt retains original physical page8 in `input.json`; the parser output is intentionally not remapped. Constructor timing includes eager model load, fixing the previous near-zero redundant initialize timing pitfall. Sampled process RSS is a local soft guard, not a hard allocation cap or deployment SLO.

`check.py` verifies registry/runner/source/input hashes, CPU/dtype/thread records,3clean exits, generated-token counts/EOS, exact normalized selected paragraphs, ordering and2negative controls. The root review separately checks model weights/snapshot integrity. All3jobs ended in EOS100257 before their512/4096budgets; none was truncated by its output token limit. Offline checks cannot prove general model accuracy.

An additional offline decode of the saved generated IDs with the pinned tokenizer proves all3generations contain complete `</formula>`/`</doctag>` followed by EOS. In the installed official Transformers engine, `text.rstrip(pad_token)` uses a character set rather than an exact suffix; `pad_token` is `<|end_of_text|>`, so it also strips the closing `>` from the preceding tag. This operation exactly reproduces all3saved engine outputs. See `token-decode.json` and saved decode text. The partial closing tag is an engine cleanup defect, distinct from a model generation defect or token truncation; this review leaves the official engine unchanged.

## Formula G1-E07

**Partial improvement, not accepted.** The model restores both mutually exclusive branches: reward1when adaptation improves performance and0otherwise. Round2CodeFormulaV2 dropped the otherwise branch on the identical crop. Granite generated84tokens and EOS, so this is not a512token limit result.

The higher-resolution frozen Eq2 and current input clearly show superscript footnote2after performance. Granite omits that anchor; only equation label `(2)` remains. The separate frozen footnote body explains the alternative reward for the single best sampled self-edit; body extraction and anchor→body delivery were not attempted. The generated condition contains3`$`delimiters and malformed inline LM subscript/text placement even before cleanup. Official engine cleanup then produces partial `</formula`, which the stage postprocessor does not remove because it only matches the complete closing tag. Thus two-branch semantic recovery is distinct from valid LaTeX output and preservation of source qualifications. No repair was applied to improve the score.

## English scan G1-O03

**Selected-scope pass.** Both complete paragraphs, covering all16frozen source lines, match after only allowed whitespace, printed `re-`/`sources` line joining and range-dash normalization. They are adjacent in raw output, Docling text items0/1 and Markdown; OVERVIEW follows, then the right-column in-context-learning item appears later. This fixes the observed stock/v3 right-column insertion for this selected scope. The installed parser preserves both source regions as separate text items.

This is not a full-page pass. A visual spot check outside the frozen region finds source `previous PLMs` in the Emergent Abilities paragraph changed to `previous LLMs` in model output. Other full-page prose, footnote association and unseen pages have no complete frozen review here.

## SkillOpt Table2 G1-T02

**Fail.** The full-page VLM separates6panel-like tables but emits only3total columns per panel (setting plus2data slots), while the source requires setting plus3benchmarks. Benchmark headers are merged, many LiveMath values are omitted, mini-batch settings8/16/32 become5/6/7, and lr8LiveMath66.9is placed into the second numeric slot while source Spreadsheet73.6is omitted. Panel(b)'s title disappears; slow-update data is duplicated after the separate Table3. Table2 caption is plain text with empty caption-reference lists on all6tables, so semantic logical-table/condition association is also not delivered through those references. No claim is made that empty references alone prove all context is irrecoverable.

All8frozen critical comparisons are independently reviewed in `table-critical-review.json`, with0accepted:4lose required values or row conditions, and4retain numeric pairs but lack the required benchmark/header binding. Numeric presence alone is not a pass. The source denominator remains84; a full84point numeric-error numerator/rate was not computed because the critical gate already fails. Table3 values are excluded from Table2 scoring and cannot replace missing Table2 data.

No GPU, remote API, company Qwen3, high-frequency workload or full551pagepilot was tested by this review. These local isolated task results do not qualify a production profile or close G2.

## Follow-up: unchanged full-table crop with official `<otsl>` prompt

**Fail, with different partial recovery.** This separate candidate uses the exact earlier144dpi six-panel cluster PNG, containing all84numeric oracle boxes; the Table2caption is outside. The official model's task prompt changes context and instruction together, so it is not a one-variable causal ablation. The adapter passes bare OTSL into the official `parse_otsl_table_content` and adds one table; it invents no source bbox or page remapping. It is an explicit task-parser seam rather than the whole-page VlmPipeline output contract.

The crop response now includes all printed numeric rows in panel(a), the first5panel(b)rows, panel(d)and panel(e). However, it packs the six-panel layout into a9column grid with incompatible header/title spans. Panel(c)has only its setting labels and loses all metric rows; panel(f)loses all settings and data. Panel(b)'s last32row is also missing. Correct numeric strings under incorrect panel/benchmark spans remain insufficient. `table-crop-critical-review.json` records all8critical comparisons:0accepted,2with missing relevant data and6with numeric pairs whose full header/condition binding is not delivered. The fixed denominator stays84and no full error numerator/rate is asserted.

The crop generated435tokens and EOS before4096. Offline decoding also proves a complete final `</doctag>` before the same official engine `rstrip` damages its closing `>`; this is distinct from omission of table data. The bare OTSL response contains no opening `<otsl>` and one closing `</otsl>`; the saved parser metadata flags that literal asymmetry, and the explicit bare-OTSL adapter documents how it was handled. No numeric or structural correction was made.
