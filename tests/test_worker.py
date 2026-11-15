import asyncio
import dataclasses
import json
import logging
import threading
import time
import uuid
from datetime import timedelta

import pytest
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError
from temporalio.testing import ActivityEnvironment
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from kp_canonicalization.methods.docling_parse import pipeline
from kp_canonicalization.ports.object_store import DictObjectStore
from kp_canonicalization.stages import (
    CheckInput,
    ChunkInput,
    EnrichInput,
    GroupInput,
    GroupRef,
    OverviewInput,
    PrepareInput,
    sha256,
)
from kp_canonicalization.weights import WeightsMismatch
from kp_canonicalization.worker import (
    D3,
    Inference,
    Orchestration,
    Summary,
    Vlm,
    WriteOnceUnsupported,
    check_write_once,
    make_worker,
)
from kp_canonicalization.workflow import task_queue
from tests.pdfs import Page, paper, write_pdf
from tests.stages.conftest import start_input, with_runtime
from tests.stages.test_enrich_local import enriched_paper, enrichment, native
from tests.stages.test_enrich_summary import summary_paper


class OverwritingStore(DictObjectStore):
    """A store without conditional writes: every put succeeds and overwrites."""

    async def put_if_absent(self, key: str, data: bytes) -> bool:
        self.objects[key] = data
        return True


async def test_a_store_with_write_once_passes_the_start_up_check():
    await check_write_once(DictObjectStore())


async def test_a_store_without_conditional_writes_stops_the_worker_from_starting():
    with pytest.raises(WriteOnceUnsupported):
        await check_write_once(OverwritingStore())


async def test_every_start_up_probes_a_fresh_key():
    store = DictObjectStore()

    await check_write_once(store)
    await check_write_once(store)

    assert len(store.objects) == 2


async def test_a_rejected_source_is_logged_with_its_reason_and_limits(ports, runtime, caplog):
    pages = paper(1)
    pages.append(Page(lines=["Poster"], size=(2384, 3370)))  # A0
    start = await start_input(ports, write_pdf(pages))

    with pytest.raises(ApplicationError), caplog.at_level(logging.WARNING):
        await ActivityEnvironment().run(
            Orchestration(ports, runtime).prepare, PrepareInput(start, "r")
        )

    assert "PIXEL_LIMIT_EXCEEDED" in caplog.text
    assert "'page': '2'" in caplog.text


async def test_the_enrich_local_activity_heartbeats_after_every_item(ports, runtime):
    # An hour between timer beats leaves only the one at start besides the per-item beats.
    settings = {**runtime.profile.runtime, "heartbeat_interval_s": 3600}
    runtime = dataclasses.replace(
        runtime, profile=dataclasses.replace(runtime.profile, runtime=settings)
    )
    input = await native(ports, runtime, enriched_paper())
    environment = ActivityEnvironment()
    beats = []
    environment.on_heartbeat = lambda *details: beats.append(details)

    outcomes = await environment.run(
        Inference(ports, runtime).enrich_local, EnrichInput("doc_1", input.inventory, "r", "run")
    )

    assert len(beats) == 1 + len(outcomes) == 4


async def test_the_enrich_vlm_activity_heartbeats_after_every_item(ports, runtime):
    runtime = with_runtime(runtime, heartbeat_interval_s=3600)
    input = await native(ports, runtime, enriched_paper())
    environment = ActivityEnvironment()
    beats = []
    environment.on_heartbeat = lambda *details: beats.append(details)

    outcomes = await environment.run(
        Vlm(ports, runtime).enrich_vlm, EnrichInput("doc_1", input.inventory, "r", "run")
    )

    assert len(beats) == 1 + len(outcomes) == 4


async def test_the_check_activity_heartbeats_after_every_check_item(ports, runtime):
    runtime = with_runtime(runtime, heartbeat_interval_s=3600)
    input = await enrichment(ports, runtime, enriched_paper())
    environment = ActivityEnvironment()
    beats = []
    environment.on_heartbeat = lambda *details: beats.append(details)

    # The picture's OCR text and the table are judged.
    enrich = EnrichInput("doc_1", input.inventory, "r", "run")
    outcomes = await environment.run(D3(ports, runtime).check, CheckInput(enrich, input.outcomes))

    assert len(beats) == 1 + len(outcomes) == 3


async def test_the_summary_activities_run_in_the_temporal_wrappers(ports, runtime):
    input = await native(ports, runtime, summary_paper())
    enrich = EnrichInput("doc_1", input.inventory, "r", "run")
    activities = Summary(ports, runtime)
    environment = ActivityEnvironment()

    plan = await environment.run(activities.summary_sections, enrich)
    for index in range(plan.chunks):
        await environment.run(activities.summary_chunk, ChunkInput(enrich, plan, index))
    overview = OverviewInput(enrich, plan, True, 900)
    outcome = await environment.run(activities.summary_overview, overview)

    record = json.loads(await ports.store.get(outcome.ref))
    assert (outcome.item_id, record["outcome"]) == ("document-summary:#", "success")


async def test_a_cancelled_parse_frees_the_slot_only_after_the_docling_thread_ends(
    ports, runtime, monkeypatch
):
    started, release = threading.Event(), threading.Event()

    def parse_group(data, pages):
        started.set()
        release.wait(10)
        raise RuntimeError("docling gave up")

    monkeypatch.setattr(pipeline, "parse_group", parse_group)
    await ports.store.put_if_absent("source.pdf", b"%PDF")
    group = GroupInput("doc_1", "source.pdf", sha256(b"%PDF"), [1, 1])
    environment = ActivityEnvironment()
    activity = asyncio.create_task(environment.run(Inference(ports, runtime).parse_group, group))
    assert await asyncio.to_thread(started.wait, 10)

    environment.cancel()
    await asyncio.sleep(0.5)
    still_running = not activity.done()
    release.set()

    assert still_running
    with pytest.raises(asyncio.CancelledError):
        await activity


@pytest.mark.network
async def test_only_the_inference_worker_checks_the_model_weights(
    client, ports, runtime, monkeypatch, tmp_path
):
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", str(tmp_path))  # no weights here

    await make_worker(client, ports, runtime, "orchestration")
    with pytest.raises(WeightsMismatch, match="layout-heron@8f39ad3c: .* missing"):
        await make_worker(client, ports, runtime, "inference")


@workflow.defn(name="cancel-probe")
class CancelProbe:
    """Two parse groups at once on the inference queue, each timing out after 3 s. The worker
    hears of a timeout only through a heartbeat, hence the heartbeat timeout."""

    @workflow.run
    async def run(self, groups: list[GroupInput]) -> list[str]:
        async def parse(group: GroupInput) -> str:
            try:
                await workflow.execute_activity(
                    "parse_group",
                    group,
                    task_queue=task_queue("paper-pdf@1", "inference"),
                    start_to_close_timeout=timedelta(seconds=3),
                    heartbeat_timeout=timedelta(seconds=2),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                    result_type=GroupRef,
                )
                return "completed"
            except ActivityError as err:
                return type(err.cause).__name__

        return list(await asyncio.gather(*(parse(group) for group in groups)))


@pytest.mark.network
async def test_a_timed_out_parse_holds_the_worker_slot_until_the_docling_thread_ends(
    client, ports, runtime, monkeypatch
):
    spans: list[list[float]] = []  # [start, end] per parse call, in call order

    def parse_group(data, pages):
        span = [time.monotonic()]
        spans.append(span)
        if len(spans) == 1:
            time.sleep(6)  # a hung parse: twice the start-to-close timeout
        span.append(time.monotonic())
        raise RuntimeError("parse failed")

    monkeypatch.setattr(pipeline, "parse_group", parse_group)
    await ports.store.put_if_absent("source.pdf", b"%PDF")
    groups = [GroupInput("doc_1", "source.pdf", sha256(b"%PDF"), [p, p]) for p in (1, 2)]
    runtime = with_runtime(runtime, heartbeat_interval_s=1)
    probe_queue = f"cancel-probe-{uuid.uuid4().hex[:8]}"

    async with (
        await make_worker(client, ports, runtime, "inference"),
        Worker(client, task_queue=probe_queue, workflows=[CancelProbe],
               workflow_runner=UnsandboxedWorkflowRunner()),
    ):  # fmt: skip
        outcomes = await client.execute_workflow(
            CancelProbe.run, groups, id=probe_queue, task_queue=probe_queue
        )

    (first_start, first_end), (second_start, _) = spans
    assert "TimeoutError" in outcomes  # the hung parse was timed out and cancelled
    assert 5.9 <= first_end - first_start <= 7
    assert 0 <= second_start - first_end <= 3  # one parser at a time, then promptly the next
