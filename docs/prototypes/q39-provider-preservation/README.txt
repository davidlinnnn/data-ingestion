Q39 provider preservation spike — THROWAWAY, not production
2026-10-13

Question
Can the accepted Q39 requirement preserve complete emitted Docling data and its
dependencies without turning the provider schema into the Canonical schema or
building a new persistence framework?

Verdict
Yes, at a bounded serialization boundary. Reuse the existing processing-result
and immutable artifact references. Preserve the first emitted provider artifact
before typed adaptation. Map required content explicitly; record deferred content
as retained and not interpreted. Keep dependency custody explicit.
This spike does not implement a Canonical mapper or prove end-to-end losslessness.

Run
Use a Python environment with Docling 2.102.0 and Core 2.96.0:
  python spike.py
The existing environment used here is:
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python
No installation, PDF parsing, OCR, model inference, database or remote calls.
The script uses temporary files and emits observations.json plus a synthetic
document.json fixture next to itself. Re-running only replaces these spike files.

Artifacts
- spike.py: reproducible ten-case experiment with executable assertions.
- observations.json: actual observations, dependency versions and limitations.
- synthetic-document.json: synthetic Docling output only; no private content.
- demo.html: standalone, in-memory demonstration with four guided scenarios.
  Open by double-click. JavaScript syntax and five pure decision checks passed.
  Browser visual verification was unavailable: browser policy blocks file URLs.
- issue-84-q39-pending.txt: proposed tracker update retained if network sync fails.

Observed in the installed pinned runtime
1. Known-schema model/JSON/model preserves the tested semantic tree, including
   Traditional Chinese, orig, inline group/formula, caption refs, merged cells,
   description annotation, bbox precision and already-embedded images.
2. A deliberately injected unknown top-level field disappears after typed reload.
   The retained original JSON bytes still contain it. This is a compatibility
   probe, not evidence that an existing production document lost a populated field.
3. A deliberately injected unknown TextItem field is rejected (extra_forbidden).
4. Old schema version labels normalize to current; a newer minor is rejected.
5. An out-of-bounds source bbox l=-4.25 becomes l=0 during validation.
6. A dangling body reference is rejected.
7. REFERENCED mode with an absolute output filename defaults to absolute image
   paths; moving the bundle breaks those references even though JSON loads.
8. Explicit relative artifact paths need a correct resolution root; deleting
   a referenced picture also leaves JSON load successful but image read failing.
   Changing CWD was only an experimental control, not a worker implementation.
9. EMBEDDED mode does not automatically embed an already-external page image.
10. Document JSON omits conversion status/errors/confidence/timings/input scope.

Minimum design recommendation (not a new API/schema selection)
- Original PDF/Capture Package remains source evidence.
- First emitted DoclingDocument serialization remains a provider artifact.
  It is not raw PDF text or proof of the author's truth. Do not overwrite it
  with a mapper's normalized reserialization.
- The processing-result reference binds source revision, provider/package/schema
  identity, original per-group diagnostic refs, images, relationships and actual
  independent OCR/enrichment results. Reuse the present artifacts/manifests.
- Canonical uses the accepted #32 representation, content, relationships and
  origin, with fixed links back to the provider artifact and source evidence.
- Nonempty provider fields have explicit mapped or retained/uninterpreted
  dispositions; no universal vendor-field mirror in Canonical DB is needed.
- Required formula/table semantics cannot be satisfied by raw retention alone.
- Adopt referenced files into custody before temporary/checkpoint cleanup.
  Q39 does not mean keeping every tensor, cache or temporary artifact forever.
- Keep existing embedded/reference choices until measured payload sizes justify
  changing them. No new database, archive layer or content-addressed service.

Repository source audit, fixed published baseline fe1b283
The current core already emits assembly document.json plus OCR, evidence,
relationships and fixed processing-result references. Group complete.json stores
status/errors/confidence. Assembly aggregation starts from the first group and
merges only confidence.pages; it does not establish complete aggregate diagnostics.
manage.export_result does not recursively export parsed-result.page_groups.
Thus diagnostic data may exist in the store yet be absent from a standalone export.
This is a source-visible coverage limit, not a measured live-data-loss incident.
Checkpoint/assembly field coverage remains to validate for newly selected features;
preserving final JSON alone cannot recover a field dropped earlier.

Sources
https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/document.py#L3551
https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/document.py#L3603
https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/document.py#L3402
https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/items/node.py#L22
https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/document.py#L5232
https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/common/reference.py#L83
https://github.com/docling-project/docling/blob/v2.102.0/docling/datamodel/document.py#L274
https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/deploy/pdf-processing/manage.py#L34
https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/execution.py#L404
https://github.com/davidlinnnn/data-ingestion/blob/a46620503a1a43fa156ff30746c98e9f76515de5/docs/design/knowledge-platform-canonical-contract-draft.md

Limits and follow-through
The physical Canonical DB/custody mechanisms (#57), actual mapper (#81), fresh vs
checkpoint restoration for new features, rich metadata/table/form collections,
real corpus quality, payload costs and models remain unverified here.
Q39 acceptance is confirmed by the user; Q38/F19 is still pending.
The demo's readiness state illustrates Q39 only, not the unresolved Q38 policy.
Do not transplant this toy reducer into production as a complete acceptance gate.
