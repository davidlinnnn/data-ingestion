"""Associate saved model paragraphs with exact provider items; never mutate provider input."""

import collections
import hashlib
import json
from pathlib import Path
import re
import sys

from docling_core.transforms.serializer.base import BaseTextSerializer
from docling_core.transforms.serializer.common import create_ser_result
from docling_core.transforms.serializer.markdown import MarkdownDocSerializer, MarkdownTextSerializer
from docling_core.types.doc import DoclingDocument
from docling_core.types.doc.tokens import DocumentToken

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INPUTS = HERE.parent / "inputs"
RUNS = HERE.parent / "vlm/paragraph/runs"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def check_inputs():
    for name, expected in read(INPUTS / "artifact-sha256.json").items():
        if sha(INPUTS / name) != expected:
            raise ValueError(f"stale input: {name}")
    manifest = read(INPUTS / "input-manifest.json")
    registry = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
    if sha(registry) != manifest["registry_sha256"]:
        raise ValueError("stale registry")
    for source in manifest["sources"]:
        if sha(REPO / source["source"]["path"]) != source["source"]["sha256"]:
            raise ValueError("stale source PDF")
        for snapshot in source["snapshots"]:
            if sha(REPO / snapshot["original_path"]) != snapshot["sha256"]:
                raise ValueError("original provider payload changed")
    return manifest


def make_plan(manifest):
    rows = []
    for source in manifest["sources"]:
        raw = read(REPO / source["document_path"])
        document = DoclingDocument.model_validate(raw)
        order = [item.self_ref for item, _ in document.iterate_items(traverse_pictures=True)]
        stock_order = {item.self_ref for item, _ in document.iterate_items()}
        by_ref = {item["self_ref"]: item for key in ("texts", "pictures", "tables", "groups") for item in raw[key]}
        for candidate in [c for c in manifest["candidates"] if c["source"] == source["name"]]:
            ref = candidate["item_ref"]
            pos = order.index(ref)
            neighbors = [order[i] for i in (pos-1, pos+1) if 0 <= i < len(order)]
            item = by_ref[ref]
            gaps, cursor = [], 0
            for fragment in candidate["fragments"]:
                start, end = fragment["provider_provenance"]["charspan"]
                if start > cursor:
                    gaps.append({"provider_charspan": [cursor, start], "text": item["text"][cursor:start]})
                cursor = end
            rows.append({"candidate_id": candidate["id"], "source": source["name"],
                "item_ref": ref, "document_path": source["document_path"],
                "document_sha256": source["document_sha256"], "canonical_document_sha256": digest(raw),
                "item_sha256": digest(item), "replacement_charspan": candidate["replacement_charspan"],
                "item_reachable_in_stock_markdown_traversal": ref in stock_order,
                "provider_text_sha256": candidate["provider_text_sha256"],
                "neighbors": [{"item_ref": r, "item_sha256": digest(by_ref[r]), "item": by_ref[r]} for r in neighbors],
                "provider_item": item, "source_association": candidate["fragments"], "provider_join_gaps": gaps})
    return {"format": "g2-inline-reinsertion-plan-v1", "input_manifest_sha256": sha(INPUTS / "input-manifest.json"),
        "scope": "Whole declared items only; original provider remains immutable; association does not establish semantic transcription accuracy",
        "rows": rows}


def strict_doctags(text):
    stripped = text.strip()
    if not stripped.startswith("<doctag>") or not stripped.endswith("</doctag>"):
        raise ValueError("incomplete DocTags document wrapper")
    stack = []
    allowed = {"doctag", "text", "formula", "code", "inline"}
    language_tokens = {token[1:-1] for token in DocumentToken.get_special_tokens() if token.startswith("<_")}
    for closing, tag in re.findall(r"<(/?)([A-Za-z_][^<>]*)>", stripped):
        if re.fullmatch(r"loc_\d+", tag) and not closing:
            if not 0 <= int(tag[4:]) <= 500:
                raise ValueError("out-of-range location token")
            continue
        if tag in language_tokens and not closing:
            continue
        if tag not in allowed:
            raise ValueError(f"unsupported DocTags token: {tag}")
        if closing:
            if not stack or stack.pop() != tag:
                raise ValueError("unbalanced DocTags structure")
        else:
            stack.append(tag)
    if stack:
        raise ValueError("unclosed DocTags structure")


def inline_spans(markdown):
    spans, pos = [], 0
    while pos < len(markdown):
        if markdown[pos] == "\\" and markdown[pos:pos+2] not in ("\\(", "\\["):
            pos += 2
            continue
        opening = next((s for s in ("```", "$$", "\\[", "\\(", "`", "$") if markdown.startswith(s, pos)), None)
        if opening is None:
            pos += 1
            continue
        closing = {"\\(": "\\)", "\\[": "\\]"}.get(opening, opening)
        end = markdown.find(closing, pos+len(opening))
        while end >= 0 and end > 0 and markdown[end-1] == "\\":
            end = markdown.find(closing, end+len(closing))
        if end < 0:
            raise ValueError(f"unclosed explicit inline delimiter: {opening}")
        kind = ("code_block" if opening == "```" else "code_inline" if opening == "`" else
                "math_display" if opening in ("$$", "\\[") else "math_inline")
        stop = end+len(closing)
        spans.append({"kind": kind, "markdown_charspan": [pos, stop], "raw_markup": markdown[pos:stop]})
        pos = stop
    return spans


def check_shape(candidate, parsed):
    roots = parsed["body"]["children"]
    if len(roots) != 1:
        raise ValueError("one provider paragraph/item requires exactly one compatible model root block; all raw blocks retained for review")
    collection, index = roots[0]["$ref"][2:].split("/")
    root = parsed[collection][int(index)]
    before_words = re.findall(r"[A-Za-z][A-Za-z0-9_]*", candidate["provider_text"].lower())
    prose = " ".join(t["text"] for t in parsed["texts"] if t["label"] != "formula")
    prose = re.sub(r"\$\$.*?\$\$|\$(?:\\.|[^$])*\$|\\\(.*?\\\)|\\\[.*?\\\]", " ", prose, flags=re.DOTALL)
    after_words = re.findall(r"[A-Za-z][A-Za-z0-9_]*", prose.lower())
    before = collections.Counter(tuple(before_words[i:i+5]) for i in range(len(before_words)-4))
    after = collections.Counter(tuple(after_words[i:i+5]) for i in range(len(after_words)-4))
    repeated = [" ".join(words) for words, count in after.items() if count > 1 and count > before[words]]
    if repeated:
        raise ValueError("model introduced repeated five-word runs: " + "; ".join(repeated[:3]))
    allowed = {"text", "inline"} if candidate["provider_label"] == "text" else {candidate["provider_label"]}
    if root["label"] not in allowed:
        raise ValueError("model root block is incompatible with provider paragraph/item role")


def validate_batch(raw_document, plan_rows, proposals):
    by_ref = {t["self_ref"]: t for t in raw_document["texts"]}
    allowed = {r["candidate_id"]: r for r in plan_rows}
    seen = set()
    for proposal in proposals:
        key = proposal["candidate_id"]
        if key in seen:
            raise ValueError("duplicate candidate item")
        seen.add(key)
        if key not in allowed:
            raise ValueError("unknown candidate")
        row = allowed[key]
        if proposal["item_ref"] != row["item_ref"] or proposal["item_ref"] not in by_ref:
            raise ValueError("unknown or mismatched provider reference")
        if digest(raw_document) != row["canonical_document_sha256"]:
            raise ValueError("stale document or dropped content outside scope")
        item = by_ref[row["item_ref"]]
        if digest(item) != row["item_sha256"] or proposal["provider_text_sha256"] != row["provider_text_sha256"]:
            raise ValueError("stale provider item")
        if proposal["replacement_charspan"] != row["replacement_charspan"] or row["replacement_charspan"] != [0, len(item["text"])]:
            raise ValueError("replacement must cover exactly the declared complete item")
        for neighbor in row["neighbors"]:
            collection, index = neighbor["item_ref"][2:].split("/")
            if digest(raw_document[collection][int(index)]) != neighbor["item_sha256"]:
                raise ValueError("changed neighbor")


class SubstitutionSerializer(BaseTextSerializer):
    def __init__(self, replacements):
        self.replacements = replacements
        self.seen = []

    def serialize(self, *, item, doc_serializer, doc, **kwargs):
        if item.self_ref in self.replacements:
            self.seen.append(item.self_ref)
            return create_ser_result(text=self.replacements[item.self_ref], span_source=item)
        return MarkdownTextSerializer().serialize(item=item, doc_serializer=doc_serializer, doc=doc, **kwargs)


def render(document, proposals):
    markers = {p["item_ref"]: "INLINEOUTPUT"+hashlib.sha256(p["candidate_id"].encode()).hexdigest() for p in proposals}
    serializer = SubstitutionSerializer(markers)
    template = MarkdownDocSerializer(doc=document, text_serializer=serializer).serialize().text
    if collections.Counter(serializer.seen) != collections.Counter(markers.keys()):
        raise ValueError("selected provider items were dropped or serialized more than once")
    replacements = {markers[p["item_ref"]]: p for p in proposals}
    for marker in replacements:
        if template.count(marker) != 1:
            raise ValueError("nonunique reinsertion marker")
    matches = sorted((template.index(m), m) for m in replacements)
    result, cursor, ranges = "", 0, {}
    for offset, marker in matches:
        result += template[cursor:offset]
        proposal = replacements[marker]
        start = len(result)
        result += proposal["markdown"]
        ranges[proposal["candidate_id"]] = [start, len(result)]
        cursor = offset+len(marker)
    result += template[cursor:]
    if any(marker in result for marker in replacements):
        raise ValueError("reinsertion marker leaked")
    return result, ranges


def load_proposal(candidate, variant):
    folder = RUNS / candidate["id"]
    result = {"candidate_id": candidate["id"], "item_ref": candidate["item_ref"],
        "provider_text_sha256": candidate["provider_text_sha256"],
        "replacement_charspan": candidate["replacement_charspan"]}
    try:
        if read(folder / "source-input.json") != candidate:
            raise ValueError("model job sidecar does not match frozen candidate")
        generation = read(folder / "generation.json")
        if not generation["last_token_is_eos"] or generation["at_token_limit"]:
            raise ValueError("model generation is truncated or lacks terminal EOS")
        textfile, parserfolder = (("engine-output.txt", "official-parser-component") if variant == "component"
                                 else ("token-aware-decode.txt", "token-aware-parser-candidate"))
        raw_path = folder / textfile
        parsed_path = folder / parserfolder / "document.json"
        markdown_path = folder / parserfolder / "document.md"
        parsed = read(parsed_path)
        markdown = markdown_path.read_text()
        result.update(raw_output_path=str(raw_path.relative_to(REPO)), raw_output_sha256=sha(raw_path),
            parsed_document_path=str(parsed_path.relative_to(REPO)), parsed_document_sha256=sha(parsed_path),
            markdown=markdown, parsed_structure=parsed["texts"])
        strict_doctags(raw_path.read_text())
        parser = read(folder / parserfolder / "parser.json")
        if parser["status"] != "completed":
            raise ValueError("official DocTags parser did not complete")
        if parsed["pictures"] or parsed["tables"] or not parsed["texts"]:
            raise ValueError("paragraph parse contains unsupported nontext structure or no text")
        if any(t["label"] not in {"text", "code", "formula"} for t in parsed["texts"]):
            raise ValueError("paragraph parse changes block role")
        if not markdown.strip():
            raise ValueError("empty parsed Markdown")
        check_shape(candidate, parsed)
        result.update(status="structurally_applied_semantic_quality_unverified", markdown=markdown,
            inline_spans=inline_spans(markdown), raw_output_path=str(raw_path.relative_to(REPO)),
            raw_output_sha256=sha(raw_path), parsed_document_path=str(parsed_path.relative_to(REPO)),
            parsed_document_sha256=sha(parsed_path), parsed_structure=parsed["texts"])
    except (ValueError, KeyError, FileNotFoundError) as error:
        result.update(status="not_applied", reason=str(error))
    return result


def main():
    manifest = check_inputs()
    plan = make_plan(manifest)
    save(HERE / "plan.json", plan)
    for variant in ("component", "token-aware"):
        out = HERE / variant
        out.mkdir(exist_ok=False)
        proposals = [load_proposal(c, variant) for c in manifest["candidates"]]
        for proposal in proposals:
            row = next(r for r in plan["rows"] if r["candidate_id"] == proposal["candidate_id"])
            if proposal["status"] != "not_applied" and not row["item_reachable_in_stock_markdown_traversal"]:
                proposal.update(status="not_applied", reason="provider item is a hidden picture child in stock Markdown traversal; no outer-picture rewrite attempted")
        for source in manifest["sources"]:
            folder = out / source["name"]
            folder.mkdir()
            raw = read(REPO / source["document_path"])
            before = digest(raw)
            document = DoclingDocument.model_validate(raw)
            source_rows = [r for r in plan["rows"] if r["source"] == source["name"]]
            ids = {r["candidate_id"] for r in source_rows}
            source_proposals = [p for p in proposals if p["candidate_id"] in ids]
            applied = [p for p in source_proposals if p["status"] != "not_applied"]
            validate_batch(raw, source_rows, applied)
            baseline_markdown = document.export_to_markdown()
            default_markdown, _ = render(document, [])
            assert baseline_markdown == default_markdown
            markdown, ranges = render(document, applied)
            assert digest(raw) == before
            (folder / "baseline.md").write_text(baseline_markdown)
            (folder / "candidate.md").write_text(markdown)
            association = []
            for proposal in source_proposals:
                row = next(r for r in source_rows if r["candidate_id"] == proposal["candidate_id"])
                association.append({**proposal, "main_markdown_charspan": ranges.get(proposal["candidate_id"]),
                    "source_association": row["source_association"], "provider_join_gaps": row["provider_join_gaps"],
                    "neighbor_checks": [{"item_ref": n["item_ref"], "before_sha256": n["item_sha256"],
                        "after_sha256": n["item_sha256"], "unchanged": True} for n in row["neighbors"]],
                    "source_precision": "Provider paragraph/page-fragment boxes; inline spans are inferred output positions, not glyph-measured source locations"})
            save(folder / "inline-structure.json", {"format": "g2-inline-supplemental-structure-v1",
                "variant": variant, "provider_document_path": source["document_path"],
                "provider_document_sha256": source["document_sha256"], "provider_unchanged": True,
                "all_provider_refs_preserved": True, "outside_scope_content_unchanged": True,
                "association_is_not_semantic_acceptance": True, "candidates": association})
        save(out / "summary.json", {"variant": variant, "candidate_count": len(proposals),
            "status_counts": dict(collections.Counter(p["status"] for p in proposals)),
            "outcomes": [{k: v for k, v in p.items() if k in {"candidate_id", "status", "reason"}} for p in proposals]})
    check_inputs()
    print("Both reinsertion variants completed; provider inputs unchanged.")


def selfcheck():
    from docling_core.types.doc import DocItemLabel
    document = DoclingDocument(name="selfcheck")
    document.add_text(label=DocItemLabel.TEXT, text="alpha")
    document.add_text(label=DocItemLabel.TEXT, text="neighbor")
    rendered, ranges = render(document, [{"candidate_id": "example", "item_ref": "#/texts/0", "markdown": "replacement"}])
    assert rendered == "replacement\n\nneighbor" and ranges == {"example": [0, 11]}
    assert document.texts[0].text == "alpha"
    raw = {"texts": [{"self_ref": "#/texts/0", "text": "alpha"}, {"self_ref": "#/texts/1", "text": "neighbor"}]}
    row = {"candidate_id": "example", "item_ref": "#/texts/0", "canonical_document_sha256": digest(raw),
        "item_sha256": digest(raw["texts"][0]), "replacement_charspan": [0, 5], "provider_text_sha256": "expected", "neighbors": []}
    valid = {"candidate_id": "example", "item_ref": "#/texts/0", "replacement_charspan": [0, 5], "provider_text_sha256": "expected"}
    validate_batch(raw, [row], [valid])
    failures = {}
    for name, candidate_doc, proposals in [
        ("stalehash", raw, [{**valid, "provider_text_sha256": "stale"}]),
        ("duplicateitem", raw, [valid, valid]),
        ("unknownref", raw, [{**valid, "item_ref": "#/texts/99"}]),
        ("dropoutside_scope", {"texts": raw["texts"][:1]}, [valid]),
        ("partialitem", raw, [{**valid, "replacement_charspan": [1, 5]}]),
    ]:
        try:
            validate_batch(candidate_doc, [row], proposals)
        except ValueError as error:
            failures[name] = str(error)
        else:
            raise AssertionError(f"negative control was accepted: {name}")
    strict_doctags("<doctag><text><loc_1>plain</text></doctag>")
    for malformed in ("<doctag><text>x</text></doctag", "<doctag><unknown>x</unknown></doctag>"):
        try:
            strict_doctags(malformed)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed/unsupported DocTags were accepted")
    assert [s["kind"] for s in inline_spans("plain $z$ and `value`.")] == ["math_inline", "code_inline"]
    example = {"provider_label": "text", "provider_text": "one two three four five six"}
    parsed = {"body": {"children": [{"$ref": "#/texts/0"}]},
        "texts": [{"label": "text", "text": example["provider_text"]}]}
    check_shape(example, parsed)
    for name, bad in [("multiple_root_blocks", {**parsed, "body": {"children": [{"$ref": "#/texts/0"}]*2}}),
                      ("introduced_repeated_prose", {**parsed, "texts": [{"label": "text", "text": (example["provider_text"]+" ")*2}]})]:
        try:
            check_shape(example, bad)
        except ValueError as error:
            failures[name] = str(error)
        else:
            raise AssertionError(f"shape/duplication negative was accepted: {name}")
    try:
        inline_spans("unclosed $z")
    except ValueError:
        pass
    else:
        raise AssertionError("unbalanced inline delimiter was accepted")
    save(HERE / "selfcheck.json", {"passed": True, "negative_controls": failures,
        "malformed_and_unsupported_doctags_rejected": True, "explicit_inline_delimiters_checked": True})
    print("Reinsertion self-check passed.")


if __name__ == "__main__":
    selfcheck() if sys.argv[1:] == ["--selfcheck"] else main()
