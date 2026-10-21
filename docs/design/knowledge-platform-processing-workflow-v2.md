# PDF processing workflow v2

The design result of
[設計 PDF processing workflow v2：stage 圖、耐久單位與處理結果 manifest v2](https://github.com/davidlinnnn/data-ingestion/issues/91),
confirmed with the user on 2026-10-21 (grilling rounds 1–6, Q1–Q28). It defines
the stage graph, durability and retry units, failure semantics and the
Processing Result that Canonical consumes. Domain terms follow `CONTEXT.md`.

v2 is a rewrite. The v1 PDF core (#33) is a concept reference and proven
evidence, not a compatibility constraint (Q27 retires it). External inference
call rules, throughput and capacity belong to
[設計 PDF workflow 的外部推論呼叫規則、併發吞吐與容量模型](https://github.com/davidlinnnn/data-ingestion/issues/93),
which builds on this graph.

## 1. Scope and owners

| Topic | Owner |
|---|---|
| Admission, dispatch, workflow start input, status contract | #31 (closed), [admission spec](knowledge-platform-admission-spec.md) |
| Stage graph, durability units, failure semantics, Processing Result | this document |
| Inference call rules, retry budgets, concurrency, capacity | #93 |
| Canonical mapping, status and signal fields in the canonical contract | #81 |
| Custody adoption, retention, purge | #57 |
| Accuracy validation and `verified` opening | #83 |
| Implementation | #80 |
| Metric conventions, collection, deployment | #78 |
| External summary API egress | #87 |

## 2. Decisions

| Q | Decision |
|---|---|
| Q1 | One request produces one complete Processing Result. Enrichment runs in the same workflow as parsing; no two-phase candidate and no child workflows. |
| Q2, Q12 | Two layers. A Temporal Activity is the scheduling, timeout and retry unit, sized as one document × one execution resource or external service. A per-item object-store registration is the durable result and reuse unit; a retried Activity skips registered items. No K-item batching until measurement (V2) requires it. |
| Q3a | Enrichment Methods are components of the platform-owned, format-specific, versioned Processing Profile. The Knowledge Profile selects projections only and never changes which enrichments run. |
| Q3b | Knowledge Profile and Processing Profile are distinct; "profile" alone is avoided. |
| Q3c | Source Caption is source content. Picture Interpretation is one VLM request per picture with a strict schema: generated caption, description, `figure_type`, chart values. Each output field is its own enrichment result with its own status. |
| Q4, Q4a | Document Category and Document Summary are Canonical data (document-scope methods). Document Category has three enum fields (document type, paper type, topic); value sets are versioned with the method and are placeholders until defined with the PM. |
| Q4b, Q4d | Document Summary cites Source Evidence per sentence and is distinct from the source abstract. Another team's API produces it (contract undecided): an adapter seam with a DEV mock. If the API returns no evidence, the adapter aligns each sentence to sections; an unsupported sentence is a strong signal. |
| Q4c | Sending content to that API needs #87 governance approval before PROD use. |
| Q5 | Document Category never serves as an access or governance input. |
| Q6 | Document-scope methods read only native body text and headings, never other enrichment outputs. |
| Q7 | Two failure tiers: native evidence is all-or-nothing; enrichment is per-item status (§6). Supersedes the #72 rule that a failed required picture OCR fails processing. |
| Q8 | Three failure classes (§6). An unavailable service is retried within the #93 budget, then the item is `failed` with `SERVICE_UNAVAILABLE` and the document completes. |
| Q9, Q14 | Finalize assigns Enrichment Status with a versioned status rule (§7). Canonical keeps the status unchanged. |
| Q10 | Processing Result and Enrichment Status are glossary terms. The result schema is a new namespace, `pdf-processing-result/v1`; `quality_accepted` is dropped. |
| Q11 | No decision-model gate Activity in v2. Calibration runs offline in #83 on the DEV validation corpus only; PROD has no dependency on it. |
| Q13 | An Enrichment Method is a code module plus a Processing Profile entry (id, version, parameters). No generic plugin framework or DSL; the stage graph is code. |
| Q15 | Enrichment failure ratios are metrics with operator alerts, not `attention[]` entries. |
| Q16 | The workflow input is the admission spec §10 input. `adopted_version` names the Processing Profile version; the dispatcher pins the workflow to the matching release and the workflow asserts the match. |
| Q17 | Status reports use four coarse stages (§9); `attempt_id` = `request_id`; reporting failures never fail processing. |
| Q18 | Failures map to admission attention kinds (§6.3). |
| Q19 | Processing Result skeleton (§8). |
| Q20 | The Processing Result registration is the custody handoff point; only listed artifacts are adoptable (§10). |
| Q21 | Known limitations (#84 U1) are declared per Processing Profile version and copied into every result; no per-document detection in v1. |
| Q22 | Reuse is scoped to one Document (`document_uid`); no cross-document reuse in v1. |
| Q23 | Items failed with `SERVICE_UNAVAILABLE` are re-run by an operator redrive (admission spec §9 redrive, extended selection), reusing all registered work and producing a new candidate. Automatic re-run waits for observed failure rates. |
| Q24 | The map row "Enrichment reuse and versioning rules" is disposed by Q3a, Q12, Q22, Q23 and Canonical design Q11. |
| Q25 | Markdown and PPTX workflows become a map Not-yet-specified row, revisited before the first non-PDF Source onboards. |
| Q26 | Validation work V1–V6 (§11). |
| Q27 | Retire v1 at this ticket's resolution: tag `archive/pdf-core-v1`, then remove `src/pdf_processing`, `tests/pdf_processing` and `deploy/pdf-processing` from `dev` in a separate PR. |
| Q28 | v2 evidence: reports, case lists and hash manifests in git; raw outputs, weights and page images outside git. |

## 3. Workflow and Activities

```
prepare → parse groups ×N (5 pages each, sequential) → assemble → inventory
  ├─ local enrichment   (CPU worker)       picture OCR, code reconstruction
  ├─ VLM enrichment     (VLM service)      Picture Interpretation, formulas[, Document Category]
  └─ summary enrichment (summary API)      Document Summary
→ finalize (status rule → Processing Result)
```

The three enrichment Activities run in parallel. Document-scope methods read
only native content (Q6), so they need not wait for item-scope methods.
Document Category runs in whichever Activity matches its execution service.

| Activity | Unit | Worker or service | Notes |
|---|---|---|---|
| prepare | document | CPU | Validate input, verify digests, preflight limits, freeze the group plan |
| parse group | 5 pages | CPU, one parser | Docling native parse; page and picture images (tier 1); per-page checkpoints |
| assemble | document | CPU | Rebuild the document from registered groups; never repeat page inference |
| inventory | document | CPU | Versioned enrichment inventory bound to the assembly version |
| local enrichment | document | CPU | Per-item registration |
| VLM enrichment | document | VLM service | Per-item registration; call rules from #93 |
| summary enrichment | document | summary API | Adapter seam; DEV mock |
| finalize | document | CPU | Inventory check, status rule, Processing Result registration |

Group parsing stays sequential with one parser per worker: the v1 calibration
did not admit two parsers within the 4 GiB worker guard. Each stage family has
its own retry policy; #93 sets the numbers for external services. Temporal
payloads carry references and digests only.

## 4. Enrichment Methods

| Method | Scope | Origin | Activity | Inputs | v1 strong signal |
|---|---|---|---|---|---|
| Picture OCR | item (picture) | reconstruction | local | high-resolution crop | none |
| Picture Interpretation | item (picture) | interpretation | VLM | crop and page image | none |
| Formula | item (source group) | reconstruction | VLM | source-group region | mismatch with the native text layer (numbers, operators) |
| Code | item (code block) | reconstruction | local | native text layer and coordinates; VLM only without a text layer | none |
| Table status | item (table) | none (status only) | finalize | native grid, HTML, crop from assembly | none (the dual cell-matching signal stays with #82) |
| Document Category | document | interpretation | per service | native body and headings | none |
| Document Summary | document | interpretation | summary | native body and headings | sentence without a supporting section |

Adding a method means a new module, a Processing Profile entry and accuracy
validation (#83), which together form a new Processing Profile version.

## 5. Durability, reuse and versioning

- **Reuse key** = hash(`document_uid`, method id and version, digest of that
  method's own module and model, digests of its actual inputs). Each method is
  its own module, so changing one method recomputes only its items. Reuse never
  crosses Documents (Q22): Custody Purge must destroy dependent copies, and
  Documents may sit in different Resources.
- **Side effects are safe to repeat.** The reconciler may re-dispatch a
  request; registration is write-once and a concurrent loser resolves to the
  registered winner.
- **Release unit** = one Processing Profile version. Any method change produces
  a new version and triggers platform refresh (Canonical design Q11).
- **First choice for deployment: Temporal Worker Versioning.** One release is
  one Worker Deployment Version. Workflows are Pinned, so a running request
  finishes on the version it started with, and new versions are ramped. The
  dispatcher starts each workflow on the version named by `adopted_version`.
  Self-hosted Temporal needs server v1.29.1 or later. The company's shared
  Temporal version is unknown, so V1 decides.
- **Fallback:** one task-queue set per release, bound at admission and never
  retargeted (proven in v1, #33 T08).

## 6. Failure semantics

### 6.1 Two tiers

| Tier | Content | Rule |
|---|---|---|
| 1. Native evidence | Page coverage, native text and structure, picture images and locations, page images, table native grids, Source Captions, native text layers | All or nothing: any missing or corrupt part fails processing |
| 2. Enrichment | OCR text, Picture Interpretation, formula and code reconstruction, table status, Document Category, Document Summary | Per item: a failure is recorded as `failed` with a reason and the document continues |

Guards between the tiers:

- **Inventory rule.** Every inventory item ends with an outcome record:
  success, `no_text`, or `failed`. A missing record is an integrity error.
- **Systemic errors by category.** A `configuration`, `method` or `integrity`
  error fails the document even when it occurs on one item. Failure ratios only
  raise alerts (Q15).
- An OCR render failure is an item failure; the picture's evidence image is
  tier 1 and already exists.

### 6.2 Failure classes

| Class | Examples | Handling | Document |
|---|---|---|---|
| Content failure | Model refusal, schema invalid after retries, empty output, render failure | Item `failed` with reason | Completes |
| Service unavailable | Service down, timeout, rate-limited beyond budget | Retry within the #93 budget, then item `failed` with `SERVICE_UNAVAILABLE` | Completes |
| Platform or integrity | Tier-1 failure, missing outcome record, configuration, method or integrity error, storage unavailable after retries | Processing fails | Fails |

The #84 U1 rule that native omissions or duplications block acceptance is a
Canonical Acceptance check, not a processing failure.

### 6.3 Mapping to admission status

| Processing outcome | Attention kind | Cause, retryable |
|---|---|---|
| Source unprocessable: password, corrupt PDF, page, size or pixel limit | `source_revision_rejected` | `source`, not retryable |
| Platform or integrity failure after retries | `processing_failed` | `platform` |
| Enrichment items `failed` | none | — |

Reasons are `UPPER_SNAKE_CASE`, for example `PASSWORD_REQUIRED`,
`PAGE_LIMIT_EXCEEDED`, `NATIVE_COVERAGE_INCOMPLETE`.

## 7. Enrichment Status rule v1

| Status | Condition |
|---|---|
| `failed` | No output: refusal, `SERVICE_UNAVAILABLE`, render failure, schema failure |
| `disputed` | At least one strong signal contradicts the output (§4) |
| `unverified` | Otherwise |
| `verified` | Not produced in v1; opening conditions are #83's (calibration set of at least 300 items per category, meaning-change rate at most 2%) |

Weak signals, such as cheap-signal agreement, are recorded but never change
status. The rule is versioned inside the Processing Profile; changing it reruns
only finalize. Canonical keeps the status; consumers check it before use.

## 8. Processing Result

Schema `pdf-processing-result/v1`. Field spellings are fixed in the
implementation spec; this is the confirmed skeleton.

```
schema
request:      request_id, document_uid, source_revision_id, files[custody_ref, sha256]
profile:      Processing Profile version, status rule version, producer and runtime identities
outcome:      complete            (a failure produces an error report, not a result)
native:       assembly, page groups, page and picture images        (tier 1)
inventory:    inventory ref; counts per method × status
enrichments[]:
  result_ref, method_ref (id@version + digest), scope (item | document),
  origin (reconstruction | interpretation), target_refs, input_refs,
  content (inline when small, otherwise a reference), evidence_refs,
  status, status_reason, signals{}, provider_artifact_ref
limitations[]: known limitations declared by the Processing Profile version
```

The enrichment fields follow the canonical contract's Enrichment group. `status`,
`signals` and `provider_artifact_ref` are additions that #81 carries into the
canonical contract. A document-scope result targets the whole candidate.

## 9. Admission integration

- Input: admission spec §10, unchanged. The workflow ID is `request_id`.
- The workflow asserts that `adopted_version` equals its own Processing Profile
  version; a mismatch is an `integrity` failure.
- Status reports follow the admission status reporting contract with four
  stages, independent of the internal Activity layout:

  | Stage | Progress unit |
  |---|---|
  | `prepare` | — |
  | `parse` | pages |
  | `enrich` | items |
  | `finalize` | — |

- `attempt_id` = `request_id`. Reports are a separate retried Activity,
  deduplicated by `seq`; a reporting failure never fails processing. On
  completion `manifest_ref` points to the Processing Result.

## 10. Custody handoff and limitations

| Artifacts | Owner |
|---|---|
| Listed in the Processing Result: assembly, page and picture images, enrichment content, provider raw outputs | Adopted into custody by #57 on Canonical Acceptance |
| Attempt scratch, group checkpoints, OCR render crops | Processing-internal; removed after a retention window unless a result references them |

Whether adoption copies or marks in place is #57's choice. Known limitations
(#84 U1, for example first-page column order on CVPR-style layouts or captions
interrupting body text) come from #83 evidence. They are declared per
Processing Profile version and copied into each result; Canonical maps them to
`limitations`. Per-document detection or repair is the optional #89.

## 11. Validation work

None of these blocks the design; each has a fallback.

| # | Owner | Check | Pass | Stop or fallback |
|---|---|---|---|---|
| V1 | #80 | Worker Versioning on the company Temporal: Pinned, start on a named version, ramp, rollback | Running requests finish on the old version; new requests run on `adopted_version` | Unsupported → per-release task queues |
| V2 | #80 | Activity sizing: the 64-page DGM paper and the most picture-heavy paper; kill a worker mid-Activity | No timeouts; recovery skips registered items | Timeouts → add K-item batching |
| V3 | #80 | Independent method change: bump only Picture Interpretation | Parse, OCR and formula work fully reused; no page reparse | Unexpected recompute → fix the reuse key |
| V4 | #80 | Failure matrix: one case per §6 class and mapping, plus a missing outcome record | Each case yields its expected outcome | — |
| V5 | #83 | Document Category and Document Summary accuracy; offline decision-model calibration on the DEV corpus | Judged test sets and thresholds; summary unsupported-statement rate reported | Below threshold → stay `unverified`, report to the PM |
| V6 | #80 | Summary API contract test against the mock | Adapter and post-hoc evidence alignment work | Real API only after #87 approval |

Evidence follows Q28: reports and hash manifests in git, raw outputs outside.

## 12. Map dispositions

| Map row | Disposition |
|---|---|
| Enrichment reuse and versioning rules | Resolved here (Q24); row removed |
| Retirement of the v1 PDF core | Resolved here (Q27, Q28); retirement PR follows |
| Markdown and PPTX processing workflows | New row (Q25) |

## Sources

- #84 decision record (D1–U5): <https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6292852297>
- #72 processing-profile handoff (required OCR rule, Q12 envelope): <https://github.com/davidlinnnn/data-ingestion/issues/72#issuecomment-6124692207>
- v1 calibration (group5, concurrency not admitted, read amplification): `tests/pdf_processing/t09b/SUPPORTED-CONFIGURATION.md` at tag `archive/pdf-core-v1`
- Canonical contract Enrichment group: [canonical contract](knowledge-platform-canonical-contract-draft.md) §2
- Canonical design Q10–Q11, ADR-0001, ADR-0003: [canonical design](knowledge-platform-canonical-design.md)
- Admission spec §7, §9, §10 and the status reporting contract: [admission spec](knowledge-platform-admission-spec.md), [admission notes](knowledge-platform-admission.md)
- Temporal Worker Versioning (minimum self-hosted server v1.29.1, Pinned, Ramping): <https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning>
- Docling `ConversionStatus` includes `PARTIAL_SUCCESS` (docling `datamodel/base_models.py`), cited as prior art for per-item partial success
