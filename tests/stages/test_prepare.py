"""Seam A: prepare (#131). Failure matrix: each unprocessable source maps to cause source, which
admission turns into source_revision_rejected (v2 §6.3); input and version problems are
platform failures."""

import json

import pytest

from kp_processing.stages import PrepareInput, ProcessingFailure, prepare
from tests.pdfs import Page, encrypt, paper, write_pdf
from tests.stages.conftest import start_input, with_runtime


async def failure(ports, runtime, start) -> ProcessingFailure:
    with pytest.raises(ProcessingFailure) as caught:
        await prepare.run(PrepareInput(start=start, run_id="run_1"), ports, runtime)
    return caught.value


async def test_plan_groups_pages_by_five_and_is_frozen_in_the_attempt_scratch(ports, runtime):
    start = await start_input(ports, write_pdf(paper(12)))

    plan = await prepare.run(PrepareInput(start=start, run_id="run_1"), ports, runtime)

    sha = start["files"][0]["sha256"]
    assert plan.source_key == f"custody/{sha}"
    assert plan.source_sha256 == sha
    assert plan.page_count == 12
    assert plan.groups == [[1, 5], [6, 10], [11, 12]]
    assert plan.no_text_layer_pages == []
    assert plan.ref == "requests/req_1/attempts/run_1/plan.json"
    assert plan.runtime == runtime.profile.runtime
    frozen = json.loads(await ports.store.get(plan.ref))
    assert frozen["groups"] == [[1, 5], [6, 10], [11, 12]]
    assert frozen["source_sha256"] == sha


async def test_rerunning_prepare_returns_the_same_plan(ports, runtime):
    start = await start_input(ports, write_pdf(paper(3)))

    first = await prepare.run(PrepareInput(start=start, run_id="run_1"), ports, runtime)
    second = await prepare.run(PrepareInput(start=start, run_id="run_1"), ports, runtime)

    assert first == second


async def test_pages_without_a_text_layer_are_listed(ports, runtime):
    pages = paper(4)
    pages[1] = Page(picture=True)  # a raster-only page, like a scanned appendix
    start = await start_input(ports, write_pdf(pages))

    plan = await prepare.run(PrepareInput(start=start, run_id="run_1"), ports, runtime)

    assert plan.no_text_layer_pages == [2]


async def test_password_protected_pdf_is_a_source_failure(ports, runtime):
    start = await start_input(ports, encrypt(write_pdf(paper(2))))

    err = await failure(ports, runtime, start)

    assert (err.cause, err.category, err.reason, err.retryable) == (
        "source", "source", "PASSWORD_REQUIRED", False,
    )  # fmt: skip


async def test_corrupt_pdf_is_a_source_failure(ports, runtime):
    start = await start_input(ports, write_pdf(paper(2))[:300])

    err = await failure(ports, runtime, start)

    assert (err.cause, err.reason, err.retryable) == ("source", "CORRUPT_PDF", False)


async def test_too_many_pages_is_a_source_failure(ports, runtime):
    start = await start_input(ports, write_pdf(paper(65)))

    err = await failure(ports, runtime, start)

    assert (err.cause, err.reason) == ("source", "PAGE_LIMIT_EXCEEDED")
    assert err.metadata == {"limit": "64", "actual": "65"}


async def test_too_large_a_file_is_a_source_failure(ports, runtime):
    pdf = write_pdf(paper(2))
    start = await start_input(ports, pdf)

    err = await failure(ports, with_runtime(runtime, preflight={
        "max_pages": 64, "max_bytes": len(pdf) - 1, "max_page_pixels": 20_000_000,
    }), start)  # fmt: skip

    assert (err.cause, err.reason) == ("source", "SIZE_LIMIT_EXCEEDED")
    assert err.metadata == {"limit": str(len(pdf) - 1), "actual": str(len(pdf))}


async def test_too_many_pixels_on_a_page_is_a_source_failure(ports, runtime):
    pages = paper(2)
    pages[1] = Page(lines=["Poster"], size=(2384, 3370))  # A0: 8,034,080 points, 4x rendered
    start = await start_input(ports, write_pdf(pages))

    err = await failure(ports, runtime, start)

    assert (err.cause, err.reason) == ("source", "PIXEL_LIMIT_EXCEEDED")
    assert err.metadata == {"limit": "20000000", "actual": "32136320", "page": "2"}


async def test_adopted_version_other_than_the_worker_profile_is_an_integrity_failure(
    ports, runtime
):
    start = await start_input(ports, write_pdf(paper(2)), adopted_version="paper-pdf@2")

    err = await failure(ports, runtime, start)

    assert (err.cause, err.category, err.reason, err.retryable) == (
        "platform", "integrity", "ADOPTED_VERSION_MISMATCH", False,
    )  # fmt: skip


@pytest.mark.parametrize(
    "overrides",
    [
        {"document_uid": None},
        {"adoption_sequence": "1"},
        {"priority": "urgent"},
        {"files": []},
    ],
)
async def test_malformed_start_input_is_a_configuration_failure(ports, runtime, overrides):
    start = await start_input(ports, write_pdf(paper(2)), **overrides)

    err = await failure(ports, runtime, start)

    assert (err.cause, err.category, err.reason) == (
        "platform", "configuration", "INVALID_START_INPUT",
    )  # fmt: skip


async def test_a_missing_field_is_a_configuration_failure(ports, runtime):
    start = await start_input(ports, write_pdf(paper(2)))
    del start["trace_id"]

    err = await failure(ports, runtime, start)

    assert err.reason == "INVALID_START_INPUT"


async def test_source_bytes_that_do_not_match_the_declared_sha256_are_an_integrity_failure(
    ports, runtime
):
    start = await start_input(ports, write_pdf(paper(2)))
    await ports.store.put(start["files"][0]["custody_ref"].removeprefix("s3://kp-dev/"), b"x")

    err = await failure(ports, runtime, start)

    assert (err.cause, err.category, err.reason) == (
        "platform", "integrity", "SOURCE_DIGEST_MISMATCH",
    )  # fmt: skip


async def test_a_missing_source_is_an_integrity_failure(ports, runtime):
    start = await start_input(ports, write_pdf(paper(2)))
    start["files"][0]["custody_ref"] = "s3://kp-dev/custody/" + "0" * 64

    err = await failure(ports, runtime, start)

    assert (err.cause, err.category, err.reason) == ("platform", "integrity", "SOURCE_NOT_FOUND")
