# PDF processing inference calls and capacity

The design result of
[設計 PDF workflow 的外部推論呼叫規則、併發吞吐與容量模型](https://github.com/davidlinnnn/data-ingestion/issues/93),
confirmed with the user on 2026-10-22 and 2026-10-23 (grilling rounds 1–3,
Q1–Q17, including an independent review whose findings became round 3). It
builds on the
[PDF processing workflow v2](knowledge-platform-processing-workflow-v2.md)
stage graph and defines the external inference call rules, worker pools,
priority tiers, the processing metric list, and the parameterized capacity
model. Domain terms follow `CONTEXT.md`.

All numeric values in this document are **initial parameters**: the first
confirmed value set for the v2 implementation, versioned inside the Processing
Profile and revised through a new profile version after the V2/V7–V10
measurements. They are not SLOs and not qualified capacity claims.

## 1. Scope and owners

| Topic | Owner |
|---|---|
| Stage graph, durability units, failure semantics, Processing Result | [workflow v2](knowledge-platform-processing-workflow-v2.md) (#91, closed) |
| External call rules, worker pools, priority tiers, metric list, capacity model | this document |
| Temporal deployment, metric naming conventions, platform sizing | #78 (consumes §8–§9) |
| PROD high-frequency load targets, peak shape, PROD latency targets | #88 (10M active documents, 10k updates/day confirmed; rest open) |
| Implementation and validation V7–V9 | #80 |
| Company VLM probe (V10) | user, research pack 1-B/1-C |
| Egress governance for inference services | #87 |
| Model-grade qualification gate (company VLM vs Sol) | #83 |

## 2. Decisions

| Q | Decision |
|---|---|
| Q1 | Company facts: the VLM is **Qwen3.8-27B** (native vision-language, Apache-2.0, 262k context; thinking on by default — reasoning tokens count against TPM, so the probe records thinking on/off separately) behind a TPM-metered endpoint; TPM is requested per need, so TPM is a capacity-model parameter, not a fixed constraint. Temporal is deployed and operated by the platform team itself with no external quota: Temporal limits are outputs of this design (handed to #78), not inputs. The quality probe (research pack 1-B/1-C) has not run; the model-grade gate stays with #83. |
| Q2 | Concurrency control uses Temporal-native mechanisms only: dedicated task queues (§4), worker activity slots bound the concurrent documents, an in-Activity request-concurrency cap bounds HTTP parallelism per document, and the task-queue rate limit (`max_task_queue_activities_per_second`) is the fleet-wide valve once the worker fleet grows. No custom distributed rate limiter. |
| Q3 | Two worker pools in one Worker Deployment Version: a CPU pool (prepare, parse, assemble, inventory, local enrichment, finalize; one parser per worker, 4 GiB guard) and an I/O pool (VLM enrichment, summary enrichment; small pods, high slots). |
| Q4 | Three-layer hard timeout: an in-code per-request deadline that force-cancels and closes the connection (the #84 dead-socket lesson), a heartbeat timeout that catches a hung worker, and start-to-close as the final backstop. |
| Q5 | Billing receipts: a durable per-attempt receipt is written **before** each outbound request; retries read receipts first, so attempt counts survive Activity reschedules and the same item is never blindly re-billed. Temporal heartbeat details are a best-effort resume hint only, never the ledger. |
| Q6 | Retry matrix by failure class with a stage budget derived from the 10-minute searchability target (§3.4). Refusals are never retried. |
| Q7 | Priority tiers align with the admission `priority` field: `normal` (everything a Source submits, **including the initial batch**) and `bulk` = admission `low` (platform-generated work: operator redrive, platform refresh — method-upgrade reprocessing and full rebuild). Normal capacity is reserved and never consumed by bulk; bulk capacity is elastic, scaled per planned event and sized against the event target. No preemption, no dynamic scheduling, no admission-contract change. Replaces the round-1 classification that put the initial batch in bulk, which the independent review showed breaks the 1-hour initial-batch target. |
| Q8 | Cost caps: a per-document external-request cap derived from the inventory (= 3 × items + 20); exceeding it is a `configuration` platform error (it indicates a bug) and fails the document. The deployment-level daily quota only alerts, never auto-blocks. |
| Q9 | The capacity model is a parameterized formula set in this document with two anchor points (pilot and PROD) plus a worst-case latency decomposition against the 10-minute target; #88 numbers substitute directly. |
| Q10 | Metric labels are low-cardinality only (stage, method, status, reason, service, tier). `request_id`, `document_uid`, `trace_id` live in structured logs and Temporal search attributes, never in metric labels. |
| Q11 | The initial parameter table (§7). Named "initial parameters", not "v1", to avoid collision with the retired v1 PDF core. |
| Q12 | Capacity headline numbers (§8): pilot requests 50k TPM, 3 normal CPU workers and small I/O pods; PROD is handed over as a scenario table (§8.4) because worker count depends on peak shape and PROD latency targets, which are open #88 items. Early action: sound out the company on the 0.5–1.5M TPM tier. |
| Q13 | Measurements V7–V9 are #80 validation work (Codex executes during implementation); V7's kill mechanism is additionally probed in this ticket with a throwaway prototype. The company VLM probe is V10, owned by the user via the research pack. |
| Q14 | (review F1/F5) Tier mapping and queue topology as in Q7/§4–§5; the two-value priority cannot express "large Source batch vs concurrent single updates" at PROD scale — recorded as a known limitation and handed to #88. |
| Q15 | (review F2) Pilot normal CPU tier is **3 workers**; V8 gains the freshness pass criterion (5 simultaneous documents each searchable within 10 minutes); the pre-agreed fallback is scaling to 5 workers, a pure deployment parameter. |
| Q16 | (review F3) The PROD anchor is a scenario table consistent with the formulas (§8.4); the previous "30–40 workers" figure was not a formula output and is withdrawn. |
| Q17 | (review F13, dismissed) "Qwen3.8-27B" verified against its Hugging Face page on 2026-10-23; the reviewer's doubt was a knowledge-cutoff artifact. |

## 3. External call rules

Two external services exist in v2: the VLM endpoint (Picture Interpretation,
formulas, Document Category) and the summary API (Document Summary). The rules
below apply to both; the summary API keeps its adapter seam and DEV mock.

### 3.1 Concurrency control (Q2)

```
configured ceiling per service = Σ over its task queues (workers × activity slots) × c
effective concurrency          ≈ min(configured ceiling, concurrent documents × c)
```

- Each external service has one task queue **per tier** (§4); its worker
  slots bound how many documents are in that enrichment at once.
- Inside an Activity, items are dispatched with a bounded concurrency `c`
  (initial: 4) rather than sequentially or unboundedly.
- At pilot scale the binding constraint is concurrent documents (≤ 5 normal
  + 2 bulk), so effective VLM concurrency stays ≤ 28 and typically ≤ 20;
  V8 enforces the configured ceiling (28).
- When the fleet grows (PROD), the Temporal task-queue rate limit is the
  single fleet-wide valve, set from the granted TPM (§8).
- 429 responses are backpressure, honored by the retry matrix; the platform
  never spins on a saturated service.

### 3.2 Hard timeouts (Q4)

| Layer | Mechanism | Catches |
|---|---|---|
| 1. Per-request deadline | `asyncio.wait_for` (or equivalent) wrapping the whole HTTP call; on expiry the request is cancelled and the connection closed. HTTP-client timeouts are configured but not trusted | Dead sockets (#84: a hung socket survived a client timeout for 30 minutes) |
| 2. Heartbeat timeout | Heartbeat after each completed item and at least every 15 s; timeout set per service above its per-request deadline (§7) | A hung or dead worker; Temporal reschedules the Activity, which skips registered items |
| 3. Start-to-close | Computed per document: `items / c × deadline × attempts + 5 min` | Final backstop only; never the primary control |

### 3.3 Billing receipts (Q5)

- Before each outbound request the Activity durably writes an attempt receipt:
  item id, method id@version, attempt number, parameter digest, timestamp.
  After the response it is completed with latency, token counts and a result
  digest.
- Retry logic reads receipts first: an item whose receipts reach the attempt
  cap is marked `failed` instead of re-sent. Writing before sending errs
  toward under-spending, never double-billing.
- Receipts live in the attempt scratch area of the object store (workflow v2
  §10). As the audit trail for the TPM quota they outlive ordinary scratch:
  retained at least 30 days after the request is terminal (aligned with the
  admission request-record retention; a parameter). Aggregate counts feed the
  metrics and persist beyond that.
- Rationale: Temporal guarantees at-least-once Activity execution; its attempt
  counter is per-Activity (not per-item) and heartbeat details are throttled
  and best-effort, so they serve as a resume hint only. If the company
  endpoint ever supports idempotency keys (research pack 1-A follow-up),
  server-side dedup is added on top; it is not assumed.

### 3.4 Retry matrix and budget (Q6)

| Failure class | Retry | Terminal outcome |
|---|---|---|
| Timeout, connection failure, 5xx, 429 | Exponential backoff with jitter: initial 2 s, ×2, cap 30 s; at most 3 attempts per item, bounded by the stage budget | `failed` / `SERVICE_UNAVAILABLE`; document completes; redrive path (workflow v2 Q23) |
| Schema-invalid, empty output | 1 retry with identical parameters | `failed` (content) |
| Model refusal | None (re-sending wastes quota) | `failed` (content) |

The enrichment stage budget is derived from the 10-minute searchability
target, not from Activity timeouts (#91 handoff): initial p50 ≈ 2 min, hard
budget 4 min for an ordinary document. The budget is enforced as an **in-code
deadline on each item's retry chain** (no retry is scheduled past it);
start-to-close stays a backstop. V2 measures the whole chain and adjusts.

### 3.5 Cost metering and caps (Q8)

- Metering: request counts and input/output tokens per service are metrics;
  receipts are the per-request ledger. Thinking-mode reasoning tokens count:
  the probe (V10) records thinking on/off separately before `T` is trusted.
- Per-document cap: total external requests ≤ `3 × inventory items + 20`.
  Exceeding it is a `configuration` platform error and fails the document — a
  runaway loop, not a content problem.
- Deployment daily quota: an alert threshold on aggregate tokens per day; it
  warns, it does not block (pilot scale: false-positive circuit-breaking costs
  more than overspend).

## 4. Worker pools and queue topology (Q3, Q14)

Six task queues: {cpu, vlm, summary} × {normal, bulk}. Both pools belong to
one Worker Deployment Version, so workflow v2 Q32 (Pinned versioning) is
unchanged. The pools scale independently: CPU worker count and VLM concurrency
are independent outputs of the capacity model and map one-to-one to deployment
parameters (#78).

| Pool | Activities | Shape | Pilot workers × slots |
|---|---|---|---|
| CPU normal | prepare, parse, assemble, inventory, local enrichment, finalize | 4 CPU / 5 GiB class; one parser per worker (v1 calibration, 4 GiB guard) | 3 × 1 |
| CPU bulk | same, for `low` requests | same | 0–1 idle; scaled per event (§5) |
| I/O normal | VLM enrichment, summary enrichment | 0.5 CPU / 512 MiB class | vlm 5, summary 5 (one pod) |
| I/O bulk | same, for `low` requests | same | vlm 2, summary 2 |

## 5. Priority tiers (Q7, Q14)

- Mapping: admission `priority: normal` → normal tier (all Source
  submissions, including the initial batch — a Source is waiting on them);
  admission `priority: low` → bulk tier (platform-generated work: operator
  redrive, platform refresh, i.e. method-upgrade reprocessing and full
  rebuild — nothing is waiting urgently). No admission-contract change.
- Normal capacity is reserved: bulk never consumes it. Bulk capacity is
  elastic, scaled per planned event and sized against the event target:
  a ≤50-paper full rebuild on 1 bulk CPU worker parses in ≈3 h, inside the
  8 h Retrieval target.
- Initial-batch check (review F1): 20 papers on 3 normal workers parse in
  ≈25 min; with enrichment pipelined the batch completes well inside the
  1-hour target. During that window a concurrent single update can exceed
  10 minutes; the first-adoption targets validate the initial batch
  separately and it is a scheduled event, so this is accepted for the pilot.
- **Known limitation (to #88):** two priority values cannot express "large
  Source batch vs concurrent single updates". At PROD scale (10k/day, many
  Sources) a big `normal` batch can starve single-document updates; a third
  value or batch-aware scheduling is decided with the #88 load shape.

## 6. Observability (Q10)

Metric names and units follow the #78 conventions; this list is the
processing-side contract. Labels are low-cardinality: `stage`, `method`
(id@version), `status`, `reason`, `service`, `tier`. Correlation identifiers
(`request_id` = workflow ID, `document_uid`, `source_revision_id`,
`trace_id`) go to structured logs and Temporal search attributes, never into
metric labels.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| stage duration | histogram | stage, tier | Wall time per stage (the four status stages plus internal Activities) |
| stage work volume | counter | stage, tier | Pages parsed, items enriched |
| item outcomes | counter | method, status, reason | Per-item results by Enrichment Status and failure reason |
| document outcomes | counter | outcome, tier | Completed / failed documents |
| queue age | histogram | task queue, tier | Schedule-to-start latency per task queue |
| external requests | counter | service, outcome, reason | Calls per service, including retries |
| external request duration | histogram | service | Per-request latency |
| external tokens | counter | service, direction | Input/output tokens (from receipts) |
| attempts per item | histogram | service | Detects systematic retrying |

Operator alerts (metrics only, no `attention[]` — workflow v2 Q15):

- per-method `failed` ratio over a sliding window exceeds its threshold;
- daily aggregate token consumption approaches the granted quota;
- queue age p95 over threshold per task queue (backlog forming).

## 7. Initial parameters (Q11)

Versioned inside the Processing Profile; revised via a new profile version
after V2/V7–V10 measurements.

| Parameter | Initial value | Basis |
|---|---|---|
| VLM per-request deadline | connect 5 s / total 60 s, force-closed | #84: seconds-level latency; 20× headroom |
| Summary per-request deadline | 120 s | Document-level; contract undecided |
| Heartbeat | per completed item and at least every 15 s | Progress signal and resume hint |
| Heartbeat timeout | VLM Activity 90 s; summary Activity 150 s | Per-request deadline + 30 s per service |
| Start-to-close (external Activities) | `items / c × deadline × attempts + 5 min` | Backstop only |
| Retry backoff | initial 2 s, ×2, cap 30 s, jitter, ≤3 attempts | Q6 |
| In-Activity VLM concurrency `c` | 4 per document | ~30 requests/document → ~23 s wall |
| CPU workers | normal 3; bulk 0–1, event-scaled | Q15; §8.3 decomposition |
| I/O slots | normal: vlm 5, summary 5; bulk: vlm 2, summary 2 | Concurrent documents bound them (§3.1) |
| Per-document request cap | `3 × inventory items + 20` → `configuration` failure | Q8 |
| Task-queue rate limit | off in pilot; set from granted TPM in PROD | Q2 |
| Document Category placement | VLM Activity (+1 request/document) | Capacity assumption |
| Enrichment stage budget | p50 2 min, hard 4 min; in-code deadline on each item's retry chain | 10-minute target decomposition |
| Receipt retention | ≥ 30 days after request terminal | Quota audit (§3.3) |

## 8. Capacity model (Q9, Q12, Q15, Q16)

### 8.1 Parameters

| Symbol | Meaning | Pilot default | PROD default |
|---|---|---|---|
| λ | document arrival rate | 5 / 10 min (peak, #54 Q14) | 10,000 / day (#88); mean ≈ 6.94 / min |
| k | peak factor on the mean | — (λ is already peak) | 3 (assumed; #88 open) |
| P | pages per document (typical) | 20 (#84 corpus ≈ 19.9) | 20 |
| R | VLM requests per document | ≈ 30 (pictures ~10 + formulas ~15 + category 1 + slack) | 30 |
| T | tokens per VLM request | ≈ 2.5k (image ~1.2k + prompt + output; thinking off — V10 verifies) | 2.5k |
| t_page | parse seconds per page | 10.5 (median, #84 DEV) | 10.5 |
| t_vlm | VLM seconds per request | 3 | 3 |
| o | non-parse CPU overhead factor (prepare, assemble, inventory, local OCR, finalize ≈ 10% of parse) | 1.1 | 1.1 |
| U | target worker utilization | 0.8 | 0.8 |

The summary API adds 1 request per document (document-scope, 120 s deadline,
DEV mock; real contract undecided). Its load is negligible against the VLM
(1 vs ~30 requests) and it runs on the same I/O pool; it gets a capacity row
when its contract lands. The three enrichment Activities run in parallel
(workflow v2 §3), so I/O-pool slots assume a document can hold a VLM and a
summary Activity at once.

### 8.2 Steady-state formulas

```
TPM            = λ(/min) × k × R × T
VLM concurrent = λ(/min) × k × R × t_vlm / 60
CPU workers    = λ(/min) × k × P × t_page × o / (60 × U)
```

### 8.3 Worst-case latency decomposition (the 10-minute check)

For a burst of B simultaneous normal documents on W normal CPU workers:

```
t_e2e(doc B) ≈ ceil(B / W) × (P × t_page) + t_assemble+inventory
               + t_enrich(p50) + t_finalize + t_accept+publish  ≤ 10 min
```

With B = 5 (the #54 Q14 envelope), P×t_page = 3.5 min, overheads ≈ 0.5 min,
enrichment p50 ≈ 1–2 min, accept+publish ≈ 1 min:

| W | doc-5 parse done | doc-5 e2e (p50) | Verdict |
|---|---|---|---|
| 2 | 10.5 min | ~13 min | Fails |
| **3** | 7 min | **~9.5 min** | Passes, ~0.5 min slack — V8 verifies |
| 5 | 3.5 min | ~6 min | Comfortable |

Pilot normal tier = **3 workers** (Q15); the pre-agreed fallback on a V8
freshness miss is 5 workers, a deployment parameter. Retry-exhausted cases
(the 4-minute hard budget) imply degraded dependencies, which the
first-adoption targets exclude. t_page is a DEV-laptop median; server CPUs
are expected to do no worse.

### 8.4 Anchor points

| Output | Pilot | PROD |
|---|---|---|
| VLM traffic | ~15 req/min ≈ 37.5k TPM → **request 50k TPM** | mean ~520k, peak ~1.56M TPM → **request the 0.5–1.5M TPM tier** |
| VLM concurrent requests | ≤ 20 effective; configured ceiling 28 | ~31 at peak |
| CPU workers | normal **3**, bulk 0–1 event-scaled | scenario table below |
| I/O workers | 1–2 small pods | 2–4 |

**PROD CPU scenario table (Q16).** The formula outputs, not a chosen number:
which scenario applies depends on peak duration and PROD latency targets,
both open #88 items. #88 decides; the numbers then substitute directly.

| Scenario | CPU workers | Consequence |
|---|---|---|
| Mean load only (6.94 docs/min) | ≈ 34 | Any sustained peak builds backlog |
| 10-minute target holds through a sustained 3× peak | ≈ 100 | Fleet sized for peak; idle at mean |
| 3× peak bounded at ≤ 15 min, 10-minute target relaxed during peaks | ≈ 40 | Backlog ≈ 175 docs per peak, drains in ≈ 80 min at mean load |

Notes:

- Temporal is self-operated (Q1): the model's workflow concurrency and action
  rates are sizing inputs for the #78 Temporal deployment, not external
  quotas. Server defaults (2 MB payload, history size caps) remain the
  engineering envelope; v2 already passes references only.
- 10M active documents drives storage and registration sizing (#57, #78),
  not call rules.
- Early action (Q12): take the PROD TPM tier (0.5–1.5M) to the company VLM
  owners to sound out feasibility before implementation hardens around it.

## 9. Validation work (Q13, Q15)

V7–V9 extend workflow v2's V1–V6 and belong to #80; Codex executes them
during implementation so the measurements exercise the real code. V7's kill
mechanism is additionally probed with a throwaway prototype during this
ticket (prototype branch linked from the ticket). V10 is the company VLM
probe, owned by the user.

| # | Owner | Check | Fixed case | Pass | Stop or fallback |
|---|---|---|---|---|---|
| V7 | #80 | Dead-socket forced termination (the #84 30-minute hang as a regression test) | Mock service accepts the connection and never responds (and a stall-mid-body variant) | Force-closed within deadline + 5 s; receipts complete; retries follow the matrix; item ends `failed`/`SERVICE_UNAVAILABLE`; document completes | Cannot be killed → switch HTTP client or add process-level isolation |
| V8 | #80 | Multi-document concurrency, backpressure and freshness | 5 documents submitted simultaneously; mock VLM at 3 s latency; pilot-shaped deployment (3 normal CPU workers) | Effective concurrency never exceeds the configured ceiling (28); queue-age metrics emitted; no cross-document starvation; **each document searchable within 10 minutes** (DEV chain) | Caps not enforced → fix pool configuration; freshness miss → scale normal tier to 5 workers (pre-agreed) |
| V9 | #80 | Receipt overhead | One document, 30 requests | Added latency p95 < 100 ms per request | Over budget → batch receipt writes |
| V10 | user (research pack 1-B/1-C) | Company VLM facts and grade probe | 1-A fact list; T1–T10 crops; 1-C strict-JSON, logprobs, 5-serial + 5-concurrent latency; thinking on/off recorded separately | Pilot 50k TPM attainable; strict JSON schema usable (or JSON mode + validator fallback); latency consistent with t_vlm = 3 s; grade comparison goes to #83 | TPM unattainable → renegotiate c and budgets; schema unsupported → prompt-constrained JSON + validator; grade below bar → #83 blocks PROD adoption (not this ticket) |

V10 does not block this design: every dependent number is a parameter
revisable through a Processing Profile version.

## 10. Handoffs

| To | What |
|---|---|
| #78 | §8 sizing outputs (worker counts, TPM request, VLM concurrency, PROD scenario table), Temporal deployment requirements (self-operated; workflow concurrency and action rates), metric naming conventions to fix |
| #88 | Confirmed ceiling recorded (10M active documents, 10k updates/day); open items now also include peak duration, PROD latency targets, and the priority-expressiveness limitation (§5) |
| #80 | Implementation scope: §3 call rules, §4 pools and queues, §5 tiers, §6 metrics, §7 parameters; V7–V9 |
| #83 | Model-grade gate unchanged; V10 grade comparison feeds it |
| #87 | Egress governance unchanged by this design |

## Sources

- #91 handoff comment (two external Activities, budget bound by the
  10-minute target, metric list ownership):
  <https://github.com/davidlinnnn/data-ingestion/issues/93#issuecomment-6328251148>
- Workflow v2 design: [knowledge-platform-processing-workflow-v2.md](knowledge-platform-processing-workflow-v2.md)
- Pilot targets (Q8/Q10/Q14/Q15, initial batch 1 h, rebuild 8 h):
  [first adoption](knowledge-platform-first-adoption.md)
- PROD ceiling (user-confirmed 2026-10-22):
  <https://github.com/davidlinnnn/data-ingestion/issues/88#issuecomment-6344327434>
- #84 measurements and the dead-socket incident:
  <https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6292852297>
- Company facts (TPM requested per need; Temporal self-operated, no external
  quota): user statements, 2026-10-22
- Company VLM model page: <https://huggingface.co/Qwen/Qwen3.8-27B>
  (verified 2026-10-23)
- Admission `priority` values (`normal`; `low` for operator redrive and
  platform refresh): [admission spec](knowledge-platform-admission-spec.md)
  §3, §9, §10; [admission notes](knowledge-platform-admission.md)
- Temporal worker tuning (activity slots, task-queue rate limit) and
  heartbeat throttling: <https://docs.temporal.io/develop/worker-performance>,
  <https://docs.temporal.io/encyclopedia/detecting-activity-failures#throttling>
- Independent review (2026-10-23): findings F1–F13; F1–F5 became Q14–Q16,
  F6–F12 became §3–§9 edits, F13 dismissed after source verification
