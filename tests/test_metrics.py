"""The processing metrics (#93 §6, #136) after a paper runs through the real workflow: the
Activity-side ones in the prometheus_client registry, the status-stage durations through the
Temporal runtime's meter. Binds a local port."""

import json
import shutil
import uuid

import pytest
from prometheus_client import REGISTRY
from temporalio.runtime import MetricBuffer, Runtime, TelemetryConfig
from temporalio.testing import WorkflowEnvironment

from tests.pdfs import encrypt, paper, write_pdf
from tests.stages.conftest import start_input
from tests.stages.test_parse import seven_pages
from tests.test_workflow import process

pytestmark = pytest.mark.network

INFERENCE_ACTIVITIES = 4  # parse_group x 2, assemble, enrich_local for seven pages
ORCHESTRATION_ACTIVITIES = 13  # prepare, inventory, finalize and ten status reports


def sample(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def samples(name: str) -> dict[tuple, float]:
    """Every sample of one metric family's series, keyed by its sorted label items."""
    return {
        tuple(sorted(s.labels.items())): s.value
        for family in REGISTRY.collect()
        for s in family.samples
        if s.name == name
    }


def delta(before: dict[tuple, float], after: dict[tuple, float]) -> dict[tuple, float]:
    return {k: v - before.get(k, 0.0) for k, v in after.items() if v != before.get(k, 0.0)}


async def test_a_processed_paper_emits_the_activity_metrics(client, ports, runtime):
    names = [
        "kp_canonicalization_stage_duration_seconds_count",
        "kp_canonicalization_stage_work_total",
        "kp_canonicalization_item_outcomes_total",
        "kp_canonicalization_document_outcomes_total",
        "kp_canonicalization_queue_age_seconds_count",
        "kp_canonicalization_external_requests_total",
        "kp_canonicalization_external_request_duration_seconds_count",
        "kp_canonicalization_external_tokens_total",
        "kp_canonicalization_item_attempts_count",
        "kp_canonicalization_item_attempts_sum",
    ]
    before = {name: samples(name) for name in names}
    start = await start_input(ports, seven_pages(), request_id=f"req_{uuid.uuid4().hex[:8]}")

    outcome, _ = await process(client, ports, runtime, start)

    assert outcome["outcome"] == "complete"
    result = json.loads(await ports.store.get(outcome["manifest_ref"]))
    items = len(json.loads(await ports.store.get(result["inventory"]["ref"]))["items"])
    d = {name: delta(before[name], samples(name)) for name in names}
    normal = ("tier", "normal")

    # prepare and finalize are status stages, timed by the workflow instead.
    assert d["kp_canonicalization_stage_duration_seconds_count"] == {
        (("stage", "parse_group"), normal): 2,
        (("stage", "assemble"), normal): 1,
        (("stage", "inventory"), normal): 1,
        (("stage", "enrich_local"), normal): 1,
        (("stage", "enrich_vlm"), normal): 1,
        (("stage", "summary_sections"), normal): 1,
        (("stage", "summary_chunk"), normal): 1,
        (("stage", "summary_overview"), normal): 1,
        (("stage", "check"), normal): 1,
        (("stage", "report"), normal): 10,
    }
    work = d["kp_canonicalization_stage_work_total"]
    assert work[(("stage", "parse_group"), normal)] == 7
    enriched = ("enrich_", "summary_overview")  # the summary's one item
    assert sum(v for k, v in work.items() if k[0][1].startswith(enriched)) == items
    outcomes = d["kp_canonicalization_item_outcomes_total"]
    # The Quality Check's judgements are counted besides the enrichments, under its own method.
    judged = sum("d3" in e["signals"] for e in result["enrichments"])
    of_check = {k: v for k, v in outcomes.items() if k[0] == ("method", "d3-check@1")}
    assert sum(of_check.values()) == judged > 0
    assert sum(outcomes.values()) - judged == len(result["enrichments"])
    assert work[(("stage", "check"), normal)] == judged
    assert outcomes[(("method", "picture-ocr@1"), ("reason", "NO_TEXT"),
                     ("status", "unverified"))] == 2  # fmt: skip
    assert d["kp_canonicalization_document_outcomes_total"] == {
        (("outcome", "complete"), normal): 1
    }
    assert d["kp_canonicalization_queue_age_seconds_count"] == {
        (("task_queue", "paper-pdf-1.orchestration"), normal): ORCHESTRATION_ACTIVITIES,
        (("task_queue", "paper-pdf-1.inference"), normal): INFERENCE_ACTIVITIES,
        (("task_queue", "paper-pdf-1.vlm"), normal): 1,
        (("task_queue", "paper-pdf-1.summary"), normal): 3,
        (("task_queue", "paper-pdf-1.d3"), normal): 1,
    }
    # Two pictures (one VLM request each); the summary of four sections of one sentence each
    # (docling reads sections 1 and 7 as empty; page 6 has no text layer): one map, four
    # verify, one reduce and four overview verify; one d3 request per judged item. All answered
    # at the first send.
    assert d["kp_canonicalization_external_requests_total"] == {
        (("outcome", "ok"), ("reason", ""), ("service", "vlm")): 2,
        (("outcome", "ok"), ("reason", ""), ("service", "summary")): 10,
        (("outcome", "ok"), ("reason", ""), ("service", "d3")): judged,
    }
    assert d["kp_canonicalization_external_request_duration_seconds_count"] == {
        (("service", "vlm"),): 2,
        (("service", "summary"),): 10,
        (("service", "d3"),): judged,
    }
    # System One reports input_tokens and output_tokens: 591 and 0 from the d3 fake.
    tokens = d["kp_canonicalization_external_tokens_total"]
    assert tokens[(("direction", "input"), ("service", "d3"))] == 591 * judged
    assert (
        d["kp_canonicalization_external_tokens_total"][(("direction", "input"), ("service", "vlm"))]
        == 2
    )
    assert (
        d["kp_canonicalization_external_tokens_total"][
            (("direction", "output"), ("service", "vlm"))
        ]
        == 2
    )
    assert d["kp_canonicalization_item_attempts_count"] == {
        (("service", "vlm"),): 2,
        (("service", "d3"),): judged,
    }
    assert d["kp_canonicalization_item_attempts_sum"] == {
        (("service", "vlm"),): 2,
        (("service", "d3"),): judged,
    }


async def test_a_failed_document_counts_as_failed(client, ports, runtime):
    before = sample("kp_canonicalization_document_outcomes_total", outcome="failed", tier="normal")
    start = await start_input(
        ports, encrypt(write_pdf(paper(2))), request_id=f"req_{uuid.uuid4().hex[:8]}"
    )

    outcome, _ = await process(client, ports, runtime, start)

    assert outcome["outcome"] == "failed"
    after = sample("kp_canonicalization_document_outcomes_total", outcome="failed", tier="normal")
    assert after - before == 1


async def test_a_low_priority_request_is_measured_as_bulk_and_its_status_stages_are_timed(
    ports, runtime
):
    buffer = MetricBuffer(100_000)  # the SDK's own metrics share it
    temporal = Runtime(telemetry=TelemetryConfig(metrics=buffer))
    before = sample("kp_canonicalization_document_outcomes_total", outcome="complete", tier="bulk")
    start = await start_input(
        ports, seven_pages(), request_id=f"req_{uuid.uuid4().hex[:8]}", priority="low"
    )
    async with await WorkflowEnvironment.start_local(
        runtime=temporal, dev_server_existing_path=shutil.which("temporal")
    ) as env:
        outcome, _ = await process(env.client, ports, runtime, start)

    assert outcome["outcome"] == "complete"
    after = sample("kp_canonicalization_document_outcomes_total", outcome="complete", tier="bulk")
    assert after - before == 1
    stages = [
        (u.attributes["stage"], u.attributes["tier"], u.value)
        for u in buffer.retrieve_updates()
        if u.metric.name == "kp_canonicalization_stage_duration_seconds"
    ]
    assert [(stage, tier) for stage, tier, _ in stages] == [
        ("prepare", "bulk"), ("parse", "bulk"), ("enrich", "bulk"), ("finalize", "bulk"),
    ]  # fmt: skip
    assert all(0 <= seconds <= 120 for _, _, seconds in stages)
