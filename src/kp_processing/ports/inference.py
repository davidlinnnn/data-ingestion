"""InferenceTransport port: one OpenAI-compatible chat-completions service, such as the company
VLM or the DEV reference model (#129, inference adapter; #93 §3.2)."""

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
    content: str | None  # choices[0].message.content
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
        """Send one chat-completions request body (messages, response_format, ...; without
        "model", which the transport adds) and return the first choice. Raises
        ServiceUnavailable or RequestRejected; nothing else escapes."""
        ...


class OpenAIChat:
    """POST {base_url}/chat/completions with {**request, "model": model}, bearer api_key.

    The whole call (connect, headers, body) runs under an in-code deadline of total_s; on expiry
    the call is cancelled, its connection closed, and ServiceUnavailable("TIMEOUT") raised
    within a second. The client's own timeouts (connect_s, and total_s for reads) are set but
    not trusted: a server that drips bytes slower than the read timeout defeats them (#84).

    Mapping: 2xx with a JSON body holding choices[0].message -> Completion; 429 -> HTTP_429;
    5xx -> HTTP_5XX; connect or transport errors -> CONNECTION; a 2xx body without
    choices[0].message -> MALFORMED_RESPONSE; any other status -> RequestRejected.
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
        try:
            async with asyncio.timeout(self.total_s):
                async with self.client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json={**request, "model": self.model},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=httpx.Timeout(self.total_s, connect=self.connect_s),
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
