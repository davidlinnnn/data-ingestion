import json

import httpx
import pytest

from kp_processing.ports.status_reporter import (
    HttpStatusReporter,
    Position,
    Progress,
    RecordingStatusReporter,
    StatusReport,
)

BASE = "http://admission.test"


def report(seq: int = 1, **overrides) -> StatusReport:
    fields = dict(
        request_id="req_01",
        attempt_id="run-a",
        seq=seq,
        stages_version="1",
        stage="parse",
        state="running",
        progress=Progress(done=5, total=28, unit="pages"),
        message="",
        method_version="paper-pdf@1",
        manifest_ref=None,
        observed_at="2026-10-30T08:00:00Z",
        error=None,
    )
    return StatusReport(**{**fields, **overrides})


def reporter(handler) -> HttpStatusReporter:
    return HttpStatusReporter(httpx.AsyncClient(transport=httpx.MockTransport(handler)), BASE)


@pytest.fixture(params=["recording", "http"])
async def status_reporter(request):
    if request.param == "recording":
        fake = RecordingStatusReporter()
        yield fake, lambda: [r.to_json() for r in fake.reports]
    else:
        received = []

        def handler(request: httpx.Request) -> httpx.Response:
            received.append(json.loads(request.content))
            return httpx.Response(202)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            yield HttpStatusReporter(client, BASE), lambda: received


async def test_a_report_is_delivered(status_reporter):
    sender, received = status_reporter

    outcome = await sender.report(report())

    assert outcome.delivered
    assert outcome.error is None
    assert received() == [report().to_json()]


async def test_reports_in_seq_order_are_each_delivered(status_reporter):
    sender, received = status_reporter

    for seq in (1, 2, 3):
        outcome = await sender.report(report(seq))
        assert outcome.delivered
        assert outcome.error is None

    assert received() == [report(seq).to_json() for seq in (1, 2, 3)]


async def test_the_contract_never_raises_when_delivery_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        outcome = await HttpStatusReporter(client, BASE).report(report())

    assert not outcome.delivered
    assert outcome.error


def test_report_json_has_the_round_3_fields():
    assert report().to_json() == {
        "request_id": "req_01",
        "attempt_id": "run-a",
        "seq": 1,
        "stages_version": "1",
        "stage": "parse",
        "state": "running",
        "progress": {"done": 5, "total": 28, "unit": "pages"},
        "message": "",
        "method_version": "paper-pdf@1",
        "manifest_ref": None,
        "observed_at": "2026-10-30T08:00:00Z",
        "error": None,
    }


async def test_recording_fake_keeps_reports_in_order():
    fake = RecordingStatusReporter()

    outcomes = [await fake.report(report(seq)) for seq in (1, 2, 3)]

    assert all(o.delivered for o in outcomes)
    assert [r.seq for r in fake.reports] == [1, 2, 3]


async def test_http_posts_the_report_json_to_the_request():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202)

    outcome = await reporter(handler).report(report(stage="finalize", progress=None))

    assert outcome.delivered
    assert outcome.error is None
    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == f"{BASE}/v1/requests/req_01/status-reports"
    assert json.loads(request.content) == report(stage="finalize", progress=None).to_json()


async def test_http_409_reads_back_the_receivers_position():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"attempt_id": "run-a", "seq": 7})

    outcome = await reporter(handler).report(report(seq=3))

    assert not outcome.delivered
    assert outcome.position == Position(attempt_id="run-a", seq=7)


async def test_http_409_with_an_unreadable_body_is_a_plain_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, text="conflict")

    outcome = await reporter(handler).report(report())

    assert not outcome.delivered
    assert outcome.position is None
    assert outcome.error


async def test_http_server_error_is_returned_not_raised():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    outcome = await reporter(handler).report(report())

    assert not outcome.delivered
    assert outcome.error and "503" in outcome.error


async def test_http_transport_failures_are_returned_not_raised():
    for exc in (httpx.ConnectError("refused"), httpx.ReadTimeout("slow")):

        def handler(request: httpx.Request, exc=exc) -> httpx.Response:
            raise exc

        outcome = await reporter(handler).report(report())

        assert not outcome.delivered
        assert outcome.error
