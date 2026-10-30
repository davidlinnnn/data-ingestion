"""The paper-pdf workflow on a real Temporal dev server (#131), with an in-process worker and the
in-process store and reporter fakes. Uses the local `temporal` CLI when installed, otherwise
the SDK downloads the dev server; either way it binds a local port (outside the Codex
sandbox)."""

import dataclasses
import json
import shutil
import uuid

import pytest
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment

from kp_processing.cli import start_request
from kp_processing.ports.status_reporter import (
    Progress,
    RecordingStatusReporter,
    ReportOutcome,
    StatusReport,
)
from kp_processing.stages import Ports
from kp_processing.worker import make_worker
from kp_processing.workflow import WORKFLOW, task_queue
from tests.pdfs import encrypt, paper, write_pdf
from tests.stages.conftest import start_input
from tests.stages.test_parse import seven_pages

pytestmark = pytest.mark.network


@pytest.fixture
async def client():
    async with await WorkflowEnvironment.start_local(
        dev_server_existing_path=shutil.which("temporal")
    ) as env:
        yield env.client


async def process(client: Client, ports: Ports, runtime, start) -> tuple[dict, str]:
    worker = await make_worker(client, ports, runtime, "normal")
    async with worker:
        handle = await client.start_workflow(
            WORKFLOW, start, id=start["request_id"], task_queue=task_queue("cpu", "normal")
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
    ports = dataclasses.replace(ports, reporter=DownReporter())
    start = await start_input(ports, write_pdf(paper(2)), request_id=f"req_{uuid.uuid4().hex[:8]}")

    outcome, _ = await process(client, ports, runtime, start)

    assert outcome["outcome"] == "complete"
    assert await ports.store.head(outcome["manifest_ref"])
    assert {r.seq for r in ports.reporter.reports} == set(range(1, 11))  # type: ignore[attr-defined]


async def test_starting_the_same_request_twice_counts_as_success(
    client, monkeypatch, capsys, ports, runtime
):
    monkeypatch.setattr("kp_processing.cli.connect", lambda: _resolved(client))
    start = await start_input(ports, write_pdf(paper(2)), request_id=f"req_{uuid.uuid4().hex[:8]}")

    async with await make_worker(client, ports, runtime, "normal"):
        assert await start_request(start, wait=True) == 0
        assert await start_request(start, wait=False) == 0

    out = capsys.readouterr().out
    assert f"started {start['request_id']}" in out
    assert f"{start['request_id']} already started" in out
    runs = [w async for w in client.list_workflows(f"WorkflowId = '{start['request_id']}'")]
    assert len(runs) == 1


async def _resolved(value):
    return value
