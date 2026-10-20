"""Register, then run pinned official parser/export controls; no inference or repair."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import sys

os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SITE = Path("/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages")
FORMULA = r"p(y_{<s}) = \sum_{i=1}^{n} x_i^2 \tag{4}"
CODE = 'def render_html(user_id):\n    literal_tag = "<b>bold</b>"\n    if user_id <= 2:\n        return {"under_score": literal_tag}\n    return "<s>strike</s>"'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def register():
    assert not (HERE / "registration.json").exists(), "Registration already frozen"
    cases = [
        ("formula-bare", "Formula", FORMULA, "formula", FORMULA, "$$" + FORMULA + "$$"),
        ("formula-display-wrapped", "Formula", "$$" + FORMULA + "$$", "formula", "$$" + FORMULA + "$$", "$$" + FORMULA + "$$"),
        ("formula-inline-wrapped", "Formula", "$x_i^2$", "formula", "$x_i^2$", "$$x_i^2$$"),
        ("inline-math-code", "Text", r"For $x_i^2$ and $\theta'$ use `items[i] <= limit`; preserve the sentence.", "text", None, None),
        ("formula-less-s-tag", "Formula", "a<s>0", "formula", "a<s>0", "$$a<s>0$$"),
        ("inline-less-s-tag", "Text", r"Require $a<s>0$ and $p(y_{<s})$.", "text", None, None),
        ("fenced-html-code", "Text", "```python\n" + CODE + "\n```", "code", CODE, "```\n" + CODE + "\n```"),
        ("inline-html-code", "Text", "Use `<b>bold</b>` literally; keep `under_score` and `a <= b`.", "text", None, None),
        ("inline-unknown-tag-code", "Text", "Use `<widget>` and `a <= b` literally.", "text", None, None),
        ("html-code-semantic", "Text", "<p>Use <code>&lt;b&gt;bold&lt;/b&gt;</code> literally.</p>", "html-code", "<b>bold</b>", "Use `<b>bold</b>` literally."),
        ("ordinary-prose", "Text", "Normal task-specific prose, price $5, identifiers under_score_name and ReflACT, 3 < 4.", "text", None, None),
        ("escaped-literal-prose", "Text", r"Literal \_\_init\_\_, \_TEMP\_, &lt;widget&gt;, price $5 and 3 < 4.", "text", None, None),
        ("unescaped-literal-prose", "Text", "Literal __init__, _TEMP_ and <widget>.", "text", None, None),
        ("ordinary-html", "Text", "<p>Normal <b>bold</b>, H<sub>2</sub>O and x<sup>2</sup>.</p>", "html", None, None),
        ("merged-table", "Table", '<table><tr><th rowspan="2">Method</th><th colspan="2">Score</th></tr><tr><th>Train</th><th>Test</th></tr><tr><td>Baseline</td><td>1</td><td>2</td></tr></table>', "table", None, None),
    ]
    inputs = []
    for name, category, text, kind, expected, markdown in cases:
        inputs.append(dict(name=name, raw=[dict(category=category, bbox=[40, 40, 1080, 300], text=text)],
                           kind=kind, expected_content=text if expected is None else expected,
                           expected_markdown=text if markdown is None else markdown))
    inputs.append(dict(name="picture-caption", kind="picture", raw=[
        dict(category="Picture", bbox=[40, 40, 240, 240]),
        dict(category="Caption", bbox=[40, 260, 400, 300], text="Figure 1. Synthetic source-fixed square.")]))
    save(HERE / "inputs.json", inputs)
    settings = [dict(name="stock", options={}),
                dict(name="no-underscore-escape", options=dict(escape_underscores=False)),
                dict(name="no-html-escape", options=dict(escape_html=False)),
                dict(name="native-markdown", options=dict(escape_underscores=False, escape_html=False)),
                dict(name="native-compact", options=dict(escape_underscores=False, escape_html=False, compact_tables=True)),
                dict(name="native-unfenced", serializer=True, options=dict(escape_underscores=False, escape_html=False, format_code_blocks=False)),
                dict(name="native-embedded", options=dict(escape_underscores=False, escape_html=False, image_mode="embedded"))]
    originals = [REPO / "docs/research/pdf-core-g2-dots-mlx-2026-10-16/run" / name / "raw.txt"
                 for name in ("controls-p1", "seal-p4", "wikiskill-p22", "dgm-p51")]
    sources = [SITE / p for p in ("docling/utils/dots_utils.py", "docling/utils/chandra_utils.py",
               "docling_core/transforms/serializer/markdown.py", "docling_core/transforms/serializer/common.py",
               "docling_core/types/doc/document.py")]
    save(HERE / "registration.json", dict(
        purpose="Parser and representation preflight, synthetic source-fixed controls plus unchanged saved raw replay; not model quality",
        prior_attempt="run-attempt01 stopped on overly strict direct-model paragraph spacing assertion (inline joins add spaces). Same 16 inputs and seven settings; assertion now checks exact code literal instead. Original registered runner and registration retained.",
        calls=dict(model=0, gpu=0, network=0, pdf_reads=0), settings=settings,
        parser_options=dict(original_page_size=dict(width=560, height=840), page_no=3,
                            model_image_size=dict(width=1120, height=1680), synthetic_page_image="1120x1680 RGB white with black square [40,40,240,240]"),
        synthetic_source_of_truth="inputs.json is both the authored source and exact native DOTS JSON control; no inferred source answers",
        direct_model_controls="A public add_code() block and an add_inline_group()+add_code() inline child; no conversion from failed parser output",
        checks="Exact parser content, exact expected Markdown or typed table/script/code representation; rendered negative prose inspected separately with Marko; geometry existence differs from source-location accuracy",
        inputs_sha256=digest(HERE / "inputs.json"), runner_sha256=digest(Path(__file__)),
        packages={p: importlib.metadata.version(p) for p in ("docling-slim", "docling-core", "docling-parse", "marko")},
        original_raw=[dict(path=str(p), sha256=digest(p)) for p in originals],
        installed_sources=[dict(path=str(p), sha256=digest(p)) for p in sources]))
    print("Registered 16 controls, seven global export settings and four unchanged saved raw replays; no parser test executed.")


def run():
    registration = json.loads((HERE / "registration.json").read_text())
    assert digest(HERE / "inputs.json") == registration["inputs_sha256"]
    assert digest(Path(__file__)) == registration["runner_sha256"]
    for entry in registration["installed_sources"] + registration["original_raw"]:
        assert digest(Path(entry["path"])) == entry["sha256"]
    def blocked(*args, **kwargs):
        raise AssertionError("Network forbidden in parser-only preflight")
    socket.socket.connect = blocked
    socket.create_connection = blocked
    from PIL import Image, ImageDraw
    import marko
    from docling.utils.dots_utils import parse_dots_json
    from docling_core.types.doc import DoclingDocument, DocItemLabel, ImageRefMode, Size
    from docling_core.transforms.serializer.markdown import MarkdownDocSerializer, MarkdownParams
    image = Image.new("RGB", (1120, 1680), "white")
    ImageDraw.Draw(image).rectangle([40, 40, 240, 240], fill="black")
    out = HERE / "run"
    out.mkdir(exist_ok=False)
    image.save(out / "synthetic-source.png")
    def export(doc, setting):
        opts = dict(setting["options"])
        if "image_mode" in opts:
            opts["image_mode"] = ImageRefMode(opts["image_mode"])
        if setting.get("serializer"):
            return MarkdownDocSerializer(doc=doc, params=MarkdownParams(**opts)).serialize().text
        return doc.export_to_markdown(**opts)
    def snapshot(name, raw):
        dest = out / name
        dest.mkdir()
        (dest / "raw.txt").write_text(raw)
        doc = parse_dots_json(raw, original_page_size=Size(width=560, height=840), page_no=3,
                              model_image_size=Size(width=1120, height=1680), page_image=image,
                              filename=name + ".json")
        doc.save_as_json(dest / "prediction.json")
        markdown = {}
        for setting in registration["settings"]:
            text = export(doc, setting)
            markdown[setting["name"]] = text
            (dest / (setting["name"] + ".md")).write_text(text)
            if name in {"ordinary-prose", "escaped-literal-prose", "unescaped-literal-prose", "inline-html-code", "inline-unknown-tag-code", "html-code-semantic"}:
                (dest / (setting["name"] + ".html")).write_text(marko.convert(text))
        return doc, markdown
    results = []
    for case in json.loads((HERE / "inputs.json").read_text()):
        doc, markdown = snapshot(case["name"], json.dumps(case["raw"], ensure_ascii=False))
        kind = case["kind"]
        if kind in {"text", "formula", "code"}:
            content = any(t.text == case["expected_content"] and t.label.value == kind for t in doc.texts)
            representation = {k: case["expected_markdown"] in text for k, text in markdown.items()}
            # Exact block fences and source delimiters are an explicit delivery contract.
            if kind == "formula":
                representation = {k: text == case["expected_markdown"] for k, text in markdown.items()}
        elif kind == "html-code":
            content = any(t.label == DocItemLabel.CODE and t.text == case["expected_content"] for t in doc.texts)
            representation = {k: case["expected_markdown"] == text for k, text in markdown.items()}
        elif kind == "html":
            scripts = [t.formatting.script.value for t in doc.texts if t.formatting and t.formatting.script]
            content = "sub" in scripts and "super" in scripts
            representation = {k: "<sub>2</sub>" in text and "<sup>2</sup>" in text for k, text in markdown.items()}
        elif kind == "table":
            cells = doc.tables[0].data.table_cells
            content = (any(c.text == "Method" and c.row_span == 2 and c.column_header for c in cells)
                       and any(c.text == "Score" and c.col_span == 2 and c.column_header for c in cells)
                       and all(any(c.text == value for c in cells) for value in ("Train", "Test", "Baseline", "1", "2")))
            representation = {k: 'rowspan="2"' in text and 'colspan="2"' in text for k, text in markdown.items()}
        else:
            crop = doc.pictures[0].get_image(doc)
            content = crop is not None and crop.size == (200, 200) and bool(doc.pictures[0].captions)
            crop.save(out / case["name"] / "native-crop.png")
            representation = {k: "data:image/png;base64," in text for k, text in markdown.items()}
        items = list(doc.iterate_items())
        prov = [p for item, _ in items if hasattr(item, "prov") for p in item.prov]
        results.append(dict(name=case["name"], content_pass=content, representation_pass=representation,
                            native_item_count=len(items), native_items_without_own_provenance=[item.self_ref for item, _ in items if hasattr(item, "prov") and not item.prov],
                            existing_provenance_page3=all(p.page_no == 3 for p in prov),
                            note="Content pass for wrapped formula means exact raw string retained, not validated TeX semantics; prose substring checks are raw Markdown, see rendered negatives."))
    replay = []
    for entry in registration["original_raw"]:
        path = Path(entry["path"])
        raw = path.read_text()
        doc, markdown = snapshot("replay-" + path.parent.name, raw)
        try:
            json.loads(raw)
            strict_valid = True
        except ValueError:
            strict_valid = False
        replay.append(dict(original=entry, strict_json_valid=strict_valid,
                           texts=len(doc.texts), tables=len(doc.tables), pictures=len(doc.pictures),
                           formula_texts=[t.text for t in doc.texts if t.label == DocItemLabel.FORMULA],
                           markdown_quad_dollar_counts={k: text.count("$$$$") for k, text in markdown.items()},
                           scope="Saved raw replay only; synthetic geometry/image not original source evidence; not rescored"))
    direct = DoclingDocument(name="typed-code-controls")
    direct.add_code(text=CODE)
    paragraph = direct.add_text(label=DocItemLabel.TEXT, text="")
    group = direct.add_inline_group(parent=paragraph)
    direct.add_text(label=DocItemLabel.TEXT, text="Use ", parent=group)
    direct.add_code(text="<b>bold</b>", parent=group)
    direct.add_text(label=DocItemLabel.TEXT, text=" literally.", parent=group)
    direct.save_as_json(out / "typed-code-controls.json")
    direct_markdown = direct.export_to_markdown()
    (out / "typed-code-controls.md").write_text(direct_markdown)
    assert CODE in direct_markdown and "`<b>bold</b>`" in direct_markdown
    by_name = {r["name"]: r for r in results}
    assert by_name["fenced-html-code"]["content_pass"]
    assert not by_name["inline-html-code"]["content_pass"]
    assert by_name["formula-bare"]["representation_pass"]["native-markdown"]
    assert not by_name["formula-display-wrapped"]["representation_pass"]["native-markdown"]
    assert by_name["merged-table"]["content_pass"]
    assert by_name["picture-caption"]["content_pass"]
    for entry in registration["installed_sources"] + registration["original_raw"]:
        assert digest(Path(entry["path"])) == entry["sha256"]
    forbidden = [m for m in sys.modules if m.split(".")[0] in {"mlx", "mlx_vlm", "torch", "transformers"}]
    assert not forbidden, forbidden
    save(out / "results.json", dict(controls=results, saved_raw_replays=replay,
                                   typed_code_controls_pass=True, model_calls=0, network_calls=0,
                                   model_libraries_imported=forbidden, output_repairs=0,
                                   original_raw_and_installed_source_hashes_unchanged=True))
    print(json.dumps(dict(controls=len(results), content_pass=sum(r["content_pass"] for r in results),
                          expected_native_limits_observed=True, typed_code_controls_pass=True, saved_raw_replays=len(replay)), indent=2))


if __name__ == "__main__":
    {"register": register, "run": run}[sys.argv[1]]()
