"""The minimal Python SDK for Sources (#194): `Client.submit` declares a batch, uploads the files
the declaration asks for and finalizes it, as the document submission guide §5 describes the
three calls (admission spec §5.1–§5.3).

Everyone who can read a document can see its Source Metadata (`metadata`), so it holds nothing
that the document's readers may not see.

A failed call raises PlatformError, which carries the response's trace id (`X-Trace-Id`): quote
it when reporting a problem. A 429 or 503 is repeated after its Retry-After, a lost connection
after a short wait; every call is safe to repeat (the declaration under one Idempotency-Key).
It depends on httpx and the standard library only.
"""

import hashlib
import logging
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

_READ = 2**20


class PlatformError(Exception):
    """A call the platform refused, or one that never got an answer (status 0). `items` lists
    every item's outcome when every item is rejected (ALL_ITEMS_REJECTED, §5.1 and §5.3)."""

    def __init__(
        self,
        status: int,
        reason: str,
        message: str,
        trace_id: str | None,
        items: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(f"{status} {reason}: {message} (trace_id {trace_id})")
        self.status, self.reason, self.message, self.trace_id = status, reason, message, trace_id
        self.items = items


class Client:
    """A Source's client of the platform API at `base_url`, its origin, with its credential."""

    def __init__(
        self,
        base_url: str,
        credential: str,
        *,
        attempts: int = 5,
        timeout: float = 300,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.http = httpx.Client(
            base_url=base_url,
            headers={"authorization": f"Bearer {credential}"},
            timeout=timeout,
            transport=transport,
        )
        self._attempts, self._sleep = attempts, sleep

    def submit(self, items: list[Mapping[str, Any]]) -> dict[str, Any]:
        """Submits `items`, each as admission spec §5.1 declares one, except that a file gives the
        `local` path of its bytes instead of `sha256` and `size`. Returns the finalized batch
        (§5.3), with each item's outcome."""
        files: dict[tuple[int, str], tuple[Path, dict[str, Any]]] = {}
        for index, item in enumerate(items):
            for f in item["files"]:
                local = Path(f["local"])
                declared = {k: v for k, v in f.items() if k != "local"} | _measure(local)
                files[(index, f["path"])] = (local, declared)
        declaration = [
            dict(item) | {"files": [files[(index, f["path"])][1] for f in item["files"]]}
            for index, item in enumerate(items)
        ]
        batch = self._call(
            "POST",
            "/v1/batches",
            json={"items": declaration},
            headers={"idempotency-key": uuid.uuid4().hex},
        ).json()
        for entry in batch["items"]:
            for upload in entry.get("uploads", []):
                self._upload(upload, *files[(entry["index"], upload["path"])])
        if batch["state"] != "open":  # nothing to upload: finalized at declaration
            return batch
        return self._call("POST", f"/v1/batches/{batch['batch_id']}/finalize").json()

    def _upload(self, upload: dict, path: Path, file: dict[str, Any]) -> None:
        url = httpx.URL(upload["url"])
        base = self.http.base_url
        if (url.scheme, url.host, url.port) != (base.scheme, base.host, base.port):
            # The credential goes to the origin it was given for only (§5.1).
            raise PlatformError(0, "UPLOAD_URL", "The upload URL is on another origin.", None)
        self._call(
            upload["method"],
            upload["url"],
            content=lambda: _chunks(path),
            headers={"content-length": str(file["size"]), "content-type": file["media_type"]},
        )

    def _call(
        self,
        method: str,
        url: str,
        content: Callable[[], Iterator[bytes]] | None = None,
        **options: Any,
    ) -> httpx.Response:
        for attempt in range(1, self._attempts + 1):
            last = attempt == self._attempts
            try:
                body = content() if content else None
                response = self.http.request(method, url, content=body, **options)
            except httpx.TransportError as error:
                if last:
                    raise PlatformError(0, "UNREACHABLE", type(error).__name__, None) from error
                log.warning("%s: %s; repeating", method, type(error).__name__)
                self._sleep(2**attempt)
                continue
            trace_id = response.headers.get("x-trace-id")
            if response.status_code in (429, 503) and not last:
                wait = response.headers.get("retry-after", "1")
                log.warning(
                    "%s: %s; repeating in %s s (trace_id %s)",
                    method,
                    response.status_code,
                    wait,
                    trace_id,
                )
                self._sleep(int(wait) if wait.isdecimal() else 1)
                continue
            if response.is_error:
                raise _refused(response, trace_id)
            return response
        raise AssertionError("unreachable")


def _refused(response: httpx.Response, trace_id: str | None) -> PlatformError:
    items = None
    try:
        body = response.json()
        error, items = body["error"], body.get("items")
        reason = (error.get("details") or [{}])[0].get("reason", error["status"])
        message = error["message"]
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        reason, message = "UNKNOWN", response.reason_phrase
    # The URL names a file path, which stays out of the log.
    log.warning("refused: %s %s (trace_id %s)", response.status_code, reason, trace_id)
    return PlatformError(response.status_code, reason, message, trace_id, items)


def _measure(path: Path) -> dict[str, Any]:
    digest, size = hashlib.sha256(), 0
    for chunk in _chunks(path):
        digest.update(chunk)
        size += len(chunk)
    return {"sha256": digest.hexdigest(), "size": size}


def _chunks(path: Path) -> Iterator[bytes]:
    with path.open("rb") as file:
        while chunk := file.read(_READ):
            yield chunk
