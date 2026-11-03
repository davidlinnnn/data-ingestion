"""Seam A, V6: the summary enrichment Activity (#134) with real docling and the summary API's
in-process fake: the provisional request, evidence alignment, the status it leads to, the
retry chain it shares with the VLM Activity, and the document-scope enrichment in the
Processing Result."""

import dataclasses
import json

import pytest

from kp_processing.ports.inference import FakeInference, ServiceUnavailable
from kp_processing.stages import EnrichInput, ProcessingFailure, enrich_local, enrich_vlm, finalize
from tests.pdfs import Page, write_pdf
from tests.stages.test_enrich_local import CODE, PICTURE_WORDS, enriched_paper, native, records
from tests.summary import MODEL, answer, completion

INTRO = [
    "Glaciers retreat faster when meltwater reaches the bedrock beneath them.",
    "This lubrication lets the ice slide over its bed during the warm season.",
]
METHOD = [
    "We measured surface velocity with radar interferometry across twelve outlet glaciers.",
    "Each glacier was observed every eleven days for three consecutive years.",
]
RESULTS = [
    "Velocity doubled during summer months while winter flow remained stable.",
    "The largest speedups followed heavy rainfall on the lower ablation zone.",
]
# What docling reads from summary_paper() (probed 2026-11-01): one heading per page; page 2's two
# lines merge into one paragraph; the code listing is its own item.
SECTIONS = [
    {"section_id": "#/texts/0", "heading": "1 Introduction", "text": "\n".join(INTRO)},
    {"section_id": "#/texts/3", "heading": "2 Method", "text": " ".join(METHOD)},
    {"section_id": "#/texts/6", "heading": "3 Results", "text": "\n".join(RESULTS)},
]
ITEM_ID = "document-summary:#"


def summary_paper() -> bytes:
    """Three sections on distinct topics, and a code listing that is not body text."""
    return write_pdf(
        [
            Page(lines=["1 Introduction", *INTRO]),
            Page(lines=["2 Method", *METHOD], code=CODE),
            Page(lines=["3 Results", *RESULTS]),
        ]
    )


def responding(*bodies: dict | str | Exception) -> FakeInference:
    """Answer each request with the next entry: a response body (dict), raw content (str) or an
    exception to raise."""
    queue = list(bodies)

    def reply(request: dict):
        entry = queue.pop(0)
        if isinstance(entry, dict):
            return completion(entry)
        if isinstance(entry, str):
            return dataclasses.replace(completion({"model": MODEL, "sentences": []}),
                                       content=entry, body=entry.encode())  # fmt: skip
        return entry

    return FakeInference(reply)


def sentences(*entries: tuple[str, list[str] | None]) -> dict:
    """A response body; evidence None leaves the "evidence" key out."""
    out = []
    for text, evidence in entries:
        sentence: dict = {"text": text}
        if evidence is not None:
            sentence["evidence"] = [{"section_id": s} for s in evidence]
        out.append(sentence)
    return {"model": MODEL, "sentences": out}


async def run_summary(ports, runtime, input, request_id="req_1", run_id="run_1"):
    return await enrich_vlm.run_summary(
        EnrichInput("doc_1", input.inventory, request_id, run_id), ports, runtime
    )


async def summarized(ports, runtime, transport: FakeInference, pdf: bytes | None = None):
    """native() of the paper, then the summary Activity against transport; (input, the outcome
    record)."""
    ports = dataclasses.replace(ports, summary=transport)
    input = await native(ports, runtime, pdf or summary_paper())
    (outcome,) = await run_summary(ports, runtime, input)
    assert outcome.item_id == ITEM_ID
    return input, (await records(ports, [outcome]))[ITEM_ID], outcome


async def summary_enrichment(ports, runtime, input, outcome) -> dict:
    """The Processing Result's summary enrichment, after local and VLM enrichment."""
    item_input = EnrichInput("doc_1", input.inventory, "req_1", "run_1")
    outcomes = await enrich_local.run(item_input, ports, runtime)
    outcomes += await enrich_vlm.run(item_input, ports, runtime)
    final = dataclasses.replace(input, outcomes=[*outcomes, outcome])
    result = json.loads(await ports.store.get(await finalize.run(final, ports, runtime)))
    (enrichment,) = [e for e in result["enrichments"] if e["item_id"] == ITEM_ID]
    return enrichment


# --- inventory and request ----------------------------------------------------------------


async def test_inventory_lists_one_document_item_for_the_summary(ports, runtime):
    input = await native(ports, runtime, summary_paper())

    items = json.loads(await ports.store.get(input.inventory.ref))["items"]

    assert items[-1] == {
        "item_id": ITEM_ID,
        "method": "document-summary",
        "target_ref": "#",
        "document_uid": "doc_1",
        "input_refs": [{"ref": input.assembly.ref, "sha256": input.assembly.digest}],
    }
    assert [i["item_id"] for i in items].count(ITEM_ID) == 1


async def test_one_request_carries_the_headings_and_body_text(ports, runtime):
    transport = FakeInference(lambda request: completion(answer(request)))

    await summarized(ports, runtime, transport)

    assert transport.requests == [
        {"document_uid": "doc_1", "sections": SECTIONS, "max_sentences": 5}
    ]


async def test_the_summary_reads_native_text_only_never_other_enrichments(ports, runtime):
    # Run on a fresh store, then on a store where local and VLM enrichment already registered
    # OCR words, interpretations and code: the request must not change.
    fresh = FakeInference(lambda request: completion(answer(request)))
    await summarized(ports, runtime, fresh, enriched_paper())
    enriched_ports = dataclasses.replace(ports, store=type(ports.store)())
    input = await native(enriched_ports, runtime, enriched_paper())
    item_input = EnrichInput("doc_1", input.inventory, "req_1", "run_1")
    await enrich_local.run(item_input, enriched_ports, runtime)
    await enrich_vlm.run(item_input, enriched_ports, runtime)
    after = FakeInference(lambda request: completion(answer(request)))

    await run_summary(dataclasses.replace(enriched_ports, summary=after), runtime, input)

    assert after.requests == fresh.requests
    sent = json.dumps(after.requests)
    for text in [*PICTURE_WORDS, "Encoder", "def fib", "return b"]:
        assert text not in sent
    assert [s["heading"] for s in after.requests[0]["sections"]] == [
        "1 Architecture",
        "2 Method",
        "3 Results",
    ]


# --- alignment and status -----------------------------------------------------------------


async def test_sentences_citing_sent_sections_are_supported_and_unverified(ports, runtime):
    body = sentences(
        ("Meltwater at the bed speeds glacier retreat.", ["#/texts/0"]),
        ("Summer velocity doubled.", ["#/texts/6", "#/texts/3"]),
    )

    input, record, outcome = await summarized(ports, runtime, responding(body))

    assert record["outcome"] == "success"
    assert record["content"] == {
        "sentences": [
            {"text": "Meltwater at the bed speeds glacier retreat.",
             "evidence": [{"section_id": "#/texts/0"}], "support": "provider"},
            {"text": "Summer velocity doubled.",
             "evidence": [{"section_id": "#/texts/6"}, {"section_id": "#/texts/3"}],
             "support": "provider"},
        ]
    }  # fmt: skip
    assert record["contradictions"] == []
    enrichment = await summary_enrichment(ports, runtime, input, outcome)
    assert (enrichment["status"], enrichment["status_reason"]) == ("unverified", None)


@pytest.mark.parametrize("evidence", [None, []])
async def test_a_sentence_without_evidence_is_aligned_by_word_overlap(ports, runtime, evidence):
    body = sentences(("Surface velocity was measured with radar interferometry.", evidence))

    _, record, _ = await summarized(ports, runtime, responding(body))

    (sentence,) = record["content"]["sentences"]
    assert sentence["evidence"] == [{"section_id": "#/texts/3"}]
    assert sentence["support"] == "overlap"
    assert record["contradictions"] == []


async def test_a_sentence_no_section_supports_makes_the_summary_disputed(ports, runtime):
    body = sentences(
        ("Surface velocity was measured with radar interferometry.", None),
        ("Penguins migrate across the southern ocean every winter.", None),
    )

    input, record, outcome = await summarized(ports, runtime, responding(body))

    assert [(s["support"], s["evidence"]) for s in record["content"]["sentences"]] == [
        ("overlap", [{"section_id": "#/texts/3"}]),
        ("none", []),
    ]
    assert record["contradictions"] == ["UNSUPPORTED_SENTENCE"]
    enrichment = await summary_enrichment(ports, runtime, input, outcome)
    assert (enrichment["status"], enrichment["status_reason"]) == (
        "disputed",
        "UNSUPPORTED_SENTENCE",
    )


async def test_evidence_naming_only_unsent_sections_is_no_support(ports, runtime):
    # The text would align by overlap; a citation of a section never sent is not replaced.
    body = sentences(
        ("Surface velocity was measured with radar interferometry.", ["#/texts/99"]),
        ("Velocity doubled during summer months.", ["#/texts/99", "#/texts/6"]),
    )

    _, record, _ = await summarized(ports, runtime, responding(body))

    assert [(s["support"], s["evidence"]) for s in record["content"]["sentences"]] == [
        ("none", []),
        ("provider", [{"section_id": "#/texts/6"}]),
    ]
    assert record["contradictions"] == ["UNSUPPORTED_SENTENCE"]


async def test_the_dev_mock_answers_with_and_without_evidence_and_both_are_supported(
    ports, runtime
):
    transport = FakeInference(lambda request: completion(answer(request)))

    input, record, outcome = await summarized(ports, runtime, transport)

    assert [(s["support"], s["evidence"]) for s in record["content"]["sentences"]] == [
        ("provider", [{"section_id": "#/texts/0"}]),
        ("overlap", [{"section_id": "#/texts/3"}]),
    ]
    first, second = record["content"]["sentences"]
    assert first["text"].split() == " ".join(INTRO).split()[:12]
    assert second["text"].split() == " ".join(METHOD).split()[:12]
    enrichment = await summary_enrichment(ports, runtime, input, outcome)
    assert (enrichment["status"], enrichment["status_reason"]) == ("unverified", None)


# --- failures -------------------------------------------------------------------------------


async def test_an_unavailable_service_fails_the_summary_and_the_document_completes(ports, runtime):
    down = ServiceUnavailable("HTTP_5XX")

    input, record, outcome = await summarized(ports, runtime, responding(down, down, down))

    assert (record["outcome"], record["reason"]) == ("failed", "SERVICE_UNAVAILABLE")
    assert outcome.ref.startswith("requests/req_1/attempts/run_1/outcomes/")
    receipts = await ports.store.list_prefix(f"requests/req_1/attempts/run_1/receipts/{ITEM_ID}/")
    assert len(receipts) == 3
    enrichment = await summary_enrichment(ports, runtime, input, outcome)
    assert (enrichment["status"], enrichment["status_reason"]) == ("failed", "SERVICE_UNAVAILABLE")
    assert await ports.store.head("documents/doc_1/service-unavailable/req_1") is not None


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("", "EMPTY_OUTPUT"),
        (json.dumps({"model": MODEL, "sentences": []}), "EMPTY_OUTPUT"),
        ("{not json", "SCHEMA_INVALID"),
        (json.dumps({"model": MODEL, "sentences": "Glaciers retreat."}), "SCHEMA_INVALID"),
        (json.dumps({"model": MODEL, "sentences": [{"text": "  "}]}), "SCHEMA_INVALID"),
        (
            json.dumps({"model": MODEL, "sentences": [{"text": "x", "evidence": "#/texts/0"}]}),
            "SCHEMA_INVALID",
        ),  # fmt: skip
        (json.dumps(sentences(*[("Glaciers retreat.", ["#/texts/0"])] * 6)), "SCHEMA_INVALID"),
    ],
)
async def test_an_invalid_answer_is_resent_once_then_fails(ports, runtime, content, reason):
    transport = responding(content, content)

    _, record, _ = await summarized(ports, runtime, transport)

    assert len(transport.requests) == 2
    assert (record["outcome"], record["reason"]) == ("failed", reason)


async def test_extra_response_fields_are_ignored(ports, runtime):
    body = sentences(("Meltwater at the bed speeds glacier retreat.", ["#/texts/0"]))
    body["usage"] = {"input_tokens": 400}
    body["sentences"][0]["confidence"] = 0.9

    _, record, _ = await summarized(ports, runtime, responding(body))

    assert record["outcome"] == "success"
    assert record["content"]["sentences"][0]["support"] == "provider"


async def test_a_summary_worker_without_a_transport_fails_the_document(ports, runtime):
    ports = dataclasses.replace(ports, summary=None)
    input = await native(ports, runtime, summary_paper())

    with pytest.raises(ProcessingFailure) as caught:
        await run_summary(ports, runtime, input)

    failure = caught.value
    assert (failure.category, failure.reason) == ("configuration", "METHOD_UNAVAILABLE")
    assert failure.metadata["item_id"] == ITEM_ID


# --- egress, reuse and the Processing Result ------------------------------------------------


async def test_each_activity_sends_only_through_its_own_service(ports, runtime):
    input = await native(ports, runtime, enriched_paper())
    item_input = EnrichInput("doc_1", input.inventory, "req_1", "run_1")

    await enrich_vlm.run(item_input, ports, runtime)
    assert ports.summary.requests == []  # type: ignore[union-attr]
    vlm_sent = len(ports.vlm.requests)  # type: ignore[union-attr]
    assert vlm_sent > 0

    await enrich_vlm.run_summary(item_input, ports, runtime)
    assert len(ports.summary.requests) == 1  # type: ignore[union-attr]
    assert len(ports.vlm.requests) == vlm_sent  # type: ignore[union-attr]


async def test_a_second_run_reuses_the_summary_without_a_request(ports, runtime):
    transport = FakeInference(lambda request: completion(answer(request)))
    input, _, first = await summarized(ports, runtime, transport)

    (again,) = await run_summary(
        dataclasses.replace(ports, summary=transport), runtime, input, "req_2", "run_2"
    )

    assert len(transport.requests) == 1
    assert (again.ref, again.digest, again.reused) == (first.ref, first.digest, True)


async def test_the_processing_result_carries_a_document_scope_summary(ports, runtime):
    transport = FakeInference(lambda request: completion(answer(request)))
    input, record, outcome = await summarized(ports, runtime, transport)
    method = runtime.profile.methods["document-summary"]

    enrichment = await summary_enrichment(ports, runtime, input, outcome)

    prefix = outcome.ref.rsplit("/", 1)[0]
    assert enrichment == {
        "item_id": ITEM_ID,
        "result_ref": outcome.ref,
        "method_ref": {"id": "document-summary", "version": 1, "digest": method.module_digest},
        "scope": "document",
        "origin": "interpretation",
        "target_refs": ["#"],
        "input_refs": [input.assembly.ref],
        "content": record["content"],
        "evidence_refs": [],
        "status": "unverified",
        "status_reason": None,
        "signals": {},
        "provider_artifact_ref": f"{prefix}/response.json",
        "reused": False,
    }
    response = json.loads(await ports.store.get(f"{prefix}/response.json"))
    assert response["model"] == MODEL
    result = json.loads(await ports.store.get("requests/req_1/result.json"))
    assert result["inventory"]["counts"]["document-summary"] == {
        "unverified": 1, "disputed": 0, "failed": 0, "no_text": 0
    }  # fmt: skip
