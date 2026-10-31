"""Enrichment Method packages. Each declares ID and VERSION; everything that shapes a
method's output (code, prompts, schemas, constants) lives inside its package, because
the package's source digest enters the reuse key (ADR-0010). The package name is the
method ID with dashes as underscores."""

from dataclasses import dataclass, field
from typing import Any, Literal


class MethodUnavailable(Exception):
    """The method cannot run at all on this worker (missing or unloadable model): a
    configuration error that fails the document, never an item outcome."""


@dataclass(frozen=True)
class MethodOutput:
    """What an item-scope method returns for one inventory item. A content failure is an
    outcome, not an exception: outcome "failed" with an UPPER_SNAKE_CASE reason."""

    outcome: Literal["success", "no_text", "failed"]
    reason: str | None = None  # set exactly when outcome is "failed"
    content: Any = None  # JSON value; "" for no_text, None for failed
    files: dict[str, bytes] = field(default_factory=dict)  # registered beside the outcome record
    evidence: list[str] = field(default_factory=list)  # names in files
    provider_artifact: str | None = None  # name in files: the raw model or library output
    signals: dict[str, Any] = field(default_factory=dict)  # weak signals; never change status
    contradictions: list[str] = field(default_factory=list)  # strong signals contradicting output
