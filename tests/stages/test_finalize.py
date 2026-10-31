"""Seam A: the Processing Result and the failure report (#131), over a real native parse."""

import importlib.metadata
import json
import platform

from kp_processing.stages import (
    AssembleInput,
    FailureInput,
    FinalizeInput,
    InventoryInput,
    error_block,
    finalize,
    inventory,
    parse,
)
from tests.stages.test_parse import parse_all, seven_pages


async def native(ports, runtime):
    start, plan, groups = await parse_all(ports, runtime, seven_pages())
    assembly = await parse.run_assemble(
        AssembleInput("doc_1", plan.source_key, plan.source_sha256, groups), ports, runtime
    )
    registered = await inventory.run(InventoryInput("doc_1", assembly), ports, runtime)
    return FinalizeInput(start, plan, groups, assembly, registered)


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
    m = runtime.profile.methods["docling-parse"]
    assert result["profile"] == {
        "id": "paper-pdf@1",
        "status_rule": "v1",
        "methods": [
            {
                "id": "docling-parse",
                "version": 1,
                "components": list(m.components),
                "module_digest": m.module_digest,
            }
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

    assert result["inventory"] == {"ref": input.inventory.ref, "counts": {}}
    assert result["enrichments"] == []
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
