"""Seam A: the Document Summary (#155) with real docling and the model's in-process fake: the
Section rules, chunking, map, verify, repair and reduce, the failure paths and their statuses,
receipts and reuse, and the summary in the Processing Result."""

import asyncio
import dataclasses
import json

import pytest

from kp_processing.methods import document_summary
from kp_processing.ports.inference import FakeInference, ServiceUnavailable, completion
from kp_processing.stages import (
    ChunkInput,
    EnrichInput,
    OverviewInput,
    ProcessingFailure,
    enrich_local,
    enrich_vlm,
    finalize,
    summary,
)
from kp_processing.stages.summary import NoAnswer
from tests.pdfs import Page, write_pdf
from tests.stages.conftest import with_runtime
from tests.stages.test_enrich_local import native, records
from tests.summary import answer, fake_llm, prompt, reply, step, summarize_all

ITEM_ID = "document-summary:#"
RECEIPTS = f"requests/req_1/attempts/run_1/receipts/{ITEM_ID}"
INTRO = "Line 1 reports that glacier measurements changed by 1 percent this year."
METHOD = "Line 1 reports that radar measurements changed by 1 percent this year."


def lines(topic: str, count: int) -> list[str]:
    return [f"Line {i} reports that {topic} measurements changed by {i} percent this year."
            for i in range(1, count + 1)]  # fmt: skip


def summary_paper() -> bytes:
    """What docling reads from it (probed 2026-11-03): Introduction (881 characters), Method
    (857) and Note (139, too short for a sentence) are summarized; References and
    Acknowledgments are skipped."""
    return write_pdf(
        [
            Page(lines=["1 Introduction", *lines("glacier", 12)]),
            Page(lines=["2 Method", *lines("radar", 12)]),
            Page(lines=["4 Note", *lines("note", 2)]),
            Page(lines=["References", "[1] A. Author. A paper on ice. 2020."]),
            Page(lines=["Acknowledgments", "We thank the funding agency for its support."]),
        ]
    )


def enrich(input, request_id="req_1") -> EnrichInput:
    return EnrichInput("doc_1", input.inventory, request_id, "run_1")


async def summarized(ports, runtime, transport: FakeInference, complete=True):
    """native() of the summary paper, then the summary Activities against transport; (input,
    outcome record, OutcomeRef)."""
    ports = dataclasses.replace(ports, summary=transport)
    input = await native(ports, runtime, summary_paper())
    (outcome,) = await summarize_all(ports, runtime, enrich(input), complete)
    assert outcome.item_id == ITEM_ID
    return input, (await records(ports, [outcome]))[ITEM_ID], outcome


async def section_ids(ports) -> dict[str, str]:
    """Each summarized Section's id by heading, from sections.json: docling numbers its texts
    differently across platforms."""
    (key,) = [k for k in await ports.store.list_prefix("documents/doc_1/items/")
              if k.endswith("/sections.json")]  # fmt: skip
    return {
        s["heading"]: s["section_id"] for s in json.loads(await ports.store.get(key))["sections"]
    }


async def summary_enrichment(ports, runtime, input, outcome) -> dict:
    """The Processing Result's summary enrichment, after local and VLM enrichment."""
    outcomes = await enrich_local.run(enrich(input), ports, runtime)
    outcomes += await enrich_vlm.run(enrich(input), ports, runtime)
    final = dataclasses.replace(input, outcomes=[*outcomes, outcome])
    result = json.loads(await ports.store.get(await finalize.run(final, ports, runtime)))
    (enrichment,) = [e for e in result["enrichments"] if e["item_id"] == ITEM_ID]
    return enrichment


def steps(transport: FakeInference) -> list[str]:
    return [step(request) for request in transport.requests]


def failing(at: str, error: Exception | str, then=None) -> FakeInference:
    """The fake, except that every request of step at raises error, or gets error as its
    content."""

    def reply_to(request: dict):
        if step(request) != at:
            return reply(answer(request))
        if isinstance(error, Exception):
            return error
        return completion(error)

    return FakeInference(reply_to)


# --- Sections and chunks (A8-A10) -------------------------------------------------------------


@pytest.mark.parametrize(
    ("heading", "text", "reason"),
    [
        ("7 References", "[1] x", "REFERENCES"),
        ("REFERENCES.", "[1] x", "REFERENCES"),
        ("Bibliography:", "[1] x", "REFERENCES"),
        ("參考文獻", "[1] x", "REFERENCES"),
        ("Acknowledgments and Disclosure of Funding", "We thank", "ACKNOWLEDGEMENTS"),
        ("致謝", "感謝", "ACKNOWLEDGEMENTS"),
        ("3 Results", "  \n ", "EMPTY"),
        ("2 Related Work", "Prior work [1] ...", None),  # cites references but is not them
        ("References to prior work", "text", None),  # the whole heading must match
        ("A.1 Proofs", "text", None),  # appendices are summarized
    ],
)
def test_a_section_is_skipped_only_for_its_heading_or_no_text(heading, text, reason):
    assert document_summary.skip_reason(heading, text) == reason


@pytest.mark.parametrize(
    ("chars", "sentences"), [(0, 0), (499, 0), (500, 1), (1500, 1), (1501, 2), (40_000, 8)]
)
def test_a_section_gets_a_sentence_per_1500_characters_up_to_8(chars, sentences):
    assert document_summary.section_target(chars) == sentences


@pytest.mark.parametrize(
    ("chars", "sentences"), [(1_000, 5), (80_000, 10), (136_201, 15), (500_000, 15)]
)
def test_the_overview_gets_a_sentence_per_8000_characters_from_5_to_15(chars, sentences):
    assert document_summary.overview_target(chars) == sentences


def test_whole_sections_are_packed_to_8000_characters_and_never_split():
    assert document_summary.pack([5000, 3000, 1, 9000, 100, 100]) == [[0, 1], [2], [3], [4, 5]]
    assert document_summary.pack([]) == []


async def test_sections_hold_native_text_and_record_what_was_skipped(ports, runtime):
    input = await native(ports, runtime, summary_paper())

    plan = await summary.run_sections(enrich(input), ports, runtime)

    assert plan.sections is not None and plan.outcome is None
    document = json.loads(await ports.store.get(plan.sections.ref))
    assert plan.sections.ref == f"documents/doc_1/items/{plan.key}/sections.json"
    assert [(s["heading"], len(s["text"]), s["target"]) for s in document["sections"]] == [
        ("1 Introduction", 881, 1),
        ("2 Method", 857, 1),
        ("4 Note", 139, 0),
    ]
    assert document["sections"][0]["text"].startswith(INTRO)
    assert [(s["heading"], s["reason"]) for s in document["skipped"]] == [
        ("References", "REFERENCES"),
        ("Acknowledgments", "ACKNOWLEDGEMENTS"),
    ]
    assert (document["title"], document["chunks"], plan.chunks) == (
        "1 Introduction",
        [[0, 1, 2]],
        1,
    )


# --- the pipeline ---------------------------------------------------------------------------


async def test_a_summary_is_an_overview_citing_sections_and_a_summary_per_section(ports, runtime):
    transport = fake_llm()

    input, record, outcome = await summarized(ports, runtime, transport)

    ids = await section_ids(ports)
    assert (record["outcome"], record["reason"], record["contradictions"]) == ("success", None, [])
    assert record["content"] == {
        "overview": [
            {"text": INTRO, "evidence": [{"section_id": ids["1 Introduction"]}]},
            {"text": METHOD, "evidence": [{"section_id": ids["2 Method"]}]},
        ],
        "sections": [
            {"section_id": ids["1 Introduction"], "heading": "1 Introduction",
             "sentences": [{"text": INTRO}]},
            {"section_id": ids["2 Method"], "heading": "2 Method",
             "sentences": [{"text": METHOD}]},
            {"section_id": ids["4 Note"], "heading": "4 Note", "sentences": []},
        ],
    }  # fmt: skip
    assert record["signals"] == {"rewritten": 0, "dropped": 0}
    # One map for the chunk, one verify per section with sentences, one reduce, one verify per
    # overview sentence against its cited section only.
    assert steps(transport) == ["map", "verify", "verify", "reduce", "verify", "verify"]
    (map_prompt, *_, overview_verify) = [prompt(r) for r in transport.requests]
    assert "<paper_title>1 Introduction</paper_title>" in map_prompt
    assert "S3 4 Note" in map_prompt and "- S3:" not in map_prompt  # outline, but no target
    assert "glacier" not in overview_verify  # the Method sentence, against Method only
    sent = " ".join(prompt(r) for r in transport.requests)
    assert "A paper on ice" not in sent and "funding agency" not in sent


async def test_the_record_keeps_skipped_sections_fates_and_usage(ports, runtime):
    _, record, outcome = await summarized(ports, runtime, fake_llm())

    prefix = outcome.ref.rsplit("/", 1)[0]
    assert record["provider_artifact_ref"] == f"{prefix}/record.json"
    detail = json.loads(await ports.store.get(f"{prefix}/record.json"))
    assert detail["schema"] == "document-summary-record/v1"
    assert [s["heading"] for s in detail["skipped"]] == ["References", "Acknowledgments"]
    assert detail["overview"]["target"] == 5
    assert detail["steps"] == {
        "map": {"calls": 1, "prompt_tokens": 1, "completion_tokens": 1},
        "verify": {"calls": 4, "prompt_tokens": 4, "completion_tokens": 4},
        "reduce": {"calls": 1, "prompt_tokens": 1, "completion_tokens": 1},
    }
    assert len(detail["responses"]) == 6
    for name in detail["responses"]:
        assert await ports.store.head(f"{prefix}/{name}") is not None


async def test_an_unsupported_sentence_is_rewritten_with_the_judges_reason(ports, runtime):
    transport = fake_llm(judge=lambda s: "glacier" not in s, rewrite=lambda s: "Ice moved.")

    _, record, outcome = await summarized(ports, runtime, transport)

    assert record["content"]["sections"][0]["sentences"] == [{"text": "Ice moved."}]
    assert record["content"]["overview"][0]["text"] == "Ice moved."
    (repair,) = [prompt(r) for r in transport.requests if step(r) == "repair"]
    assert f"<sentence>{INTRO}</sentence>" in repair and "<problem>judged 1</problem>" in repair
    detail = json.loads(await ports.store.get(outcome.ref.replace("outcome.json", "record.json")))
    assert detail["sections"][0]["fates"] == [
        {"text": "Ice moved.", "original": INTRO, "reason": "judged 1"}
    ]
    assert record["signals"] == {"rewritten": 1, "dropped": 0}


@pytest.mark.parametrize("rewrite", ["", "Glacier speed doubled."])
async def test_a_sentence_still_unsupported_after_repair_is_dropped(ports, runtime, rewrite):
    transport = fake_llm(judge=lambda s: "glacier" not in s.lower(), rewrite=lambda s: rewrite)

    _, record, outcome = await summarized(ports, runtime, transport)

    assert record["content"]["sections"][0]["sentences"] == []
    assert [o["text"] for o in record["content"]["overview"]] == [METHOD]
    detail = json.loads(await ports.store.get(outcome.ref.replace("outcome.json", "record.json")))
    (fate,) = detail["sections"][0]["fates"]
    assert fate == {"text": None, "original": INTRO, "reason": "judged 1", "rewrite": rewrite,
                    "second_reason": "judged 1" if rewrite else None}  # fmt: skip
    # Two sections, one overview sentence, and the rewrite's verify unless it is empty.
    assert steps(transport).count("verify") == (4 if rewrite else 3)
    assert record["signals"] == {"rewritten": 0, "dropped": 1}


async def test_no_supported_sentence_fails_the_summary_without_a_reduce(ports, runtime):
    transport = fake_llm(judge=lambda s: False, rewrite=lambda s: "")

    input, record, outcome = await summarized(ports, runtime, transport)

    assert (record["outcome"], record["reason"]) == ("failed", "NO_SUPPORTED_SENTENCE")
    assert "reduce" not in steps(transport)
    enrichment = await summary_enrichment(ports, runtime, input, outcome)
    assert (enrichment["status"], enrichment["status_reason"]) == (
        "failed",
        "NO_SUPPORTED_SENTENCE",
    )
    assert await ports.store.list_prefix("documents/doc_1/service-unavailable") == []


async def test_an_overview_sentence_without_a_valid_source_is_dropped(ports, runtime):
    def reply_to(request: dict):
        if step(request) == "reduce":
            return reply({"sentences": [{"text": "Unsourced.", "sources": [0, 9]},
                                        {"text": METHOD, "sources": [2, 2]}]})  # fmt: skip
        return reply(answer(request))

    _, record, _ = await summarized(ports, runtime, FakeInference(reply_to))

    assert record["content"]["overview"] == [
        {"text": METHOD, "evidence": [{"section_id": (await section_ids(ports))["2 Method"]}]}
    ]
    assert record["signals"]["dropped"] == 1


async def test_large_documents_run_one_chunk_activity_per_chunk(ports, runtime, monkeypatch):
    monkeypatch.setattr(document_summary, "CHUNK_CHARS", 1000)
    transport = fake_llm()

    _, record, _ = await summarized(ports, runtime, transport)

    # [Introduction], [Method], [Note]: Note has no target, so its chunk sends no map.
    assert steps(transport).count("map") == 2
    for name in ("c0", "c1", "c2", "overview"):
        receipts = await ports.store.list_prefix(f"{RECEIPTS}/{name}")
        assert len(receipts) == {"c0": 2, "c1": 2, "c2": 0, "overview": 3}[name]
    assert record["outcome"] == "success"


async def test_an_overview_left_empty_keeps_the_section_summaries(ports, runtime):
    def judge(sentence: str) -> bool:
        return sentence != METHOD  # the only overview sentence is unsupported

    def reply_to(request: dict):
        if step(request) == "reduce":
            return reply({"sentences": [{"text": METHOD, "sources": [2]}]})
        return reply(answer(request, judge, rewrite=lambda s: ""))

    _, record, _ = await summarized(ports, runtime, FakeInference(reply_to))

    assert record["outcome"] == "success"
    assert record["content"]["overview"] == []
    assert record["content"]["sections"][0]["sentences"] != []


async def test_a_reduce_without_a_sentence_is_empty_output(ports, runtime):
    transport = failing("reduce", json.dumps({"sentences": [{"text": " ", "sources": [1]}]}))

    _, record, _ = await summarized(ports, runtime, transport)

    assert (record["outcome"], record["reason"]) == ("failed", "EMPTY_OUTPUT")
    assert steps(transport).count("reduce") == 2


# --- failure paths --------------------------------------------------------------------------


async def test_a_chunk_without_an_answer_raises_for_a_temporal_retry(ports, runtime):
    ports = dataclasses.replace(ports, summary=failing("map", ServiceUnavailable("HTTP_5XX")))
    input = await native(ports, runtime, summary_paper())
    plan = await summary.run_sections(enrich(input), ports, runtime)

    with pytest.raises(NoAnswer) as caught:
        await summary.run_chunk(ChunkInput(enrich(input), plan, 0), ports, runtime)

    assert caught.value.reason == "SERVICE_UNAVAILABLE"
    assert len(await ports.store.list_prefix(f"{RECEIPTS}/c0")) == 3  # retry.max_attempts
    assert await ports.store.list_prefix(f"documents/doc_1/items/{plan.key}/chunks/") == []


@pytest.mark.parametrize(
    ("content", "reason"), [("{not json", "SCHEMA_INVALID"), ("", "EMPTY_OUTPUT")]
)
async def test_an_invalid_answer_is_resent_once_then_fails_the_summary(
    ports, runtime, content, reason
):
    transport = failing("verify", content)

    input, record, outcome = await summarized(ports, runtime, transport)

    assert (record["outcome"], record["reason"]) == ("failed", reason)
    assert steps(transport).count("verify") == 2 * 2  # two sections, each sent twice
    enrichment = await summary_enrichment(ports, runtime, input, outcome)
    assert (enrichment["status"], enrichment["status_reason"]) == ("failed", reason)


async def test_a_verify_answer_missing_a_verdict_is_invalid(ports, runtime):
    def reply_to(request: dict):
        if step(request) == "verify":
            return reply({"verdicts": []})
        return reply(answer(request))

    _, record, _ = await summarized(ports, runtime, FakeInference(reply_to))

    assert (record["outcome"], record["reason"]) == ("failed", "SCHEMA_INVALID")


async def test_a_refusal_fails_the_summary_and_is_not_sent_again(ports, runtime):
    transport = failing("reduce", "")
    transport.answer = lambda request: (
        completion(None, refusal="no") if step(request) == "reduce" else reply(answer(request))
    )

    _, record, _ = await summarized(ports, runtime, transport)

    assert (record["outcome"], record["reason"]) == ("failed", "MODEL_REFUSAL")
    assert steps(transport).count("reduce") == 1


async def test_incomplete_chunks_make_a_transient_service_unavailable_outcome(ports, runtime):
    transport = fake_llm()

    input, record, outcome = await summarized(ports, runtime, transport, complete=False)

    assert (record["outcome"], record["reason"]) == ("failed", "SERVICE_UNAVAILABLE")
    assert outcome.ref.startswith("requests/req_1/attempts/run_1/outcomes/")
    assert transport.requests == []
    assert [
        k for k in await ports.store.list_prefix("documents/") if k.endswith("outcome.json")
    ] == []
    enrichment = await summary_enrichment(ports, runtime, input, outcome)
    assert (enrichment["status"], enrichment["status_reason"]) == ("failed", "SERVICE_UNAVAILABLE")
    assert await ports.store.list_prefix("documents/doc_1/service-unavailable") == [
        "documents/doc_1/service-unavailable/req_1"
    ]


async def test_an_overview_out_of_budget_is_service_unavailable(ports, runtime):
    ports = dataclasses.replace(ports, summary=fake_llm())
    input = await native(ports, runtime, summary_paper())
    plan = await summary.run_sections(enrich(input), ports, runtime)
    await summary.run_chunk(ChunkInput(enrich(input), plan, 0), ports, runtime)
    ports.clock.now = 100.0  # type: ignore[attr-defined]

    outcome = await summary.run_overview(
        OverviewInput(enrich(input), plan, True, -1.0), ports, runtime
    )

    record = json.loads(await ports.store.get(outcome.ref))
    assert (record["outcome"], record["reason"]) == ("failed", "SERVICE_UNAVAILABLE")
    assert "reduce" not in steps(ports.summary)  # type: ignore[arg-type]


async def test_a_send_past_the_request_cap_fails_the_document(ports, runtime):
    runtime = with_runtime(runtime, request_cap={"per_item": 3, "per_section": 0, "extra": 1})
    ports = dataclasses.replace(ports, summary=fake_llm())
    input = await native(ports, runtime, summary_paper())
    plan = await summary.run_sections(enrich(input), ports, runtime)

    with pytest.raises(ProcessingFailure) as caught:
        await summary.run_chunk(ChunkInput(enrich(input), plan, 0), ports, runtime)

    assert (caught.value.category, caught.value.reason) == ("configuration", "REQUEST_CAP_EXCEEDED")
    assert len(ports.summary.requests) == 1  # type: ignore[union-attr]


async def test_the_request_cap_counts_sends_of_chunks_running_at_once(ports, runtime, monkeypatch):
    monkeypatch.setattr(document_summary, "CHUNK_CHARS", 1000)
    runtime = with_runtime(runtime, request_cap={"per_item": 3, "per_section": 0, "extra": 3})
    both = asyncio.Event()

    async def held(request: dict):
        # Each chunk's map waits for the other's, so both Activities have started sending.
        if step(request) == "map":
            if steps(transport).count("map") == 2:
                both.set()
            await both.wait()
        return reply(answer(request))

    transport = FakeInference(held)
    ports = dataclasses.replace(ports, summary=transport)
    input = await native(ports, runtime, summary_paper())
    plan = await summary.run_sections(enrich(input), ports, runtime)

    results = await asyncio.gather(
        *(summary.run_chunk(ChunkInput(enrich(input), plan, i), ports, runtime) for i in (0, 1)),
        return_exceptions=True,
    )

    # Each chunk needs a map and a verify: 4 sends, of which the cap allows 3.
    assert len(transport.requests) == 3
    (failure,) = [r for r in results if isinstance(r, ProcessingFailure)]
    assert failure.reason == "REQUEST_CAP_EXCEEDED"


async def test_a_summary_worker_without_a_transport_fails_the_document(ports, runtime):
    ports = dataclasses.replace(ports, summary=None)
    input = await native(ports, runtime, summary_paper())
    plan = await summary.run_sections(enrich(input), ports, runtime)

    with pytest.raises(ProcessingFailure) as caught:
        await summary.run_chunk(ChunkInput(enrich(input), plan, 0), ports, runtime)

    assert caught.value.reason == "METHOD_UNAVAILABLE"


async def test_the_summary_never_goes_through_the_vlm_transport(ports, runtime):
    vlm = fake_llm()
    ports = dataclasses.replace(ports, vlm=vlm)

    await summarized(ports, runtime, fake_llm())

    assert vlm.requests == []


# --- receipts and reuse ---------------------------------------------------------------------


async def test_every_send_has_a_receipt_in_its_chunk_or_overview_directory(ports, runtime):
    await summarized(ports, runtime, fake_llm())

    keys = await ports.store.list_prefix(RECEIPTS)
    assert sorted(k[len(RECEIPTS) + 1 :] for k in keys) == [
        "c0/1.json", "c0/2.json", "c0/3.json",
        "overview/1.json", "overview/2.json", "overview/3.json",
    ]  # fmt: skip
    receipt = json.loads(await ports.store.get(f"{RECEIPTS}/c0/1.json"))
    assert (receipt["item_id"], receipt["method"], receipt["result"]) == (
        ITEM_ID, "document-summary@2", "ok",
    )  # fmt: skip


async def test_a_finished_chunk_is_reused_without_a_send(ports, runtime):
    transport = fake_llm()
    ports = dataclasses.replace(ports, summary=transport)
    input = await native(ports, runtime, summary_paper())
    plan = await summary.run_sections(enrich(input), ports, runtime)
    await summary.run_chunk(ChunkInput(enrich(input), plan, 0), ports, runtime)
    sent = len(transport.requests)

    await summary.run_chunk(ChunkInput(enrich(input, "req_2"), plan, 0), ports, runtime)

    assert len(transport.requests) == sent == 3


async def test_a_second_request_reuses_the_summary_without_a_send(ports, runtime):
    transport = fake_llm()
    input, _, first = await summarized(ports, runtime, transport)
    sent = len(transport.requests)

    (again,) = await summarize_all(
        dataclasses.replace(ports, summary=transport), runtime, enrich(input, "req_2")
    )

    assert len(transport.requests) == sent
    assert (again.ref, again.digest, again.reused) == (first.ref, first.digest, True)


async def test_the_processing_result_carries_the_document_summary(ports, runtime):
    input, record, outcome = await summarized(ports, runtime, fake_llm())
    method = runtime.profile.methods["document-summary"]

    enrichment = await summary_enrichment(ports, runtime, input, outcome)

    prefix = outcome.ref.rsplit("/", 1)[0]
    assert enrichment == {
        "item_id": ITEM_ID,
        "result_ref": outcome.ref,
        "method_ref": {"id": "document-summary", "version": 2, "digest": method.module_digest},
        "scope": "document",
        "origin": "interpretation",
        "target_refs": ["#"],
        "input_refs": [input.assembly.ref],
        "content": record["content"],
        "evidence_refs": [],
        "status": "unverified",
        "status_reason": None,
        "signals": {"rewritten": 0, "dropped": 0},
        "provider_artifact_ref": f"{prefix}/record.json",
        "reused": False,
    }


async def test_a_document_without_a_section_long_enough_has_no_summary_text(ports, runtime):
    transport = fake_llm()
    ports = dataclasses.replace(ports, summary=transport)
    input = await native(ports, runtime, write_pdf([Page(lines=["1 Intro", *lines("ice", 2)])]))

    (outcome,) = await summarize_all(ports, runtime, enrich(input))

    record = json.loads(await ports.store.get(outcome.ref))
    assert (record["outcome"], record["content"]) == ("no_text", "")
    assert transport.requests == []
    enrichment = await summary_enrichment(ports, runtime, input, outcome)
    assert (enrichment["status"], enrichment["status_reason"]) == ("unverified", "NO_TEXT")
