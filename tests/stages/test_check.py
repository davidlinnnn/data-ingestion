"""Seam A: the d3 Quality Check (#161, ADR-0011) with real docling and the in-process d3 fake:
which items are checked and with what request, strong and weak signals in the Processing Result,
the degraded result when the service gives no answer, the request cap, reuse and the profile
switch."""

import base64
import dataclasses
import json

import pytest
from prometheus_client import REGISTRY

from kp_processing.ports.inference import FakeInference, ServiceUnavailable, completion
from kp_processing.stages import (
    CheckInput,
    FinalizeInput,
    PrepareInput,
    ProcessingFailure,
    check,
    finalize,
    prepare,
)
from tests.d3 import category, fake_d3
from tests.pdfs import Page, write_pdf
from tests.stages.conftest import with_runtime
from tests.stages.test_enrich_local import (
    PICTURE_WORDS,
    TABLE,
    enrich_input,
    enrichment,
    records,
)
from tests.stages.test_enrich_vlm import BODY, EQUATION
from tests.vlm import canned, schema_name

TABLE_MARKDOWN = (
    "Table 1: Scores of the three models.\n\n"
    "| Model    | Params    |   Score |\n"
    "|----------|-----------|---------|\n"
    "| Alpha    | 7B        |    61.2 |\n"
    "| Beta     | 13B       |    64.8 |\n"
    "| Gamma    | 70B       |    71.5 |"
)


def checked_paper() -> bytes:
    """A picture with words, a display formula, a captioned table and a picture without text."""
    return write_pdf(
        [
            Page(lines=["1 Architecture", *BODY], picture=True, picture_text=PICTURE_WORDS),
            Page(lines=["2 Method", *BODY, "", EQUATION, "", "Line after the equation continues."]),
            Page(
                lines=["3 Results", *BODY, "", "Table 1: Scores of the three models."], table=TABLE
            ),
            Page(lines=["4 Appendix", *BODY], picture=True),
        ]
    )


async def run_check(ports, runtime, input: FinalizeInput, request_id: str = "req_1"):
    """The check Activity over the enrichment outcomes of input."""
    enrich = enrich_input(input.inventory, request_id)
    return await check.run(CheckInput(enrich, input.outcomes), ports, runtime)


def data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


async def test_each_successful_formula_table_and_ocr_item_is_checked_with_its_image(ports, runtime):
    ports = dataclasses.replace(ports, d3=fake_d3(0.99))
    input = await enrichment(ports, runtime, checked_paper())
    judged = await records(ports, input.outcomes)
    (formula_id,) = [item_id for item_id in judged if item_id.startswith("formula:")]

    outcomes = await run_check(ports, runtime, input)

    # In inventory order; the picture without text (no_text) is not checked.
    assert [(o.item_id, o.reused) for o in outcomes] == [
        ("d3-check:picture-ocr:#/pictures/0", False),
        (f"d3-check:{formula_id}", False),
        ("d3-check:table-status:#/tables/0", False),
    ]
    inventory = json.loads(await ports.store.get(input.inventory.ref))["items"]
    picture = next(i for i in inventory if i["item_id"] == "picture-ocr:#/pictures/0")
    by_category = {r["state"]["category"]: r for r in ports.d3.requests}
    assert len(ports.d3.requests) == 3
    assert by_category["recognised text"]["state"]["reconstruction"] == "\n".join(PICTURE_WORDS)
    assert by_category["recognised text"]["images"] == [
        data_url(await ports.store.get(picture["input_refs"][0]["ref"]))
    ]
    assert by_category["formula LaTeX"]["state"]["reconstruction"] == "L = 2x + 3y - 7 = 0"
    assert by_category["formula LaTeX"]["images"] == [
        data_url(await ports.store.get(judged[formula_id]["evidence_refs"][0]))
    ]
    assert by_category["table grid (Markdown)"]["state"]["reconstruction"] == TABLE_MARKDOWN
    assert by_category["table grid (Markdown)"]["images"] == [
        data_url(await ports.store.get(judged["table-status:#/tables/0"]["evidence_refs"][0]))
    ]
    assert all(set(r["questions"]) == {"Q2"} for r in ports.d3.requests)

    checks = await records(ports, outcomes)
    assert all(o.ref.startswith("documents/doc_1/items/") for o in outcomes)
    record = checks[f"d3-check:{formula_id}"]
    assert record["method_ref"]["id"] == "d3-check"
    assert (record["outcome"], record["contradictions"]) == ("success", [])
    assert record["signals"]["d3"]["score"] == 0.99
    assert record["provider_artifact_ref"] == f"{outcomes[1].ref.rsplit('/', 1)[0]}/response.json"


async def result_of(ports, runtime, input: FinalizeInput, request_id: str = "req_1") -> dict:
    """The Processing Result after the check and finalize."""
    checks = await run_check(ports, runtime, input, request_id)
    final = dataclasses.replace(input, outcomes=[*input.outcomes, *checks])
    return json.loads(await ports.store.get(await finalize.run(final, ports, runtime)))


def scores(**by_category: float | Exception):
    """A d3 fake scoring formula, table and ocr requests as given."""
    names = {"formula LaTeX": "formula", "table grid (Markdown)": "table", "recognised text": "ocr"}
    return fake_d3(lambda request: by_category[names[category(request)]])


def judged_enrichments(result: dict) -> dict[str, dict]:
    """The enrichments of the judged methods by item_id, the formula's as "formula"."""
    return {
        "formula" if e["item_id"].startswith("formula:") else e["item_id"]: e
        for e in result["enrichments"]
        if e["method_ref"]["id"] in ("formula", "table-status", "picture-ocr")
    }


SIGNAL = {
    "model": "vllm-sr/d3-mini",
    "revision": "bd0090dd758d32ba59ef5c749910a8e87fc4391f",
    "question": "Q2",
}
MARKER = "documents/doc_1/service-unavailable/req_1"


async def test_a_formula_judged_unfaithful_is_disputed_and_a_weak_signal_changes_no_status(
    ports, runtime
):
    ports = dataclasses.replace(ports, d3=scores(formula=0.5, table=0.99, ocr=0.0))
    input = await enrichment(ports, runtime, checked_paper())

    result = await result_of(ports, runtime, input)

    judged = judged_enrichments(result)
    formula, table = judged["formula"], judged["table-status:#/tables/0"]
    assert (formula["status"], formula["status_reason"]) == ("disputed", "FORMULA_D3_UNFAITHFUL")
    assert formula["signals"]["d3"] == {
        **SIGNAL, "score": 0.5, "p": pytest.approx(0.06317271386388043),
        "t_d": 0.4452267235556272,
    }  # fmt: skip
    assert "2 x + 3 y - 7 = 0" in formula["signals"]["native_text"]
    assert (table["status"], table["status_reason"]) == ("unverified", None)
    assert table["signals"] == {
        "d3": {**SIGNAL, "score": 0.99, "p": pytest.approx(0.9991631623506171),
               "t_d": 0.306418651215859}
    }  # fmt: skip
    # picture OCR is a weak signal: the lowest score still leaves the status alone.
    ocr = judged["picture-ocr:#/pictures/0"]
    assert (ocr["status"], ocr["status_reason"]) == ("unverified", None)
    assert ocr["signals"] == {
        "d3": {**SIGNAL, "score": 0.0, "p": pytest.approx(0.0024236212131999247), "t_d": None}
    }
    # Nothing else carries the signal: the picture without text, interpretations, the summary.
    assert [e["item_id"] for e in result["enrichments"] if "d3" in e["signals"]] == [
        ocr["item_id"], formula["item_id"], table["item_id"],
    ]  # fmt: skip
    assert judged["picture-ocr:#/pictures/1"]["status_reason"] == "NO_TEXT"
    zero = {"unverified": 0, "disputed": 0, "failed": 0, "no_text": 0}
    assert result["inventory"]["counts"]["formula"] == {**zero, "disputed": 1}
    assert result["inventory"]["counts"]["table-status"] == {**zero, "unverified": 1}
    # Check items are not enrichments, and the profile names the check.
    assert not [e for e in result["enrichments"] if e["method_ref"]["id"] == "d3-check"]
    assert result["profile"]["methods"][-1]["id"] == "d3-check"
    assert await ports.store.head(MARKER) is None


async def test_a_table_judged_unfaithful_is_disputed(ports, runtime):
    ports = dataclasses.replace(ports, d3=scores(formula=0.99, table=0.2, ocr=0.99))
    input = await enrichment(ports, runtime, checked_paper())

    judged = judged_enrichments(await result_of(ports, runtime, input))

    table = judged["table-status:#/tables/0"]
    assert (table["status"], table["status_reason"]) == ("disputed", "TABLE_D3_UNFAITHFUL")
    assert (judged["formula"]["status"], judged["formula"]["status_reason"]) == ("unverified", None)


def formula_answering(content: str) -> FakeInference:
    """The canned VLM, except that every formula request gets content."""
    return FakeInference(
        lambda r: completion(content) if schema_name(r) == "formula" else canned(r)
    )


async def test_the_rules_contradiction_stays_first_when_d3_contradicts_too(ports, runtime):
    ports = dataclasses.replace(
        ports,
        vlm=formula_answering('{"latex": "L = 9x"}'),
        d3=scores(formula=0.2, table=0.99, ocr=0.99),
    )
    input = await enrichment(ports, runtime, checked_paper())
    checks = await run_check(ports, runtime, input)

    result = await result_of(ports, runtime, input)

    formula = judged_enrichments(result)["formula"]
    assert (formula["status"], formula["status_reason"]) == ("disputed", "FORMULA_NATIVE_MISMATCH")
    (check,) = [r for i, r in (await records(ports, checks)).items() if ":formula:" in i]
    assert check["contradictions"] == ["FORMULA_D3_UNFAITHFUL"]
    assert formula["signals"]["d3"]["p"] <= formula["signals"]["d3"]["t_d"]


async def test_a_failed_item_is_not_checked(ports, runtime):
    ports = dataclasses.replace(ports, vlm=formula_answering("{not json"))
    input = await enrichment(ports, runtime, checked_paper())

    checks = await run_check(ports, runtime, input)
    result = await result_of(ports, runtime, input)

    assert [o.item_id.split(":")[1] for o in checks] == ["picture-ocr", "table-status"]
    formula = judged_enrichments(result)["formula"]
    assert (formula["status"], formula["status_reason"]) == ("failed", "SCHEMA_INVALID")
    assert "d3" not in formula["signals"]


async def test_without_an_answer_the_item_keeps_its_status_and_a_redrive_fills_the_judgement_in(
    ports, runtime
):
    down = dataclasses.replace(ports, d3=fake_d3(ServiceUnavailable("TIMEOUT")))
    input = await enrichment(down, runtime, checked_paper())

    checks = await run_check(down, runtime, input)
    result = await result_of(down, runtime, input)

    attempts = runtime.profile.runtime["retry"]["max_attempts"]
    assert len(down.d3.requests) == 3 * attempts
    assert all(o.ref.startswith("requests/req_1/attempts/run_1/outcomes/") for o in checks)
    not_run = {"state": "not_run", "reason": "SERVICE_UNAVAILABLE"}
    assert {
        e["item_id"].split(":")[0]: (e["status"], e["status_reason"], e["signals"].get("d3"))
        for e in judged_enrichments(result).values()
        if e["status_reason"] != "NO_TEXT"
    } == {
        "picture-ocr": ("unverified", None, not_run),
        "formula": ("unverified", None, not_run),
        "table-status": ("unverified", None, not_run),
    }
    assert await ports.store.head(MARKER) is not None

    # The redrive is a new request: every enrichment is reused and only the checks are sent.
    back = dataclasses.replace(ports, d3=scores(formula=0.5, table=0.99, ocr=0.99))
    again = await enrichment(back, runtime, checked_paper(), "req_2")
    redriven = await result_of(back, runtime, again, "req_2")

    assert all(o.reused for o in again.outcomes)
    assert len(back.d3.requests) == 3
    formula = judged_enrichments(redriven)["formula"]
    assert (formula["status"], formula["status_reason"]) == ("disputed", "FORMULA_D3_UNFAITHFUL")
    assert await ports.store.head("documents/doc_1/service-unavailable/req_2") is None


async def test_a_reply_without_a_score_is_not_run_for_good_and_waits_for_no_redrive(ports, runtime):
    garbled = dataclasses.replace(ports, d3=FakeInference(lambda request: completion("{}")))
    input = await enrichment(garbled, runtime, checked_paper())

    result = await result_of(garbled, runtime, input)

    formula = judged_enrichments(result)["formula"]
    assert (formula["status"], formula["status_reason"]) == ("unverified", None)
    assert formula["signals"]["d3"] == {"state": "not_run", "reason": "SCHEMA_INVALID"}
    assert await ports.store.head(MARKER) is None

    # Registered like any invalid reply: the next request reuses it and asks nothing.
    sent = len(garbled.d3.requests)
    again = await enrichment(garbled, runtime, checked_paper(), "req_2")
    await result_of(garbled, runtime, again, "req_2")
    assert len(garbled.d3.requests) == sent


async def test_a_judged_item_without_its_check_outcome_fails_integrity(ports, runtime):
    input = await enrichment(ports, runtime, checked_paper())

    with pytest.raises(ProcessingFailure) as caught:
        await finalize.run(input, ports, runtime)

    failure = caught.value
    assert (failure.category, failure.reason) == ("integrity", "OUTCOME_RECORD_MISSING")
    assert failure.metadata == {"item_id": "d3-check:picture-ocr:#/pictures/0"}


async def test_the_request_cap_counts_the_check_items(ports, runtime):
    # Four sends per unanswered chain: the three checks want 12, the cap allows
    # per_item x (7 inventory items + 3 check items) + extra = 10.
    retry = {**runtime.profile.runtime["retry"], "max_attempts": 4}
    capped = with_runtime(
        runtime, retry=retry, request_cap={"per_item": 1, "per_section": 40, "extra": 0}
    )
    ports = dataclasses.replace(ports, d3=fake_d3(ServiceUnavailable("TIMEOUT")))
    input = await enrichment(ports, capped, checked_paper())
    assert input.inventory.items == 7

    with pytest.raises(ProcessingFailure) as caught:
        await run_check(ports, capped, input)

    failure = caught.value
    assert (failure.category, failure.reason) == ("configuration", "REQUEST_CAP_EXCEEDED")
    assert failure.metadata["limit"] == "10"
    # Only the checks' own receipts count: the VLM's three sends of this attempt do not.
    assert len(ports.d3.requests) == 10


def with_check_digest(runtime, digest: str):
    """The runtime whose d3-check package has another source digest, as a changed t_d gives."""
    methods = dict(runtime.profile.methods)
    methods["d3-check"] = dataclasses.replace(methods["d3-check"], module_digest=digest)
    return dataclasses.replace(
        runtime, profile=dataclasses.replace(runtime.profile, methods=methods)
    )


async def test_an_unchanged_output_reuses_its_check_and_a_changed_check_reruns_only_itself(
    ports, runtime
):
    input = await enrichment(ports, runtime, checked_paper())
    first = await run_check(ports, runtime, input)
    sent = len(ports.vlm.requests), len(ports.d3.requests)
    assert sent[1] == 3

    again = await enrichment(ports, runtime, checked_paper(), "req_2")
    second = await run_check(ports, runtime, again, "req_2")

    assert second == [dataclasses.replace(o, reused=True) for o in first]
    assert (len(ports.vlm.requests), len(ports.d3.requests)) == sent
    assert await ports.store.list_prefix("requests/req_2/attempts/run_1/receipts") == []

    changed = with_check_digest(runtime, "f" * 64)
    third = await enrichment(ports, changed, checked_paper(), "req_3")
    rechecked = await run_check(ports, changed, third, "req_3")

    # Inventory and every enrichment are reused: nothing goes to the VLM again.
    assert third.inventory.reused and all(o.reused for o in third.outcomes)
    assert [o.reused for o in rechecked] == [False, False, False]
    assert {o.ref for o in rechecked}.isdisjoint(o.ref for o in first)
    assert (len(ports.vlm.requests), len(ports.d3.requests)) == (sent[0], 6)


def without_check(runtime):
    methods = {k: m for k, m in runtime.profile.methods.items() if k != "d3-check"}
    return dataclasses.replace(
        runtime, profile=dataclasses.replace(runtime.profile, methods=methods)
    )


async def test_a_profile_without_the_check_judges_nothing_and_needs_no_d3_service(ports, runtime):
    off = without_check(runtime)
    ports = dataclasses.replace(ports, d3=None)
    input = await enrichment(ports, off, checked_paper())

    result = json.loads(await ports.store.get(await finalize.run(input, ports, off)))

    assert input.plan.check is False
    assert [m["id"] for m in result["profile"]["methods"]] == [m for m in off.profile.methods]
    assert not [e["item_id"] for e in result["enrichments"] if "d3" in e["signals"]]
    assert {(e["status"], e["status_reason"]) for e in judged_enrichments(result).values()} == {
        ("unverified", None), ("unverified", "NO_TEXT"),
    }  # fmt: skip
    assert not await ports.store.list_prefix("documents/doc_1/service-unavailable")

    # The same paper under the profile with the check: all else is reused, the checks are new.
    on = dataclasses.replace(ports, d3=scores(formula=0.5, table=0.99, ocr=0.99))
    sent = len(ports.vlm.requests)
    again = await enrichment(on, runtime, checked_paper(), "req_2")
    checks = await run_check(on, runtime, again, "req_2")
    judged = judged_enrichments(await result_of(on, runtime, again, "req_2"))

    assert (await prepare.run(PrepareInput(again.start, "run_1"), on, runtime)).check is True
    assert again.inventory.reused and all(o.reused for o in again.outcomes)
    assert len(ports.vlm.requests) == sent
    assert [o.reused for o in checks] == [False, False, False]
    assert (judged["formula"]["status"], judged["formula"]["status_reason"]) == (
        "disputed", "FORMULA_D3_UNFAITHFUL",
    )  # fmt: skip


async def test_each_judgement_is_counted_as_an_item_outcome_of_the_check(ports, runtime):
    def count(status: str, reason: str) -> float:
        labels = {"method": "d3-check@1", "status": status, "reason": reason}
        return REGISTRY.get_sample_value("kp_processing_item_outcomes_total", labels) or 0.0

    series = [("disputed", "FORMULA_D3_UNFAITHFUL"), ("unverified", ""),
              ("not_run", "SERVICE_UNAVAILABLE")]  # fmt: skip
    before = [count(*labels) for labels in series]
    answered = dataclasses.replace(
        ports, d3=scores(formula=0.5, table=ServiceUnavailable("TIMEOUT"), ocr=0.99)
    )
    input = await enrichment(answered, runtime, checked_paper())

    await result_of(answered, runtime, input)

    assert [count(*labels) - was for labels, was in zip(series, before, strict=True)] == [1, 1, 1]
