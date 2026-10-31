"""The paper-pdf workflow on a real Temporal dev server (#131), with an in-process worker and the
in-process store and reporter fakes. Uses the local `temporal` CLI when installed, otherwise
the SDK downloads the dev server; either way it binds a local port (outside the Codex
sandbox)."""

import contextlib
import dataclasses
import json
import uuid

import pytest
from temporalio.client import Client

from kp_processing.cli import start_request
from kp_processing.ports.clock import SystemClock
from kp_processing.ports.status_reporter import (
    Progress,
    RecordingStatusReporter,
    ReportOutcome,
    StatusReport,
)
from kp_processing.stages import Ports
from kp_processing.worker import make_worker
from kp_processing.workflow import ORCHESTRATION_QUEUE, WORKFLOW
from tests.pdfs import Page, encrypt, paper, write_pdf
from tests.stages.conftest import start_input, with_runtime
from tests.stages.test_parse import seven_pages

pytestmark = pytest.mark.network


@contextlib.asynccontextmanager
async def workers(client: Client, ports: Ports, runtime):
    """One worker per task queue, as the deployments run them."""
    async with (
        await make_worker(client, ports, runtime, "orchestration"),
        await make_worker(client, ports, runtime, "inference"),
    ):
        yield


async def process(client: Client, ports: Ports, runtime, start) -> tuple[dict, str]:
    async with workers(client, ports, runtime):
        handle = await client.start_workflow(
            WORKFLOW, start, id=start["request_id"], task_queue=ORCHESTRATION_QUEUE
        )
        outcome = await handle.result()
    return outcome, handle.result_run_id or ""


def shape(reports: list[StatusReport]) -> list[tuple]:
    return [(r.seq, r.stage, r.state, r.progress) for r in reports]


async def test_a_paper_runs_end_to_end_and_reports_four_stages(client, ports, runtime):
    start = await start_input(ports, seven_pages(), request_id=f"req_{uuid.uuid4().hex[:8]}")

    outcome, run_id = await process(client, ports, runtime, start)

    ref = f"requests/{start['request_id']}/result.json"
    assert outcome == {"outcome": "complete", "manifest_ref": ref}
    result = json.loads(await ports.store.get(ref))
    assert result["outcome"] == "complete"
    assert result["enrichments"] == []
    assert {"code": "NO_TEXT_LAYER_PAGES", "scope": "document",
            "detail": "no text layer on pages 6"} in result["limitations"]  # fmt: skip

    reports = ports.reporter.reports  # type: ignore[attr-defined]
    pages, items = (lambda n: Progress(n, 7, "pages")), Progress(0, 0, "items")
    assert shape(reports) == [
        (1, "prepare", "running", None),
        (2, "prepare", "succeeded", None),
        (3, "parse", "running", pages(0)),
        (4, "parse", "running", pages(5)),
        (5, "parse", "running", pages(7)),
        (6, "parse", "succeeded", pages(7)),
        (7, "enrich", "running", items),
        (8, "enrich", "succeeded", items),
        (9, "finalize", "running", None),
        (10, "finalize", "succeeded", None),
    ]
    assert {(r.request_id, r.attempt_id, r.method_version, r.stages_version) for r in reports} == {
        (start["request_id"], run_id, "paper-pdf@1", "1")
    }
    assert [r.manifest_ref for r in reports][-1] == ref
    assert all(r.error is None for r in reports)


async def test_a_second_request_for_the_same_document_reuses_every_registered_item(
    client, ports, runtime
):
    pdf = seven_pages()
    first = await start_input(ports, pdf, request_id=f"req_{uuid.uuid4().hex[:8]}")
    second = {**first, "request_id": f"req_{uuid.uuid4().hex[:8]}"}
    await process(client, ports, runtime, first)
    items = {k for k in ports.store.objects if k.startswith("documents/")}  # type: ignore[attr-defined]

    outcome, _ = await process(client, ports, runtime, second)

    assert outcome["outcome"] == "complete"
    assert {k for k in ports.store.objects if k.startswith("documents/")} == items  # type: ignore[attr-defined]
    one, two = [
        json.loads(await ports.store.get(f"requests/{s['request_id']}/result.json"))
        for s in (first, second)
    ]
    assert one["native"] == two["native"]


async def test_an_unprocessable_source_ends_with_a_failure_report(client, ports, runtime):
    start = await start_input(
        ports, encrypt(write_pdf(paper(2))), request_id=f"req_{uuid.uuid4().hex[:8]}"
    )

    outcome, run_id = await process(client, ports, runtime, start)

    ref = f"requests/{start['request_id']}/failure.json"
    assert outcome == {"outcome": "failed", "manifest_ref": ref}
    failure = json.loads(await ports.store.get(ref))
    assert (failure["cause"], failure["stage"], failure["error"]["reason"]) == (
        "source", "prepare", "PASSWORD_REQUIRED",
    )  # fmt: skip
    assert failure["error"]["support_ref"] == f"temporal:{start['request_id']}/{run_id}"
    reports = ports.reporter.reports  # type: ignore[attr-defined]
    assert shape(reports) == [(1, "prepare", "running", None), (2, "prepare", "failed", None)]
    assert reports[-1].manifest_ref == ref
    assert reports[-1].error == failure["error"]
    assert reports[-1].message == failure["error"]["message"]


def _poster() -> bytes:
    pages = paper(1)
    pages.append(Page(lines=["Poster"], size=(5000, 4001)))
    return write_pdf(pages)


@pytest.mark.parametrize(
    "pdf, limits, reason",
    [
        (lambda: write_pdf(paper(2))[:300], {}, "CORRUPT_PDF"),
        (lambda: write_pdf(paper(65)), {}, "PAGE_LIMIT_EXCEEDED"),
        (lambda: write_pdf(paper(2)), {"max_bytes": 100}, "SIZE_LIMIT_EXCEEDED"),
        (_poster, {}, "PIXEL_LIMIT_EXCEEDED"),
    ],
)
async def test_every_source_rejection_ends_with_a_source_failure_report(
    client, ports, runtime, pdf, limits, reason
):
    preflight = {**runtime.profile.runtime["preflight"], **limits}
    start = await start_input(ports, pdf(), request_id=f"req_{uuid.uuid4().hex[:8]}")

    outcome, _ = await process(client, ports, with_runtime(runtime, preflight=preflight), start)

    failure = json.loads(await ports.store.get(outcome["manifest_ref"]))
    assert (failure["cause"], failure["stage"], failure["error"]["reason"]) == (
        "source", "prepare", reason,
    )  # fmt: skip
    assert failure["error"]["retryable"] is False
    last = ports.reporter.reports[-1]  # type: ignore[attr-defined]
    assert (last.state, last.error, last.manifest_ref) == (
        "failed", failure["error"], outcome["manifest_ref"],
    )  # fmt: skip


async def test_an_adopted_version_other_than_the_worker_profile_fails_integrity(
    client, ports, runtime
):
    start = await start_input(
        ports, write_pdf(paper(2)), request_id=f"req_{uuid.uuid4().hex[:8]}",
        adopted_version="paper-pdf@2",
    )  # fmt: skip

    outcome, _ = await process(client, ports, runtime, start)

    failure = json.loads(await ports.store.get(outcome["manifest_ref"]))
    assert failure["cause"] == "platform"
    assert failure["error"]["metadata"]["category"] == "integrity"
    assert failure["error"]["reason"] == "ADOPTED_VERSION_MISMATCH"
    assert ports.reporter.reports[-1].method_version == "paper-pdf@2"  # type: ignore[attr-defined]


class DownReporter(RecordingStatusReporter):
    async def report(self, report: StatusReport) -> ReportOutcome:
        self.reports.append(report)
        return ReportOutcome(delivered=False, error="ConnectError: connection refused")


async def test_processing_completes_while_the_report_receiver_is_down(client, ports, runtime):
    # Skipping depends on reports piling up while one spends its budget in real time.
    ports = dataclasses.replace(ports, reporter=DownReporter(), clock=SystemClock())
    start = await start_input(ports, write_pdf(paper(2)), request_id=f"req_{uuid.uuid4().hex[:8]}")

    outcome, _ = await process(client, ports, runtime, start)

    assert outcome["outcome"] == "complete"
    assert await ports.store.head(outcome["manifest_ref"])
    attempted = ports.reporter.reports  # type: ignore[attr-defined]
    # Superseded reports are skipped while the receiver is down; first and last are tried.
    assert attempted[0].seq == 1
    assert (attempted[-1].seq, attempted[-1].stage, attempted[-1].state) == (
        9, "finalize", "succeeded",
    )  # fmt: skip
    assert len(attempted) < 9


async def test_starting_the_same_request_twice_counts_as_success(
    client, monkeypatch, capsys, ports, runtime
):
    monkeypatch.setattr("kp_processing.cli.connect", lambda: _resolved(client))
    start = await start_input(ports, write_pdf(paper(2)), request_id=f"req_{uuid.uuid4().hex[:8]}")

    async with workers(client, ports, runtime):
        assert await start_request(start, wait=True) == 0
        assert await start_request(start, wait=False) == 0

    out = capsys.readouterr().out
    assert f"started {start['request_id']}" in out
    assert f"{start['request_id']} already started" in out
    runs = [w async for w in client.list_workflows(f"WorkflowId = '{start['request_id']}'")]
    assert len(runs) == 1


@pytest.mark.parametrize("admission, key", [("normal", 2), ("low", 4)])
async def test_admission_priority_sets_the_temporal_priority_key(
    client, monkeypatch, ports, admission, key
):
    monkeypatch.setattr("kp_processing.cli.connect", lambda: _resolved(client))
    start = await start_input(ports, write_pdf(paper(1)), request_id=f"req_{uuid.uuid4().hex[:8]}")
    start["priority"] = admission

    assert await start_request(start, wait=False) == 0

    described = await client.get_workflow_handle(start["request_id"]).describe()
    assert described.raw_description.workflow_execution_info.priority.priority_key == key


async def _resolved(value):
    return value
