# Q02 relationship delivery

Branch: `codex/q02-relationships`; baseline: `9ba0bab559f4248aaeb2d54b6b74c8e01c0e12b7`.
Implements #49 within #47. Q01 continuation correction and Q03 symbol dispositions
are not included. This is a processing-internal interface, not canonical schema.

## Profile / Q03 interface

Use request version 3 with completion `required_evidence_v1`, a new request ID,
and a new immutable worker release/profile containing:

```json
{
  "content_evidence": {
    "version": "typed-source-relationships-v2",
    "reviews": {},
    "relationships": {
      "method": "local-function-block-v1",
      "coverage": {
        "mode": "selected_regions",
        "source_sha256": "<64 lowercase hex characters>",
        "regions": [
          {"id": "operator-selection", "page": 1, "box": [10, 10, 500, 600], "required_count": 1}
        ]
      },
      "unresolved": "reject"
    }
  }
}
```

Regions are nonoverlapping top-left PDF-point rectangles on physical pages.
They encompass the complete algorithm including caption. Their counts are
operator declarations made **before** derivation and frozen in the accepted plan.
Counts, source identity and region bounds are validated independently of the
method's success list. Counts are not evidence of universal detection. Missing
review annotations cannot establish full detection: there is no supported `all`
coverage mode. No expected names, edges, roles, or transcript answers are supplied
to discovery. Qualification declarations for the retained source live only in tests.

The other supported coverage is `{"mode":"unknown"}`, requiring
`"unresolved":"allow_unknown"`. It persists candidates, full-page source evidence,
coverage and a reason, with no resolved-result claim. `allow_unknown` can also
permit a selected region's explicitly reported unresolved result. Missing or
invalid artifacts/references never become permissible unknowns. Outside selected
regions coverage always remains unknown. No ongoing required work remains at
completion. Unknown methods and unsupported coverage/dispositions fail explicitly.

The generic method recognizes bounded English `function … returns … failure`
syntax and a nearby numbered `Figure` caption. Same-line multi-item headers and
caption fragments, multi-provenance items and adjacent range fragmentation are
supported. Other layouts may be unresolved; this is not universal discovery.
Actual parser text, labels and geometry are unchanged. Embedded headers cite
ranges within their original item and exclude preceding prose. Isolated combining
marks remain separate evidence and make selected results unresolved; Q03 must
introduce a separately versioned policy to decide symbol cases. No symbol
normalization or early depth-limited/iterative-deepening acceptance is included.

## Artifact / completion boundary

The existing supervised `pdf_processing.evidence` child writes typed evidence and
`relationships.json`. A separate `pdf-relationships-v1:<digest>` registration wraps
that report, its content-evidence registration and exact evidence dependencies.
The final `processing-result.json` references this registration as `relationships`.
The report separates `candidates`, `resolved`, `unresolved`, `source_review` and
`coverage`. Every resolved result has an ID, kind, method and selection ID. Member
lists carry original refs, exact ranges, page/box, actual type and text digest.
`order` must be a non-boolean integer equal to the zero-based list position.
Headers precede bodies, then captions; every role is nonempty. Validation compares
ordered character coverage, so splitting a range does not change its meaning.

Finalization resolves every artifact through checked shared-storage reads,
recomputes bounded method expectations against the exact assembly, enforces the
frozen coverage policy and validates references, attribution, roles, ranges and
order **before** publishing complete. Reuse goes through the same barrier. All
selected OCR outcomes are checked first. `processing_complete` keeps
`quality_accepted` and `canonical_accepted` false.

## Identity and integration

`relationships.py` and `relationship_method.py`, plus `evidence.py`, enter evidence
and finalization dependency fingerprints. The relationship policy enters both
stage identities. The initial change to `compatibility.py` conservatively
invalidates parsing/assembly versus the pinned baseline; do not transplant old
registrations based on source-byte equality. Subsequent evidence-only method or
policy changes under the same dependency contract preserve equal checked
parse/assembly operation contracts and change evidence/final dependencies.
Old policy `typed-source-evidence-v1` remains supported. Existing accepted plans
must run on their retained immutable producer: full producer equality prevents
this worker from reinterpreting old accepted requests. No released image or route
was overwritten. Main must reconcile shared compatibility/profile/finalization
changes with Q01 and publish a new release after qualification.

## Verification and limits

Fast tests use the retained baseline assembly, whose file SHA-256 is
`7cbc44478d4a3d2f60256f6f92828b2396b1b932579436546e3d32b6f601f564`.
The source is `b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980`.
The baseline's unrelated continuation defect remains present. All 21 local
handoff hashes and the original experiment checkpoint hashes were verified.
`oracle/` preserves the corrected P2 source oracle at `68886d4`, adapting only
imports/paths for scoring. Runtime never imports it. Original historical outputs
are not overwritten. Full PDF/text/image data stays in private storage.

`runtime.py` uses a unique Temporal queue and shared `t07/q02/<run>/<case>` storage
prefix. It exercises real Activities, the supervised evidence child, durable
separate relationship artifacts, retry reads and final publication failures.
**Upstream plan/assembly/page/OCR selections are seeded fixtures.** This is real
runtime verification of changed evidence/finalization, not full native conversion,
OCR engine execution or restored-assembly acceptance. It neither alters shared
workers nor pauses services. The first runtime attempt failed on internal `cref`
serialization; subsequent runs use Docling's production `save_as_json` format.

Remaining qualification: a coordinated model-heavy window is required for a full
versioned `PDFProcessing` request, selected OCR engine completion, fresh/restored/
warm processing reuse, and interruption/recovery of this exact producer. Checked
operation-contract tests alone do not establish actual parse/assembly reuse.
No Q04 or #44 acceptance is claimed. Q03 can use this interface contract but must
not interpret partial runtime evidence as release acceptance.
