# #81: Canonical content from real papers, and through the real platform API

Two checks of `canonical-mapping@1` ([the spec](../../design/knowledge-platform-canonical-content-spec.md)),
run on 2026-11-24 on a Mac.

## 1. All 21 papers of #233, mapped and validated

[map_corpus.py](map_corpus.py) reads the Processing Results #233 registered for the 20 corpus
papers and W2 (its kept object store, outside git), builds each content object and validates it
in memory. No model is called. Each paper also gets two negative controls: a body text block
dropped (validate must refuse it with `COVERAGE`) and a manifest entry dropped
(`REFERENCE_UNLISTED`).

```sh
.venv/bin/python docs/validation/81/map_corpus.py ~/archive/research/233-release-rerun/run1 OUT
```

**All 21 valid; all 42 controls refused with their check.** Readings per paper are in
[evidence.json](evidence.json).

| Reading | Value |
|---|---|
| Blocks | 6588 (222 `role_uncertain`) |
| Tables | 167: 56 as HTML (a cell spans), 111 as Markdown |
| Picture native text entries | 5867 |
| Enrichment items | 1532, 169 `disputed` |
| Omitted (FURNITURE) | 755 |
| Content object size | largest 1.10 MB (paper 20, 50 pages) |
| build + validate | at most 0.48 s per paper; paper 16 (64 pages) 0.38 s, against finalize's 120 s `start_to_close` |

The first run found a defect: on papers 11, 13, 16 and 20 docling places a code node inside a
picture (a boxed prompt). The node is the picture's native text, and the code item's
reconstruction targets it there, so `REFERENCE_UNRESOLVED` refused it. The rule now accepts a
picture's `native_text` ref as a target (spec §3.3 and §6), and a unit test holds the case.

Every paper carries the profile's four limitations; none has a document-scope one, so that
kind is held by a unit fixture only.

## 2. End to end through the platform API

[e2e.py](e2e.py) submits papers through the real `kp-admission api` and `dispatcher`
(PostgreSQL 17 in Docker), processed by the paper-pdf workflow on #199's models, stand-ins and
runtime: W2 on the stand-ins, corpus papers 8 and 7 on the providers (Claude Sonnet 5.5 for
the VLM methods and the summary, d3-mini on MPS). Each of 8 and 7 has a table with merged
cells, delivered as HTML. The run was on the branch's last code (`67fb753c`).

```sh
set -a; . ~/.config/kp-dev/anthropic.env; set +a
A=~/archive/data-ingestion-wip-2026-10-21/untracked
scripts/heavy-lock 81-e2e -- env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/81/e2e.py \
    NEW_OUT "$A/docs/fixtures/agent-self-evolution-pilot-2026-10-11/manifest.json" "$A" \
    ~/models/issue84/w4b-d3-models/d3-mini ~/archive/data-ingestion-153-untracked/d3-runtime/venv/bin/python \
    w2 8 7
```

**All three pass: each request `succeeded`, its Source Revision `accepted`, the Document has a
current revision, the feed has its `current_revision_changed`, and
`kp_admission_not_accepted_total` did not rise.** Readings in [e2e.json](e2e.json); the
content objects and each paper's full row stay outside git (OUT `content/` and `papers/`).

| Paper | Services | Submit to `succeeded` | Canonical Revision | Content object sha256, size | finalize Activity |
|---|---|---|---|---|---|
| W2 (14 pages) | stand-ins | 50 s | `crv_4af519b8…` | `927ee4ab7af07321…`, 193628 B | 0.31 s |
| 8 (12 pages) | providers | 45 s | `crv_72f8f13b…` | `7e4e2a0e09383635…`, 179680 B | 0.21 s |
| 7 (18 pages) | providers | 50 s | `crv_61073ee4…` | `66c3685f6c3b7f15…`, 291091 B | 0.25 s |

The time includes the 5-second poll of `GET /v1/requests/{id}`. In each case the stored
object's sha256 and size equal the acceptance row's (`canonical_revision`), and the read API's
`current` names the request's revision.

What it does not show:

- **The gate.** The adoption is `kp-admission adopt`, so `apply-adoption`'s test workflow did
  not run here. Its candidate check is a unit test (`tests/admission/test_adoption_gate.py`),
  and the gate's test file runs end to end in `tests/test_workflow.py`.
- **A retry or a redispatch.** Write-once is held by `tests/stages/test_finalize.py` (a retried
  finalize reports the stored object) and `tests/test_workflow.py` (a second run of a
  succeeded request keeps the object and its candidate).
- **A not-accepted case.** The `not_accepted` counter is checked to be exported (its TYPE line)
  before it is read, but no run here makes a request that forms no acceptance, so the check
  has no positive control.
