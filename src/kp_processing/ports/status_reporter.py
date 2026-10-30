"""StatusReporter port: the sending side of the #31 round-3 status contract (#129 Admission
整合). The report fields are fixed; the HTTP wrapping is provisional until #97."""

from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol

import httpx

Stage = Literal["prepare", "parse", "enrich", "finalize"]
State = Literal["pending", "running", "succeeded", "failed"]


@dataclass(frozen=True)
class Progress:
    done: int
    total: int
    unit: str  # "pages" for parse, "items" for enrich


@dataclass(frozen=True)
class StatusReport:
    request_id: str
    attempt_id: str  # Temporal run ID
    seq: int  # per attempt, assigned by the caller, starts at 1
    stages_version: str
    stage: Stage
    state: State
    progress: Progress | None
    message: str
    method_version: str  # the adopted_version, e.g. "paper-pdf@1"
    manifest_ref: str | None
    observed_at: str  # RFC 3339 UTC
    error: dict[str, Any] | None  # AIP-193 block: domain, reason, message, ...

    def to_json(self) -> dict[str, Any]:
        """All twelve fields, nulls kept; progress as {done, total, unit} or null."""
        return asdict(self)


@dataclass(frozen=True)
class Position:
    attempt_id: str
    seq: int


@dataclass(frozen=True)
class ReportOutcome:
    delivered: bool
    position: Position | None = None  # receiver's current position, read back on a 409
    error: str | None = None  # why it was not delivered


class StatusReporter(Protocol):
    async def report(self, report: StatusReport) -> ReportOutcome:
        """Never raises: a failed report must not fail processing."""
        ...


class RecordingStatusReporter:
    """In-process fake: keeps every report in order and accepts them all."""

    def __init__(self) -> None:
        self.reports: list[StatusReport] = []

    async def report(self, report: StatusReport) -> ReportOutcome:
        raise NotImplementedError


class HttpStatusReporter:
    """Provisional HTTP wrapping, to be revisited when #97 fixes it:
    POST {base_url}/v1/requests/{request_id}/status-reports with report.to_json().
    2xx -> delivered. 409 -> not delivered; the body {"attempt_id", "seq"} is the receiver's
    current position. Anything else (other status, transport error, timeout, unreadable
    409 body) -> not delivered with an error string; nothing is raised."""

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")

    async def report(self, report: StatusReport) -> ReportOutcome:
        raise NotImplementedError
