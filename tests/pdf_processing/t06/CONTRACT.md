# T06 implementation contract

Confirmed test seam (Q27 and #41): versioned processing request → actual Temporal
Activities/shared object store → complete internal result or explicit failure.
The new v3 request selects `required_evidence_v1`; v1/v2 behavior is retained.
The frozen maintainer-owned profile supplies reviewed source-region annotations,
keyed by exact processed source digest; unreviewed documents have explicit unknown
coverage. Input PDF derivatives keep original-page mappings in these annotations.

The final manifest references a separately registered content/evidence manifest:
complete typed graph including furniture and picture children, unchanged original
Docling JSON, per-region readable page evidence with render attribution, explicit
formula occurrence/type and text-representation uncertainty. No canonical adoption,
LaTeX, graph-edge extraction or universal formula detection is implied.

Tests assert independent S2 expected content through final references. Small
negative cases at the same interface cover absent required review/evidence and
invalid source/region association. Existing version1/version2 regression suites
remain mandatory. Checkpoint-restored output compares with fresh uninterrupted
Docling output, with no removal of semantic symbols from comparison.
