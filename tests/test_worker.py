import pytest

from kp_processing.ports.object_store import DictObjectStore
from kp_processing.worker import WriteOnceUnsupported, check_write_once


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
