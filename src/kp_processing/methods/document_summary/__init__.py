"""document-summary: a short summary of the whole document from the summary API, each sentence
tied to the sections that support it (v2 Q4b, Q4d, Q6). request and parse use the provisional
contract of #129 as their shape, whatever the summary API's own wire format (SummaryApi)."""

import json
import re
from typing import Any

from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.items.text import TextItem
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kp_processing.methods import DocumentItem, InvalidOutput, MethodOutput

ID = "document-summary"
VERSION = 1
SCOPE = "document"
SERVICE = "summary"
ORIGIN = "interpretation"
INPUTS = ("assembly",)

MAX_SENTENCES = 5
HEADING_LABELS = ("title", "section_header")
BODY_LABELS = ("text", "paragraph", "list_item")
MIN_WORD_LENGTH = 4  # shorter words are mostly function words
MIN_OVERLAP = 0.5


class Evidence(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    section_id: str


class Sentence(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    text: str
    evidence: list[Evidence] = Field(default_factory=list)


class Summary(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    model: str
    sentences: list[Sentence] = Field(max_length=MAX_SENTENCES)


def _words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) >= MIN_WORD_LENGTH}


def request(item: DocumentItem, inputs: list[bytes]) -> dict[str, Any]:
    """{"document_uid": item["document_uid"], "sections": [...], "max_sentences": MAX_SENTENCES}
    for inputs [assembly.json].

    Sections come from the assembly's docling document in reading order, and from nothing else
    (v2 Q6: no caption, footnote, table, picture, code, formula or enrichment output). Each
    heading (label in HEADING_LABELS) opens a section {"section_id": its self_ref, "heading":
    its text, "text": the texts of the body items (label in BODY_LABELS) after it and before the
    next heading, joined by "\\n"}. Body items before the first heading form a first section
    {"section_id": "#/body", "heading": "", "text": ...}, only when there are any.
    """
    document = DoclingDocument.model_validate(json.loads(inputs[0])["document"])
    sections: list[dict[str, str]] = []
    body: list[str] = []
    for node, _ in document.iterate_items():
        if not isinstance(node, TextItem):
            continue
        if node.label in HEADING_LABELS:
            if sections:
                sections[-1]["text"] = "\n".join(body)
            sections.append({"section_id": node.self_ref, "heading": node.text, "text": ""})
            body = []
        elif node.label in BODY_LABELS:
            if not sections:
                sections.append({"section_id": "#/body", "heading": "", "text": ""})
            body.append(node.text)
    if sections:
        sections[-1]["text"] = "\n".join(body)
    return {
        "document_uid": item["document_uid"],
        "sections": sections,
        "max_sentences": MAX_SENTENCES,
    }


def parse(item: DocumentItem, inputs: list[bytes], content: str) -> MethodOutput:
    """The output for the summary API's response body content:

        {"model": str, "sentences": [{"text": str, "evidence": [{"section_id": str}]}]}

    "evidence" may be absent; other fields are ignored. Raises InvalidOutput("EMPTY_OUTPUT")
    when content is blank or "sentences" is empty, InvalidOutput("SCHEMA_INVALID") when it is
    not that shape, a sentence's text is blank, or it has more than MAX_SENTENCES sentences.

    Each sentence's support, against the sections request(item, inputs) sends:
      provider  its evidence names at least one sent section; evidence keeps those, in order
      overlap   its evidence is absent or empty, and one section's heading and text together
                hold at least MIN_OVERLAP of the sentence's words (lowercase runs of [a-z0-9]
                of at least MIN_WORD_LENGTH characters); evidence [{"section_id"}] of the
                section holding the largest share, the first on a tie
      none      otherwise (evidence naming only sections never sent included); evidence []

    Returns outcome "success" with content {"sentences": [{"text", "evidence":
    [{"section_id"}], "support"}]} in response order, and contradictions
    ["UNSUPPORTED_SENTENCE"] when any sentence's support is none, else [].
    """
    if not content.strip():
        raise InvalidOutput("EMPTY_OUTPUT")
    try:
        summary = Summary.model_validate_json(content)
    except ValidationError as exc:
        raise InvalidOutput("SCHEMA_INVALID") from exc
    if not summary.sentences:
        raise InvalidOutput("EMPTY_OUTPUT")
    if any(not sentence.text.strip() for sentence in summary.sentences):
        raise InvalidOutput("SCHEMA_INVALID")
    sections = request(item, inputs)["sections"]
    section_ids = {section["section_id"] for section in sections}
    section_words = [
        (section["section_id"], _words(section["heading"] + "\n" + section["text"]))
        for section in sections
    ]
    sentences: list[dict[str, Any]] = []
    for sentence in summary.sentences:
        evidence = [ref.model_dump() for ref in sentence.evidence if ref.section_id in section_ids]
        support = "provider" if evidence else "none"
        if not sentence.evidence:
            words = _words(sentence.text)
            best_overlap = 0.0
            for section_id, source_words in section_words:
                overlap = len(words & source_words) / len(words) if words else 0.0
                if overlap >= MIN_OVERLAP and overlap > best_overlap:
                    best_overlap = overlap
                    evidence = [{"section_id": section_id}]
                    support = "overlap"
        sentences.append({"text": sentence.text, "evidence": evidence, "support": support})
    return MethodOutput(
        outcome="success",
        content={"sentences": sentences},
        contradictions=(
            ["UNSUPPORTED_SENTENCE"] if any(s["support"] == "none" for s in sentences) else []
        ),
    )
