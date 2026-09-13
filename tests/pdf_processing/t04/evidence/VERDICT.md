# T04 bounded acceptance

Implementation acceptance passed on the pinned Linux ARM64 runtime, real Temporal
and MinIO in `pdf-t04-validation`. Required two-axis code review remains pending;
this evidence does not close #39 or claim canonical/HTTP/profile qualification.

- Multiple picture request: 2 required components, ALPHA 12345 and BETA 67890
  recovered in individually registered OCR results referenced by the final manifest.
- No picture request: 0 selected, explicit not-applicable OCR coverage.
- Actual no-text picture: 1 selected, attributable no-text outcome. Separate real
  rendering contract tests verify `txts`, `scores`, `boxes` all absent and both
  coordinate origins; only the external OCR output is replaced for that check.
- NCCU manual original physical page 3: automatic assembled PictureItem selection
  selects 1 screenshot. Final OCR references contain both 我的專區 and 最新公告.
  Source/derivative digests and provenance are recorded separately. This verifies
  the missing screenshot-text delivery path observed in S2, not full OCR quality.
- Each successful request is repeated with identical final references and all
  returned parsing/assembly/component steps reused.
- Selected rotated picture fails `integrity / invalid_component_crop`, not silently
  excluded. Wrong cached crop fails the isolated real-render contract before OCR.
- Version-1 compatibility control remains `parsed_ready`, processing incomplete.
- Post-registration assembly/OCR/final publication faults retry with recorded
  Activity started attempts `[1,1,2,1,2,1,2]`; completed assembly and OCR are reused.
  An explicit incomplete finalization probe fails rather than registering success.
- Exhausted second component fails processing while component 1 remains registered.
  After that terminal failure, independently publishing the late valid component
  leaves the original terminal Workflow result unchanged.
- Final local contract suite: 5 passed. Modified-module static checking: 0 errors.

All four complete-result selection producer dictionaries match `producer-hashes.json`.
The raw object-store PVC and Temporal history remain in the isolated namespace.
`runtime.json` records the final normal worker Pods/image identities; fault worker
Pod UIDs are not claimed to be preserved. Fault scripts inject at the publication
return seam; they do not emulate a dropped wire-level ACK. T03 owns provider races.

Known bounded scope: one-page provenance, unrotated effective page box at origin,
TOPLEFT/BOTTOMLEFT; 3x recognition under the frozen rendering pixel cap. One OCR
Activity is scheduled at a time. No warm OCR, generic selection plugins, automatic
repair, artifact GC, canonical acceptance or production performance qualification.
The 51-page parsing baseline is unchanged by this slice and was not rerun as a
full 51-page required-OCR workload here; long full-workflow calibration is T09.

Preparation failures remain described in the README: simple borders/text-only
rasters did not become PictureItems, and initial source comparison omitted
Docling's 1.5x supersampling. The first fault harness keyed on `document.json`,
which also exists in page-group output; corrected targeting uses assembly
attribution. None of those exploratory runs are counted as passing acceptance.
