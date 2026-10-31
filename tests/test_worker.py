import asyncio
import dataclasses
import logging
import threading

import pytest
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from kp_processing.methods.docling_parse import pipeline
from kp_processing.ports.object_store import DictObjectStore
from kp_processing.stages import EnrichInput, GroupInput, PrepareInput, sha256
from kp_processing.weights import WeightsMismatch
from kp_processing.worker import (
    Inference,
    Orchestration,
    WriteOnceUnsupported,
    check_write_once,
    make_worker,
)
from tests.pdfs import Page, paper, write_pdf
from tests.stages.conftest import start_input
from tests.stages.test_enrich_local import enriched_paper, native


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
        Inference(ports, runtime).enrich_local, EnrichInput("doc_1", input.inventory)
    )

    assert len(beats) == 1 + len(outcomes) == 5


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
