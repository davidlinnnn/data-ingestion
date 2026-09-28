# Verdict: inconclusive for the complete brief; local checkpoint boundary supported

Measured 2026-09-11 on macOS arm64, Python 3.12.13, CPU with four inference threads.
This is a throwaway primary-source experiment, not a production implementation.

The narrow question is supported for the pinned Docling 2.102.0 configuration:
explicit completed page outputs can reconstruct full-document assembly in a fresh
process, with no repeated page-processing stages and no observed additional
structure/evidence loss. The complete Temporal/Kubernetes requirement remains
**inconclusive**: no Kubernetes Pod-loss or shared-storage durability test ran.
There is no basis here to adopt the checkpoint as the canonical schema.

## Inputs and method

- Native fixture: the complete **51-page** *A Survey of Large Language Models*,
  [arXiv:2303.18223v1](https://arxiv.org/abs/2303.18223v1), downloaded from its
  versioned public PDF for local evaluation. SHA-256
  `d58be5fc39608dc9aec45194c602436d793f2f2bf56f267d0e38d6258a9f7a9e`.
  Multiple columns, formulas, tables, figures, captions, headings and footnotes.
- Scan fixture: original pages 3 and 5 rasterized at 144 DPI into a new PDF with
  no native text layer. Digest and per-page inventory are in
  [fixtures.json](evidence/fixtures.json). This covers a text page and a figure page;
  physical scan noise/skew and scanned tables/formulas remain untested.
- [uv.lock](uv.lock) pins packages; [native-method.json](evidence/native-method.json)
  records runtime, full options and artifact hashes. Layout Heron snapshot
  `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`; TableFormer snapshot
  `fc0f2d45e2218ea24bce5045f58a389aed16dc23`. Replay is offline and checks model hashes.
- Native PDF page OCR is disabled; scan page OCR uses RapidOCR 3.9.2 with
  ONNX Runtime 1.24.3 and forced full-page OCR. Table structure is enabled.
  Post-parsing code/formula/picture enrichment is disabled during baseline/replay.
  Separate component OCR follows only after grouped reconstruction passes.

## What was actually persisted and reconstructed

`CapturePipeline._release_page_resources` intercepts a completed page **before**
stock cleanup. It writes an explicit envelope containing source/method digests,
original page number, dimensions, coordinate convention, tagged assembled elements,
body/header membership, and a hashed rendered PNG. Elements retain cluster trees,
associated native/OCR cells, positions, table cells/structure, and hyperlinks.
Typed tags avoid ambiguous deserialization of Docling's overlapping element union.

`CapturePipeline._assemble_document` records the successful group/document manifest,
confidence and errors before any document assembly. Undefined confidence floats
round-trip as JSON nulls and are restored to NaN. The initial strict-JSON attempt
failed on NaN; its log is retained rather than concealed.

`RestorePipeline._init_models` constructs only the stock reading-order assembler.
`_build_document` checks identities and every artifact digest, reconstructs typed
page assembly inputs and image caches, and verifies original page coverage. The
stock document assembler then processes the entire page collection at once.
The converter reopens the pinned source for input identity/backend setup; it does
not rerun page preprocessing, layout, OCR, table processing or page assembly.
Class-level guards would fail the experiment if any of those stages ran on restore.
This is neither a live `Page` serialization nor concatenation of exported fragments.

Private dependencies: `_release_page_resources`, `_assemble_document`, `_init_models`,
`_build_document`, `_get_expected_page_nos`, `_page_sizes_by_no`, `_image_cache`,
`_default_image_scale`, and Docling's internal typed assembled-element models.
This release's reading-order assembler consumes those elements, page sizes and input
origin; no separate outline/font/heading-inference state was needed. That conclusion
is release/configuration-specific. No installed upstream file was patched and no
queue, inference or core pipeline implementation was rewritten.
The complete experimental Python suite is about 750 lines; the two adapter classes
are roughly 120 lines. Most remaining code acquires fixtures, instruments, injects
failures, evaluates and records evidence.

## Baseline and fresh-process measurements

Initial isolated trials, not averages or throughput promises. GB below is decimal.
Conversion time excludes interpreter/model initialization and final JSON/Markdown
export; process wall includes imports and export. RSS is macOS `ru_maxrss` in bytes.

| Fixture/run | Conversion seconds | Process wall seconds | Peak RSS GB | Repeated page stages |
|---|---:|---:|---:|---:|
| Native uninterrupted | 18.876 | 21.968 | 5.274 | n/a |
| Native fresh reconstruction | 2.104 | 4.915 | 1.450 | 0 |
| Scan uninterrupted | 6.980 | 10.126 | 4.188 | n/a |
| Scan fresh reconstruction | 0.329 | 3.007 | 1.123 | 0 |

Native baseline stage sums: preprocessing 2.667 s, layout 12.340 s, tables 13.749 s.
Scan OCR stage sum: 6.673 s. Stages overlap, so their sums are **not** wall time.
Native restore: checkpoint load 0.901 s, assembly 1.192 s. Scan restore: load
0.268 s, assembly 0.053 s. The initial baseline did not separately time document
assembly; the final reproduction measured it at 1.081 s ([native reproduction](evidence/final-reproduction-native.json)). Cold model download
cost is outside these timings.

The full accepted native checkpoint payload is **52,705,014 bytes** (page JSON+PNGs,
excluding method/group manifest/registry overhead). The final run spent 1.193 s inside 53 page-persistence calls, including the two unregistered page files from the failed attempt ([stage totals](evidence/final-stage-totals.json)). Per-page write durations,
stage batch calls, page input identities and checkpoint-load timing are retained
in logs. Counters count **stage entries/page inputs**, not neural-network forward
passes: native `RapidOcrModel` entries are no-ops because OCR is disabled, and table
stage entries on pages without tables do not imply table inference.

See [native comparison](evidence/native-comparison.json),
[scan comparison](evidence/scan-comparison.json), and
[final grouped comparison](evidence/final-grouped-comparison.json).
All compared document JSON fields were equal: text/original text, reading order,
parent/child references, levels, tables, captions, footnotes, hyperlinks, provenance
page/bbox/charspan, and embedded page/picture images. Nothing was stripped to make
comparison pass. Distinct process IDs and zero replay page-stage counts are recorded.

## Source inspection and existing parser limitations

Visual source checks used full-page renders of pages 3, 5, 6 and 13, plus the actual
216-DPI component crop. These are representative checks, not a manual audit of all
51 pages. Baseline is a comparator, not ground truth.

| Content checked | Observation in both uninterrupted and recovered output |
|---|---|
| Page 3 multicolumn overview and footnotes | Left-column content precedes right-column bullets; source positions and both footnotes preserved. The left footnote appears before right-column body in baseline order. |
| Page 5 Fig. 1 timeline/caption | `#/pictures/0` links to the same caption; region, original page and embedded pixels agree. |
| Page 6 large table | Baseline produces 44 rows × 13 columns; representative T5 row values and source positions survive recovery. No exhaustive cell audit claimed. |
| Page 6 small table | **Existing error:** collapsed into two rows; multiple source rows concatenate inside cells, and the final ROOTS row is not recovered in the inspected cells. |
| Page 13 formulas | **Existing limitation:** formula `text` is empty with formula enrichment disabled; flattened source text remains in `orig`, with source boxes. Recovery preserves both. |
| Page 13 numbered headings | **Existing limitation:** 4.3 and 4.3.1 both receive level 1 / body parent; true hierarchy is not inferred here. |
| Raster scan cases | OCR-based page processing reconstructs exactly; this alone does not prove complete OCR accuracy. |

## Group-size trial and failure observations

First ten source pages, including figures and tables; a new process per group:

| Group size | Processes | Wall seconds | Peak child RSS GB |
|---|---:|---:|---:|
| 1 | 10 | 42.106 | 2.097 |
| 5 | 2 | 14.701 | 3.580 |
| 10 | 1 | 11.553 | 3.650 |

[Sizing evidence](evidence/sizing.json). Five pages was selected for the recovery
trial because it reduced startup overhead substantially while keeping a smaller
retry unit than ten. This is not a production optimum; persistent-model workers,
GPUs and representative scan mixes were not benchmarked.

Real Temporal CLI 1.8.3 / server 1.31.2 / Python SDK 1.23.0 ran locally with SQLite
persistence. Activities launch separate parsing/assembly/OCR child processes.
Artifacts sit outside those children and Workflow history. Output registration is
an atomic, no-overwrite local hard link after validation. Identity includes source,
method, page bounds, producing code, and OCR reference/parsed-result version.

| Scenario | Observed result |
|---|---|
| All pages saved; process exits before document assembly | Exit 73; a fresh process reconstructs the same complete document with zero page-stage calls. |
| Group 1 persistence succeeds; completion withheld | An injected Activity exception prevents success acknowledgement; attempt 2 finds the registration and reuses it. This is not a real network partition. |
| Group 2 child exits after page 7 file persistence | Exit 75; no successful group manifest/registration exists. Retry recomputes that unregistered group. Pages 6–10 repeat preprocessing/layout/table stage entry; only pages 6–7 had reached page assembly/file persistence. |
| Assembly output not persisted | Exit 74 after assembly but before document export; retry loads saved groups, repeats assembly and executes zero page stages. This does not inject midway through the reading-order algorithm. |
| OCR output not registered | First OCR attempt completes recognition then fails before registration; second attempt reruns OCR only. Parsing remains reusable. |
| Second Workflow execution | All 11 page groups, assembly and OCR reuse accepted outputs; no new producing child process starts. |
| Kubernetes worker/Pod loss | **Not performed.** Configured API endpoint refused the connection; Docker daemon socket was absent. |

Final fault workflow: **79.258 s**. All-output-reuse workflow: **0.448 s**.
Group failure to registered replacement: **10.256 s**; assembly failure to registered
replacement: **5.985 s**. Exactly **13 accepted registrations**, maximum one per
operation identity. Layout/table stage inputs totaled 56 for 51 unique pages;
the extra five belong solely to the unregistered failed group. No registered group
repeated. This is a sequential experiment, not proof about concurrent races.

The historical event name `checkpoint_commit` means a **page file was persisted**;
it is not an accepted group registration. Partial-group page files are staging
artifacts. They are deliberately not independently reusable in this group-level
protocol. Finer per-page registration could reduce the measured repeated work;
that extension has not been implemented.

[Recovery summary](evidence/recovery-summary.json),
[registration ledger](evidence/final-temporal-ledger.jsonl),
[page-stage events](evidence/final-page-events.jsonl), and Temporal histories provide
the measurements. Initial harness logging failed before any computation due to an
argument-name collision; the fixed and failed-run evidence are both retained.

## Independent component OCR

The Activity resolves `#/pictures/0` against the parsed JSON digest and page 5
provenance. It proves the saved component pixels equal the crop of the saved page
at the declared coordinates, then renders those source coordinates at 216 DPI.
The crop is 1,391 × 687 pixels in the final result (see the result for exact metadata).
Visual inspection found the timeline region intact, with no caption included.
RapidOCR uses separately pinned bundled ONNX models. Source digest, parsed-result
digest, component, box, crop hash and producing model hashes accompany the result.

The final attempt took **0.566 s** including OCR engine initialization and recovered
**58/58 scored labels** using case/punctuation-insensitive substring matching.
This metric excludes logo text, reading order, duplicate occurrences and precision;
it is not a general OCR accuracy claim or character error rate. An initial 57/58
score was a transcription error: source label “Galatica” was initially written as
“Galactica.” The original result and corrected re-score remain in evidence; the
final fault run used the corrected reference. No crop defect was observed.
See [final OCR](evidence/final-ocr.json), [transcription](ocr-reference.json) and
[the actual crop](evidence/figure.png).

## Stop conditions and next design consequence

The initial native and scan reconstruction comparisons passed before group/Temporal
work. Grouped full-document reconstruction passed before component OCR. The adapter
remained bounded, required no core patches, preserved compared evidence, and did not
repeat registered completed parsing. Therefore none of the custom-integration stop
conditions triggered, and page-range **export-and-merge** was not selected or claimed
validated. Public `page_range` merely bounds page processing here; saved internal
outputs still undergo one global document assembly.

The result supports keeping an **internal execution checkpoint** separate from a
Canonical Revision and treating parsing, document assembly and Enrichment as
independently recoverable producers. It does not resolve the canonical schema or
production acceptance/lifecycle design.

Remaining gaps: real Pod/worker loss and cancellation, shared durable storage and
object-store completion semantics, concurrent registration races, noisy/rotated
scans, scanned tables/formulas, multiple scientific papers, exhaustive evidence
inspection, memory limits, GPU batching, and an upgrade compatibility matrix.
Kubernetes access must be restored before the full brief can receive a supported
verdict. No Kubernetes success is inferred from local Temporal success.
