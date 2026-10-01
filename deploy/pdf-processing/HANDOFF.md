# Processing Completion integration handoff

The executable seam is captured source → `routing.submission` → shared real
Temporal `PDFRolloutProcessing` → checked shared store → summary/result export.
`manage.py` is the reference adapter. HTTP admission (#31) and canonical
normalization/validation (#32) must use the same binding and completion boundary.

```json
{
  "version": 3,
  "completion": "required_evidence_v1",
  "profile": "native-v1",
  "request_id": "stable-business-request",
  "source_revision": "upstream-immutable-revision",
  "artifact": {
    "key": "release-prefix/sources/unique/input.pdf",
    "name": "input.pdf",
    "version_id": "non-null-version-id",
    "sha256": "64-character-source-digest"
  }
}
```

This is a shape example; `tests/pdf_processing/t10/evidence/` supplies actual
captured requests and terminal summaries. The Workflow ID is an execution
identity; request ID/source revision/artifact/profile are computation identity.
Submission must retain the explicit content-addressed routing ID. The request
validator and source preflight reject unsupported shape, absent versions, changed
bytes, release mismatches and configured size/page/pixel bounds.

| Processing artifact | Downstream seam | Completion / ownership |
| --- | --- | --- |
| `summary` | status/error/reuse/timestamp reporting | Inspect `status` and `processing_complete`; failure can be a normally completed Temporal execution |
| `processing-result.json` | enumerate required work and checked adopted references | Only registered final result with all required pages/OCR/evidence/relationships finished is complete |
| `assembly/document.json` | canonical document candidate | Full Docling-style assembled graph, stable refs/page provenance; #32 performs canonical validation |
| `selection`, OCR/crops | evidence-backed region enrichment mapping | Required selected region work is complete; no universal OCR quality claim |
| typed `content-evidence`, `relationships` | source provenance and representation/association outcomes | Unknown/unresolved representation remains explicit; completion does not convert it to accepted quality |
| parsed result / plan | internal traceability and stage summaries | Retain for custody; do not expose checkpoints as public projection |
| `retained-references.json` | #31/#32 retention handoff | Version/hash/operation references checked at export; custody owners define lifetime and deletion policy |

`processing_complete: true`, `canonical_accepted: false` and
`quality_accepted: false` are distinct outcomes. #32 must create its own accepted
canonical output and validation evidence; the processing adapter cannot set that
decision. No public canonical schema, ingestion admission endpoint or production
retention policy is invented here.

Retention handoff includes the captured source version, original-source mapping
for source-reviewed derivatives, final result registration, every adopted
artifact version/digest, release binding, image/profile/model identifiers and
terminal stage summaries. Keep source-original review references in their historic
prefixes; copying a derivative into a fresh prefix does not erase that provenance.
Store migrations and capacity targets follow #52/#57 and related tickets.
