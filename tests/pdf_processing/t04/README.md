# T04 required component OCR

The accepted seam is versioned request → actual Temporal Activities → shared
MinIO registrations → complete processing result or explicit failure. A version-1
request retains T02's `parsed_ready` behavior. A version-2 request must explicitly
freeze `completion: required_picture_ocr_v1`; request identity conflicts cannot
silently change that target. Neither result grants canonical acceptance.

The new required rule selects all assembled PictureItems, with stable identity
only within that assembled-result version. Page renders are explicitly excluded.
One component is scheduled at a time. Each component owns a separate registration;
finalization validates every group, assembly and the exact component coverage.
Unsupported crop geometry fails the selected target, never silently excludes it.

## Supported crop geometry

TOPLEFT and BOTTOMLEFT, one-page provenance, rotation zero and effective page box
at (0,0,width,height). Source SHA, source-render pixels, saved component crop,
parsed artifact SHA and provenance are checked. The source-render comparison uses
the pinned Docling backend's 1.5x supersampling followed by resize; recognition uses
a 3x source crop. Full-page rendering at 3x is bounded by the request's frozen pixel
limit. Arbitrary rotation/CropBox handling is explicitly unsupported in this slice.

## Reproduce

Use the same pinned Linux image as T02; do not install packages in that image.
Create namespace `pdf-t04-validation`, instantiate prototype storage/Temporal
manifests there, and create `t04-package` (package Python files), `t04-driver`
(worker, native profile and this folder's drivers), and a small `t04-fixtures`
ConfigMap. Apply `k8s-validation.yaml`. Keep the source PDFs out of ConfigMaps when
size/annotation limits apply: copy them into the coordinator's `/tmp/t04-fixtures`.

Generate the small fixtures with `fixtures.py <output>` in the existing local
fixture environment. The real-source regression uses physical page 3 of the NCCU
manual; `source-provenance.json` records original and derivative SHA and URL.
Downloaded/derived PDFs are not committed. This is two screenshot-anchor delivery
checks, not multilingual profile qualification or complete text-quality approval.

Run coordinator `/experiment/.venv/bin/python /driver/verify.py` with
`T04_FIXTURES=/tmp/t04-fixtures`. It checks multiple/no pictures, actual no-text OCR,
unsupported rotation, screenshot text in final enrichment references, and second
Workflow reuse. The standalone `test_ocr_geometry.py` checks both coordinate origins,
wrong crop and all-None OCR fields; only the external OCR engine is replaced there.

For fault cases, mount `fault_worker.py` and `fault_verify.py`. Use the test worker
entry point instead of production worker with `T04_FAULT=lost_ack`, then
`component_failure`, restarting only T04 activities and waiting for rollouts.
`fault_verify.py lost_ack` injects post-registration loss at assembly/OCR/final
publication and verifies retry/reuse plus rejection of incomplete finalization.
`component_failure` exhausts the second component while the first remains durable.
Restart normal worker, run `fault_verify.py late`, and verify late component output
cannot alter the previously terminal failed Workflow result.

These synthetic publication faults are not claims of network-level ACK injection.
T03 independently owns competing/lost-ACK store semantics. Keep the T04 PVCs and
raw evidence. No shared artifact deletion or canonical retention policy is added.

Fixture preparation observations: an empty border and a text-only raster were not
classified as PictureItems by the pinned layout model. The committed generator
uses visible colored diagrams to exercise actual PictureItems. This does not
claim that every source bitmap becomes a PictureItem; selection completeness
beyond the parser's assembled candidates remains a separate quality limitation.
