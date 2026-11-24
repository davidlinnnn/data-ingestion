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
runtime. See the script's docstring for what it records.
