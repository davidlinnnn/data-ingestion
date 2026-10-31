"""Seam A: the VLM enrichment Activity (#133) with real docling and the in-process VLM fake:
receipts, the retry matrix, the stage budget, the request cap, concurrency, the methods, the
per-field enrichments and the redrive marker; V7 over hung transports and V9 receipt overhead."""

import asyncio
import base64
import dataclasses
import hashlib
import io
import json
import os
import re
import statistics
import time
import uuid
from typing import Any

import httpx
import pytest
from PIL import Image

from kp_processing.methods import InventoryItem, code, formula, picture_interpretation
from kp_processing.ports.clock import FakeClock
from kp_processing.ports.inference import (
    Completion,
    FakeInference,
    OpenAIChat,
    RequestRejected,
    ServiceUnavailable,
    completion,
)
from kp_processing.ports.object_store import DictObjectStore, S3ObjectStore
from kp_processing.profile import ProcessingProfile
from kp_processing.stages import (
    EnrichInput,
    FinalizeInput,
    InventoryRef,
    ProcessingFailure,
    enrich_local,
    enrich_vlm,
    finalize,
)
from tests.pdfs import Page, write_pdf
from tests.ports.test_inference import Hang
from tests.stages.conftest import with_runtime
from tests.stages.test_enrich_local import (
    CODE,
    PICTURE_WORDS,
    enriched_paper,
    items_of,
    native,
    records,
    with_items,
)
from tests.vlm import CANNED, canned, images, schema_name

BODY = [f"Line {i} of the method section describes the approach in plain prose." for i in range(4)]
EQUATION = "                    L = 2 x + 3 y - 7 = 0                    (1)"
EMPTY_BOX = {"l": 300.0, "t": 780.0, "r": 500.0, "b": 760.0, "coord_origin": "BOTTOMLEFT"}


def one_picture_paper() -> bytes:
    return write_pdf([Page(lines=["1 Architecture", *BODY], picture=True,
                          picture_text=PICTURE_WORDS)])  # fmt: skip


def two_picture_paper() -> bytes:
    return write_pdf([Page(lines=["1 Architecture", *BODY], picture=True,
                          picture_text=PICTURE_WORDS),
                      Page(lines=["2 Results", *BODY], picture=True)])  # fmt: skip


def formula_paper() -> bytes:
    """docling labels the equation line `formula` (probed 2026-10-31); its box holds "(1)"."""
    return write_pdf(
        [Page(lines=["2 Method", *BODY, "", EQUATION, "", "Line after the equation continues."])]
    )


def answers(*script: Any) -> FakeInference:
    """Answer each request with the next entry: a Completion, an exception, "BAD" (not JSON),
    "EMPTY" (blank content) or "REFUSE"; after the script, the canned answer."""
    queue = list(script)

    def answer(request: dict) -> Completion | Exception:
        if not queue:
            return canned(request)
        entry = queue.pop(0)
        if entry == "BAD":
            return completion("{not json")
        if entry == "EMPTY":
            return completion("")
        if entry == "REFUSE":
            return completion(None, refusal="I can't help with that.")
        return entry

    return FakeInference(answer)


def unavailable(reason: str = "TIMEOUT") -> ServiceUnavailable:
    return ServiceUnavailable(reason)  # type: ignore[arg-type]


async def run_vlm(
    ports, runtime, inv: InventoryRef, request_id="req_1", run_id="run_1", document_uid="doc_1"
):
    input = EnrichInput(document_uid, inv, request_id, run_id)
    return await enrich_vlm.run(input, ports, runtime)


async def finalized(ports, runtime, input: FinalizeInput, outcomes) -> dict:
    """finalize with the local outcomes and the given VLM outcomes; the Processing Result."""
    local = await enrich_local.run(EnrichInput("doc_1", input.inventory, "req_1", "run_1"),
                                   ports, runtime)  # fmt: skip
    ref = await finalize.run(
        dataclasses.replace(input, outcomes=[*local, *outcomes]), ports, runtime
    )
    return json.loads(await ports.store.get(ref))


async def receipts(ports, item_id: str, request_id="req_1", run_id="run_1") -> list[dict]:
    prefix = f"requests/{request_id}/attempts/{run_id}/receipts/{item_id}/"
    keys = await ports.store.list_prefix(prefix)
    return [json.loads(await ports.store.get(f"{prefix}{n}.json")) for n in range(1, len(keys) + 1)]


async def vlm_items(ports, inv: InventoryRef) -> list[dict]:
    return [i for i in await items_of(ports, inv) if i["method"] in enrich_vlm.METHODS]


async def clones(ports, inv: InventoryRef, count: int) -> InventoryRef:
    """An inventory of `count` picture-interpretation items cloned from the first picture."""
    (item,) = [i for i in await vlm_items(ports, inv) if i["method"] == "picture-interpretation"]
    copies = [{**item, "item_id": f"picture-interpretation:#/pictures/{n}",
               "target_ref": f"#/pictures/{n}"} for n in range(count)]  # fmt: skip
    return await with_items(ports, inv, copies)


def decoded(url: str) -> bytes:
    prefix = "data:image/png;base64,"
    assert url.startswith(prefix)
    return base64.b64decode(url[len(prefix) :])


def size(png: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(png)) as image:
        return image.size


# --- the methods, through the Activity -----------------------------------------------------


async def test_each_picture_is_one_request_with_the_page_and_the_crop(ports, runtime):
    input = await native(ports, runtime, enriched_paper())

    await run_vlm(ports, runtime, input.inventory)

    pictures = [i for i in await vlm_items(ports, input.inventory)
                if i["method"] == "picture-interpretation"]  # fmt: skip
    requests = ports.vlm.requests
    assert [schema_name(r) for r in requests] == ["picture-interpretation"] * 2
    for item, request in zip(pictures, requests, strict=True):
        assert "model" not in request
        response_format = request["response_format"]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True
        page, crop = map(decoded, images(request))
        page_ref, picture_ref = item["input_refs"][1], item["input_refs"][0]
        assert size(page) == size(await ports.store.get(page_ref["ref"]))
        assert size(crop) == size(await ports.store.get(picture_ref["ref"]))


async def test_code_with_a_text_layer_sends_nothing(ports, runtime):
    input = await native(ports, runtime, enriched_paper())

    outcomes = await run_vlm(ports, runtime, input.inventory)

    assert "code" not in [schema_name(r) for r in ports.vlm.requests]
    (listing,) = [r for i, r in (await records(ports, outcomes)).items() if i.startswith("code:")]
    assert listing["content"] == "\n".join(CODE)
    assert listing["signals"] == {"indent_quantized": True}


async def test_code_without_a_text_layer_is_read_by_the_vlm(ports, runtime):
    input = await native(ports, runtime, enriched_paper())
    items = await vlm_items(ports, input.inventory)
    (item,) = [i for i in items if i["method"] == "code"]
    inv = await with_items(ports, input.inventory, [{**item, "bbox": EMPTY_BOX}])
    ports = dataclasses.replace(
        ports, vlm=answers(completion(json.dumps({"code": "def f():\n    return 1  \n\n"})))
    )

    (outcome,) = await run_vlm(ports, runtime, inv)

    (request,) = ports.vlm.requests
    assert schema_name(request) == "code"
    (crop,) = map(decoded, images(request))
    record = (await records(ports, [outcome]))[outcome.item_id]
    assert (record["outcome"], record["content"]) == ("success", "def f():\n    return 1")
    assert record["signals"] == {"vlm_fallback": True}
    (evidence,) = record["evidence_refs"]
    assert await ports.store.get(evidence) == crop


async def test_picture_interpretation_fields_are_recorded_one_by_one(ports, runtime):
    input = await native(ports, runtime, one_picture_paper())

    (outcome,) = await run_vlm(ports, runtime, input.inventory)

    record = (await records(ports, [outcome]))[outcome.item_id]
    assert record["origin"] == "interpretation"
    assert record["outcome"] == "success"
    expected = CANNED["picture-interpretation"]
    assert set(record["fields"]) == set(picture_interpretation.FIELDS)
    for name, field in record["fields"].items():
        assert (field["outcome"], field["reason"], field["content"]) == (
            "success",
            None,
            expected[name],
        )
        assert field["contradictions"] == []
    (answer,) = [canned(r) for r in ports.vlm.requests]
    assert await ports.store.get(record["provider_artifact_ref"]) == answer.body


async def test_a_blank_field_fails_alone_in_the_result(ports, runtime):
    input = await native(ports, runtime, one_picture_paper())
    blank = {**CANNED["picture-interpretation"], "caption": "  "}
    ports = dataclasses.replace(ports, vlm=answers(completion(json.dumps(blank))))

    outcomes = await run_vlm(ports, runtime, input.inventory)
    result = await finalized(ports, runtime, input, outcomes)

    fields = {e["item_id"]: (e["status"], e["status_reason"]) for e in result["enrichments"]
              if e["method_ref"]["id"] == "picture-interpretation"}  # fmt: skip
    assert fields == {
        "picture-interpretation:#/pictures/0/caption": ("failed", "EMPTY_OUTPUT"),
        "picture-interpretation:#/pictures/0/chart_values": ("unverified", None),
        "picture-interpretation:#/pictures/0/description": ("unverified", None),
        "picture-interpretation:#/pictures/0/figure_type": ("unverified", None),
    }
    assert result["inventory"]["counts"]["picture-interpretation"] == {
        "unverified": 3, "disputed": 0, "failed": 1, "no_text": 0
    }  # fmt: skip
    description = next(e for e in result["enrichments"]
                       if e["item_id"].endswith("/description"))  # fmt: skip
    assert description["content"] == blank["description"]
    assert description["result_ref"] == outcomes[0].ref


async def test_a_refused_picture_fails_every_field(ports, runtime):
    input = await native(ports, runtime, one_picture_paper())
    ports = dataclasses.replace(ports, vlm=answers("REFUSE"))

    outcomes = await run_vlm(ports, runtime, input.inventory)
    result = await finalized(ports, runtime, input, outcomes)

    fields = [(e["status"], e["status_reason"]) for e in result["enrichments"]
              if e["method_ref"]["id"] == "picture-interpretation"]  # fmt: skip
    assert fields == [("failed", "MODEL_REFUSAL")] * 4


@pytest.mark.parametrize(
    ("latex", "status"),
    [
        ("L = 2x + 3y - 7 = 0", ("unverified", None)),
        (r"L = 2x + 3y - 7 = 0 \tag{1}", ("unverified", None)),
        ("L = 2x + 5y - 7 = 0", ("disputed", "FORMULA_NATIVE_MISMATCH")),  # a number differs
        ("L = 2x - 3y - 7 = 0", ("disputed", "FORMULA_NATIVE_MISMATCH")),  # an operator differs
        ("L = 2x + 3y - 7 = 0 = 0", ("disputed", "FORMULA_NATIVE_MISMATCH")),  # one too many
    ],
)
async def test_a_formula_that_contradicts_the_text_layer_is_disputed(ports, runtime, latex, status):
    input = await native(ports, runtime, formula_paper())
    ports = dataclasses.replace(ports, vlm=answers(completion(json.dumps({"latex": latex}))))

    outcomes = await run_vlm(ports, runtime, input.inventory)
    result = await finalized(ports, runtime, input, outcomes)

    (request,) = ports.vlm.requests
    assert schema_name(request) == "formula"
    (enrichment,) = [e for e in result["enrichments"] if e["method_ref"]["id"] == "formula"]
    assert (enrichment["status"], enrichment["status_reason"]) == status
    assert enrichment["content"] == latex
    assert "2 x + 3 y - 7 = 0" in enrichment["signals"]["native_text"]
    (crop_ref,) = enrichment["evidence_refs"]
    crop = await ports.store.get(crop_ref)
    assert decoded(images(request)[0]) == crop
    item = next(i for i in await items_of(ports, input.inventory) if i["method"] == "formula")
    box = item["bbox"]
    width, height = size(crop)
    # The page image has 2.0 pixels per PDF point.
    assert 0.8 * 2 * (box["r"] - box["l"]) <= width <= 1.2 * 2 * (box["r"] - box["l"])
    assert 0.8 * 2 * abs(box["t"] - box["b"]) <= height <= 1.2 * 2 * abs(box["t"] - box["b"])


async def test_a_formula_without_a_text_layer_has_nothing_to_contradict(ports, runtime):
    input = await native(ports, runtime, formula_paper())
    item = next(i for i in await items_of(ports, input.inventory) if i["method"] == "formula")
    inputs = [await ports.store.get(source["ref"]) for source in item["input_refs"]]
    blank: InventoryItem = {**item, "bbox": EMPTY_BOX}  # type: ignore[typeddict-item]

    output = formula.parse(blank, inputs, json.dumps({"latex": "x = 1"}))

    assert (output.outcome, output.content, output.contradictions) == ("success", "x = 1", [])
    assert output.signals == {"native_text": ""}


def test_the_model_is_the_shared_vlm_component(runtime):
    assert enrich_vlm.model(runtime.profile) == "gpt-6-luna"


def test_vlm_methods_that_disagree_on_the_model_are_refused(runtime):
    methods = dict(runtime.profile.methods)
    methods["formula"] = dataclasses.replace(methods["formula"], components=("openai/other",))
    profile: ProcessingProfile = dataclasses.replace(runtime.profile, methods=methods)

    with pytest.raises(ValueError):
        enrich_vlm.model(profile)


# --- receipts --------------------------------------------------------------------------------


async def test_every_send_has_a_complete_receipt(ports, runtime):
    input = await native(ports, runtime, one_picture_paper())

    (outcome,) = await run_vlm(ports, runtime, input.inventory)

    (request,) = ports.vlm.requests
    answer = canned(request)
    (receipt,) = await receipts(ports, outcome.item_id)
    method = runtime.profile.methods["picture-interpretation"]
    params = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    assert {k: receipt[k] for k in ("item_id", "method", "attempt", "params_digest")} == {
        "item_id": outcome.item_id,
        "method": method.ref,
        "attempt": 1,
        "params_digest": hashlib.sha256(params).hexdigest(),
    }
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", receipt["sent_at"])
    assert (receipt["result"], receipt["reason"]) == ("ok", None)
    assert receipt["result_digest"] == hashlib.sha256(answer.body).hexdigest()
    assert (receipt["model"], receipt["system_fingerprint"]) == (answer.model, None)
    assert receipt["usage"] == answer.usage
    assert 0 <= receipt["latency_ms"] < 60_000


async def test_a_receipt_is_written_before_its_request_is_sent(ports, runtime):
    input = await native(ports, runtime, one_picture_paper())
    item_id = "picture-interpretation:#/pictures/0"
    seen = []

    async def answer(request: dict) -> Completion:
        seen.append(await receipts(ports, item_id))
        return canned(request)

    ports = dataclasses.replace(ports, vlm=FakeInference(answer))

    await run_vlm(ports, runtime, input.inventory)

    ((receipt,),) = seen
    assert receipt["attempt"] == 1
    assert "result" not in receipt


async def test_receipts_left_by_a_killed_worker_count_as_attempts(ports, runtime):
    input = await native(ports, runtime, one_picture_paper())
    item_id = "picture-interpretation:#/pictures/0"
    for n in (1, 2):  # sent, then the worker died before completing the receipt
        sent = {"item_id": item_id, "method": "picture-interpretation@1", "attempt": n,
                "params_digest": "0" * 64, "sent_at": "2026-10-31T00:00:00Z"}  # fmt: skip
        await ports.store.put(
            f"requests/req_1/attempts/run_1/receipts/{item_id}/{n}.json", json.dumps(sent).encode()
        )
    ports = dataclasses.replace(ports, vlm=answers(unavailable(), unavailable()))

    (outcome,) = await run_vlm(ports, runtime, input.inventory)

    assert len(ports.vlm.requests) == 1
    assert [r["attempt"] for r in await receipts(ports, item_id)] == [1, 2, 3]
    record = (await records(ports, [outcome]))[item_id]
    assert (record["outcome"], record["reason"]) == ("failed", "SERVICE_UNAVAILABLE")


async def test_an_invalid_answer_from_an_earlier_attempt_is_remembered(ports, runtime):
    input = await native(ports, runtime, one_picture_paper())
    item_id = "picture-interpretation:#/pictures/0"
    first = {"item_id": item_id, "method": "picture-interpretation@1", "attempt": 1,
             "params_digest": "0" * 64, "sent_at": "2026-10-31T00:00:00Z", "result": "invalid",
             "reason": "SCHEMA_INVALID", "latency_ms": 900, "usage": {}, "result_digest": None,
             "model": "fake", "system_fingerprint": None}  # fmt: skip
    await ports.store.put(
        f"requests/req_1/attempts/run_1/receipts/{item_id}/1.json", json.dumps(first).encode()
    )
    ports = dataclasses.replace(ports, vlm=answers("BAD"))

    (outcome,) = await run_vlm(ports, runtime, input.inventory)

    assert len(ports.vlm.requests) == 1
    record = (await records(ports, [outcome]))[item_id]
    assert (record["outcome"], record["reason"]) == ("failed", "SCHEMA_INVALID")


# --- the retry matrix (#93 §3.4) -------------------------------------------------------------

OK = "OK"


@pytest.mark.parametrize(
    ("script", "results", "outcome", "sleeps"),
    [
        ([unavailable()] * 3, ["unavailable"] * 3, ("failed", "SERVICE_UNAVAILABLE"),
         [(1, 2), (2, 4)]),
        ([unavailable("CONNECTION"), OK], ["unavailable", "ok"], ("success", None), [(1, 2)]),
        ([unavailable("HTTP_5XX"), unavailable("HTTP_429"), OK], ["unavailable"] * 2 + ["ok"],
         ("success", None), [(1, 2), (2, 4)]),
        (["BAD", OK], ["invalid", "ok"], ("success", None), []),
        (["BAD", "BAD"], ["invalid"] * 2, ("failed", "SCHEMA_INVALID"), []),
        (["EMPTY", "EMPTY"], ["invalid"] * 2, ("failed", "EMPTY_OUTPUT"), []),
        (["REFUSE"], ["refused"], ("failed", "MODEL_REFUSAL"), []),
        (["BAD", unavailable(), unavailable()], ["invalid"] + ["unavailable"] * 2,
         ("failed", "SERVICE_UNAVAILABLE"), [(1, 2)]),
        ([unavailable(), "BAD", "BAD"], ["unavailable"] + ["invalid"] * 2,
         ("failed", "SCHEMA_INVALID"), [(1, 2)]),
    ],
    ids=["timeouts", "connect-then-ok", "5xx-429-ok", "invalid-then-ok", "invalid-twice",
         "empty-twice", "refusal", "invalid-then-timeouts", "timeout-then-invalid-twice"],
)  # fmt: skip
async def test_the_retry_matrix(ports, runtime, script, results, outcome, sleeps):
    input = await native(ports, runtime, one_picture_paper())
    script = [s for s in script if s != OK]  # after the script, answers are canned (ok)
    ports = dataclasses.replace(ports, vlm=answers(*script))
    item_id = "picture-interpretation:#/pictures/0"

    (ref,) = await run_vlm(ports, runtime, input.inventory)

    assert len(ports.vlm.requests) == len(results)
    assert [r["result"] for r in await receipts(ports, item_id)] == results
    record = (await records(ports, [ref]))[item_id]
    assert (record["outcome"], record["reason"]) == outcome
    clock = ports.clock
    assert isinstance(clock, FakeClock)
    assert len(clock.sleeps) == len(sleeps)
    for slept, (low, high) in zip(clock.sleeps, sleeps, strict=True):
        assert low <= slept <= high


async def test_no_send_is_scheduled_past_the_stage_budget(ports, runtime):
    runtime = with_runtime(runtime, enrichment_stage_budget_s={"p50": 0.5, "hard": 0.9})
    input = await native(ports, runtime, one_picture_paper())
    ports = dataclasses.replace(ports, vlm=answers(*[unavailable()] * 3))

    (ref,) = await run_vlm(ports, runtime, input.inventory)

    assert len(ports.vlm.requests) == 1
    assert ports.clock.sleeps == []  # type: ignore[attr-defined]
    record = (await records(ports, [ref]))[ref.item_id]
    assert (record["outcome"], record["reason"]) == ("failed", "SERVICE_UNAVAILABLE")


async def test_the_stage_budget_bounds_first_sends_too(ports, runtime):
    runtime = with_runtime(runtime, vlm_concurrency_per_document=1)
    input = await native(ports, runtime, two_picture_paper())
    clock = ports.clock
    assert isinstance(clock, FakeClock)

    def slow(request: dict) -> Completion:
        clock.now += 300  # longer than the hard budget of 240 s
        return canned(request)

    ports = dataclasses.replace(ports, vlm=FakeInference(slow))

    outcomes = await run_vlm(ports, runtime, input.inventory)

    assert len(ports.vlm.requests) == 1
    by_id = await records(ports, outcomes)
    assert [(r["outcome"], r["reason"]) for r in by_id.values()] == [
        ("success", None),
        ("failed", "SERVICE_UNAVAILABLE"),
    ]


# --- what fails the document -----------------------------------------------------------------


@pytest.mark.parametrize("earlier", [0, 1])
async def test_a_send_past_the_request_cap_fails_the_document(ports, runtime, earlier):
    runtime = with_runtime(
        runtime, request_cap={"per_item": 0, "extra": 1}, vlm_concurrency_per_document=1
    )
    input = await native(ports, runtime, two_picture_paper())
    for n in range(earlier):  # a send of another Activity of this attempt
        await ports.store.put(f"requests/req_1/attempts/run_1/receipts/other:#/x/{n}/1.json", b"{}")

    with pytest.raises(ProcessingFailure) as caught:
        await run_vlm(ports, runtime, input.inventory)

    failure = caught.value
    assert (failure.cause, failure.category, failure.reason) == (
        "platform",
        "configuration",
        "REQUEST_CAP_EXCEEDED",
    )
    assert failure.metadata["limit"] == "1"
    assert failure.metadata["item_id"].startswith("picture-interpretation:")
    assert len(ports.vlm.requests) == 1 - earlier


async def test_a_rejected_request_fails_the_document(ports, runtime):
    input = await native(ports, runtime, one_picture_paper())
    ports = dataclasses.replace(ports, vlm=answers(RequestRejected(401)))

    with pytest.raises(ProcessingFailure) as caught:
        await run_vlm(ports, runtime, input.inventory)

    failure = caught.value
    assert (failure.cause, failure.category, failure.reason) == (
        "platform",
        "configuration",
        "INFERENCE_REQUEST_REJECTED",
    )
    assert failure.metadata == {"item_id": "picture-interpretation:#/pictures/0", "status": "401"}


# --- reuse, concurrency, heartbeat -----------------------------------------------------------


async def test_a_second_run_sends_nothing(ports, runtime):
    input = await native(ports, runtime, enriched_paper())
    first = await run_vlm(ports, runtime, input.inventory)
    sent = len(ports.vlm.requests)
    objects = dict(ports.store.objects)  # type: ignore[attr-defined]

    again = await run_vlm(ports, runtime, input.inventory, "req_2", "run_2")

    assert sent == 2
    assert len(ports.vlm.requests) == sent  # V3: no VLM call the second time
    assert again == [dataclasses.replace(o, reused=True) for o in first]
    assert ports.store.objects == objects  # type: ignore[attr-defined]


async def test_items_run_four_at_a_time(ports, runtime):
    input = await native(ports, runtime, one_picture_paper())
    inv = await clones(ports, input.inventory, 6)
    flight = {"now": 0, "max": 0}

    async def answer(request: dict) -> Completion:
        flight["now"] += 1
        flight["max"] = max(flight["max"], flight["now"])
        await asyncio.sleep(0.05)
        flight["now"] -= 1
        return canned(request)

    ports = dataclasses.replace(ports, vlm=FakeInference(answer))

    outcomes = await run_vlm(ports, runtime, inv)

    assert flight["max"] == runtime.profile.runtime["vlm_concurrency_per_document"] == 4
    assert [o.item_id for o in outcomes] == [f"picture-interpretation:#/pictures/{n}"
                                             for n in range(6)]  # fmt: skip


async def test_every_item_run_or_reused_sends_a_heartbeat(ports, runtime):
    beats = []
    ports = dataclasses.replace(ports, heartbeat=lambda: beats.append(1))
    input = await native(ports, runtime, enriched_paper())

    outcomes = await run_vlm(ports, runtime, input.inventory)
    await run_vlm(ports, runtime, input.inventory)

    assert len(beats) == 2 * len(outcomes) == 6


# --- SERVICE_UNAVAILABLE and redrive ---------------------------------------------------------


async def test_service_unavailable_completes_the_document_and_leaves_a_redrive_marker(
    ports, runtime
):
    input = await native(ports, runtime, one_picture_paper())
    ports = dataclasses.replace(ports, vlm=answers(*[unavailable()] * 3))

    (outcome,) = await run_vlm(ports, runtime, input.inventory)
    result = await finalized(ports, runtime, input, [outcome])

    assert result["outcome"] == "complete"
    assert outcome.ref.startswith("requests/req_1/attempts/run_1/outcomes/")
    assert await ports.store.list_prefix("documents/doc_1/service-unavailable/") == [
        "documents/doc_1/service-unavailable/req_1"
    ]
    assert await ports.store.get("documents/doc_1/service-unavailable/req_1") == b""
    assert await finalize.service_unavailable(ports.store) == [
        {"document_uid": "doc_1", "request_id": "req_1"}
    ]


async def test_a_redrive_sends_again_instead_of_reusing_the_failure(ports, runtime):
    input = await native(ports, runtime, one_picture_paper())
    down = dataclasses.replace(ports, vlm=answers(*[unavailable()] * 3))
    await run_vlm(down, runtime, input.inventory)

    (outcome,) = await run_vlm(ports, runtime, input.inventory, "req_2", "run_2")

    assert len(ports.vlm.requests) == 1
    assert not outcome.reused
    assert outcome.ref.startswith("documents/doc_1/items/")
    record = (await records(ports, [outcome]))[outcome.item_id]
    assert record["outcome"] == "success"


async def test_a_document_without_service_failures_leaves_no_marker(ports, runtime):
    input = await native(ports, runtime, one_picture_paper())

    result = await finalized(ports, runtime, input, await run_vlm(ports, runtime, input.inventory))

    assert result["outcome"] == "complete"
    assert await finalize.service_unavailable(ports.store) == []


async def test_the_redrive_list_names_every_marked_request(ports):
    for uid, request_id in [("doc_2", "req_9"), ("doc_1", "req_3"), ("doc_1", "req_4")]:
        await ports.store.put(f"documents/{uid}/service-unavailable/{request_id}", b"")
    await ports.store.put("documents/doc_1/items/abc/outcome.json", b"{}")

    assert await finalize.service_unavailable(ports.store) == [
        {"document_uid": "doc_1", "request_id": "req_3"},
        {"document_uid": "doc_1", "request_id": "req_4"},
        {"document_uid": "doc_2", "request_id": "req_9"},
    ]


# --- V7: hung transports under the real adapter ----------------------------------------------


@pytest.mark.parametrize("variant", ["silent", "headers", "drip"])
async def test_v7_a_hung_service_ends_the_item_and_the_document_completes(ports, runtime, variant):
    total_s = 0.3
    hang = Hang(variant)
    chat = OpenAIChat(httpx.AsyncClient(transport=hang), "http://vlm.test/v1", "k", "gpt-6-luna",
                      connect_s=5, total_s=total_s)  # fmt: skip
    input = await native(ports, runtime, one_picture_paper())
    ports = dataclasses.replace(ports, vlm=chat)
    item_id = "picture-interpretation:#/pictures/0"

    (outcome,) = await run_vlm(ports, runtime, input.inventory)
    result = await finalized(ports, runtime, input, [outcome])

    sent = await receipts(ports, item_id)
    assert [(r["result"], r["reason"]) for r in sent] == [("unavailable", "TIMEOUT")] * 3
    assert all(total_s * 1000 <= r["latency_ms"] <= (total_s + 5) * 1000 for r in sent)
    assert hang.ended() == 3
    record = (await records(ports, [outcome]))[item_id]
    assert (record["outcome"], record["reason"]) == ("failed", "SERVICE_UNAVAILABLE")
    assert result["outcome"] == "complete"
    assert await finalize.service_unavailable(ports.store) == [
        {"document_uid": "doc_1", "request_id": "req_1"}
    ]


# --- V9: receipt overhead --------------------------------------------------------------------


class TimingStore:
    """Wraps a store and adds the time of each receipt call to its item's total."""

    def __init__(self, store) -> None:
        self.store = store
        self.per_item: dict[str, list[float]] = {}

    def __getattr__(self, name: str):
        call = getattr(self.store, name)

        async def timed(key: str, *args):
            started = time.perf_counter()
            try:
                return await call(key, *args)
            finally:
                if "/receipts/" in key:
                    item = key.split("/receipts/", 1)[1].rsplit("/", 1)[0]
                    self.per_item.setdefault(item, []).append(time.perf_counter() - started)

        return timed


@pytest.fixture(params=["dict", pytest.param("s3", marks=pytest.mark.s3)])
async def v9_store(request):
    if request.param == "dict":
        return DictObjectStore()
    if not os.environ.get("KP_S3_ENDPOINT"):
        pytest.skip("KP_S3_ENDPOINT not set; start tests/s3/compose.yaml")
    store = S3ObjectStore.from_env()
    if not store.client.list_buckets()["Buckets"]:
        store.client.create_bucket(Bucket=store.bucket)
    return store


async def test_v9_receipts_add_under_100_ms_per_request_at_p95(ports, runtime, v9_store):
    input = await native(ports, runtime, one_picture_paper())
    inv = await clones(ports, input.inventory, 30)
    for key, data in ports.store.objects.items():  # type: ignore[attr-defined]
        await v9_store.put(key, data)
    timing = TimingStore(v9_store)
    ports = dataclasses.replace(ports, store=timing)

    # A fresh document and attempt, so that nothing in a shared store is reused.
    fresh = uuid.uuid4().hex
    await run_vlm(ports, runtime, inv, run_id=f"run_{fresh}", document_uid=f"doc_{fresh}")

    assert len(ports.vlm.requests) == 30
    per_request = [sum(calls) for calls in timing.per_item.values()]
    assert len(per_request) == 30
    assert all(len(calls) >= 2 for calls in timing.per_item.values())  # written, completed
    p95 = statistics.quantiles(per_request, n=20)[-1]
    assert 0 < p95 < 0.1


async def test_an_exception_inside_a_vlm_method_is_a_method_failure(ports, runtime, monkeypatch):
    input = await native(ports, runtime, enriched_paper())

    def broken(item, inputs):
        raise RuntimeError("bug")

    monkeypatch.setattr(code, "request", broken)

    with pytest.raises(ProcessingFailure) as caught:
        await run_vlm(ports, runtime, input.inventory)

    failure = caught.value
    assert (failure.cause, failure.category, failure.reason) == (
        "platform",
        "method",
        "METHOD_ERROR",
    )
    assert failure.metadata["item_id"].startswith("code:#/texts/")
