# PDF processing inference calls and capacity

The design result of
[設計 PDF workflow 的外部推論呼叫規則、併發吞吐與容量模型](https://github.com/davidlinnnn/data-ingestion/issues/93),
confirmed with the user on 2026-10-22 and 2026-10-23 (grilling rounds 1–2,
Q1–Q13). It builds on the
[PDF processing workflow v2](knowledge-platform-processing-workflow-v2.md)
stage graph and defines the external inference call rules, worker pools,
priority tiers, the processing metric list, and the parameterized capacity
model. Domain terms follow `CONTEXT.md`.

All numeric values in this document are **initial parameters**: the first
confirmed value set for the v2 implementation, versioned inside the Processing
Profile and revised through a new profile version after the V2/V7–V9
measurements. They are not SLOs and not qualified capacity claims.

## 1. Scope and owners

| Topic | Owner |
|---|---|
| Stage graph, durability units, failure semantics, Processing Result | [workflow v2](knowledge-platform-processing-workflow-v2.md) (#91, closed) |
| External call rules, worker pools, priority, metric list, capacity model | this document |
| Temporal deployment, metric naming conventions, platform sizing | #78 (consumes §8–§9) |
| PROD high-frequency load targets | #88 (10M active documents, 10k updates/day confirmed; rest open) |
| Implementation and validation V7–V9 | #80 |
| Egress governance for inference services | #87 |
| Model-grade qualification gate (company VLM vs Sol) | #83 |

## 2. Decisions

| Q | Decision |
|---|---|
| Q1 | Company facts: VLM is Qwen3.8-27B behind a TPM-metered endpoint; TPM is requested per need, so TPM is a capacity-model parameter, not a fixed constraint. Temporal is deployed and operated by the platform team itself with no external quota: Temporal limits are outputs of this design (handed to #78), not inputs. The quality probe (research pack 1-B/1-C) has not run; the model-grade gate stays with #83. |
| Q2 | Concurrency control uses Temporal-native mechanisms only: one dedicated task queue per external service, worker activity slots bound the concurrent documents, an in-Activity request-concurrency cap bounds HTTP parallelism per document, and the task-queue rate limit (`max_task_queue_activities_per_second`) is the fleet-wide valve once the worker fleet grows. No custom distributed rate limiter. |
| Q3 | Two worker pools in one Worker Deployment Version: a CPU pool (prepare, parse, assemble, inventory, local enrichment, finalize; one parser per worker, 4 GiB guard) and an I/O pool (VLM enrichment, summary enrichment; small pods, high slots). |
| Q4 | Three-layer hard timeout: an in-code per-request deadline that force-cancels and closes the connection (the #84 dead-socket lesson), a heartbeat timeout that catches a hung worker, and start-to-close as the final backstop. |
| Q5 | Billing receipts: a durable per-attempt receipt is written **before** each outbound request; retries read receipts first, so attempt counts survive Activity reschedules and the same item is never blindly re-billed. Temporal heartbeat details are a best-effort resume hint only, never the ledger. |
| Q6 | Retry matrix by failure class with a stage budget derived from the 10-minute searchability target (§5). Refusals are never retried. |
| Q7 | Two priority tiers, `normal` (ordinary adds/updates) over `bulk` (initial batch, full rebuild, method-upgrade reprocessing), implemented as a fixed 70/30 capacity split; no preemption, no dynamic scheduling. The admission `priority` field selects the tier. |
| Q8 | Cost caps: a per-document external-request cap derived from the inventory (= 3 × items + 20); exceeding it is a `configuration` platform error (it indicates a bug) and fails the document. The deployment-level daily quota only alerts, never auto-blocks. |
| Q9 | The capacity model is a parameterized formula set in this document with two anchor points (pilot and PROD); #88 numbers substitute directly. |
| Q10 | Metric labels are low-cardinality only (stage, method, status, reason, service, tier). `request_id`, `document_uid`, `trace_id` live in structured logs and Temporal search attributes, never in metric labels. |
| Q11 | The initial parameter table (§7). Named "initial parameters", not "v1", to avoid collision with the retired v1 PDF core. |
| Q12 | Capacity headline numbers (§8): pilot requests 50k TPM and 2–3 CPU workers; PROD (10k documents/day, peak factor 3) requests a 0.5–1.5M TPM tier and 30–40 CPU workers. Early action: sound out the company on the PROD TPM tier. |
| Q13 | Measurements V7–V9 are #80 validation work (Codex executes during implementation); the company VLM probe stays in the research pack (1-B/1-C) and feeds parameters when it returns. |

## 3. External call rules

Two external services exist in v2: the VLM endpoint (Picture Interpretation,
formulas, Document Category) and the summary API (Document Summary). The rules
below apply to both; the summary API keeps its adapter seam and DEV mock.

### 3.1 Concurrency control (Q2)

```
global concurrency to a service
  = (workers polling its task queue) × (activity slots per worker)
    × (in-Activity request concurrency)
```

- Each external service has a dedicated task queue; its worker slots bound how
  many documents are in that enrichment at once.
- Inside an Activity, items are dispatched with a bounded concurrency `c`
  (initial: 4) rather than sequentially or unboundedly.
- When the fleet grows (PROD), the Temporal task-queue rate limit is the
  single fleet-wide valve, set from the granted TPM (§8).
- 429 responses are backpressure, honored by the retry matrix; the platform
  never spins on a saturated service.

### 3.2 Hard timeouts (Q4)

| Layer | Mechanism | Catches |
|---|---|---|
| 1. Per-request deadline | `asyncio.wait_for` (or equivalent) wrapping the whole HTTP call; on expiry the request is cancelled and the connection closed. HTTP-client timeouts are configured but not trusted | Dead sockets (#84: a hung socket survived a client timeout for 30 minutes) |
| 2. Heartbeat timeout | Heartbeat after each completed item and at least every 15 s | A hung or dead worker; Temporal reschedules the Activity, which skips registered items |
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
  §10), within the processing retention window; aggregate counts feed the
  metrics. They are the audit trail for the TPM quota.
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
budget 4 min for an ordinary document. V2 measures the whole chain and
adjusts.

### 3.5 Cost metering and caps (Q8)

- Metering: request counts and input/output tokens per service are metrics;
  receipts are the per-request ledger.
- Per-document cap: total external requests ≤ `3 × inventory items + 20`.
  Exceeding it is a `configuration` platform error and fails the document — a
  runaway loop, not a content problem.
- Deployment daily quota: an alert threshold on aggregate tokens per day; it
  warns, it does not block (pilot scale: false-positive circuit-breaking costs
  more than overspend).

## 4. Worker pools (Q3)

| Pool | Activities | Shape | Slots |
|---|---|---|---|
| CPU | prepare, parse, assemble, inventory, local enrichment, finalize | 4 CPU / 5 GiB class; one parser per worker (v1 calibration, 4 GiB guard) | 1–2 |
| I/O | VLM enrichment, summary enrichment | 0.5 CPU / 512 MiB class | 16 |

Both pools belong to one Worker Deployment Version, so workflow v2 Q32
(Pinned versioning) is unchanged. The pools scale independently: CPU worker
count and VLM concurrency are the two independent outputs of the capacity
model and map one-to-one to deployment parameters (#78).

## 5. Priority tiers (Q7)

- Tiers: `normal` (ordinary adds and updates) and `bulk` (initial batch, full
  rebuild, method-upgrade reprocessing). The admission `priority` field maps
  the request to a tier.
- Mechanism: fixed capacity split 70/30 (normal/bulk) in both pools —
  pilot CPU pool: 2 workers normal + 1 bulk. No preemption, no dynamic
  scheduling; the rebuild target (Retrieval 8 h for ≤50 papers) has enormous
  slack, so reserved normal capacity is enough to protect the 10-minute
  target.
- Finer scheduling waits for observed PROD load shapes (#88).

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
after V2/V7–V9 measurements.

| Parameter | Initial value | Basis |
|---|---|---|
| VLM per-request deadline | connect 5 s / total 60 s, force-closed | #84: seconds-level latency; 20× headroom |
| Summary per-request deadline | 120 s | Document-level; contract undecided |
| Heartbeat | per completed item and at least every 15 s; timeout 90 s | > per-request deadline, avoids false kills |
| Start-to-close (external Activities) | `items / c × deadline × attempts + 5 min` | Backstop only |
| Retry backoff | initial 2 s, ×2, cap 30 s, jitter, ≤3 attempts | Q6 |
| In-Activity VLM concurrency `c` | 4 per document | ~30 requests/document → ~23 s wall |
| I/O pool slots | 16 per worker | I/O-bound |
| normal/bulk split | 70/30 both pools | Q7 |
| Per-document request cap | `3 × inventory items + 20` → `configuration` failure | Q8 |
| Task-queue rate limit | off in pilot; set from granted TPM in PROD | Q2 |
| Document Category placement | VLM Activity (+1 request/document) | Capacity assumption |
| Enrichment stage budget | p50 2 min, hard 4 min | 10-minute target decomposition |

## 8. Capacity model (Q9, Q12)

### 8.1 Parameters

| Symbol | Meaning | Pilot default | PROD default |
|---|---|---|---|
| λ | document arrival rate | 5 / 10 min (peak, #54 Q14) | 10,000 / day (#88); mean ≈ 6.94 / min |
| k | peak factor on the mean | — (λ is already peak) | 3 |
| P | pages per document (typical) | 20 (#84 corpus ≈ 19.9) | 20 |
| R | VLM requests per document | ≈ 30 (pictures ~10 + formulas ~15 + category 1 + slack) | 30 |
| T | tokens per VLM request | ≈ 2.5k (image ~1.2k + prompt + output) | 2.5k |
| t_page | parse seconds per page | 10.5 (median, #84 DEV) | 10.5 |
| t_vlm | VLM seconds per request | 3 | 3 |
| U | target worker utilization | 0.8 | 0.8 |

### 8.2 Formulas

```
TPM            = λ(/min) × k × R × T
VLM concurrent = λ(/min) × k × R × t_vlm / 60
CPU workers    = λ(/min) × k × P × t_page / (60 × U)
```

### 8.3 Anchor points

| Output | Pilot | PROD |
|---|---|---|
| VLM traffic | ~15 req/min ≈ 37.5k TPM → **request 50k TPM** | mean ~520k, peak ~1.56M TPM → **request the 0.5–1.5M TPM tier** |
| VLM concurrent requests | ≤ 20 | ~31 at peak |
| CPU parse workers | **2** (3 with headroom) | mean **25**, peak smoothed by queueing → **30–40** |
| I/O workers | 1–2 small pods | 2–4 |

Notes:

- The PROD column substitutes the #88 confirmed ceiling (10k updates/day);
  the peak factor 3, document mix and remaining #88 items (peak duration,
  scan ratio, latency targets) are open parameters.
- Temporal is self-operated (Q1): the model's workflow concurrency and action
  rates are sizing inputs for the #78 Temporal deployment, not external
  quotas. Server defaults (2 MB payload, history size caps) remain the
  engineering envelope; v2 already passes references only.
- 10M active documents drives storage and registration sizing (#57, #78),
  not call rules.
- Early action (Q12): take the PROD TPM tier (0.5–1.5M) to the company VLM
  owners to sound out feasibility before implementation hardens around it.

## 9. Validation work (Q13)

V7–V9 extend workflow v2's V1–V6 and belong to #80; Codex executes them
during implementation so the measurements exercise the real code. The company
VLM probe (latency, concurrency, TPM behavior, idempotency support) remains
research-pack item 1-B/1-C and substitutes parameters when it returns.

| # | Owner | Check | Fixed case | Pass | Stop or fallback |
|---|---|---|---|---|---|
| V7 | #80 | Dead-socket forced termination (the #84 30-minute hang as a regression test) | Mock service accepts the connection and never responds (and a stall mid-body variant) | Force-closed within deadline + 5 s; receipts complete; retries follow the matrix; item ends `failed`/`SERVICE_UNAVAILABLE`; document completes | Cannot be killed → switch HTTP client or add process-level isolation |
| V8 | #80 | Multi-document concurrency and backpressure | 5 documents submitted together; mock VLM at 3 s latency | Slot caps hold (global concurrency never exceeds the computed bound); queue-age metrics emitted; no cross-document starvation | Caps not enforced → fix pool configuration |
| V9 | #80 | Receipt overhead | One document, 30 requests | Added latency p95 < 100 ms per request | Over budget → batch receipt writes |

## 10. Handoffs

| To | What |
|---|---|
| #78 | §8 sizing outputs (worker counts, TPM request, VLM concurrency), Temporal deployment requirements (self-operated, workflow concurrency and action rates), metric naming conventions to fix |
| #88 | Confirmed ceiling recorded (10M active documents, 10k updates/day); remaining items stay open there |
| #80 | Implementation scope: §3 call rules, §4 pools, §5 tiers, §6 metrics, §7 parameters; V7–V9 |
| #83 | Model-grade gate unchanged; quality probe pending (research pack 1-B) |
| #87 | Egress governance unchanged by this design |

## Sources

- #91 handoff comment (two external Activities, budget bound by the
  10-minute target, metric list ownership):
  <https://github.com/davidlinnnn/data-ingestion/issues/93#issuecomment-6328251148>
- Workflow v2 design: [knowledge-platform-processing-workflow-v2.md](knowledge-platform-processing-workflow-v2.md)
- Pilot targets (Q8/Q10/Q14/Q15): [first adoption](knowledge-platform-first-adoption.md)
- PROD ceiling (user-confirmed 2026-10-22):
  <https://github.com/davidlinnnn/data-ingestion/issues/88#issuecomment-6344327434>
- #84 measurements and the dead-socket incident:
  <https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6292852297>
- Company facts (Qwen3.8-27B, TPM requested per need; Temporal self-operated,
  no external quota): user statements, 2026-10-22
- Temporal worker tuning (activity slots, task-queue rate limit) and
  heartbeat throttling: <https://docs.temporal.io/develop/worker-performance>,
  <https://docs.temporal.io/encyclopedia/detecting-activity-failures#throttling>
- Admission correlation fields and status reporting:
  [admission spec](knowledge-platform-admission-spec.md) §3, §9
