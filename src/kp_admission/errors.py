"""The AIP-193 errors of the platform API (admission spec §4, §12)."""

from dataclasses import dataclass
from typing import Any, Literal

ErrorStatus = Literal[
    "INVALID_ARGUMENT",
    "UNAUTHENTICATED",
    "PERMISSION_DENIED",
    "NOT_FOUND",
    "FAILED_PRECONDITION",
    "RESOURCE_EXHAUSTED",
    "UNAVAILABLE",
]


@dataclass
class Refused(Exception):
    """A /v1/ call answered with an AIP-193 error. `retry_after` overrides the Retry-After of a
    503 and gives a 429 one; `items` lists every item's outcome (ALL_ITEMS_REJECTED)."""

    code: int
    status: ErrorStatus
    reason: str
    message: str
    retry_after: int | None = None
    items: list[dict[str, Any]] | None = None
