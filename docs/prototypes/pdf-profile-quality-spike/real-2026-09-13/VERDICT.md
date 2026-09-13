# Real-source follow-up: component enrichment remains necessary

**Adoption remains inconclusive.** On eight selected modern pages, both mixed and forced full-page OCR recover all 23 short content anchors. Neither exports the nine valid screenshot-only anchors in the manuals. Independent manually selected 3x crops recover all eleven valid crop anchors. A full-page OCR flag alone does not establish the required screenshot-text delivery behavior.

These are bounded diagnostics, not complete page accuracy, approved universal thresholds or T06 acceptance. No new T04 dependency is introduced; the examples can inform component-output regression tests.

## Frozen sources and sample

[plan.json](plan.json) was fixed before recognition with SHA-256 `e8217b298574f01931d6e54d25098995361c05de3051ab3e9d9425c423866509`. Source URLs, hashes, page selections, excerpts, crop rectangles and criteria are retained there. All five original PDF hashes and sizes match the supplied candidate manifest.

PDF physical pages (one-based):

- New Taipei Fuzhou minutes: pages 1–2, scanned body text, dates, road-width changes and overlaid stamps.
- Tainan hearing minutes: pages 1–2, scanned meeting details and continued three-column response table.
- NCCU personal-statement manual: pages 3–4, native instructions and embedded UI screenshots.
- NDHU internship-system manual: pages 6–7, native captions/instructions and embedded login/UI screenshots.
- Historical gazette: page 1 only, supplementary vertical-text scan. It has no extractable native text and is **not** a faulty-layer example.

All were selected by visual inspection before recognition, not by observed OCR success. Only nine physical pages were converted under three profiles (27 page conversions), plus five manual crop recognitions. The original 94 pages were not processed in full.

## Results and limitations

| Observation | Native | Mixed | Force-full-page |
|---|---:|---:|---:|
| Modern short content anchors | 9/23 | 23/23 | 23/23 |
| Valid screenshot-only anchors in exported document | 0/9 | 0/9 | 0/9 |
| Historical supplementary short anchors | 0/3 | 3/3 | 3/3 |

Native omissions on raster pages are expected with OCR disabled. Successful conversion is not complete extraction: the screenshot regions remain image placeholders in the exported document. The run does not isolate whether the omitted screenshot words were skipped in OCR, filtered by layout, or excluded in assembly; no unsupported causal claim is made.

The manual-crop control recovers eleven valid anchors across five crops, including menu labels and confirmation text. Those crops were chosen visually, not by a production component-selection implementation. This supports a separate component enrichment path but does not prove selection completeness, full screenshot transcription or proper final-result integration.

Both OCR profiles detect the first Tainan table as 2 rows × 3 columns. The continuation page, visually still a three-column table with blank leading columns, becomes 1 × 1. Required text anchors survive, but preserving the continued-table structure is **not demonstrated**. Cross-page table merging is not tested.

Historical success on three short anchors does not validate vertical reading order, historical glyph completeness or broaden the modern-document support claim. No historical ordered-anchor sequence was declared.

### Ground-truth and probe review

The raw planned scores remain unchanged. Review found confounds which are explicitly excluded in [summary.json](summary.json):

- Three intended screenshot-only anchors also occur in native instructions, so their presence cannot prove screenshot OCR.
- One anchor was transcribed incorrectly: the source UI says `機關代號`, while the plan says `機關代碼`. Raw crop result is **11/12**, and raw export result after native-prose exclusion is **0/10**. Excluding that invalid ground truth gives **11/11** crop and **0/9** exported anchors. The plan is not rewritten and the corrected spelling is not retroactively scored as a pass.
- The NCCU page-4 order probe uses `說明`, also a substring of earlier `操作說明`; its first-occurrence order failure is invalid, not evidence of wrong reading order.
- A vacuous historical order result is not counted as a pass.
- Experimental intermediate-cell introspection did not validly observe the OCR cells and was discarded. All reported content metrics use public per-page Docling exports or independent crop OCR.

This narrow anchor method cannot estimate character error rate, hallucination rate, or whole-page completeness. Numeric values in the chosen anchors survive, but unselected numbers have not been audited.

## Runtime and portability

Pinned Linux image `sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`, network disabled, 4 CPU / 5 GiB memory cap. Exact Linux/Python/package/options/model identity is in [environment.json](environment.json). All **17 fixed baseline model artifact hashes** match. No model download, alternate-model search or language conversion occurred.

Direct unmodified Docling conversion only: no Temporal, checkpoint adapter or production enrichment. Linux executes these real cases successfully; this is not a matched macOS/Linux equivalence experiment or a K8s deployment qualification. Page/picture image generation was disabled for this direct text diagnostic and that option is recorded; it is not a frozen production configuration. Timing fields are diagnostic metadata, not a throughput benchmark.

## Remaining decisions

- Keep the pinned models as candidates: the bounded data does not yet require replacement.
- T04 should verify that selected screenshot OCR actually reaches the final processing result, with source/component attribution and its required completion barrier. An OCR-enabled parsing profile is insufficient evidence of this.
- Review representative expected content, acceptable errors and table/language support boundaries before freezing profiles in T06. User provision of documents authorizes diagnostics, not new universal thresholds.
- No real unreliable-native-layer sample was provided. Retain the prior synthetic faulty-layer regression; do not misclassify the gazette or silently waive that gate.

No T06 implementation, issue closure, dependency change, deployment, push or original evidence modification was performed.
