# Producer boundaries before inline replacement

Read-only audit, 2026-10-15. The frozen comparison has **six new context images**: three complete formula envelopes, one combined comment/code block, one repaired SEAL body context, and SEAL32 with its adjacent display formula as context. Reuse the prior model/schema/settings with a generic context prompt; declare changed pixels and prompt. These inputs test boundary/context repair, not a model-only improvement. Reuse the old separate prose/code-line response without a new call. Keep the old SEAL32 response as a semantic negative control and do not inject an expected-answer runtime guard into the new context comparison.

The source audit (`source-audit.json`) hashes 20 exact saved/provider/runtime sources and records the geometry and native cells below. Its assertions check graph links, stock traversal visibility, native whitespace, unique text-and-bbox matches between provenance and stage clusters, the whitespace-only fragment join, and the historical continuation source hash. No model/API calls, credentials, old payload edits, production changes, or oracle boxes were used to derive these boundaries. Evaluator acceptance remains separate.

## Six input decisions

| Input | Producer-derived scope | Preserve during application |
|---|---|---|
| controls formula child `#/texts/6` | Union its provenance with its immediate `#/pictures/0` parent, then existing 2pt padding and 3x outward rounding | Original picture, child, refs/provenance/image evidence; replace the declared outer picture rendering once |
| controls formula child `#/texts/8` | Same rule with `#/pictures/1` | Same; child extends below parent, so parent alone is insufficient |
| controls formula child `#/texts/10` | Same rule with `#/pictures/2` | Same; child extends right of parent |
| controls `#/texts/12` + `#/texts/13` | One uninterrupted same-parent, same-page code context, corroborated by contiguous native lines and compatible line pitch | Both consumed refs, comment, all native leading whitespace, order; do not emit either native block again |
| SEAL body fragment of `#/texts/34` + continuation `#/texts/45` | Isolate the uniquely matched left-body stage cluster, recover its adjacent native-line continuation; retain the right title fragment as a separately mapped context block if included in the image | Both fragments of text34, text45, right title once, algorithm/list association and all outside items |
| SEAL `#/texts/32` with following `#/texts/33` | Colon-ended prose followed immediately by same-page formula within4pt; formula is context only | Consume only text32; preserve text33 in its original graph/serialization; retain old response as semantic negative control |

The frozen input manifest (`inputs/input-manifest.json`), SHA `9cbaf2d1e31dc8fca9820c75f5c7b14d3a08f4bf8909698e39f3f6466856e22b`, is authoritative for final image layout and every included fragment. Controls item14 stays in its own `groups/0` context and reuses the prior response; its compatible prose/code role still needs application support. If the right title is supplied as context, the model must return it separately and application must associate it separately. Excluding it from body transcription does not authorize dropping it from the document. The SEAL body crop's2pt padding creates a five-pixel vertical source overlap between its body and continuation crops (pixel rows947–952). Only a glyph fringe appears in the first crop; the full continuation appears in the second. No full source word or line is duplicated, but the padded fragments are not pixel-disjoint.

## Formula crop completeness and visibility

The saved controls conversion result (`docs/research/pdf-core-g2-heading-2026-10-15/inputs/controls/runs/controls-p1/conversion-result.json`) retains original picture clusters and native cells. Matrix cells 8–12 contain the text and numbers; the drawn brackets are not represented by text-cell bounds. The three formula children are hidden below pictures in stock document traversal. The complete copied provider document (`docs/research/pdf-core-g2-inline-2026-10-15/inputs/baselines/controls/document.json`) stores each parent image at 72dpi. Decoding those existing images shows both matrix brackets, the fraction bar/denominator, and the complete piecewise brace/branches. They establish why the wider picture envelope matters; rerender the frozen PDF at 3x rather than enlarge the 72dpi cache.

| Child → picture | Parent bounds, top-left PDF points | Child bounds, top-left PDF points | Union +2pt, outward 3x pixel crop |
|---|---|---|---|
| 6 → 0 | `[41.2121,192.4295,205.9699,240.3277]` | `[42,198.9600,182.495,235.0449]` | `[117,571,624,727]` |
| 8 → 1 | `[41.3396,282.1257,166.0417,316.8060]` | `[42,283.2840,147.832,319.6242]` | `[118,840,505,965]` |
| 10 → 2 | `[41.8772,367.1366,221.0569,419.6320]` | `[42,368.9320,221.868,418.9857]` | `[119,1095,672,1265]` |

Use a checked immediate parent with the same physical page, transform every box into the same top-left point space, take the union, pad, clamp to page bounds, and floor left/top and ceil right/bottom at the declared scale. Keep every contributing source ref and exact crop transform. A picture with unrelated children, conflicting pages, missing provenance, or ambiguous ownership requires abstention or a separately declared broader context; a universal “parent picture equals formula” rule is unsupported.

The installed `iterate_items` (`docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling_core/types/doc/document.py`) defaults `traverse_pictures=False`, allowing only caption children through. `BasePipeline._enrich_document` (`docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling/pipeline/base_pipeline.py`) uses that default. Consequently, a corrected hidden formula child alone does not change stock Markdown. The prior reinsertion adapter (`docs/research/pdf-core-g2-inline-api-2026-10-15/reinsertion/apply.py`) correctly rejected invisible child-only substitutions; boundary repair needs an explicit outer-picture rendering replacement, while retaining the native graph and image evidence.

## Code context and native whitespace

Controls items12/13 are adjacent body CodeItems, native cluster22 then9, x=48pt, with native cell indices26–32. The comment and first body line have 14pt baseline pitch, matching the body. Native cells retain the six body lines' leading space counts `[0,4,4,8,0,4]`. The page assembly stage (`docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling/models/stages/page_assemble/page_assemble_model.py`) calls `.strip()` on each cell before sanitizing into paragraph text, explaining why provider text alone cannot restore indentation. Prefer the saved original cells for whitespace fidelity; do not reconstruct indentation from flattened words.

A bounded grouping rule can require consecutive body CodeItem siblings on one page, no intervening node, compatible x origin/line geometry, and contiguous native line evidence. This admits12/13 without a fixture-name or expected-text predicate. Record the consumed ref set and source ranges. Do not extend across the next group: item14 is under `groups/0` label `key_value_area`, from stage cluster20 `key_value_region`. Its two cells33/34 occupy one baseline: a prose cell and a separate code cell. The group is **not already an InlineGroup**, and a CodeItem label alone cannot establish block semantics. Preserve this uncertainty; the installed document API supports `add_inline_group`, but applying such a structural migration requires explicit parent/child/provenance accounting.

## SEAL split, continuation, and model identity

The saved SEAL page4 checkpoint (`docs/research/paper-pdf-functional-2026-10-11/remaining-group5/17-2506.10943v1/group-001/checkpoints/page-0004.json`) retains stage clusters and native cells even though `generate_parsed_pages=false`. Each text34 provenance fragment uniquely matches one original cluster by exact text slice and top-left bbox:

| Provider slice | Stage evidence | Geometry and decision |
|---|---|---|
| text34 `[0,657]` | cluster7, native cells157–187, label `text` | Left body `[107.641,186.7643,321.4521,315.3162]` |
| text34 `[658,734]` | cluster13, native cells67–69, label `text` | Separate right title `[329.4,190.7498,503.9537,210.5992]`; disjoint x, vertical overlap |
| text45 complete | cluster10, native cell188, label `text` | `[108,317.6743,440.6711,326.2262]`; same left edge, contiguous native index, next-line pitch10.910pt |

The single unlocated character `[657,658]` is whitespace. Both clusters are labelled `text`; producer evidence supports isolation, not automatic caption typing. A repaired body candidate can use cluster7 followed by cluster10 after verifying exact source association, uninterrupted native cells, same-left geometry, compatible line pitch and a unique candidate. The following paragraph starts at334.062pt, providing a separate gap. These are bounded rules to validate on this saved case, not a proven general paragraph detector. Ambiguous cases must remain separate. Preserve the right title and its relationship to the following algorithm; no title-string or oracle-box selector is needed.

The historical continuation-v3 source (`docs/research/pdf-core-g2-round2-2026-10-14/order/historical-continuation-v3.py`) SHA `ab5f1bb51b86c1cd8966c645e6e96df839c86460ce265be079451530402935ed` exactly matches the saved SEAL method. Its retained-upstream-inline branch accepts left/right same-page boxes with any vertical overlap. The installed upstream predictor (`docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling_ibm_models/reading_order/reading_order_rb.py`) also uses text labels and permissive ending/starting letters. A tall left paragraph and short right title therefore meet the preserved join condition despite belonging to different flows. This is a boundary-policy failure that enlarged model crops cannot resolve by themselves.

For text32, native checkpoint cells28/29/30 are separate `LM`, theta, and prime cells with distinct measured rectangles. They retain the model-name/subscript identity before model inference. This is source evidence for independent evaluation, **not an answer injected into a prompt or runtime acceptance predicate**. A brace-balanced or schema-valid model response still needs semantic review; preserve the old response unchanged.

## Runtime seam and safe application

The installed `BaseItemAndImageEnrichmentModel.prepare_element` (`docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling/models/base_model.py`) uses only `element.prov[0]` for non-picture crops; it neither unions picture/child geometry nor stitches multiple provenances. Its code/formula stage uses image scale1.67 and expansion factor0.18. It processes the returned element image and writes `item.text`; it does not repair graph ownership. These are different input semantics from the research 3x parent/fragment context method and should not be described as the same pipeline.

The existing [picture OCR helper](https://github.com/davidlinnnn/data-ingestion/blob/archive/pdf-core-v1/src/pdf_processing/ocr.py) has useful source-geometry checks: one picture provenance, supported page rotation/CropBox, render pixel limit, bounds validation, and cached page/picture pixel agreement. It handles a single picture and nearest-rounded PIL crop; the research input preparer (`docs/research/pdf-core-g2-inline-2026-10-15/inputs/prepare.py`) instead uses explicit 2pt padding and outward rounding. Reuse the integrity ideas while declaring the changed union/stitch transform. Do not execute that helper merely to crop, because it also runs OCR.

Application should use explicit repair units rather than relaxing the old one-item/one-root guard globally. Freeze source/document/item hashes; list every consumed ref and charspan, retained fragment, parent/sibling order, and output association. Keep native objects as source evidence. Render each declared replacement once at its visible anchor; account for the consumed outer picture placeholder, both code siblings, and both text34 fragments plus text45. Check all outside nodes/refs/order/provenance and outside serialized spans unchanged. If output roots cannot be mapped unambiguously to those declared units, retain the native rendering and save an unapplied proposal. Structural application remains distinct from source-faithful semantic approval.

No production adapter or historical artifact was changed. General boundary detection, automatic caption semantics, and semantic approval remain unqualified.
