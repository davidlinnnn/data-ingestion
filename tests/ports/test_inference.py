"""InferenceTransport: the fake and the adapters (OpenAI-compatible chat, System One) pass one
contract; the adapters' failure mapping and their in-code deadline (V7: the #84 dead-socket hang
as a regression test); no adapter follows a redirect; Bounded caps a worker's requests in flight
(#155)."""

import asyncio
import base64
import io
import json
import time

import httpx
import pytest
from PIL import Image

from kp_processing.ports.inference import (
    Bounded,
    FakeInference,
    OpenAIChat,
    RequestRejected,
    ServiceUnavailable,
    SystemOne,
    completion,
)

BASE = "http://vlm.test/v1"
D3_BASE = "http://d3.test"


def synthetic_png() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


REQUEST = {
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Transcribe the formula."},
                {"type": "image_url", "image_url": {"url": synthetic_png(), "detail": "high"}},
            ],
        }
    ],
    "response_format": {"type": "json_object"},
}


def response_body(content: str | None = '{"latex": "x"}', refusal: str | None = None) -> dict:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "model": "gpt-6-luna-2026-09-01",
        "system_fingerprint": "fp_abc",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content, "refusal": refusal},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 812, "completion_tokens": 9, "total_tokens": 821},
    }


def adapter(transport: httpx.AsyncBaseTransport, total_s: float = 60) -> OpenAIChat:
    """OpenAIChat over transport; a test of its deadline passes a small total_s."""
    client = httpx.AsyncClient(transport=transport)
    return OpenAIChat(client, BASE, "sk-test", "gpt-6-luna", connect_s=5, total_s=total_s)


def answering(status: int, body: bytes | dict) -> OpenAIChat:
    content = body if isinstance(body, bytes) else json.dumps(body).encode()
    return adapter(httpx.MockTransport(lambda request: httpx.Response(status, content=content)))


SYSTEM_ONE_REQUEST = {
    "model": "vllm-sr/d3-mini",
    "state": {"category": "formula LaTeX", "reconstruction": "x"},
    "images": [synthetic_png()],
    "questions": {"Q2": {"type": "noul", "instructions": "Is it faithful?"}},
}
# The reply shape measured on vLLM Semantic Router Engine mode and d3_server.py (#161).
SYSTEM_ONE_REPLY = {
    "model": "d3-mini",
    "answers": {"Q2": {"type": "noul", "noul": 0.25}},
    "usage": {"input_tokens": 591, "output_tokens": 0},
}


def system_one(transport: httpx.AsyncBaseTransport, total_s: float = 60) -> SystemOne:
    client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    return SystemOne(client, D3_BASE, "sk-d3", connect_s=5, total_s=total_s)


def judging(status: int, body: bytes | dict) -> SystemOne:
    content = body if isinstance(body, bytes) else json.dumps(body).encode()
    return system_one(httpx.MockTransport(lambda request: httpx.Response(status, content=content)))


# --- contract: fake and adapters ----------------------------------------------------------


@pytest.fixture(params=["fake", "openai", "system-one"])
def transport(request):
    """(transport answering an ok response, transport answering 503, the ok answer's content)."""
    body = response_body()
    content = body["choices"][0]["message"]["content"]
    if request.param == "fake":
        ok = completion(content, model=body["model"])
        down = FakeInference(lambda r: ServiceUnavailable("HTTP_5XX"))
        return FakeInference(lambda r: ok), down, content
    if request.param == "system-one":
        reply = json.dumps(SYSTEM_ONE_REPLY)
        return judging(200, reply.encode()), judging(503, b"overloaded"), reply
    return answering(200, body), answering(503, b"overloaded"), content


async def test_an_answer_carries_its_content_and_the_body_as_received(transport):
    ok, _, content = transport

    answer = await ok.complete(REQUEST)

    assert answer.content == content
    assert answer.refusal is None
    assert answer.model
    assert answer.body


async def test_an_openai_answer_is_the_first_choice():
    answer = await answering(200, response_body()).complete(REQUEST)

    assert answer.content == '{"latex": "x"}'
    assert answer.model == "gpt-6-luna-2026-09-01"
    assert json.loads(answer.body)["choices"][0]["message"]["content"] == answer.content


async def test_an_unavailable_service_raises_service_unavailable(transport):
    _, down, _ = transport

    with pytest.raises(ServiceUnavailable) as caught:
        await down.complete(REQUEST)

    assert caught.value.reason == "HTTP_5XX"


# --- adapter ------------------------------------------------------------------------------


async def test_the_request_carries_the_model_and_the_key():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=json.dumps(response_body()).encode())

    answer = await adapter(httpx.MockTransport(handler)).complete(REQUEST)

    (request,) = seen
    assert (request.method, str(request.url)) == ("POST", f"{BASE}/chat/completions")
    assert request.headers["authorization"] == "Bearer sk-test"
    assert json.loads(request.content) == {**REQUEST, "model": "gpt-6-luna"}
    assert answer.body == json.dumps(response_body()).encode()
    assert answer.system_fingerprint == "fp_abc"
    assert answer.usage == {"prompt_tokens": 812, "completion_tokens": 9, "total_tokens": 821}


async def test_a_refusal_is_returned_not_raised():
    answer = await answering(200, response_body(None, "I can't help with that.")).complete(REQUEST)

    assert (answer.content, answer.refusal) == (None, "I can't help with that.")


async def test_a_response_without_usage_has_empty_usage():
    body = response_body()
    del body["usage"]

    assert (await answering(200, body).complete(REQUEST)).usage == {}


@pytest.mark.parametrize(
    ("status", "body", "reason"),
    [
        (429, b"slow down", "HTTP_429"),
        (500, b"boom", "HTTP_5XX"),
        (502, b"bad gateway", "HTTP_5XX"),
        (503, b"", "HTTP_5XX"),
        (200, b"<html>not json</html>", "MALFORMED_RESPONSE"),
        (200, json.dumps({"choices": []}).encode(), "MALFORMED_RESPONSE"),
        (200, json.dumps({"model": "m"}).encode(), "MALFORMED_RESPONSE"),
    ],
)
async def test_transient_failures_map_to_service_unavailable(status, body, reason):
    with pytest.raises(ServiceUnavailable) as caught:
        await answering(status, body).complete(REQUEST)

    assert caught.value.reason == reason


@pytest.mark.parametrize("error", [httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError])
async def test_transport_errors_map_to_connection(error):
    def handler(request: httpx.Request) -> httpx.Response:
        raise error("down", request=request)

    with pytest.raises(ServiceUnavailable) as caught:
        await adapter(httpx.MockTransport(handler)).complete(REQUEST)

    assert caught.value.reason == "CONNECTION"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
async def test_other_statuses_are_rejected_requests(status):
    with pytest.raises(RequestRejected) as caught:
        await answering(status, b'{"error": {}}').complete(REQUEST)

    assert caught.value.status == status


# --- SystemOne: the d3 service (#161) ------------------------------------------------------


async def test_system_one_posts_the_request_as_given_with_the_key():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=json.dumps(SYSTEM_ONE_REPLY).encode())

    answer = await system_one(httpx.MockTransport(handler)).complete(SYSTEM_ONE_REQUEST)

    (request,) = seen
    assert (request.method, str(request.url)) == ("POST", f"{D3_BASE}/v1/systemone")
    assert request.headers["authorization"] == "Bearer sk-d3"
    assert json.loads(request.content) == SYSTEM_ONE_REQUEST
    assert json.loads(answer.content or "")["answers"]["Q2"]["noul"] == 0.25
    assert answer.body == json.dumps(SYSTEM_ONE_REPLY).encode()
    assert (answer.model, answer.refusal, answer.system_fingerprint) == ("d3-mini", None, None)
    assert answer.usage == {"input_tokens": 591, "output_tokens": 0}


@pytest.mark.parametrize(
    ("status", "body", "reason"),
    [
        (429, b"slow down", "HTTP_429"),
        (500, b"500: the server failed on this request (RuntimeError)", "HTTP_5XX"),
        (200, b"<html>not json</html>", "MALFORMED_RESPONSE"),
        (200, json.dumps({"model": "d3-mini"}).encode(), "MALFORMED_RESPONSE"),
        (200, json.dumps({"answers": []}).encode(), "MALFORMED_RESPONSE"),
        (200, json.dumps([SYSTEM_ONE_REPLY]).encode(), "MALFORMED_RESPONSE"),
    ],
)
async def test_system_one_maps_transient_failures_to_service_unavailable(status, body, reason):
    with pytest.raises(ServiceUnavailable) as caught:
        await judging(status, body).complete(SYSTEM_ONE_REQUEST)

    assert caught.value.reason == reason


@pytest.mark.parametrize("status", [401, 307, 422])  # wrong key, redirect, unreadable request
async def test_system_one_rejects_other_statuses_without_following_a_redirect(status):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(status, headers={"location": "http://elsewhere.test/collect"})

    with pytest.raises(RequestRejected) as caught:
        await system_one(httpx.MockTransport(handler)).complete(SYSTEM_ONE_REQUEST)

    assert caught.value.status == status
    assert seen == [f"{D3_BASE}/v1/systemone"]


async def test_a_hung_system_one_call_is_cut_at_the_deadline():
    hang = Hang("drip")
    started = time.monotonic()

    with pytest.raises(ServiceUnavailable) as caught:
        await system_one(hang, total_s=0.5).complete(SYSTEM_ONE_REQUEST)

    assert caught.value.reason == "TIMEOUT"
    assert 0.5 <= time.monotonic() - started <= 1.5
    assert hang.ended() == 1


# --- Bounded: a worker's requests in flight ------------------------------------------------


async def test_bounded_holds_requests_past_its_limit_until_one_returns():
    release = asyncio.Event()
    running = 0
    peak = 0

    async def slow(request: dict):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await release.wait()
        running -= 1
        return completion("{}")

    bounded = Bounded(FakeInference(slow), 2)
    calls = [asyncio.create_task(bounded.complete({"n": n})) for n in range(5)]
    await asyncio.sleep(0.01)
    assert (peak, running) == (2, 2)
    release.set()
    await asyncio.gather(*calls)
    assert peak == 2


# --- egress: requests leave only for the configured endpoint -------------------------------


async def test_a_redirect_elsewhere_is_never_followed():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(307, headers={"location": "http://elsewhere.test/collect"})

    # The client would follow redirects; the adapter must not.
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    sender = OpenAIChat(client, BASE, "sk-test", "gpt-6-luna", connect_s=5, total_s=60)

    with pytest.raises(RequestRejected) as caught:
        await sender.complete(REQUEST)

    assert caught.value.status == 307
    assert len(seen) == 1
    assert "elsewhere.test" not in seen[0]


# --- V7 at the transport layer: three ways to hang, one deadline --------------------------


class Body(httpx.AsyncByteStream):
    """A response body that never ends: nothing after the headers, or one byte every drip_s."""

    def __init__(self, drip_s: float | None) -> None:
        self.drip_s = drip_s
        self.closed = False

    async def __aiter__(self):
        drip_s = self.drip_s
        if drip_s is None:
            await asyncio.Event().wait()
            return
        while True:
            yield b" "
            await asyncio.sleep(drip_s)

    async def aclose(self) -> None:
        self.closed = True


class Hang(httpx.AsyncBaseTransport):
    """silent: accepts and never answers; headers: sends headers, then nothing; drip: sends
    headers, then a byte every 0.05 s, faster than any read timeout."""

    def __init__(self, variant: str) -> None:
        self.variant = variant
        self.bodies: list[Body] = []
        self.cancelled = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self.variant == "silent":
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled += 1
                raise
        self.bodies.append(Body(None if self.variant == "headers" else 0.05))
        return httpx.Response(
            200, headers={"content-type": "application/json"}, stream=self.bodies[-1]
        )

    def ended(self) -> int:
        """Calls that ended: cancelled while silent, or with their body closed."""
        return self.cancelled + sum(body.closed for body in self.bodies)


@pytest.mark.parametrize("variant", ["silent", "headers", "drip"])
async def test_a_hung_call_is_cut_at_the_deadline_and_closed(variant):
    hang = Hang(variant)
    total_s = 0.5
    tasks_before = asyncio.all_tasks()
    started = time.monotonic()
    call = adapter(hang, total_s=total_s).complete(REQUEST)

    with pytest.raises(ServiceUnavailable) as caught:
        await call

    elapsed = time.monotonic() - started
    assert caught.value.reason == "TIMEOUT"
    assert total_s <= elapsed <= total_s + 1
    assert hang.ended() == 1
    await asyncio.sleep(0)
    assert asyncio.all_tasks() == tasks_before


# --- V7 on real sockets (outside the Codex sandbox) ---------------------------------------


class Servers:
    """Local HTTP peers that never finish (from prototype/93-v7-dead-socket): silent accepts and
    stays silent; headers sends headers and one chunk; drip sends a chunk every drip_s. Each
    connection records whether the client closed it (EOF)."""

    def __init__(self, drip_s: float) -> None:
        self.drip_s = drip_s
        self.servers: dict[str, asyncio.Server] = {}
        self.connections: list[dict] = []
        self.handlers: set[asyncio.Task] = set()

    async def __aenter__(self) -> "Servers":
        for variant in ("silent", "headers", "drip"):
            self.servers[variant] = await asyncio.start_server(
                lambda r, w, v=variant: self._accept(v, r, w), "127.0.0.1", 0
            )
        return self

    async def __aexit__(self, *exc) -> None:
        if self.handlers:
            await asyncio.wait_for(asyncio.gather(*self.handlers), 5)
        for server in self.servers.values():
            server.close()
            await server.wait_closed()

    def url(self, variant: str) -> str:
        return f"http://127.0.0.1:{self.servers[variant].sockets[0].getsockname()[1]}/v1"

    def _accept(self, variant, reader, writer) -> None:
        task = asyncio.ensure_future(self._handle(variant, reader, writer))
        self.handlers.add(task)
        task.add_done_callback(self.handlers.discard)

    async def _handle(self, variant, reader, writer) -> None:
        record = {"variant": variant, "eof": False}
        self.connections.append(record)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(int(line.split(b":", 1)[1]) for line in headers.split(b"\r\n")
                          if line.lower().startswith(b"content-length:"))  # fmt: skip
            await reader.readexactly(length)
            if variant != "silent":
                writer.write(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n"
                             b"Content-Type: application/json\r\n\r\n4\r\n{\"a\"\r\n")  # fmt: skip
                await writer.drain()
            while True:
                try:
                    data = await asyncio.wait_for(reader.read(1), self.drip_s)
                except TimeoutError:
                    if variant == "drip":
                        writer.write(b"1\r\n \r\n")
                        await writer.drain()
                    continue
                if not data:
                    record["eof"] = True
                    return
        finally:
            writer.close()


@pytest.mark.network
@pytest.mark.parametrize("variant", ["silent", "headers", "drip"])
async def test_a_hung_server_is_cut_at_the_deadline_and_its_socket_closed(variant):
    total_s = 2.0
    async with Servers(drip_s=0.2) as servers:
        # The client's read timeout (10 s) is longer than the drip interval (0.2 s), so for the
        # drip only the in-code deadline can end the call.
        client = httpx.AsyncClient(timeout=httpx.Timeout(10, connect=5))
        chat = OpenAIChat(client, servers.url(variant), "k", "m", connect_s=5, total_s=total_s)
        started = time.monotonic()

        with pytest.raises(ServiceUnavailable) as caught:
            await chat.complete(REQUEST)

        elapsed = time.monotonic() - started
        await client.aclose()
    assert caught.value.reason == "TIMEOUT"
    assert total_s <= elapsed <= total_s + 5
    assert [c["eof"] for c in servers.connections] == [True]


@pytest.mark.network
async def test_negative_control_without_the_deadline_the_drip_outlives_the_read_timeout():
    """The drip defeats httpx's own read timeout: without the in-code deadline the call is
    still running when the test gives up, so the V7 test above can see a missing deadline."""
    async with Servers(drip_s=0.2) as servers:
        client = httpx.AsyncClient(timeout=httpx.Timeout(1, connect=5))
        call = asyncio.ensure_future(client.post(servers.url("drip") + "/chat/completions",
                                                 json=REQUEST))  # fmt: skip
        await asyncio.sleep(3)
        still_running = not call.done()
        call.cancel()
        await asyncio.gather(call, return_exceptions=True)
        await client.aclose()
    assert still_running
