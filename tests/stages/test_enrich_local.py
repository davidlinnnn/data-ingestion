"""Seam A: inventory items and the local enrichment Activity (#132), with real docling and
RapidOCR. Needs the weights from scripts/fetch-models under $DOCLING_ARTIFACTS_PATH."""

import dataclasses
import hashlib
import json

import pytest

from kp_processing.identity import reuse_key
from kp_processing.methods import picture_ocr
from kp_processing.ports.object_store import DictObjectStore
from kp_processing.stages import (
    AssembleInput,
    EnrichInput,
    FinalizeInput,
    InventoryInput,
    InventoryRef,
    ProcessingFailure,
    enrich_local,
    enrich_vlm,
    finalize,
    inventory,
    parse,
)
from tests.pdfs import Page, write_pdf
from tests.stages.test_parse import parse_all

PICTURE_WORDS = ["Encoder", "Attention x4", "Decoder 512", "Loss: 0.031"]
CODE = [
    "def fib(n):",
    "    if n < 2:",
    "        return n",
    "    a, b = 0, 1",
    "    for _ in range(n - 1):",
    "        a, b = b, a + b",
    "    return b",
]
TABLE = [
    ["Model", "Params", "Score"],
    ["Alpha", "7B", "61.2"],
    ["Beta", "13B", "64.8"],
    ["Gamma", "70B", "71.5"],
]


def enriched_paper() -> bytes:
    """Page 1: a picture with words; page 2: a code listing and a ruled table; page 3: a
    picture without text."""
    body = [f"Line {i} of the method section describes the approach in plain prose."
            for i in range(4)]  # fmt: skip
    return write_pdf(
        [
            Page(lines=["1 Architecture", *body], picture=True, picture_text=PICTURE_WORDS),
            Page(lines=["2 Method", *body], code=CODE, table=TABLE),
            Page(lines=["3 Results", *body], picture=True),
        ]
    )


async def native(ports, runtime, pdf: bytes, request_id: str = "req_1"):
    """prepare, parse, assemble and inventory: the finalize input before any enrichment."""
    start, plan, groups = await parse_all(ports, runtime, pdf)
    start = {**start, "request_id": request_id}
    assembly = await parse.run_assemble(
        AssembleInput("doc_1", plan.source_key, plan.source_sha256, groups), ports, runtime
    )
    inv = await inventory.run(
        InventoryInput("doc_1", plan.source_key, plan.source_sha256, groups, assembly),
        ports,
        runtime,
    )
    return FinalizeInput(start, plan, groups, assembly, inv, [])


def enrich_input(inv: InventoryRef, request_id: str = "req_1") -> EnrichInput:
    return EnrichInput("doc_1", inv, request_id, "run_1")


async def enriched(ports, runtime, pdf: bytes, request_id: str = "req_1") -> FinalizeInput:
    """native() plus the outcomes of the local and the VLM enrichment (ports.vlm answers)."""
    input = await native(ports, runtime, pdf, request_id)
    outcomes = await enrich_local.run(enrich_input(input.inventory, request_id), ports, runtime)
    outcomes += await enrich_vlm.run(enrich_input(input.inventory, request_id), ports, runtime)
    return dataclasses.replace(input, outcomes=outcomes)


async def local_only(ports, inv: InventoryRef) -> InventoryRef:
    """The inventory without the items of other Activities."""
    items = await items_of(ports, inv)
    return await with_items(ports, inv, [i for i in items if i["method"] in enrich_local.METHODS])


async def items_of(ports, inv: InventoryRef) -> list[dict]:
    return json.loads(await ports.store.get(inv.ref))["items"]


async def records(ports, outcomes) -> dict[str, dict]:
    return {o.item_id: json.loads(await ports.store.get(o.ref)) for o in outcomes}


async def with_items(ports, inv: InventoryRef, items: list[dict]) -> InventoryRef:
    """Register a variant inventory (fault injection) and return a reference to it."""
    body = json.dumps({**json.loads(await ports.store.get(inv.ref)), "items": items}).encode()
    ref = f"test/inventory-{hashlib.sha256(body).hexdigest()}.json"
    await ports.store.put(ref, body)
    return InventoryRef(ref, hashlib.sha256(body).hexdigest(), False, len(items))


def counting(monkeypatch) -> list[bytes]:
    """Record every call of the real RapidOCR entry point."""
    calls: list[bytes] = []
    real = picture_ocr.ocr

    def spy(png: bytes):
        calls.append(png)
        return real(png)

    monkeypatch.setattr(picture_ocr, "ocr", spy)
    return calls


# --- inventory ---------------------------------------------------------------------------


async def test_inventory_lists_one_item_per_target_with_its_input_refs(ports, runtime):
    input = await native(ports, runtime, enriched_paper())

    stored = await ports.store.get(input.inventory.ref)
    body = json.loads(stored)
    item_methods = [m for m in runtime.profile.methods.values() if hasattr(m.package, "TARGET")]
    identity = [[m.ref, m.module_digest] for m in item_methods]
    key_input = json.dumps(["paper-pdf@1", input.assembly.digest, identity], separators=(",", ":"))
    key = hashlib.sha256(key_input.encode()).hexdigest()
    assert input.inventory.ref == f"documents/doc_1/items/{key}/inventory.json"
    assert input.inventory.digest == hashlib.sha256(stored).hexdigest()
    assert (body["assembly_ref"], body["assembly_digest"]) == (
        input.assembly.ref,
        input.assembly.digest,
    )
    items = body["items"]
    assert input.inventory.items == len(items)
    assert [i["item_id"] for i in items] == [
        "picture-ocr:#/pictures/0",
        "picture-ocr:#/pictures/1",
        "picture-interpretation:#/pictures/0",
        "picture-interpretation:#/pictures/1",
        "code:#/texts/" + items[4]["target_ref"].split("/")[-1],
        "table-status:#/tables/0",
    ]
    assert items[4]["target_ref"].startswith("#/texts/")
    assert [(i["method"], i["page"]) for i in items] == [
        ("picture-ocr", 1),
        ("picture-ocr", 3),
        ("picture-interpretation", 1),
        ("picture-interpretation", 3),
        ("code", 2),
        ("table-status", 2),
    ]

    assembly = json.loads(await ports.store.get(input.assembly.ref))
    document = assembly["document"]
    for item in items:
        kind, index = item["target_ref"].split("/")[1:]
        prov = document[kind][int(index)]["prov"][0]
        assert (item["page"], item["bbox"]) == (prov["page_no"], prov["bbox"])

    pictures = {p["picture_id"]: p for p in assembly["picture_images"]}
    page_images = {
        image["page"]: {"ref": image["ref"], "sha256": image["sha256"]}
        for group in input.groups
        for image in json.loads(await ports.store.get(group.ref))["page_images"]
    }
    for item in items[:2]:
        picture = pictures[item["target_ref"]]
        assert item["input_refs"] == [{"ref": picture["ref"], "sha256": picture["sha256"]}]
    for item in items[2:4]:
        picture = pictures[item["target_ref"]]
        assert item["input_refs"] == [
            {"ref": picture["ref"], "sha256": picture["sha256"]},
            page_images[item["page"]],
        ]
    plan = input.plan
    assert items[4]["input_refs"] == [
        {"ref": plan.source_key, "sha256": plan.source_sha256},
        page_images[2],
    ]
    page_2 = page_images[2]
    assert items[5]["input_refs"] == [
        {"ref": input.assembly.ref, "sha256": input.assembly.digest},
        {"ref": page_2["ref"], "sha256": page_2["sha256"]},
    ]


async def test_inventory_is_registered_once(ports, runtime):
    input = await native(ports, runtime, enriched_paper())
    plan = input.plan

    again = await inventory.run(
        InventoryInput("doc_1", plan.source_key, plan.source_sha256, input.groups, input.assembly),
        ports,
        runtime,
    )

    assert again == dataclasses.replace(input.inventory, reused=True)


async def test_a_method_added_to_the_draft_profile_gets_a_new_inventory_and_reuses_the_rest(
    ports, runtime
):
    methods = {k: v for k, v in runtime.profile.methods.items() if k != "code"}
    without_code = dataclasses.replace(
        runtime, profile=dataclasses.replace(runtime.profile, methods=methods)
    )
    before = await enriched(ports, without_code, enriched_paper())

    after = await enriched(ports, runtime, enriched_paper())

    assert after.assembly.reused
    assert after.inventory.ref != before.inventory.ref
    assert not after.inventory.reused
    reused = {o.item_id: o.reused for o in after.outcomes}
    assert reused == {
        "picture-ocr:#/pictures/0": True,
        "picture-ocr:#/pictures/1": True,
        "picture-interpretation:#/pictures/0": True,
        "picture-interpretation:#/pictures/1": True,
        next(i for i in reused if i.startswith("code:")): False,
        "table-status:#/tables/0": True,
    }


# --- local enrichment ----------------------------------------------------------------------


async def test_enrichment_files_exist_before_the_outcome_is_registered(ports, runtime):
    checked = []

    class CheckingStore(DictObjectStore):
        async def put_if_absent(self, key: str, data: bytes) -> bool:
            if key.endswith("/outcome.json"):
                record = json.loads(data)
                refs = record["evidence_refs"] + [record["provider_artifact_ref"]]
                for ref in refs:
                    if ref:
                        assert await self.head(ref) is not None
                        checked.append(ref)
            return await super().put_if_absent(key, data)

    await enriched(dataclasses.replace(ports, store=CheckingStore()), runtime, enriched_paper())

    assert checked


async def test_every_item_gets_an_outcome_record_under_its_reuse_key(ports, runtime):
    input = await enriched(ports, runtime, enriched_paper())

    items = await items_of(ports, input.inventory)
    outcomes = {o.item_id: o for o in input.outcomes}
    assert len(outcomes) == len(input.outcomes)
    assert sorted(outcomes) == sorted(i["item_id"] for i in items)
    assert not any(o.reused for o in input.outcomes)
    for item in items:
        outcome = outcomes[item["item_id"]]
        method = runtime.profile.methods[item["method"]]
        target = json.dumps(
            {k: item[k] for k in ("target_ref", "page", "bbox")},
            sort_keys=True,
            separators=(",", ":"),
        )
        key = reuse_key(
            "doc_1",
            method.ref,
            method.components,
            method.module_digest,
            [*(r["sha256"] for r in item["input_refs"]), target],
        )
        assert outcome.ref == f"documents/doc_1/items/{key}/outcome.json"
        stored = await ports.store.get(outcome.ref)
        assert outcome.digest == hashlib.sha256(stored).hexdigest()
        record = json.loads(stored)
        assert record["schema"] == "enrichment-outcome/v1"
        assert record["method_ref"] == {
            "id": method.id,
            "version": method.version,
            "digest": method.module_digest,
        }
        assert record["scope"] == "item"
        for ref in record["evidence_refs"] + [record["provider_artifact_ref"] or ""]:
            assert not ref or ref.startswith(f"documents/doc_1/items/{key}/")
            assert not ref or await ports.store.head(ref) is not None

    by_id = await records(ports, input.outcomes)
    origins = {item_id.split(":")[0]: r["origin"] for item_id, r in by_id.items()}
    assert origins == {"picture-ocr": "reconstruction", "picture-interpretation": "interpretation",
                       "code": "reconstruction", "table-status": "reconstruction"}  # fmt: skip
    assert {i: r["outcome"] for i, r in by_id.items() if i.startswith("picture-ocr:")} == {
        "picture-ocr:#/pictures/0": "success",
        "picture-ocr:#/pictures/1": "no_text",
    }
    assert all(r["outcome"] == "success" for i, r in by_id.items()
               if not i.startswith("picture-ocr:"))  # fmt: skip


async def test_a_second_run_reuses_every_item_without_calling_rapidocr(ports, runtime, monkeypatch):
    calls = counting(monkeypatch)
    first = await enriched(ports, runtime, enriched_paper())
    assert len(calls) == 2  # the spy sees the real calls: one per picture
    objects = dict(ports.store.objects)  # type: ignore[attr-defined]

    again = await enrich_local.run(enrich_input(first.inventory), ports, runtime)

    assert len(calls) == 2
    local = [o for o in first.outcomes if o.item_id.split(":")[0] in enrich_local.METHODS]
    assert again == [dataclasses.replace(o, reused=True) for o in local]
    assert ports.store.objects == objects  # type: ignore[attr-defined]


async def test_every_item_run_or_reused_sends_a_heartbeat(ports, runtime):
    beats = []
    ports = dataclasses.replace(ports, heartbeat=lambda: beats.append(1))
    first = await enriched(ports, runtime, enriched_paper())
    assert len(beats) == len(first.outcomes) == 6

    await enrich_local.run(enrich_input(first.inventory), ports, runtime)

    assert len(beats) == 9


async def test_an_undecodable_picture_is_a_failed_item_and_the_document_completes(ports, runtime):
    input = await native(ports, runtime, enriched_paper())
    items = await items_of(ports, await local_only(ports, input.inventory))
    junk = b"not a png"
    await ports.store.put("test/junk.png", junk)
    items[0]["input_refs"] = [{"ref": "test/junk.png", "sha256": hashlib.sha256(junk).hexdigest()}]
    inv = await with_items(ports, input.inventory, items)

    outcomes = await enrich_local.run(enrich_input(inv), ports, runtime)
    ref = await finalize.run(
        dataclasses.replace(input, inventory=inv, outcomes=outcomes), ports, runtime
    )

    record = (await records(ports, outcomes))["picture-ocr:#/pictures/0"]
    assert (record["outcome"], record["reason"], record["content"]) == (
        "failed",
        "RENDER_FAILED",
        None,
    )
    result = json.loads(await ports.store.get(ref))
    assert result["outcome"] == "complete"
    enrichment = result["enrichments"][0]
    assert (enrichment["status"], enrichment["status_reason"]) == ("failed", "RENDER_FAILED")


async def test_a_document_whose_items_all_fail_still_completes(ports, runtime):
    input = await native(ports, runtime, enriched_paper())
    items = await items_of(ports, await local_only(ports, input.inventory))
    junk = b"not a png"
    await ports.store.put("test/junk.png", junk)
    junk_ref = {"ref": "test/junk.png", "sha256": hashlib.sha256(junk).hexdigest()}
    for item in items:
        if item["method"] == "picture-ocr":
            item["input_refs"] = [junk_ref]
        if item["method"] == "table-status":
            item["input_refs"][1] = junk_ref
    inv = await with_items(ports, input.inventory, items)

    outcomes = await enrich_local.run(enrich_input(inv), ports, runtime)
    ref = await finalize.run(
        dataclasses.replace(input, inventory=inv, outcomes=outcomes), ports, runtime
    )

    result = json.loads(await ports.store.get(ref))
    assert result["outcome"] == "complete"
    assert [(e["status"], e["status_reason"]) for e in result["enrichments"]] == [
        ("failed", "RENDER_FAILED"),
        ("failed", "RENDER_FAILED"),
        ("failed", "RENDER_FAILED"),
    ]
    assert result["inventory"]["counts"]["picture-ocr"] == {
        "unverified": 0, "disputed": 0, "failed": 2, "no_text": 0
    }  # fmt: skip


async def test_an_input_that_differs_from_its_digest_fails_integrity(ports, runtime):
    input = await native(ports, runtime, enriched_paper())
    item = (await items_of(ports, input.inventory))[0]
    await ports.store.put(item["input_refs"][0]["ref"], b"tampered")

    with pytest.raises(ProcessingFailure) as caught:
        await enrich_local.run(enrich_input(input.inventory), ports, runtime)

    failure = caught.value
    assert (failure.cause, failure.category, failure.reason) == (
        "platform",
        "integrity",
        "INPUT_DIGEST_MISMATCH",
    )
    assert failure.metadata["item_id"] == item["item_id"]


async def test_missing_ocr_weights_are_a_configuration_failure(
    ports, runtime, monkeypatch, tmp_path
):
    input = await native(ports, runtime, enriched_paper())
    monkeypatch.setenv("DOCLING_ARTIFACTS_PATH", str(tmp_path))

    with pytest.raises(ProcessingFailure) as caught:
        await enrich_local.run(enrich_input(input.inventory), ports, runtime)

    failure = caught.value
    assert (failure.cause, failure.category, failure.reason) == (
        "platform",
        "configuration",
        "METHOD_UNAVAILABLE",
    )
    assert failure.metadata["item_id"] == "picture-ocr:#/pictures/0"


async def test_an_exception_inside_a_method_is_a_method_failure(ports, runtime, monkeypatch):
    input = await native(ports, runtime, enriched_paper())

    def broken(item, inputs):
        raise RuntimeError("bug")

    monkeypatch.setattr(picture_ocr, "run", broken)

    with pytest.raises(ProcessingFailure) as caught:
        await enrich_local.run(enrich_input(input.inventory), ports, runtime)

    failure = caught.value
    assert (failure.cause, failure.category, failure.reason) == (
        "platform",
        "method",
        "METHOD_ERROR",
    )
    assert failure.metadata["item_id"] == "picture-ocr:#/pictures/0"
