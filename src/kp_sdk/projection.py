"""The consumer SDK for projections (#127): the governed reads under `/read/v1/` (#126, canonical
consumption DR §3), the two Canonical content reads (#268), the projection reports under
`/report/v1/` (admission spec §7.4) and, for a projection's query side, the Resources a user
may read (`readable`, authorization guide §5). Every obligation of the protocol is met over
HTTP; this wraps the calls and leaves the protocol to its caller.

Cursors, feed positions, `crv_` revision IDs, `resource_id` and the image references inside
content are opaque strings: nothing here parses them.

Every call is safe to repeat, so a lost connection, a 429 or a 5xx is sent again, after its
Retry-After when it has one; what is still refused raises kp_sdk.PlatformError. `readable` is
the exception: the guide allows it one more listing from the first page. It depends on
httpx and the standard library only.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote

import httpx

from kp_sdk import PlatformError, _refused

log = logging.getLogger(__name__)

# shortcut: #268 names the content routes; these are provisional until it merges.
CONTENT = "/read/v1/documents/{uid}/revisions/{crv}"
ARTIFACT = "/read/v1/documents/{uid}/revisions/{crv}/artifacts/{reference}"
AUTHZ_TIMEOUT_S = 1.0  # above the platform's 500 ms, so its 503 comes first (guide §5.12)


class ProjectionClient:
    """Projection `projection`'s client of the platform API at `base_url`, with its service
    credential, registered under that name for the feed and in `KP_PIPELINES` (spec §7.4)."""

    def __init__(
        self,
        base_url: str,
        credential: str,
        projection: str,
        *,
        attempts: int = 5,
        timeout: float = 60,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.http = httpx.AsyncClient(
            base_url=base_url,
            headers={"authorization": f"Bearer {credential}"},
            timeout=timeout,
            transport=transport,
        )
        self.projection = projection
        self._attempts, self._sleep = attempts, sleep

    async def aclose(self) -> None:
        await self.http.aclose()

    # Governed reads (#126)

    async def feed(self, cursor: str | None, limit: int = 100) -> dict[str, Any]:
        """`{"events", "next_cursor"}` after `cursor`; without one, no events and the position
        to start from. An expired cursor raises PlatformError `CURSOR_EXPIRED` (410)."""
        params: dict[str, Any] = {"limit": limit} | ({"cursor": cursor} if cursor else {})
        return (await self._call("GET", "/read/v1/feed", params=params)).json()

    async def report_cursor(self, cursor: str) -> None:
        """Reports the position read to; a step back raises `CURSOR_BACKWARDS` (409)."""
        path = f"/read/v1/consumers/{quote(self.projection, safe='')}/cursor"
        await self._call("PUT", path, json={"cursor": cursor})

    async def document_state(self, uid: str, at_least: str | None = None) -> dict[str, Any] | None:
        """`{"resource_id", "current", "status", ...}` at least as new as `at_least`; None for
        `404 DOCUMENT_NOT_FOUND`."""
        params = {"at_least": at_least} if at_least else {}
        try:
            response = await self._call("GET", f"/read/v1/documents/{_q(uid)}/state", params=params)
        except PlatformError as error:
            if error.reason == "DOCUMENT_NOT_FOUND":
                return None
            raise
        return response.json()

    async def sources(self) -> list[str]:
        return (await self._call("GET", "/read/v1/sources")).json()["source_ids"]

    async def source_profile(self, source_id: str) -> dict[str, Any]:
        return (await self._call("GET", f"/read/v1/sources/{_q(source_id)}/profile")).json()

    async def source_documents(
        self, source_id: str, after: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        """`{"document_uids", "next_after"}`, `next_after` null on the last page."""
        params: dict[str, Any] = {"limit": limit} | ({"after": after} if after else {})
        path = f"/read/v1/sources/{_q(source_id)}/documents"
        return (await self._call("GET", path, params=params)).json()

    # Canonical content (#268)

    async def content(self, uid: str, canonical_revision_id: str) -> bytes:
        """The Canonical content object of that exact revision."""
        path = CONTENT.format(uid=_q(uid), crv=_q(canonical_revision_id))
        return (await self._call("GET", path)).content

    async def artifact(self, uid: str, canonical_revision_id: str, reference: str) -> bytes:
        """The bytes of an artifact the revision's content lists, by its opaque reference."""
        path = ARTIFACT.format(uid=_q(uid), crv=_q(canonical_revision_id), reference=_q(reference))
        return (await self._call("GET", path)).content

    # The authz API, for a projection's query side (authorization guide §5)

    async def readable(
        self, user: str, actor: str | None = None, headers: dict[str, str] | None = None
    ) -> list[str]:
        """Every Resource `user` may read: all pages of `list_resources` (guide §5.4), with
        `actor` the agent application that asks for the user and `headers` the caller's
        `traceparent` and `x-request-id` (§5.9, §5.11). Anything but a 200, a lost connection
        or a timeout reads once more from the first page, then raises PlatformError: the
        caller gives no content (§5.6). Each answer is used once (§5.8)."""
        body: dict[str, Any] = {"subject": {"type": "user", "id": user}, "action": "read"}
        if actor:
            body["actor"] = {"type": "client", "id": actor}
        for attempt in (1, 2):
            try:
                return await self._list_all(body, headers or {})
            except PlatformError as error:
                if attempt == 2:
                    raise
                log.warning("list_resources: %s %s; from the first page again", error.status,
                            error.reason)  # fmt: skip
        raise AssertionError("unreachable")

    async def _list_all(self, body: dict[str, Any], headers: dict[str, str]) -> list[str]:
        ids: list[str] = []
        cursor = None
        while True:
            page = body | ({"cursor": cursor} if cursor else {})
            try:
                response = await self.http.post(
                    "/authz/v1/list_resources", json=page, headers=headers, timeout=AUTHZ_TIMEOUT_S
                )
            except httpx.TransportError as error:  # a timeout too: no decision (§5.6)
                raise PlatformError(0, "UNREACHABLE", type(error).__name__, None) from error
            trace_id = response.headers.get("x-trace-id")
            if response.status_code != 200:
                raise _refused(response, trace_id)
            answer = response.json()
            log.info(
                "resources listed: decision_id=%s trace_id=%s count=%s",
                answer["decision_id"],
                trace_id,
                len(answer["resource_ids"]),
            )
            ids += answer["resource_ids"]
            if not (cursor := answer.get("next_cursor")):  # an empty page is not the end
                return ids

    # Reports (spec §7.4)

    async def report_build(self, build_id: str, report: dict[str, Any]) -> dict[str, Any]:
        """`{"state", "repair_requested"}`; refusals raise `GATE_FAILED` or `BUILD_STATE`."""
        return (await self._call("PUT", f"/report/v1/builds/{_q(build_id)}", json=report)).json()

    async def register(self, build_id: str, facts: list[dict[str, Any]]) -> dict[str, Any]:
        """Records every fact `pending` or none: `SUPERSEDED`, `FENCED` raise (409)."""
        return await self._post(build_id, "registrations", {"facts": facts})

    async def report_facts(self, build_id: str, facts: list[dict[str, Any]]) -> dict[str, Any]:
        """`{"fenced", "repair_requested"}`: the facts listed in `fenced` are not sent again."""
        return await self._post(build_id, "facts", {"facts": facts})

    async def heartbeat(self, build_id: str, count: int, digest: str) -> dict[str, Any]:
        return await self._post(build_id, "heartbeats", {"count": count, "digest": digest})

    async def report_attempt(self, build_id: str, report: dict[str, Any]) -> dict[str, Any] | None:
        """None when taken or a resend; the current position `{"attempt_no", "seq"}` when the
        report is out of order (409). A retired Build raises `BUILD_STATE`."""
        path = f"/report/v1/builds/{_q(build_id)}/status-reports"
        try:
            await self._call("POST", path, json=report)
        except PlatformError as error:
            if error.status == 409 and error.reason == "POSITION":
                return error.items[0] if error.items else None
            raise
        return None

    async def report_backfill(self, source_id: str, profile_seq: str) -> None:
        path = f"/report/v1/sources/{_q(source_id)}/backfill"
        await self._call("PUT", path, json={"profile_seq": profile_seq})

    async def _post(self, build_id: str, route: str, body: dict[str, Any]) -> dict[str, Any]:
        path = f"/report/v1/builds/{_q(build_id)}/{route}"
        return (await self._call("POST", path, json=body)).json()

    async def _call(self, method: str, path: str, **options: Any) -> httpx.Response:
        for attempt in range(1, self._attempts + 1):
            last = attempt == self._attempts
            try:
                response = await self.http.request(method, path, **options)
            except httpx.TransportError as error:
                if last:
                    raise PlatformError(0, "UNREACHABLE", type(error).__name__, None) from error
                log.warning("%s: %s; repeating", method, type(error).__name__)
                await self._sleep(2**attempt)
                continue
            trace_id = response.headers.get("x-trace-id")
            if (response.status_code == 429 or response.status_code >= 500) and not last:
                wait = response.headers.get("retry-after", "")
                log.warning(
                    "%s: %s; repeating (trace_id %s)", method, response.status_code, trace_id
                )
                await self._sleep(int(wait) if wait.isdecimal() else 2**attempt)
                continue
            if response.status_code == 409 and _is_position(response):
                # A status report's 409 is the bare position, not an error (spec §7.3).
                raise PlatformError(409, "POSITION", "", trace_id, [response.json()])
            if response.is_error:
                raise _refused(response, trace_id)
            return response
        raise AssertionError("unreachable")


def _q(segment: str) -> str:
    return quote(segment, safe="")


def _is_position(response: httpx.Response) -> bool:
    try:
        return "error" not in response.json()
    except ValueError:
        return False
