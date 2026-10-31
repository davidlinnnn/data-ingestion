"""Enrichment Status rule v1 (v2 §7): never `verified`."""

from typing import Any, Literal

Status = Literal["failed", "disputed", "unverified"]


def assign(record: dict[str, Any]) -> tuple[Status, str | None]:
    """(status, status_reason) for one outcome record:

    failed      outcome "failed"; reason = the record's reason
    disputed    otherwise, when contradictions is non-empty; reason = its first entry
    unverified  otherwise; reason "NO_TEXT" for outcome "no_text", else None
    """
    if record["outcome"] == "failed":
        return "failed", record["reason"]
    if record["contradictions"]:
        return "disputed", record["contradictions"][0]
    return "unverified", "NO_TEXT" if record["outcome"] == "no_text" else None
