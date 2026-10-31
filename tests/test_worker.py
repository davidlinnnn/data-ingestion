import logging

import pytest
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from kp_processing.ports.object_store import DictObjectStore
from kp_processing.stages import PrepareInput
from kp_processing.worker import Orchestration, WriteOnceUnsupported, check_write_once
from tests.pdfs import Page, paper, write_pdf
from tests.stages.conftest import start_input


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
