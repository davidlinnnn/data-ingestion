"""InferenceTransport port: one external inference service (#129, inference adapter; #93 §3.2).
OpenAIChat serves an OpenAI-compatible chat-completions service: the company VLM or LLM, the DEV
reference model, or Anthropic's OpenAI-compatible endpoint for the DEV Document Summary (#155).
SystemOne serves a d3 decision model's System One service (#161)."""

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

UnavailableReason = Literal["TIMEOUT", "CONNECTION", "HTTP_5XX", "HTTP_429", "MALFORMED_RESPONSE"]


@dataclass(frozen=True)
class Completion:
    content: str | None  # choices[0].message.content; from SystemOne, the response JSON text
    refusal: str | None  # choices[0].message.refusal, set when the model refused
    model: str  # the response's model
    system_fingerprint: str | None
    usage: dict[str, Any]  # the response's usage object, {} when absent
    body: bytes  # the response JSON as received: the provider artifact


class ServiceUnavailable(Exception):
    """The service gave no usable answer: the retry matrix's transient class (#93 §3.4)."""

    def __init__(self, reason: UnavailableReason, message: str = "") -> None:
        super().__init__(f"{reason}: {message}" if message else reason)
        self.reason: UnavailableReason = reason


class RequestRejected(Exception):
    """The service refused the request itself (a non-2xx status other than 429 and 5xx): the
    request or the credentials are wrong, which no retry cures."""

    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.status = status


class InferenceTransport(Protocol):
    async def complete(self, request: dict[str, Any]) -> Completion:
        """Send one request body of the service's contract (for chat completions: messages,
        response_format, ...; without "model", which the transport adds) to the one endpoint
        the transport was built for, and return the answer. Raises ServiceUnavailable or
        RequestRejected; nothing else escapes."""
        ...


async def _post(
    client: httpx.AsyncClient,
    url: str,
    api_key: str,
    request: dict[str, Any],
    connect_s: float,
    total_s: float,
) -> bytes:
    try:
        async with asyncio.timeout(total_s):
            async with client.stream(
                "POST",
                url,
                json=request,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=httpx.Timeout(total_s, connect=connect_s),
                follow_redirects=False,
            ) as response:
                body = await response.aread()
                status = response.status_code
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise ServiceUnavailable("TIMEOUT") from exc
    except httpx.TransportError as exc:
        raise ServiceUnavailable("CONNECTION") from exc
    if status == 429:
        raise ServiceUnavailable("HTTP_429")
    if 500 <= status < 600:
        raise ServiceUnavailable("HTTP_5XX")
    if not 200 <= status < 300:
        raise RequestRejected(status)
    return body


class OpenAIChat:
    """POST {base_url}/chat/completions with {**request, "model": model}, bearer api_key.

    The whole call (connect, headers, body) runs under an in-code deadline of total_s; on expiry
    the call is cancelled, its connection closed, and ServiceUnavailable("TIMEOUT") raised
    within a second. The client's own timeouts (connect_s, and total_s for reads) are set but
    not trusted: a server that drips bytes slower than the read timeout defeats them (#84).

    Mapping: 2xx with a JSON body holding choices[0].message -> Completion; 429 -> HTTP_429;
    5xx -> HTTP_5XX; connect or transport errors -> CONNECTION; a 2xx body without
    choices[0].message -> MALFORMED_RESPONSE; any other status -> RequestRejected. A redirect
    is never followed, whatever the client's setting: requests leave only for base_url (the
    3xx status is a RequestRejected).
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        model: str,
        connect_s: float,
        total_s: float,
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.connect_s = connect_s
        self.total_s = total_s

    async def complete(self, request: dict[str, Any]) -> Completion:
        body = await _post(
            self.client,
            f"{self.base_url}/chat/completions",
            self.api_key,
            {**request, "model": self.model},
            self.connect_s,
            self.total_s,
        )
        try:
            data = json.loads(body)
            message = data["choices"][0]["message"]
            if not isinstance(message, dict):
                raise ValueError("Missing response message")
            return Completion(
                message.get("content"),
                message.get("refusal"),
                data.get("model", ""),
                data.get("system_fingerprint"),
                data.get("usage", {}),
                body,
            )
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ServiceUnavailable("MALFORMED_RESPONSE") from exc


class SystemOne:
    """POST {base_url}/v1/systemone with the request as given, bearer api_key: the System One
    service of a d3 decision model, as vLLM Semantic Router's Engine mode and the model package's
    d3_server.py serve it. The request names its own model.

    Deadline, redirects and status mapping are OpenAIChat's. A 2xx JSON object holding an
    "answers" object -> Completion with content = the body as text, model and usage from the
    body and no refusal; any other 2xx body -> MALFORMED_RESPONSE.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        connect_s: float,
        total_s: float,
    ) -> None:
        self.client = client
        self.url = f"{base_url.rstrip('/')}/v1/systemone"
        self.api_key = api_key
        self.connect_s = connect_s
        self.total_s = total_s

    async def complete(self, request: dict[str, Any]) -> Completion:
        body = await _post(
            self.client, self.url, self.api_key, request, self.connect_s, self.total_s
        )
        try:
            data = json.loads(body)
            if not isinstance(data["answers"], dict):
                raise ValueError("Missing answers")
            return Completion(
                body.decode(), None, data.get("model", ""), None, data.get("usage", {}), body
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise ServiceUnavailable("MALFORMED_RESPONSE") from exc


class Bounded:
    """At most limit requests of the wrapped transport in flight at once, for one worker process;
    the others wait here, before the transport's deadline starts."""

    def __init__(self, transport: InferenceTransport, limit: int) -> None:
        self.transport = transport
        self.slots = asyncio.Semaphore(limit)

    async def complete(self, request: dict[str, Any]) -> Completion:
        async with self.slots:
            return await self.transport.complete(request)


class FakeInference:
    """In-process fake: answer(request) gives a Completion to return or an exception to raise,
    directly or awaited; every request is recorded in order."""

    def __init__(
        self,
        answer: Callable[[dict[str, Any]], Completion | Exception | Awaitable[Completion]],
    ) -> None:
        self.answer = answer
        self.requests: list[dict[str, Any]] = []

    async def complete(self, request: dict[str, Any]) -> Completion:
        self.requests.append(request)
        answer = self.answer(request)
        if isinstance(answer, Exception):
            raise answer
        return await answer if inspect.isawaitable(answer) else answer


def completion(content: str | None, refusal: str | None = None, model: str = "fake") -> Completion:
    """A Completion as an OpenAI-compatible service would return it (for fakes and tests)."""
    message = {"role": "assistant", "content": content, "refusal": refusal}
    body = {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "model": model,
        "system_fingerprint": None,
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    return Completion(content, refusal, model, None, body["usage"], json.dumps(body).encode())
