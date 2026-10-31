"""Seam A: the Processing Result and the failure report (#131, #132), over a real native parse
and the real local enrichment."""

import dataclasses
import importlib.metadata
import json
import platform
import sys
import types

import pytest

from kp_processing.stages import FailureInput, ProcessingFailure, error_block, finalize
from tests.stages.test_enrich_local import counting, enriched, enriched_paper
from tests.stages.test_parse import seven_pages


async def native(ports, runtime):
    return await enriched(ports, runtime, seven_pages())


async def test_the_processing_result_describes_request_profile_and_native_evidence(ports, runtime):
    input = await native(ports, runtime)

    ref = await finalize.run(input, ports, runtime)

    assert ref == "requests/req_1/result.json"
    result = json.loads(await ports.store.get(ref))
    assert result["schema"] == "pdf-processing-result/v1"
    file = input.start["files"][0]
    assert result["request"] == {
        "request_id": "req_1",
        "document_uid": "doc_1",
        "source_revision_id": "srv_1",
        "adopted_version": "paper-pdf@1",
        "adoption_sequence": 1,
        "files": [{k: file[k] for k in ("role", "custody_ref", "sha256", "size", "media_type")}],
    }
    assert result["profile"] == {
        "id": "paper-pdf@1",
        "status_rule": "v1",
        "methods": [
            {
                "id": m.id,
                "version": m.version,
                "components": list(m.components),
                "module_digest": m.module_digest,
            }
            for m in runtime.profile.methods.values()
        ],
        "runtime_identity": {
            "python": platform.python_version(),
            "docling_slim": importlib.metadata.version("docling-slim"),
            "build_id": "test-r1",
        },
    }
    assert result["outcome"] == "complete"

    native_part = result["native"]
    assert native_part["assembly_ref"] == input.assembly.ref
    assert native_part["page_groups"] == [{"pages": g.pages, "ref": g.ref} for g in input.groups]
    assert [p["page"] for p in native_part["page_images"]] == [1, 2, 3, 4, 5, 6, 7]
    groups = [json.loads(await ports.store.get(g.ref)) for g in input.groups]
    assert native_part["page_images"] == [i for g in groups for i in g["page_images"]]
    assembly = json.loads(await ports.store.get(input.assembly.ref))
    assert native_part["picture_images"] == assembly["picture_images"]
    assert native_part["picture_images"]

    # seven_pages has two pictures and neither holds text; each is also interpreted, four
    # field enrichments apiece. Docling also reads the eleven-line paragraphs of some pages as
    # tables; each native table becomes a table-status item.
    tables = len(assembly["document"]["tables"])
    zero = {"unverified": 0, "disputed": 0, "failed": 0, "no_text": 0}
    assert result["inventory"] == {
        "ref": input.inventory.ref,
        "counts": {"picture-ocr": {**zero, "no_text": 2},
                   "picture-interpretation": {**zero, "unverified": 8}}
        | ({"table-status": {**zero, "unverified": tables}} if tables else {}),
    }  # fmt: skip
    assert [(e["status"], e["status_reason"], e["content"]) for e in result["enrichments"][:2]] == [
        ("unverified", "NO_TEXT", ""),
        ("unverified", "NO_TEXT", ""),
    ]
    assert len(result["enrichments"]) == 2 + 8 + tables
    assert result["limitations"] == [
        {"code": "READING_ORDER_DEFECTS", "scope": "profile",
         "detail": runtime.profile.limitations[0].detail},
        {"code": "CAPTION_INTERRUPTS_BODY", "scope": "profile",
         "detail": runtime.profile.limitations[1].detail},
        {"code": "NO_TEXT_LAYER_PAGES", "scope": "document", "detail": "no text layer on pages 6"},
    ]  # fmt: skip


async def test_the_failure_report_carries_cause_stage_and_the_error_block(ports, runtime):
    error = error_block(
        {
            "cause": "source",
            "category": "source",
            "reason": "PASSWORD_REQUIRED",
            "message": "the PDF needs a password",
            "retryable": False,
            "metadata": {},
        },
        occurred_at="2026-10-31T00:00:00Z",
        support_ref="temporal:req_1/run_1",
    )
    start = {"request_id": "req_1", "document_uid": "doc_1", "source_revision_id": "srv_1"}

    ref = await finalize.run_failure(
        FailureInput("req_1", start, "prepare", "source", error, None), ports, runtime
    )

    assert ref == "requests/req_1/failure.json"
    assert json.loads(await ports.store.get(ref)) == {
        "schema": "pdf-processing-failure/v1",
        "request": {"request_id": "req_1", "document_uid": "doc_1", "source_revision_id": "srv_1"},
        "cause": "source",
        "stage": "prepare",
        "error": {
            "domain": "kp-processing",
            "reason": "PASSWORD_REQUIRED",
            "message": "the PDF needs a password",
            "retryable": False,
            "metadata": {"category": "source"},
            "support_ref": "temporal:req_1/run_1",
            "occurred_at": "2026-10-31T00:00:00Z",
        },
    }


async def test_a_failure_report_names_the_inventory_and_survives_a_malformed_start(ports, runtime):
    error = error_block(
        {"cause": "platform", "category": "configuration", "reason": "INVALID_START_INPUT",
         "message": "m", "retryable": False, "metadata": {}},
        occurred_at="2026-10-31T00:00:00Z",
        support_ref="s",
    )  # fmt: skip

    ref = await finalize.run_failure(
        FailureInput("req_9", {"files": "nonsense"}, "enrich", "platform", error, "inv/ref"),
        ports,
        runtime,
    )

    report = json.loads(await ports.store.get(ref))
    assert ref == "requests/req_9/failure.json"
    assert report["request"] == {
        "request_id": "req_9", "document_uid": None, "source_revision_id": None,
    }  # fmt: skip
    assert report["inventory_ref"] == "inv/ref"


async def test_a_retried_finalize_keeps_the_result_already_registered(ports, runtime):
    input = await native(ports, runtime)
    await ports.store.put_if_absent("requests/req_1/result.json", b"first")

    ref = await finalize.run(input, ports, runtime)

    assert await ports.store.get(ref) == b"first"


async def test_a_retried_failure_report_keeps_the_first(ports, runtime):
    error = error_block(
        {"cause": "source", "category": "source", "reason": "CORRUPT_PDF",
         "message": "m", "retryable": False, "metadata": {}},
        occurred_at="2026-10-31T00:00:00Z",
        support_ref="s",
    )  # fmt: skip
    failure = FailureInput("req_9", {}, "prepare", "source", error, None)
    await ports.store.put_if_absent("requests/req_9/failure.json", b"first")

    ref = await finalize.run_failure(failure, ports, runtime)

    assert await ports.store.get(ref) == b"first"


# --- enrichments (#132) ------------------------------------------------------------------


async def test_each_enrichment_joins_its_inventory_item_outcome_record_and_status(ports, runtime):
    input = await enriched(ports, runtime, enriched_paper())

    result = json.loads(await ports.store.get(await finalize.run(input, ports, runtime)))

    items = json.loads(await ports.store.get(input.inventory.ref))["items"]
    outcomes = {o.item_id: o for o in input.outcomes}
    expected = []
    for item in items:
        outcome = outcomes[item["item_id"]]
        record = json.loads(await ports.store.get(outcome.ref))
        common = {
            "item_id": item["item_id"],
            "result_ref": outcome.ref,
            "method_ref": record["method_ref"],
            "scope": "item",
            "origin": record["origin"],
            "target_refs": [item["target_ref"]],
            "input_refs": [r["ref"] for r in item["input_refs"]],
            "content": record["content"],
            "evidence_refs": record["evidence_refs"],
            "signals": record["signals"],
            "provider_artifact_ref": record["provider_artifact_ref"],
            "reused": False,
        }
        if "fields" not in record:
            expected.append(common)
        for name, field in record.get("fields", {}).items():  # one enrichment per field
            expected.append({**common, "item_id": f"{item['item_id']}/{name}",
                             "content": field["content"], "signals": field["signals"]})  # fmt: skip
    enrichments = result["enrichments"]
    assert [{k: v for k, v in e.items() if k not in ("status", "status_reason")}
            for e in enrichments] == expected  # fmt: skip
    pictures = [f"picture-interpretation:#/pictures/{n}/{field}" for n in (0, 1)
                for field in ("caption", "chart_values", "description", "figure_type")]  # fmt: skip
    assert [e["item_id"] for e in enrichments][2:10] == pictures
    assert [(e["status"], e["status_reason"]) for e in enrichments] == [
        ("unverified", None),
        ("unverified", "NO_TEXT"),
        *[("unverified", None)] * 8,
        ("unverified", None),
        ("unverified", None),
    ]
    zero = {"unverified": 0, "disputed": 0, "failed": 0, "no_text": 0}
    assert result["inventory"]["counts"] == {
        "picture-ocr": {**zero, "unverified": 1, "no_text": 1},
        "picture-interpretation": {**zero, "unverified": 8},
        "code": {**zero, "unverified": 1},
        "table-status": {**zero, "unverified": 1},
    }


async def test_an_item_without_an_outcome_record_fails_integrity(ports, runtime):
    input = await enriched(ports, runtime, enriched_paper())
    dropped = dataclasses.replace(input, outcomes=input.outcomes[:2] + input.outcomes[3:])

    with pytest.raises(ProcessingFailure) as caught:
        await finalize.run(dropped, ports, runtime)

    failure = caught.value
    assert (failure.cause, failure.category, failure.reason) == (
        "platform",
        "integrity",
        "OUTCOME_RECORD_MISSING",
    )
    assert failure.metadata["item_id"] == input.outcomes[2].item_id
    assert await ports.store.head("requests/req_1/result.json") is None


async def test_an_outcome_record_that_differs_from_its_digest_fails_integrity(ports, runtime):
    input = await enriched(ports, runtime, enriched_paper())
    await ports.store.put(input.outcomes[0].ref, b"{}")

    with pytest.raises(ProcessingFailure) as caught:
        await finalize.run(input, ports, runtime)

    assert (caught.value.category, caught.value.reason) == ("integrity", "OUTCOME_RECORD_MISSING")


async def test_a_new_status_rule_reruns_only_finalize(ports, runtime, monkeypatch):
    calls = counting(monkeypatch)
    first = await enriched(ports, runtime, enriched_paper())
    ocr_calls = len(calls)
    rule = types.ModuleType("kp_processing.status_rules.vtest")
    rule.assign = lambda outcome: ("disputed", "TEST_RULE")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "kp_processing.status_rules.vtest", rule)
    profile = dataclasses.replace(runtime.profile, status_rule="vtest")
    runtime = dataclasses.replace(runtime, profile=profile)

    second = await enriched(ports, runtime, enriched_paper(), request_id="req_2")
    result = json.loads(await ports.store.get(await finalize.run(second, ports, runtime)))

    assert len(calls) == ocr_calls
    assert all(o.reused for o in second.outcomes)
    assert [o.ref for o in second.outcomes] == [o.ref for o in first.outcomes]
    assert result["profile"]["status_rule"] == "vtest"
    assert {(e["status"], e["status_reason"], e["reused"]) for e in result["enrichments"]} == {
        ("disputed", "TEST_RULE", True)
    }


async def test_an_unknown_status_rule_is_a_configuration_failure(ports, runtime):
    input = await enriched(ports, runtime, enriched_paper())
    profile = dataclasses.replace(runtime.profile, status_rule="v404")

    with pytest.raises(ProcessingFailure) as caught:
        await finalize.run(input, ports, dataclasses.replace(runtime, profile=profile))

    assert (caught.value.category, caught.value.reason) == (
        "configuration",
        "STATUS_RULE_UNKNOWN",
    )


async def test_large_content_stays_in_the_outcome_record(ports, runtime, monkeypatch):
    input = await enriched(ports, runtime, enriched_paper())
    monkeypatch.setattr(finalize, "CONTENT_INLINE_MAX", 40)

    result = json.loads(await ports.store.get(await finalize.run(input, ports, runtime)))

    contents = {e["item_id"].split(":")[0]: e["content"] for e in result["enrichments"]}
    assert contents["table-status"] is None  # HTML and grid exceed 40 bytes
    assert contents["code"] is None
    table = next(e for e in result["enrichments"] if e["item_id"].startswith("table-status:"))
    assert json.loads(await ports.store.get(table["result_ref"]))["content"]["html"]
