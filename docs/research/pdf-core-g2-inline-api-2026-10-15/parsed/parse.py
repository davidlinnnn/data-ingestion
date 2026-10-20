"""Validate the explicit API segment contract and render it without semantic repair."""

import copy
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INPUTS = HERE.parent / "inputs"
API = HERE.parent / "api"
BLOCKS = {"paragraph", "heading", "code", "formula", "caption", "footnote", "list_item", "other"}
SEGMENTS = {"text", "math", "code", "unknown"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON constant: "+value)))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def validate(data, dimensions):
    if not isinstance(data, dict) or set(data) != {"blocks", "uncertainties"}:
        raise ValueError("root must contain exactly blocks and uncertainties")
    if not isinstance(data["uncertainties"], list) or any(not isinstance(v, str) for v in data["uncertainties"]):
        raise ValueError("uncertainties must be strings")
    if not isinstance(data["blocks"], list) or not data["blocks"]:
        raise ValueError("blocks must be a nonempty array")
    width, height = dimensions
    for block in data["blocks"]:
        if not isinstance(block, dict) or set(block) != {"kind", "bbox", "segments", "code_language"} or block["kind"] not in BLOCKS:
            raise ValueError("invalid block fields or kind")
        box = block["bbox"]
        if not isinstance(box, list) or len(box) != 4 or any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in box):
            raise ValueError("bbox must have four finite numbers")
        left, top, right, bottom = box
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError("bbox outside supplied image or empty")
        language = block["code_language"]
        if language is not None and (not isinstance(language, str) or not re.fullmatch(r"[A-Za-z0-9_+.#-]*", language)):
            raise ValueError("code language cannot safely label a Markdown fence")
        if not isinstance(block["segments"], list) or not block["segments"]:
            raise ValueError("segments must be a nonempty array")
        for segment in block["segments"]:
            if not isinstance(segment, dict) or set(segment) != {"kind", "text"} or segment["kind"] not in SEGMENTS:
                raise ValueError("invalid segment fields or type")
            text = segment["text"]
            if text is not None and not isinstance(text, str):
                raise ValueError("segment text must be string or null")
            if segment["kind"] == "math" and text is not None:
                if text.startswith(("$", "\\(", "\\[")) or text.endswith(("$", "\\)", "\\]")) or "```" in text:
                    raise ValueError("math segment has forbidden outer delimiters or a fence")
            if block["kind"] in {"code", "formula"} and segment["kind"] not in ({"code", "unknown"} if block["kind"] == "code" else {"math", "unknown"}):
                raise ValueError("standalone code/formula block has incompatible typed segments")


def text_markup(text):
    return re.sub(r"([\\`*_{}\[\]])", r"\\\1", html.escape(text, quote=False))


def code_fence(text):
    return "`"*max(3, max((len(run) for run in re.findall(r"`+", text)), default=0)+1)


def segment_markup(segment, block_kind):
    text = segment["text"]
    if text is None or segment["kind"] == "unknown":
        return "[unknown source span]"
    if block_kind in {"code", "formula"}:
        return text
    if segment["kind"] == "text":
        return text_markup(text)
    if segment["kind"] == "math":
        return "$"+text+"$"
    delimiter = "`"*max(1, max((len(run) for run in re.findall(r"`+", text)), default=0)+1)
    pad = " " if text.startswith(("`", " ")) or text.endswith(("`", " ")) else ""
    return delimiter+pad+text+pad+delimiter


def render(data):
    result, mapped = "", []
    for block_index, block in enumerate(data["blocks"]):
        if result:
            result += "\n\n"
        start = len(result)
        pieces = [segment_markup(s, block["kind"]) for s in block["segments"]]
        combined = "".join(pieces)
        if block["kind"] == "code":
            fence = code_fence(combined)
            prefix, suffix = fence+(block["code_language"] or "")+"\n", ("" if combined.endswith("\n") else "\n")+fence
        elif block["kind"] == "formula":
            prefix, suffix = "$$\n", "\n$$"
        else:
            prefix, suffix = ("## " if block["kind"] == "heading" else "- " if block["kind"] == "list_item" else ""), ""
        result += prefix
        segments = []
        for segment_index, (segment, markup) in enumerate(zip(block["segments"], pieces, strict=True)):
            left = len(result)
            result += markup
            segments.append({"segment_index": segment_index, "kind": segment["kind"], "raw_text": segment["text"],
                "markdown_charspan": [left, len(result)], "rendered_markup": markup,
                "source_precision": "Model segment association within a source block; no measured source glyph box"})
        result += suffix
        mapped.append({"block_index": block_index, "kind": block["kind"], "model_bbox_image_pixels": block["bbox"],
            "bbox_precision": "Model-predicted supplied-image block bounds; not source-measured glyph coordinates",
            "code_language": block["code_language"], "markdown_charspan": [start, len(result)], "segments": segments})
    return result, mapped


def parse_all():
    manifest = read(INPUTS / "input-manifest.json")
    outcomes = []
    for row in manifest["inputs"]:
        folder = HERE / row["id"]
        folder.mkdir(exist_ok=False)
        output = API / row["id"] / "output.json"
        record = {"input_id": row["id"], "phase": row["phase"], "image_path": row["image_path"],
            "image_sha256": row["image_sha256"], "api_output_path": str(output.relative_to(REPO))}
        try:
            if sha(REPO / row["image_path"]) != row["image_sha256"]:
                raise ValueError("input image changed")
            record["api_output_sha256"] = sha(output)
            data = read(output)
            validate(data, row["image_pixels_wh"])
            markdown, mapped = render(data)
            assert data == read(output)
            unknown = any(s["kind"] == "unknown" or s["text"] is None for b in data["blocks"] for s in b["segments"])
            save(folder / "original-blocks.json", data)
            (folder / "document.md").write_text(markdown)
            record.update(status="parsed", eligible_for_reinsertion=not unknown,
                eligibility_limit="Unknown/null segments abstain; uncertainties remain visible and semantic quality is independently reviewed",
                uncertainties=data["uncertainties"], block_count=len(mapped), blocks=mapped,
                input_source_metadata=row, document_markdown_sha256=sha(folder / "document.md"))
            save(folder / "render-map.json", record)
        except (ValueError, KeyError, TypeError, FileNotFoundError) as error:
            record.update(status="parse_failed", reason=str(error))
            save(folder / "failure.json", record)
        outcomes.append({k: v for k, v in record.items() if k in {"input_id", "phase", "status", "reason", "eligible_for_reinsertion"}})
    save(HERE / "summary.json", {"scope": "Offline contract validation and Markdown rendering; no Docling Core/provider claim or semantic correction",
        "parser_sha256": sha(Path(__file__)), "input_manifest_sha256": sha(INPUTS / "input-manifest.json"), "outcomes": outcomes})
    print("Saved offline parsing outcomes for all22 inputs; failures remain explicit.")


def selfcheck():
    example = {"blocks": [{"kind": "paragraph", "bbox": [0, 0, 100, 100], "code_language": None,
        "segments": [{"kind": "text", "text": "Alpha "}, {"kind": "math", "text": "z^{2}"},
                     {"kind": "text", "text": " and "}, {"kind": "code", "text": "items[k]"}]}], "uncertainties": []}
    validate(example, [100, 100])
    markdown, mapped = render(example)
    assert markdown == "Alpha $z^{2}$ and `items[k]`"
    for segment in mapped[0]["segments"]:
        left, right = segment["markdown_charspan"]
        assert markdown[left:right] == segment["rendered_markup"]
    rejected = []
    for name in ("bbox", "segment_type", "math_fence", "extra_field", "nonfinite"):
        bad = copy.deepcopy(example)
        if name == "bbox":
            bad["blocks"][0]["bbox"][2] = 101
        elif name == "segment_type":
            bad["blocks"][0]["segments"][0]["kind"] = "invented"
        elif name == "math_fence":
            bad["blocks"][0]["segments"][1]["text"] = "$z$"
        elif name == "extra_field":
            bad["unexpected"] = "not allowed"
        else:
            bad["blocks"][0]["bbox"][0] = float("nan")
        try:
            validate(bad, [100, 100])
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(name+" was accepted")
    unknown = copy.deepcopy(example)
    unknown["blocks"][0]["segments"] = [{"kind": "unknown", "text": None}]
    validate(unknown, [100, 100])
    assert render(unknown)[0] == "[unknown source span]"
    code = {"blocks": [{"kind": "code", "bbox": [0, 0, 100, 100], "code_language": None,
        "segments": [{"kind": "code", "text": "  literal ``` and `\nnext"}]}], "uncertainties": []}
    validate(code, [100, 100])
    assert render(code)[0] == "````\n  literal ``` and `\nnext\n````"
    try:
        json.loads("null").get("blocks")
    except AttributeError:
        try:
            validate(None, [100, 100])
        except ValueError:
            rejected.append("null_json_root")
    save(HERE / "selfcheck.json", {"passed": True, "rejected_negative_controls": rejected,
        "unknown_null_preserved": True, "code_fence_indentation_and_literal_backticks_preserved": True,
        "segment_output_spans_checked": True})
    print("Offline JSON/render self-check passed.")


if __name__ == "__main__":
    selfcheck() if sys.argv[1:] == ["--selfcheck"] else parse_all()
