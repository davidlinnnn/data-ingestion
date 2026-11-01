"""document-summary: a short summary of the whole document from the summary API, each sentence
tied to the sections that support it (v2 Q4b, Q4d, Q6). The request and response follow the
provisional contract of #129; when the real contract arrives, only this package and the
SummaryApi adapter change."""

from typing import Any

from kp_processing.methods import DocumentItem, MethodOutput

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
    raise NotImplementedError


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
    raise NotImplementedError
