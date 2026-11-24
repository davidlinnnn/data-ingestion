"""The consumer SDK (#127) at its HTTP seam: what each call sends, which answers it repeats and
what it returns or raises. The end-to-end tests in tests/reference_projection run it against the
real api."""

import json

import httpx
import pytest

from kp_sdk import PlatformError
from kp_sdk.projection import ProjectionClient


def client(*answers: httpx.Response) -> tuple[ProjectionClient, list[httpx.Request]]:
    sent: list[httpx.Request] = []
    queue = list(answers)

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return queue.pop(0)

    async def no_wait(_: float) -> None:
        pass

    sdk = ProjectionClient(
        "http://api", "secret", "retrieval", transport=httpx.MockTransport(handle), sleep=no_wait
    )
    return sdk, sent


def error(status: int, reason: str) -> httpx.Response:
    body = {
        "error": {"code": status, "status": "X", "message": "m", "details": [{"reason": reason}]}
    }
    return httpx.Response(status, json=body)


async def test_a_lost_answer_or_a_5xx_is_sent_again_with_the_same_body():
    sdk, sent = client(
        httpx.Response(503, headers={"retry-after": "1"}),
        httpx.Response(500),
        httpx.Response(200, json={"fenced": [], "repair_requested": None}),
    )
    facts = [{"document_uid": "doc_1", "state": "included", "fact_version": 3}]

    answer = await sdk.report_facts("b/1", facts)

    assert answer == {"fenced": [], "repair_requested": None}
    assert [r.url.raw_path for r in sent] == [b"/report/v1/builds/b%2F1/facts"] * 3
    assert [json.loads(r.content) for r in sent] == [{"facts": facts}] * 3
    assert sent[0].headers["authorization"] == "Bearer secret"


async def test_a_refusal_raises_its_reason_and_an_unknown_document_reads_as_none():
    sdk, _ = client(error(409, "SUPERSEDED"), error(404, "DOCUMENT_NOT_FOUND"))

    with pytest.raises(PlatformError) as refused:
        await sdk.register("b1", [{"document_uid": "doc_1"}])
    assert (refused.value.status, refused.value.reason) == (409, "SUPERSEDED")
    assert await sdk.document_state("doc_1", at_least="0" * 32) is None


async def test_an_out_of_order_attempt_report_returns_the_position_and_a_retired_build_raises():
    sdk, _ = client(
        httpx.Response(202),
        httpx.Response(409, json={"attempt_no": 2, "seq": 3}),
        error(409, "BUILD_STATE"),
    )

    assert await sdk.report_attempt("b1", {"seq": 1}) is None
    assert await sdk.report_attempt("b1", {"seq": 1}) == {"attempt_no": 2, "seq": 3}
    with pytest.raises(PlatformError, match="BUILD_STATE"):
        await sdk.report_attempt("b1", {"seq": 1})


async def test_feed_cursor_and_content_calls_pass_opaque_strings_unparsed():
    sdk, sent = client(
        httpx.Response(200, json={"events": [], "next_cursor": "c2"}),
        httpx.Response(204),
        httpx.Response(200, content=b"{}"),
        httpx.Response(200, content=b"png"),
    )

    assert await sdk.feed(None) == {"events": [], "next_cursor": "c2"}
    await sdk.report_cursor("c2")
    assert await sdk.content("doc_1", "crv_1") == b"{}"
    assert await sdk.artifact("doc_1", "crv_1", "items/fig 1.png") == b"png"

    assert [str(r.url) for r in sent] == [
        "http://api/read/v1/feed?limit=100",
        "http://api/read/v1/consumers/retrieval/cursor",
        "http://api/read/v1/documents/doc_1/revisions/crv_1",
        "http://api/read/v1/documents/doc_1/revisions/crv_1/artifacts/items%2Ffig%201.png",
    ]
