"""document-summary: an overview of the whole document and a summary of each Section, every
sentence checked against the Section text it rests on (v2 Q4b, Q6; #155). Sentences found
unsupported are rewritten once with the judge's reason, then dropped if still unsupported.

The package is the whole output-shaping half of the pipeline (ADR-0010): how a document becomes
Sections and chunks, the prompts and schemas, and the map, verify, repair and reduce steps. The
summary stage runs it in three Activities and supplies `ask`, which sends one chat-completions
request through the retry chain and returns parse(content), or raises when no usable answer
came back:

    sections(item, inputs) -> the sections document          (one Activity)
    chunk(document, index, ask) -> one chunk's result         (one Activity per chunk)
    overview(document, chunks, ask) -> (MethodOutput, record) (one Activity)
"""

import asyncio
import html
import json
import math
import re
from collections.abc import Awaitable, Callable
from typing import Any

from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.items.text import TextItem
from pydantic import BaseModel, ConfigDict, ValidationError

from kp_processing.methods import DocumentItem, InvalidOutput, MethodOutput

ID = "document-summary"
VERSION = 2
SCOPE = "document"
SERVICE = "summary"
ORIGIN = "interpretation"
INPUTS = ("assembly",)

HEADING_LABELS = ("title", "section_header")
BODY_LABELS = ("text", "paragraph", "list_item")
# A9: a heading equal to one of these, after normalize(), marks the reference list.
REFERENCES = {
    "references", "bibliography", "works cited", "literature cited", "references and notes",
    "參考文獻", "参考文献", "參考資料",
}  # A9  # fmt: skip
ACKNOWLEDGEMENTS = ("acknowledg", "致謝", "致谢", "誌謝")  # A10: heading prefixes
CHUNK_CHARS = 8000  # whole sections are packed up to this; a larger section is its own chunk
CHARS_PER_SECTION_SENTENCE = 1500
MAX_SECTION_SENTENCES = 8
MIN_SECTION_CHARS = 500  # a shorter section gets no sentences
CHARS_PER_OVERVIEW_SENTENCE = 8000
OVERVIEW_SENTENCES = (5, 15)
MAX_TOKENS = 8000  # per answer

Ask = Callable[[str, dict[str, Any], Callable[[str], Any]], Awaitable[Any]]


# --- sections -------------------------------------------------------------------------------


def normalize(heading: str) -> str:
    """The heading without its numbering ("3.1", "A.2", "IV"), trailing punctuation and case."""
    heading = re.sub(r"^\s*(\d+(\.\d+)*|[A-Z](\.\d+)*|[IVXLC]+)[.)]?\s+", "", heading.strip())
    return re.sub(r"[\s:：.]+$", "", heading).strip().lower()


def skip_reason(heading: str, text: str) -> str | None:
    """Why a section is not summarized (A8-A10): EMPTY, REFERENCES, ACKNOWLEDGEMENTS, or None."""
    if not text.strip():
        return "EMPTY"
    name = normalize(heading)
    if name in REFERENCES:
        return "REFERENCES"
    if name.startswith(ACKNOWLEDGEMENTS):
        return "ACKNOWLEDGEMENTS"
    return None


def section_target(chars: int) -> int:
    """Sentences for a section of chars characters (A8)."""
    if chars < MIN_SECTION_CHARS:
        return 0
    return min(MAX_SECTION_SENTENCES, math.ceil(chars / CHARS_PER_SECTION_SENTENCE))


def overview_target(chars: int) -> int:
    """Overview sentences for chars characters of summarized sections (A8)."""
    low, high = OVERVIEW_SENTENCES
    return max(low, min(high, round(chars / CHARS_PER_OVERVIEW_SENTENCE)))


def pack(sizes: list[int]) -> list[list[int]]:
    """Consecutive section indices packed into chunks of at most CHUNK_CHARS characters; a
    section is never split, so a larger one is a chunk of its own."""
    chunks: list[list[int]] = []
    size = 0
    for index, chars in enumerate(sizes):
        if not chunks or size + chars > CHUNK_CHARS:
            chunks.append([])
            size = 0
        chunks[-1].append(index)
        size += chars
    return chunks


def sections(item: DocumentItem, inputs: list[bytes]) -> dict[str, Any]:
    """The sections document for inputs [assembly.json]:

        {"title": the first heading's text, "" when there is none,
         "sections": [{"section_id", "heading", "text", "target"}],  summarized, reading order
         "skipped": [{"section_id", "heading", "chars", "reason"}],  skip_reason() not None
         "chunks": [[index into sections, ...], ...]}                pack() of the text sizes

    Sections come from the assembly's docling document in reading order, and from nothing else
    (v2 Q6: no caption, footnote, table, picture, code, formula or enrichment output). Each
    heading (label in HEADING_LABELS) opens a section {"section_id": its self_ref, "heading":
    its text, "text": the texts of the body items (label in BODY_LABELS) after it and before the
    next heading, joined by "\\n"}. Body items before the first heading form a first section
    {"section_id": "#/body", "heading": "", ...}, only when there are any. "target" is
    section_target(len(text)).
    """
    document = DoclingDocument.model_validate(json.loads(inputs[0])["document"])
    raw: list[dict[str, Any]] = []
    for node, _ in document.iterate_items():
        if not isinstance(node, TextItem):
            continue
        if node.label in HEADING_LABELS:
            raw.append({"section_id": node.self_ref, "heading": node.text, "body": []})
        elif node.label in BODY_LABELS:
            if not raw:
                raw.append({"section_id": "#/body", "heading": "", "body": []})
            raw[-1]["body"].append(node.text)
    kept, skipped = [], []
    for section in raw:
        text = "\n".join(section["body"])
        entry = {"section_id": section["section_id"], "heading": section["heading"]}
        if reason := skip_reason(section["heading"], text):
            skipped.append({**entry, "chars": len(text), "reason": reason})
        else:
            kept.append({**entry, "text": text, "target": section_target(len(text))})
    title = next((s["heading"] for s in raw if s["heading"]), "")
    chunks = pack([len(s["text"]) for s in kept])
    return {"title": title, "sections": kept, "skipped": skipped, "chunks": chunks}


# --- prompts, schemas and parsing -------------------------------------------------------------


def _schema(name: str, body: dict[str, Any]) -> dict[str, Any]:
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": body}}


def _object(**properties: Any) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}  # fmt: skip


_STRING = {"type": "string"}
_STRINGS = {"type": "array", "items": _STRING}
_INTEGER = {"type": "integer"}
MAP = _schema(
    "map", _object(sections={"type": "array", "items": _object(id=_STRING, sentences=_STRINGS)})
)
# supported before reason: with reason first the judge missed more planted errors (#164)
VERIFY = _schema("verify", _object(verdicts={"type": "array", "items": _object(
    n=_INTEGER, supported={"type": "boolean"}, reason=_STRING)}))  # fmt: skip
REPAIR = _schema("repair", _object(quotes=_STRINGS, sentence=_STRING))
REDUCE = _schema("reduce", _object(sentences={"type": "array", "items": _object(
    text=_STRING, sources={"type": "array", "items": _INTEGER})}))  # fmt: skip


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class _MapSection(_Strict):
    id: str
    sentences: list[str]


class _Map(_Strict):
    sections: list[_MapSection]


class _Verdict(_Strict):
    n: int
    supported: bool
    reason: str


class _Verify(_Strict):
    verdicts: list[_Verdict]


class _Repair(_Strict):
    quotes: list[str]
    sentence: str


class _ReduceSentence(_Strict):
    text: str
    sources: list[int]


class _Reduce(_Strict):
    sentences: list[_ReduceSentence]


def _parse[M: BaseModel](model: type[M], content: str) -> M:
    if not content.strip():
        raise InvalidOutput("EMPTY_OUTPUT")
    try:
        return model.model_validate_json(content)
    except ValidationError as exc:
        raise InvalidOutput("SCHEMA_INVALID") from exc


def _is_sentence(text: str) -> bool:
    """At least three words: letter runs, each CJK character counting as one (#164)."""
    return len(re.findall(r"[\u3400-\u9fff]|[^\W\d_]+", text)) >= 3


def _repair_parse() -> Callable[[str], _Repair]:
    """parse for one repair request: its first answer is SCHEMA_INVALID when the sentence is not
    a sentence, unless it is "" without quotes, so the retry chain sends it again once (#164)."""
    answers = 0

    def parse(content: str) -> _Repair:
        nonlocal answers
        answers += 1
        repaired = _parse(_Repair, content)
        sentence = repaired.sentence.strip()
        empty = not sentence and not any(q.strip() for q in repaired.quotes)
        if answers == 1 and not empty and not _is_sentence(sentence):
            raise InvalidOutput("SCHEMA_INVALID", "the repair is not a sentence")
        return repaired

    return parse


def _reduced(content: str) -> _Reduce:
    """The reduce answer's non-blank sentences; EMPTY_OUTPUT when there are none."""
    sentences = [s for s in _parse(_Reduce, content).sentences if s.text.strip()]
    if not sentences:
        raise InvalidOutput("EMPTY_OUTPUT")
    return _Reduce(sentences=sentences)


def _request(prompt: str, response_format: dict[str, Any]) -> dict[str, Any]:
    return {
        "messages": [{"role": "user", "content": prompt}],
        "response_format": response_format,
        "max_tokens": MAX_TOKENS,
    }


def label(index: int) -> str:
    """The id a section has in prompts: S1 for the first summarized section."""
    return f"S{index + 1}"


def _section_xml(index: int, section: dict[str, Any]) -> str:
    heading = html.escape(section["heading"], quote=True)
    return f'<section id="{label(index)}" heading="{heading}">\n{section["text"]}\n</section>'


def _sections_xml(document: dict[str, Any], indices: list[int]) -> str:
    sections = document["sections"]
    body = "\n".join(_section_xml(i, sections[i]) for i in indices)
    return f"<sections>\n{body}\n</sections>"


def _titled_sections_xml(document: dict[str, Any], indices: list[int]) -> str:
    """The sections with the paper's title, so a sentence may name what the title names."""
    return f"<paper_title>{document['title']}</paper_title>\n{_sections_xml(document, indices)}"


def map_request(document: dict[str, Any], indices: list[int]) -> dict[str, Any]:
    """Summarize the sections of indices that have a target, each in its target's sentences."""
    sections = document["sections"]
    outline = "\n".join(f"{label(i)} {s['heading']}" for i, s in enumerate(sections))
    targets = "\n".join(
        f"- {label(i)}: {sections[i]['target']} sentence(s)"
        for i in indices
        if sections[i]["target"]
    )
    prompt = (
        f"<paper_title>{document['title']}</paper_title>\n<outline>\n{outline}\n</outline>\n\n"
        f"{_sections_xml(document, indices)}\n\n"
        "Summarize each section listed below in the given number of sentences, in the language "
        "of the section. Keep each sentence to about 35 words. Each sentence must stand alone "
        "(no 'this section', no 'the authors' without context), carry the section's most "
        "important facts, and state only what the section's own text says. Use the outline only "
        f"to judge what matters; never summarize other sections.\n\n{targets}"
    )
    return _request(prompt, MAP)


def verify_request(document: dict[str, Any], indices: list[int], sentences: list[str]) -> dict:
    """Judge each sentence against the sections of indices only."""
    listing = "\n".join(f'<sentence n="{n}">{s}</sentence>' for n, s in enumerate(sentences, 1))
    prompt = (
        f"{_titled_sections_xml(document, indices)}\n\n<sentences>\n{listing}\n</sentences>\n\n"
        "For each sentence, is every claim in it supported by the sections above? Judge only "
        "against their text and the paper's title (a sentence may call the paper's method or "
        "system by the name in its title): background knowledge, plausibility and other parts "
        "of the paper do not count. Paraphrase is fine; added numbers, causes, comparisons or "
        "generalisations that the text does not state are not. Give one verdict per sentence, "
        "with its n; in reason name the unsupported part in one sentence (or say why it is "
        "supported)."
    )
    return _request(prompt, VERIFY)


def parse_verdicts(count: int, content: str) -> list[tuple[bool, str]]:
    """(supported, reason) per sentence, in sentence order; SCHEMA_INVALID unless the verdicts'
    n are exactly 1..count."""
    verdicts = _parse(_Verify, content).verdicts
    if sorted(v.n for v in verdicts) != list(range(1, count + 1)):
        raise InvalidOutput("SCHEMA_INVALID", "verdicts do not match the sentences")
    return [(v.supported, v.reason) for v in sorted(verdicts, key=lambda v: v.n)]


def repair_request(
    document: dict[str, Any], indices: list[int], sentence: str, reason: str
) -> dict[str, Any]:
    prompt = (
        f"{_titled_sections_xml(document, indices)}\n\n<sentence>{sentence}</sentence>\n"
        f"<problem>{reason}</problem>\n\n"
        "The sentence was judged not fully supported by the sections, for the problem given. "
        "First copy into quotes the passages of the sections that support any part of the "
        "sentence. Then rewrite the sentence with as few changes as possible so that every "
        "claim is supported by those quotes (or names what the title names), in the "
        "sentence's language; never add a claim. If "
        "nothing in the sections supports it, return an empty sentence."
    )
    return _request(prompt, REPAIR)


def reduce_request(document: dict[str, Any], statements: list[tuple[int, str]], target: int):
    """An overview of at most target sentences from statements [(section index, text)]."""
    sections = document["sections"]
    listing = "\n".join(
        f"[{n}] ({sections[i]['heading']}) {text}" for n, (i, text) in enumerate(statements, 1)
    )
    prompt = (
        f"<paper_title>{document['title']}</paper_title>\n<statements>\n{listing}\n"
        f"</statements>\n\nWrite an overview of the paper in at most {target} sentences, in the "
        "language of the statements, for a reader deciding whether to read it: the problem, the "
        "approach, the main results with their numbers, and limitations where stated. Use only "
        "information in the statements above. For each sentence, list in sources the numbers "
        "of the statements it draws on."
    )
    return _request(prompt, REDUCE)


# --- the steps --------------------------------------------------------------------------------


async def checked(
    document: dict[str, Any], indices: list[int], sentences: list[str], ask: Ask
) -> list[dict[str, Any]]:
    """Each sentence's fate against the sections of indices, in order: one verify call for all
    of them (D4); each unsupported one repaired once with the judge's reason and the rewrite
    verified alone. A fate is {"text"} when supported, {"text", "original", "reason"} when
    rewritten, {"text": None, "original", "reason", "rewrite", "second_reason"} when dropped
    (second_reason None, never verified, when the rewrite is "" because repair found nothing
    to keep, or is still not a sentence when sent again)."""
    if not sentences:
        return []
    verdicts = await ask(
        "verify",
        verify_request(document, indices, sentences),
        lambda content: parse_verdicts(len(sentences), content),
    )

    async def fate(sentence: str, supported: bool, reason: str) -> dict[str, Any]:
        if supported:
            return {"text": sentence}
        repaired = await ask(
            "repair",
            repair_request(document, indices, sentence, reason),
            _repair_parse(),
        )
        rewrite = repaired.sentence.strip()
        dropped = {"text": None, "original": sentence, "reason": reason, "rewrite": rewrite}
        if not _is_sentence(rewrite):
            return {**dropped, "second_reason": None}
        ((ok, second_reason),) = await ask(
            "verify",
            verify_request(document, indices, [rewrite]),
            lambda content: parse_verdicts(1, content),
        )
        if ok:
            return {"text": rewrite, "original": sentence, "reason": reason}
        return {**dropped, "second_reason": second_reason}

    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(fate(s, *v)) for s, v in zip(sentences, verdicts, strict=True)]
    return [task.result() for task in tasks]


async def chunk(document: dict[str, Any], index: int, ask: Ask) -> dict[str, Any]:
    """The result of chunk index: {"sections": [{"index", "fates"}]} for each of its sections,
    in order. One map call for the sections with a target (none when no section has one): each
    section keeps at most its target of the non-blank sentences the map gave it, then checked()
    against that section alone (D4). A section the map did not answer for has no fates."""
    indices = document["chunks"][index]
    targets = {label(i): i for i in indices if document["sections"][i]["target"]}
    given: dict[int, list[str]] = {}
    if targets:
        answer = await ask(
            "map", map_request(document, indices), lambda content: _parse(_Map, content)
        )
        for entry in answer.sections:
            if (i := targets.get(entry.id)) is not None and i not in given:
                target = document["sections"][i]["target"]
                given[i] = [s.strip() for s in entry.sentences if s.strip()][:target]
    async with asyncio.TaskGroup() as group:
        tasks = {
            i: group.create_task(checked(document, [i], given.get(i, []), ask)) for i in indices
        }
    return {"sections": [{"index": i, "fates": tasks[i].result()} for i in indices]}


async def overview(
    document: dict[str, Any], chunks: list[dict[str, Any]], ask: Ask
) -> tuple[MethodOutput, dict[str, Any]]:
    """The summary from every chunk's result, in chunk order, and the processing record.

    The statements are the kept sentences of every section, in reading order. One reduce call
    asks for an overview of at most overview_target(summarized characters) sentences; each
    keeps the sections of the statements its sources name (numbers outside the list ignored),
    in reading order, at most that many sentences; one without such a source is dropped
    (reason NO_SOURCES, never verified), the others checked() against their sections.

    Output:
      no_text  no summarized section has a target (none, or all too short); content ""; no
               call
      failed   NO_SUPPORTED_SENTENCE when every section sentence was dropped, so there is no
               statement (no call); a reduce answer without a sentence is EMPTY_OUTPUT
      success  content {"overview": [{"text", "evidence": [{"section_id"}]}],
                        "sections": [{"section_id", "heading", "sentences": [{"text"}]}]}
               with every summarized section in reading order (sentences [] when it has none),
               and signals {"rewritten", "dropped"}: counts over all sentences
    The record: {"skipped": the document's, "sections": [{"section_id", "heading", "chars",
    "target", "fates"}], "overview": {"target", "fates"}} (overview fates also carry
    "evidence"); the caller adds what it measured.
    """
    sections = document["sections"]
    fates = {s["index"]: s["fates"] for result in chunks for s in result["sections"]}
    record: dict[str, Any] = {
        "skipped": document["skipped"],
        "sections": [
            {
                "section_id": s["section_id"],
                "heading": s["heading"],
                "chars": len(s["text"]),
                "target": s["target"],
                "fates": fates.get(i, []),
            }
            for i, s in enumerate(sections)
        ],  # fmt: skip
        "overview": {"target": 0, "fates": []},
    }
    if not any(s["target"] for s in sections):
        return MethodOutput(outcome="no_text", content=""), record
    statements = [
        (i, f["text"]) for i in range(len(sections)) for f in fates.get(i, []) if f["text"]
    ]
    if not statements:
        return MethodOutput(outcome="failed", reason="NO_SUPPORTED_SENTENCE"), record
    target = overview_target(sum(len(s["text"]) for s in sections))
    record["overview"]["target"] = target
    reduced = await ask(
        "reduce",
        reduce_request(document, statements, target),
        _reduced,
    )

    async def fate(sentence: _ReduceSentence) -> dict[str, Any]:
        cited = sorted(
            {statements[n - 1][0] for n in sentence.sources if 1 <= n <= len(statements)}
        )
        evidence = [{"section_id": sections[i]["section_id"]} for i in cited]
        if not cited:
            return {"text": None, "original": sentence.text, "reason": "NO_SOURCES",
                    "evidence": evidence}  # fmt: skip
        (result,) = await checked(document, cited, [sentence.text], ask)
        return {**result, "evidence": evidence}

    texts = reduced.sentences[:target]
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(fate(sentence)) for sentence in texts]
    record["overview"]["fates"] = [task.result() for task in tasks]
    kept = [f for f in record["overview"]["fates"] if f["text"]]
    every = [f for s in record["sections"] for f in s["fates"]] + record["overview"]["fates"]
    content = {
        "overview": [{"text": f["text"], "evidence": f["evidence"]} for f in kept],
        "sections": [
            {
                "section_id": s["section_id"],
                "heading": s["heading"],
                "sentences": [{"text": f["text"]} for f in s["fates"] if f["text"]],
            }
            for s in record["sections"]
        ],  # fmt: skip
    }
    signals = {
        "rewritten": sum(bool(f["text"]) and "original" in f for f in every),
        "dropped": sum(not f["text"] for f in every),
    }
    return MethodOutput(outcome="success", content=content, signals=signals), record
