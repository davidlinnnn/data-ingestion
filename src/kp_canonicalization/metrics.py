"""The processing metrics of #93 §6 (#136), in the prometheus_client default registry, served
by each worker on its --metrics-port. Names are provisional until #78's naming conventions.
Labels stay low-cardinality; correlation IDs go to logs and search attributes, never here.

The status-stage durations (prepare, parse, enrich, finalize) come from workflow code, which
only the Temporal runtime's replay-safe meter may record: the workflow records them under
STAGE_DURATION on the worker's --temporal-metrics-port. Here, stage duration covers the
internal Activities.
"""

from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from kp_canonicalization.workflow import STAGE_DURATION

STAGE_BUCKETS = (1, 5, 15, 30, 60, 120, 240, 480, 900, 1800)

# Always 1: join on it to split any metric here by Worker Deployment and build. The Temporal
# runtime's metrics carry the same two labels themselves.
build_info = Gauge(
    "kp_canonicalization_build_info",
    "The worker's Worker Deployment and build ID",
    ["worker_deployment", "build_id"],
)

stage_duration = Histogram(
    STAGE_DURATION, "Wall time per internal Activity", ["stage", "tier"], buckets=STAGE_BUCKETS
)
stage_work = Counter(
    "kp_canonicalization_stage_work",
    "Pages parsed and items enriched or checked, reuse excluded",
    ["stage", "tier"],
)
item_outcomes = Counter(
    "kp_canonicalization_item_outcomes",
    "Enrichments by Enrichment Status and reason; a Quality Check's judgements under its own "
    "method, with status not_run, disputed or unverified",
    ["method", "status", "reason"],
)
document_outcomes = Counter(
    "kp_canonicalization_document_outcomes", "Completed and failed documents", ["outcome", "tier"]
)
queue_age = Histogram(
    "kp_canonicalization_queue_age_seconds",
    "Schedule-to-start latency per task queue",
    ["task_queue", "tier"],
    buckets=(0.1, 0.5, 1, 5, 15, 30, 60, 120, 300, 600),
)
external_requests = Counter(
    "kp_canonicalization_external_requests",
    "External requests per service, retries included",
    ["service", "outcome", "reason"],
)
external_request_duration = Histogram(
    "kp_canonicalization_external_request_duration_seconds",
    "Latency per external request",
    ["service"],
    buckets=(0.25, 0.5, 1, 2, 3, 5, 10, 20, 30, 60, 120),
)
external_tokens = Counter(
    "kp_canonicalization_external_tokens",
    "Tokens per service, from receipts",
    ["service", "direction"],
)
item_attempts = Histogram(
    "kp_canonicalization_item_attempts",
    "External sends per item, earlier attempts' receipts included",
    ["service"],
    buckets=(1, 2, 3, 4, 5),
)


def external_request(
    service: str, result: str, reason: str | None, seconds: float, usage: dict[str, Any] | None
) -> None:
    """One completed send, as its receipt records it."""
    external_requests.labels(service, result, reason or "").inc()
    external_request_duration.labels(service).observe(seconds)
    usage = usage or {}
    # OpenAI names its counts prompt_tokens and completion_tokens, System One input_tokens and
    # output_tokens.
    external_tokens.labels(service, "input").inc(
        usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    )
    external_tokens.labels(service, "output").inc(
        usage.get("completion_tokens") or usage.get("output_tokens") or 0
    )
