"""Enrichment Method packages. Each declares ID and VERSION; everything that shapes a
method's output (code, prompts, schemas, constants) lives inside its package, because
the package's source digest enters the reuse key (ADR-0010). The package name is the
method ID with dashes as underscores.

An item-scope method package also declares:

    TARGET   (collection, label): its enrichment targets are the docling document's nodes in
             that collection ("pictures", "texts", "tables"), only those with that label
             unless label is None
    INPUTS   the kinds of its inputs, in order, from "source" (the source PDF), "assembly"
             (assembly.json), "picture_image" (the target's registered picture image),
             "page_image" (the image of the target's page)
    ORIGIN   "reconstruction" or "interpretation"
    run(item: InventoryItem, inputs: list[bytes]) -> MethodOutput, inputs in INPUTS order

A method that calls the VLM (kp_processing.stages.enrich_vlm.METHODS) declares instead of run:

    request(item, inputs) -> dict | MethodOutput
             the chat-completions request body without "model": messages carrying the images
             as data URLs, and response_format {"type": "json_schema", "json_schema": {"name",
             "strict": True, "schema"}} with the package's schema; or the MethodOutput itself
             when no request is needed (code with a text layer)
    parse(item, inputs, content: str) -> MethodOutput
             the output for the response message's content; raises InvalidOutput when the
             content is empty or does not validate against the schema
    FIELDS   (optional) names of output fields that are each their own enrichment (v2 Q3c):
             the MethodOutput of parse then sets fields, one MethodOutput per name
"""

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict


class InventoryItem(TypedDict):
    item_id: str  # "<method id>:<target_ref>"
    method: str
    target_ref: str  # docling self_ref, e.g. "#/pictures/0"
    page: int  # the target's first provenance entry
    bbox: dict[str, Any]  # its docling bbox: l, t, r, b, coord_origin
    input_refs: list[dict[str, str]]  # [{"ref", "sha256"}] in the method's INPUTS order


InvalidReason = Literal["EMPTY_OUTPUT", "SCHEMA_INVALID"]


class InvalidOutput(Exception):
    """A model answer that is empty or breaks the schema: retried once, then a content failure
    (#93 §3.4)."""

    def __init__(self, reason: InvalidReason, message: str = "") -> None:
        super().__init__(f"{reason}: {message}" if message else reason)
        self.reason: InvalidReason = reason


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
    # Per FIELDS name, that field's own outcome, reason, content, signals and contradictions.
    fields: dict[str, "MethodOutput"] = field(default_factory=dict)
