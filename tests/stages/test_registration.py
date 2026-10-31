"""Registration races and serialized group evidence use the real docling method."""

import dataclasses
import json

import pytest
from docling.datamodel.base_models import FigureElement, PageConfidenceScores

from kp_processing.methods.docling_parse.serialization import (
    Group,
    capture_page,
    group_json,
    json_bytes,
    pack_assembled,
    restore_page,
    unpack_assembled,
)
from kp_processing.ports.object_store import DictObjectStore
from kp_processing.stages import (
    AssembleInput,
    GroupInput,
    InventoryInput,
    ProcessingFailure,
    inventory,
    parse,
    sha256,
)
from tests.stages.conftest import start_input
from tests.stages.test_parse import parse_all, seven_pages


class LosingStore(DictObjectStore):
    async def put_if_absent(self, key: str, data: bytes) -> bool:
        if key.endswith(("/group.json", "/assembly.json", "/inventory.json")):
            body = json.loads(data)
            for image in body.get("page_images", []) + body.get("picture_images", []):
                assert sha256(self.objects[image["ref"]]) == image["sha256"]
            winner = json.dumps(body, indent=2).encode()
            assert winner != data
            self.objects[key] = winner
            return False
        return await super().put_if_absent(key, data)


async def test_a_losing_json_writer_returns_the_registered_winner(ports, runtime):
    store = LosingStore()
    ports = dataclasses.replace(ports, store=store)
    _, plan, groups = await parse_all(ports, runtime, seven_pages())
    assembly = await parse.run_assemble(
        AssembleInput("doc_1", plan.source_key, plan.source_sha256, groups), ports, runtime
    )
    registered = await inventory.run(
        InventoryInput("doc_1", plan.source_key, plan.source_sha256, groups, assembly),
        ports,
        runtime,
    )

    for item in [*groups, assembly, registered]:
        assert item.reused is True
        assert item.digest == sha256(store.objects[item.ref])


async def test_group_json_round_trips_typed_pages_and_confidence(ports, runtime):
    _, _, groups = await parse_all(ports, runtime, seven_pages())
    raw = await ports.store.get(groups[0].ref)
    group = Group.model_validate_json(raw)

    assert group_json(group) == raw
    figures = []
    for saved, image in zip(group.page_results, group.page_images, strict=True):
        page = restore_page(saved, await ports.store.get(image.ref))
        confidence = PageConfidenceScores.model_validate(saved.confidence)
        assert capture_page(page, confidence).model_dump(mode="json") == saved.model_dump(
            mode="json"
        )
        assert page.assembled is not None
        assert pack_assembled(page.assembled) == saved.assembled
        figures.extend(
            element for element in page.assembled.elements if isinstance(element, FigureElement)
        )
    assert figures
    with pytest.raises(ValueError):
        json_bytes({"score": float("nan")})
    with pytest.raises(ValueError):
        unpack_assembled(
            {"elements": [{"type": "Unknown", "value": {}}], "headers": [], "body": []}
        )


async def test_group_rejects_source_digest_mismatch_before_registration(ports, runtime):
    start = await start_input(ports, seven_pages())
    key = start["files"][0]["custody_ref"].removeprefix("s3://kp-dev/")
    await ports.store.put(key, b"changed")

    with pytest.raises(ProcessingFailure) as caught:
        await parse.run_group(
            GroupInput("doc_1", key, start["files"][0]["sha256"], [1, 5]), ports, runtime
        )

    assert (caught.value.cause, caught.value.category, caught.value.reason) == (
        "platform",
        "integrity",
        "SOURCE_DIGEST_MISMATCH",
    )
    assert await ports.store.list_prefix("documents/") == []
