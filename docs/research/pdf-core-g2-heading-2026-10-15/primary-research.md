# Exact Docling heading stage — 2026-10-15

The tested candidate is the official **docling-slim 2.132.0** wheel with **docling-core 2.99.0** and **docling-parse 7.22.3**, isolated at `<tmp>/pdf-core-g2-heading-20261015/venv/bin/python`. The `docling` meta-package is not installed. Five relevant installed files are byte-identical to their v2.132.0 tagged sources; package requirements pass `pip check`. Exact versions, source hashes and final artifact hashes are in runtime evidence (`runtime/runtime-evidence.json`), with the dependency lock (`runtime/requirements-lock.txt`).

## What the official stage does

`HeadingHierarchyModel.assign_heading_levels(document, parsed_pages=None, outline=None)` mutates a complete `DoclingDocument` and returns it. Per heading, the precedence is bookmark, numbering, then style. Numbering and style each compress the distinct signals present into contiguous levels, clamped by `max_level`. Style reads overlapping text-line glyph heights and PDF font names; it runs on ordinary CPU rules and does not load a model. Bookmark matches can promote a `ListItem` via `document.replace_item`; otherwise the assignments only change `SectionHeaderItem.level`. There is no heading-driven reparenting pass. [Exact stage source](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/heading_hierarchy/heading_hierarchy_model.py).

The pipeline option defaults to **disabled**. Other defaults are bookmarks/numbering/style/font-style enabled, size tolerance `0.05`, maximum level `6`, and bookmark match threshold `0.8`. Style requires retained parsed pages (`generate_parsed_pages=True`); otherwise it silently has no cells to use. [Exact options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py#L1923).

The pipeline wrapper checks `enabled`; direct `assign_heading_levels` always applies its configured signals. This replay explicitly supplies `enabled=True`.

## Complete replay inputs

- `document`: the entire assembled `DoclingDocument`, not a heading-only reconstruction.
- `parsed_pages`: `dict[int, SegmentedPdfPage]`, keyed by **1-based physical page**. The style pass reads `dimension.height` and `textline_cells` with rectangles, text and `PdfTextCell.font_name`. Retain all pages containing headings because style ranks headings across the document.
- `outline`: a flat ordered list of `_PdfOutlineItem` Pydantic models, with `title`, raw **0-based** depth `level`, optional **1-based** `page_no`, and optional top-left `y_top`. [Exact outline model and native extraction](https://github.com/docling-project/docling/blob/v2.132.0/docling/utils/pdf_outline.py).

The pipeline runs the stage immediately after reading order. It discards parsed pages unless requested, and the heading wrapper clears `_pdf_outline` after consumption. `_pdf_outline` is a private attribute excluded from `ConversionResult` serialization, so ordinary result JSON alone cannot recover bookmarks. A complete checkpoint must explicitly save full parsed pages and outline before this cleanup, alongside the full document. [Pipeline assembly and cleanup](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py), [private result attribute](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/document.py#L591).

The old saved documents lack parsed styles. This experiment therefore combines the intact old assembled document with fresh official native backend extraction from the unchanged PDF. It is **assembly replay**, not a complete 2.132 pipeline run or a recovery qualification. The isolated dependency choice is deliberate: slim 2.132 permits Core ≥2.98, but its supported native parse versions require Core ≥2.99; forcing 2.98 caused a resolver rejection. [Tagged package requirements](https://github.com/docling-project/docling/blob/v2.132.0/pyproject.toml), [official parse 7.22.3 metadata](https://pypi.org/pypi/docling-parse/7.22.3/json).

## Final bounded executions

| Fixed scope | End-to-end worker pair | Maximum sampled process-tree RSS | Official stage changes |
| --- | ---: | ---: | --- |
| WikiSkill, all 28 physical pages | 1.886 s | 414.34 MiB | 39 level-only edits, 52 headings |
| Controls, physical page 1 | 0.815 s | 128.09 MiB | 6 level-only edits, 7 headings |

The native backend used one parser thread, no rendering or bitmap bytes; ML packages are absent. These times include native extraction, serialization, fresh stage evaluation and a separate process reloading the persisted stage inputs. Controls' earlier baseline conversion is measured separately in `inputs/controls/`. Both executions held the existing qualification lock, checked ≥8 GiB available memory, and used a 180-second/6-GiB sampled stop with 50-ms polling. Lock waits are excluded. This is a sampled soft bound, not an OS hard memory limit. Exact final WikiSkill record (`runtime/wikiskill-final/bounded-execution.json`), controls record (`runtime/controls-p1-final/bounded-execution.json`).

All final outputs preserve text, original text, physical provenance and actual parent fields; complete JSON diffs contain only levels and both document trees validate. Loading the old export into the compatible Core changes reference aliases and explicit null serialization only; the separate normalization comparison confirms equality after alias/null normalization. Fresh and reloaded stage outputs are identical in JSON and Markdown, including exact PDF-font-cell subclass counts. WikiSkill's separate no-outline ablation makes 44 level-only changes. Final evidence is immutable under WikiSkill (`runtime/wikiskill-final/input-manifest.json`) and controls (`runtime/controls-p1-final/input-manifest.json`); the heading trees explicitly declare a display convention and do not pretend Docling reparented items.

Skipped a new full conversion, ML inference and custom heading corrections. This stage evidence establishes execution and serialization behavior; correctness against the source belongs to the separate oracle review.
