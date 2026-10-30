"""HttpStatusReporter against the fake_admission receiver over a real local socket
(outside the Codex sandbox, which blocks local ports)."""

import threading

import httpx
import pytest

from kp_processing.ports.status_reporter import HttpStatusReporter, Position
from tests.ports.test_status_reporter import report
from tools.fake_admission.server import make_server

pytestmark = pytest.mark.network


@pytest.fixture
def base_url():
    server = make_server()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


async def test_reports_round_trip_and_out_of_order_gets_the_position(base_url):
    async with httpx.AsyncClient() as client:
        reporter = HttpStatusReporter(client, base_url)

        assert (await reporter.report(report(seq=1))).delivered
        assert (await reporter.report(report(seq=3))).delivered  # a gap is fine
        assert (await reporter.report(report(seq=3))).delivered  # a retry of the last one
        stale = await reporter.report(report(seq=2))
        assert (await reporter.report(report(seq=1, attempt_id="run-b"))).delivered

        stored = (await client.get(f"{base_url}/v1/requests/req_01/status-reports")).json()

    assert not stale.delivered
    assert stale.position == Position(attempt_id="run-a", seq=3)
    assert [(r["attempt_id"], r["seq"]) for r in stored] == [
        ("run-a", 1),
        ("run-a", 3),
        ("run-b", 1),
    ]
    assert stored[0] == report(seq=1).to_json()


async def test_a_report_missing_a_field_is_rejected(base_url):
    body = report().to_json()
    del body["observed_at"]
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{base_url}/v1/requests/req_01/status-reports", json=body)

    assert response.status_code == 400
