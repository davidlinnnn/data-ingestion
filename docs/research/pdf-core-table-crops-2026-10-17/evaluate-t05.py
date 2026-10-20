"""Post-call T05 review; reuse the frozen oracle evaluator, never repair output."""
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument, RefItem
from markdown_it import MarkdownIt


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASE = HERE / "wikiskill-p13"
ORACLE = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
OLD = HERE.parent / "pdf-core-direct-cell-2026-10-17/evaluate-t05.py"
spec = importlib.util.spec_from_file_location("previous_t05_evaluator", OLD)
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RenderedTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.table, self.row, self.cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("th", "td") and self.row is not None:
            self.cell = ""
        elif tag == "br" and self.cell is not None:
            self.cell += " "

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self.cell is not None:
            self.row.append(previous.norm(self.cell))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def main():
    completed = json.loads((HERE / "all-calls-complete.json").read_text())
    records = json.loads((HERE / "live-observations.json").read_text())
    assert completed["requests"] == len(records) == 6
    assert all(x["attempts"] == 1 for x in records)
    registration = json.loads((HERE / "registration.json").read_text())
    page = next(p for p in registration["pages"] if p["name"] == "wikiskill-p13")
    job = next(j for j in registration["jobs"] if j["page_name"] == "wikiskill-p13")
    protected = {**registration["method_files"], **{
        str(Path(j["directory"]) / "response.json"): completed["response_hashes"][j["name"]]
        for j in registration["jobs"]}}
    assert all(sha(path) == digest for path, digest in protected.items())
    for field in ("baseline", "image", "options"):
        assert sha(page[field]) == page[field + "_sha256"]
    assert sha(job["image"]) == job["image_sha256"]
    details = next(c for c in json.loads(ORACLE.read_text())["cases"] if c["id"] == "G1-T05")["details"]
    visual = ROOT / details["rendered_evidence"][1]["path"]
    assert sha(visual) == details["rendered_evidence"][1]["sha256"]
    source_pdf = ROOT / "docs/fixtures/agent-self-evolution-pilot-2026-10-11" / page["source"]
    assert sha(source_pdf) == page["source_sha256"]
    baseline = DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
    doc = DoclingDocument.model_validate_json((CASE / "document.json").read_text())
    before = doc.model_dump(mode="json")
    bindings = json.loads((CASE / "bindings.json").read_text())
    payload = json.loads((CASE / "output.json").read_text())
    assert len(bindings) == len(payload["targets"]) == 1 and len(bindings[0]["panels"]) == 1
    table = RefItem(cref=bindings[0]["panels"][0]["table_ref"]).resolve(doc)
    grid = table.data.grid
    paths = [[previous.norm(grid[0][col].text), previous.norm(grid[1][col].text)] for col in range(1, 7)]
    rows = [(i, [previous.norm(c.text) for c in row]) for i, row in enumerate(grid)
            if not any(c.column_header for c in row)]
    typed = previous.evaluate(previous.observations(paths, rows), details)
    markdown = (CASE / "document.md").read_text()
    rendered = MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown)
    parser = RenderedTables()
    parser.feed(rendered)
    assert len(parser.tables) == 1
    rendered_paths = [h.split(" - ", 1) for h in parser.tables[0][0][1:]]
    rendered_result = previous.evaluate(previous.observations(rendered_paths,
        list(enumerate(parser.tables[0][1:]))), details)
    sections = [c for c in table.data.table_cells if c.row_section]
    caption = details["caption"]["text"]
    old_table = baseline.tables[0]
    structural = {
        "literal_category_header_and_rowspan": grid[0][0].text == "Category"
            and grid[0][0].column_header and grid[0][0].row_span == 2,
        "hierarchical_headers_preserved": paths == [["Skills", "Create (Proposed / Accepted)"],
            ["Skills", "Edit (Proposed / Accepted)"], ["Skills", "Avg. Length"],
            ["Wiki Patterns", "Create"], ["Wiki Patterns", "Edit"], ["Wiki Patterns", "Avg. Length"]],
        "parent_spans_preserved": grid[0][1].col_span == 3 and grid[0][4].col_span == 3,
        "two_row_sections_and_roles": len(sections) == 2 and all(c.col_span == 7
            and not c.column_header and not c.row_header for c in sections),
        "group_names_and_order": [previous.norm(c.text) for c in sections] == [
            r["text"] for r in details["structure"]["row_group_headers"]],
        "ten_category_row_headers": sum(c.row_header for c in table.data.table_cells) == 10,
        "all_twenty_pairs_typed_and_rendered": typed["paired_physical_cells_passed"] == 20
            and rendered_result["paired_physical_cells_passed"] == 20,
        "caption_units_scope_and_retained_condition": markdown.count(caption) == 1,
        "provider_caption_empty": payload["targets"][0]["caption"] == "",
        "source_standalone_caption_preserved_once": not old_table.captions and not table.captions
            and sum(t.text == caption for t in baseline.texts) == sum(t.text == caption for t in doc.texts) == 1,
        "native_table_envelope_preserved": table.prov == old_table.prov,
        "canonical_unchanged_by_review": doc.model_dump(mode="json") == before,
    }
    # The new mapper adds an empty panel-title node, so compare all nonempty source text.
    structural["non_target_text_order_and_provenance_preserved"] = [
        (t.text, t.orig, t.label, t.prov) for t in baseline.texts if t.text] == [
        (t.text, t.orig, t.label, t.prov) for t in doc.texts if t.text]
    bad = deepcopy(typed["observations"])
    bad[0]["value"] = "999"
    assert previous.evaluate(bad, details)["numeric_errors_including_extras"] == 1
    bad[0]["column"] = "Wiki Patterns/Create"
    assert previous.evaluate(bad, details)["numeric_errors_including_extras"] > 1
    html_control = RenderedTables()
    html_control.feed("<table><tr><td>A &amp; B<br>C</td><td><code>&lt;x&gt;</code></td></tr></table>")
    assert html_control.tables == [[["A & B C", "<x>"]]]
    content_pass = all(structural.values()) and typed["numeric_and_critical_threshold_passed"] \
        and rendered_result["numeric_and_critical_threshold_passed"]
    report = {"case": "G1-T05", "evaluation_after_all_six_fixed_requests": True,
        "method": "Independently viewed source216dpi and actual144dpi crop; reused frozen80point/7comparison/20pair oracle; parsed actual rendered CommonMark HTML cells.",
        "typed": typed, "rendered_markdown": rendered_result, "structural_checks": structural,
        "caption_occurrences_in_main_markdown": markdown.count(caption),
        "conditions": "All-Dataset/All-Model row-group conditions in body; average length in markdown lines and all wiki creations/edits retained remain in the original standalone caption.",
        "source_shape_note": "Two typed header rows retain the source's wrapped role labels; Markdown repeats row-section labels across its seven display cells while typed spans preserve a single physical source row section.",
        "content_pass": content_pass, "complete_t05_delivery_pass": content_pass,
        "material_errors": [], "minor_observations": ["Stock pipe-table display repeats each row-section label across columns; group scope remains unambiguous and typed colspan7 preserved."],
        "self_checks": ["numeric_change_detected", "wrong_header_binding_detected", "rendered_html_entities_and_nested_inline_text"],
        "limitations": ["Exposed DEV case; no new generalization or full-profile qualification.",
            "Source caption remains standalone; no guessed native attachment.",
            "Only native table-envelope location precision, no per-cell geometry."],
        "sha256": {str(p.relative_to(ROOT)): sha(p) for p in (ORACLE, visual, source_pdf, OLD,
            Path(job["image"]), CASE / "document.json", CASE / "document.md", CASE / "output.json", Path(__file__))}}
    assert all(sha(path) == digest for path, digest in protected.items())
    report["frozen_method_and_response_hashes_unchanged"] = True
    (CASE / "evaluated-rendered.html").write_text(rendered)
    (HERE / "t05-evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"typed_correct": typed["correct_expected_bindings"],
        "rendered_correct": rendered_result["correct_expected_bindings"],
        "critical_each": typed["critical_comparisons_passed"], "pairs_each": typed["paired_physical_cells_passed"],
        "structural_checks": structural, "complete_t05_delivery_pass": content_pass}, indent=2))


if __name__ == "__main__":
    main()
