# OCR region dilation: official-source research

Research date: 2026-10-20 (Asia/Taipei). This is source research, not a new inference experiment. Historical sealed experiments were not modified.

## Finding

The available evidence supports investigating **OCR region selection** before replacing Heron. The layout model supplies boxes, but the shared OCR base class transforms those boxes before the OCR detector sees pixels. Different layout predictions can change the transformed crops indirectly; changing the model does not bypass this transformation. This is a source-based inference, not proof that every other layout model will fail.

In pinned v2.132.0, `LAYOUT_REGIONS` collects all layout boxes and calls `_deduplicate_rects` with the base class's fixed `DEFAULT_DILATION_SIZE = 20`. The PDF-aware branch calls the same function after selecting boxes. That function rasterizes boxes in page coordinates, dilates, and returns each connected component's enclosing rectangle. `FULL_PAGE` bypasses this selection. These are **crop-selection semantics**, separate from OCR detector morphology or reading order. [Pinned source, lines 196–368](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/base_ocr_model.py#L196-L368).

The prior statement “no public switch” should not be expanded into “there is no solution.” It means the examined public configuration does not expose this fixed kernel as an `OcrOptions` field. A maintained extension or upstream change is technically possible; it needs coverage and regression checks.

## English searches and provenance

Web and upstream GitHub issue/PR searches included `Docling OCR dilation columns`, `LAYOUT_REGIONS merge`, `DEFAULT_DILATION_SIZE`, `OCR regions`, `layout-first`, `multi-column OCR`, and `dilation`. GitHub issue/PR bodies and non-bot comments were inspected. Search results containing Dosu answers were **not** treated as human maintainer guidance.

### 1. The maintainers explicitly considered removing dilation

During [PR #3746](https://github.com/docling-project/docling/pull/3746), member `cau-git` said the dilation computation might become obsolete as layout-guided OCR was being tested in #3710. This is direct human maintainer evidence that the design is not immutable. However, it is a statement of work in progress, not a released option or guarantee. #3746 itself optimized the implementation with OpenCV, retaining a SciPy fallback; it did not provide column preservation. [Maintainer comment](https://github.com/docling-project/docling/pull/3746#issuecomment-4874623369).

[PR #3710](https://github.com/docling-project/docling/pull/3710), merged 2026-07-23, introduced the layout-first Standard pipeline and the four OCR modes. Its description says layout boxes feed OCR. The released implementation still deduplicates/dilates those boxes, so “layout-driven” must not be interpreted as one independent OCR call per raw layout box. [PR design and merge metadata](https://github.com/docling-project/docling/pull/3710).

### 2. A closely matching layout-first request remains open

[Issue #3499](https://github.com/docling-project/docling/issues/3499) asks for native surgical OCR of Heron regions to avoid collapsed columns on very large archival pages. The issue and its sample script are a **user proposal**, not an accepted official recipe.

A human contributor independently tested the same 73 MP example. Cropping recovered more characters but took longer and had a lower dictionary-word proxy; the contributor recommended a gated escalation rather than universal use. The comment also identifies `LayoutOptions(keep_empty_clusters=True)` as necessary when extracting layout with OCR disabled, since otherwise empty clusters are discarded. The proxy is not ground truth and the page differs substantially from our small scanned-paper case. There is no maintainer commitment to a native surgical flag in the inspected thread. [Contributor's experiment and caveats](https://github.com/docling-project/docling/issues/3499#issuecomment-5294993834).

### 3. A recent merged fix does not split cross-column crops

[PR #4748](https://github.com/docling-project/docling/pull/4748), merged 2026-10-14, removes a final OCR rectangle wholly contained inside another rectangle. Its code leaves partially overlapping rectangles and the connected-component/dilation step intact. It prevents duplicate OCR of enclosed material; it does not restore separate columns after they become one connected crop. A one-crop input has no contained second crop for this change to remove. [Exact patch](https://github.com/docling-project/docling/pull/4748/files).

In [issue #4489](https://github.com/docling-project/docling/issues/4489#issuecomment-6168906852), member `nikos-livathinos` confirms #4209 and #4748 addressed the issues discussed there except the remaining checkbox concern. That confirmation concerns shape-triggered excess OCR and enclosed duplicates, not a demonstrated multi-column split fix.

### 4. Detector input size is a supported workaround for a different mechanism

[Issue #4131](https://github.com/docling-project/docling/issues/4131#issuecomment-5507889527) contains a human contributor's concrete `RapidOcrOptions(rapidocr_params={"Global.max_side_len": 4000})` example and effective-value check. This changes RapidOCR's input cap, not Docling's shared region dilation. The same thread documents a substantial quality/resource trade-off on large engineering drawings. It is relevant when detector downscaling is the cause; it is not evidence that increasing resolution preserves layout boundaries.

### 5. Public extension support exists

The official [plugin documentation](https://docling-project.github.io/docling/concepts/plugins/) supports registering an OCR engine implementing `BaseOcrModel`, providing its own `OcrOptions`, and enabling external plugins. This is the official **extension seam**. A custom region-preserving implementation placed there would remain our engineering, not a built-in column-preserving algorithm endorsed by the documentation.

### 6. Reading-order issues are not equivalent evidence

[Issue #2204](https://github.com/docling-project/docling/issues/2204) reports failures across multiple layout models and includes a later contributor's readable-text/order-only case. [Issue #2067](https://github.com/docling-project/docling/issues/2067) uses `do_ocr=False`; a member requests a reproducer. [Issue #1186](https://github.com/docling-project/docling/issues/1186#issuecomment-2897992500) has a human maintainer acknowledging work on a separator/order edge case. These confirm broader multi-column limitations, but do not establish the cause or a fix for our OCR-region merger. Reading-order dilation settings must not be substituted for OCR-region dilation.

## Bounded recommendation

A separate zero-inference native geometry replay in this investigation retained the known page's 22 Heron boxes. None crossed the page midline. Kernels 0/4/8/12/16/20 produced 15/10/7/1/1/1 OCR regions respectively; only the last three settings produced a midline-crossing region. The nearest opposite-column box gap was 10.6816 pt. This isolates a concrete merge-policy mechanism on this page; kernel 8 is **not** a production recommendation. [Replay results](pdf-core-ocr-dilation-source-2026-10-20/geometry.json).

Current upstream `main` was pinned to `d01c9c0991920924cf17f6b8366079ac035ffc38` for source inspection and still uses the 20 constant in both region modes. [Source receipt](pdf-core-ocr-dilation-source-2026-10-20/source-receipt.json), [retained source](pdf-core-ocr-dilation-source-2026-10-20/base_ocr_model.py).

1. The first geometry replay is complete. Inspect the retained component connections before deciding the next comparison; disabling dilation alone cannot separate boxes that already overlap on other pages.
2. If the retained boxes are already accurate, do not launch an unrestricted layout-model search. A different model can be a finite control, but it must demonstrate different OCR crops and preserve coverage on the same regression corpus before being called a remedy.
3. Keep `FULL_PAGE` as the already measured official configuration candidate. It bypasses this selector, but its result is not evidence that its detector always respects columns or that unrelated content defects are acceptable.
4. If column-preserving OCR is still required, explicitly choose between an upstream report/patch and a small custom OCR plugin. Use the existing crop ablation's missing-heading result as a required negative control: “fewer mixed lines” alone is insufficient. Preserve source coverage, headings, inline mathematics, identifiers, orientation, and final paragraph order on the frozen regression corpus. Do not introduce text repair rules or tune a gap threshold to the single exposed page.

No alternate layout model was inferred or benchmarked in this research. No reviewed source establishes a general ready-made, publicly configurable, column-preserving crop algorithm; that is a bounded search finding, not a claim that no such solution exists anywhere.
