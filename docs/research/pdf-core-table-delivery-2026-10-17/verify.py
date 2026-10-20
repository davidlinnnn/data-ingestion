"""Offline delivery gate. Only this evaluator reads the frozen G1 oracle."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
from importlib.metadata import version
import json
from pathlib import Path
import resource
import sys
import time

from docling_core.types.doc import DoclingDocument, RefItem, ContentLayer

from mapper import inventory, map_response, parse_response, recover_provider_from_cells

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RAW = ROOT / "docs/research/pdf-core-g2-api-2026-10-14/skillopt-p8/output.json"
BASE = ROOT / "docs/research/pdf-core-native-round-2026-10-17/S0/skillopt/document.json"
ORACLE = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
EVAL = ROOT / "docs/research/pdf-core-g2-api-2026-10-14/review/evaluate.py"
OLD_API = RAW.parent


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk(doc, root=None):
    return [node for node, _ in doc.iterate_items(root=root, with_groups=True,
             traverse_pictures=True, included_content_layers=set(ContentLayer))]


def signature(node):
    return node.model_dump(mode="json", exclude={"self_ref", "parent", "children", "captions", "references"})


def assert_graph(doc):
    refs = []
    for root in (doc.body, doc.furniture):
        assert doc.validate_tree(root=root, raise_on_error=True)
        refs.extend(n.self_ref for n in walk(doc, root))
    assert len(refs) == len(set(refs)), "duplicate node in document tree"
    obj = doc.model_dump(mode="json")
    for field in ("groups", "texts", "tables", "pictures", "key_value_items", "form_items"):
        assert all(n["self_ref"] in refs for n in obj.get(field, [])), f"orphan in {field}"
    def visit(value):
        if isinstance(value, dict):
            if "$ref" in value:
                RefItem(cref=value["$ref"]).resolve(doc)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(obj)


def markdown_tables(text):
    tables, block = [], []
    for line in text.splitlines() + [""]:
        if line.startswith("|") and line.endswith("|"):
            block.append([v.strip() for v in line[1:-1].split("|")])
        elif block:
            assert len(block) >= 2
            tables.append([block[0], *block[2:]])
            block = []
    return tables


def controls():
    doc = DoclingDocument(name="synthetic ordinary table")
    from docling_core.types.doc import BoundingBox, PageItem, ProvenanceItem, Size, TableData
    doc.pages[1] = PageItem(page_no=1, size=Size(width=100, height=100))
    old = doc.add_table(data=TableData(num_rows=0, num_cols=0),
        prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=1,t=1,r=99,b=99), charspan=(0,0)))
    keys = list(inventory(doc, 1))
    panel = {"panel_label":"", "title":"Measurement", "columns":["Score"],
             "rows":[{"setting":"source row", "values":[{"column":"Score","value":"001.20"}]}]}
    payload = {"targets":[{"target_key":keys[0],"caption":"","conditions":[],"panels":[panel]}]}
    out, bindings = map_response(doc, payload, 1, keys)
    assert_graph(out)
    loaded = DoclingDocument.model_validate_json(out.model_dump_json())
    assert "001.20" in loaded.export_to_markdown()
    assert recover_provider_from_cells(loaded, bindings[0])["panels"] == payload["targets"][0]["panels"]
    good = ["new-live-schema ordinary table through parser/mapper/export/reload", "printed precision retained"]
    # Valid but source-incorrect values/rows must reach the evaluator, not be guessed here.
    legal = deepcopy(payload)
    legal["targets"][0]["panels"][0]["rows"].append({"setting":"another row", "values":[{"column":"Score","value":"999"}]})
    parse_response(legal, keys)
    good.append("schema-valid extra row accepted for source evaluation")
    variants = {}
    v = deepcopy(payload); v["targets"] = []; variants["missing target"] = v
    v = deepcopy(payload); v["targets"] *= 2; variants["duplicate target"] = v
    v = deepcopy(payload); v["targets"][0]["target_key"] = "unknown"; variants["unknown target"] = v
    v = deepcopy(payload); v["targets"][0]["panels"][0]["columns"] *= 2; variants["duplicate metric"] = v
    v = deepcopy(payload); v["targets"][0]["panels"][0]["rows"][0]["values"] = []; variants["missing metric"] = v
    v = deepcopy(payload); v["targets"][0]["panels"][0]["rows"][0]["values"].append({"column":"extra","value":"9"}); variants["extra-width metric"] = v
    v = deepcopy(payload); v["targets"][0]["panels"][0]["rows"][0]["values"][0]["value"] = 1.2; variants["numeric coercion"] = v
    v = deepcopy(payload); v["targets"][0]["panels"] *= 2; variants["duplicate panel identity"] = v
    for name, value in variants.items():
        try:
            map_response(doc, value, 1, keys)
        except ValueError:
            good.append(f"reject {name}")
        else:
            raise AssertionError(name)
    for name, invalid_doc, selected in (
        ("unknown registered source", doc, ["absent"]),
        ("out-of-page source", doc.model_copy(deep=True), keys),
    ):
        if name == "out-of-page source":
            invalid_doc.tables[0].prov[0].bbox.r = 101
        try:
            map_response(invalid_doc, payload, 1, selected)
        except ValueError:
            good.append(f"reject {name}")
        else:
            raise AssertionError(name)
    assert doc.tables[0] == old and len(doc.tables) == 1
    good.append("input document unchanged after success and rejection")
    return good


def main():
    start = time.perf_counter()
    registration = {"started_at":datetime.now(timezone.utc).isoformat(), "stage":"offline only",
        "budget_seconds":5400, "new_inferences":0, "input_hashes":{str(p.relative_to(ROOT)):sha(p) for p in (RAW,BASE,ORACLE,EVAL)},
        "code_hashes":{p.name:sha(p) for p in (HERE/"mapper.py",HERE/"verify.py")},
        "versions":{name:version(name) for name in ("docling-slim","docling-core","pydantic")},
        "python":sys.version, "replay_registered_keys":["p8:#/tables/0"],
        "routing":"known replay binding; not automatic target-discovery proof"}
    import docling_core.types.doc.document as source
    source_path = Path(source.__file__)
    registration["core_document_source"] = {"path":str(source_path),"sha256":sha(source_path)}
    registration["evidence_hashes"] = {str(p.relative_to(ROOT)):sha(p) for p in (
        OLD_API/"input.png",OLD_API/"request-description.json",OLD_API/"response.json")}
    write("registration.json",registration)
    checked_controls = controls()
    baseline = DoclingDocument.model_validate_json(BASE.read_text())
    assert_graph(baseline)
    raw = json.loads(RAW.read_text())
    key = registration["replay_registered_keys"][0]
    old = inventory(baseline,8)[key]
    old_nodes = {n.self_ref for n in walk(baseline,old)}
    expected_untouched = [signature(n) for n in walk(baseline) if n.self_ref not in old_nodes]
    original_captions = [signature(r.resolve(baseline)) for r in old.captions]
    old_native_md = baseline.export_to_markdown()
    original_body = baseline.model_dump(mode="json")
    response = {"targets":[{"target_key":key, **raw}]}
    doc, bindings = map_response(baseline,response,8,[key])
    assert baseline.model_dump(mode="json") == original_body
    assert_graph(doc)
    b = bindings[0]
    b["source_evidence"] = {"baseline_document":str(BASE.relative_to(ROOT)),
        "baseline_sha256":sha(BASE),"provider_output":str(RAW.relative_to(ROOT)),
        "provider_output_sha256":sha(RAW),"original_api_evidence":registration["evidence_hashes"],
        "source_pdf_sha256":"87f7f0f323b1671e9202b3ebb1596e909e507c71ecd1b360b0075a5ee1727fe3",
        "binding_mode":"known replay mapping; not model-discovered or automatic routing"}
    group = RefItem(cref=b["group_ref"]).resolve(doc)
    changed = {n.self_ref for n in walk(doc,group)}
    actual_untouched = [signature(n) for n in walk(doc) if n.self_ref not in changed]
    assert actual_untouched == expected_untouched
    assert [signature(RefItem(cref=r).resolve(doc)) for r in b["captions"]] == original_captions
    assert doc.origin == baseline.origin and doc.pages == baseline.pages and doc.furniture == baseline.furniture
    text = doc.export_to_markdown()
    for p, refs in zip(raw["panels"], b["panels"], strict=True):
        title = RefItem(cref=refs["title_ref"]).resolve(doc)
        assert title.text == " ".join(s for s in (p["panel_label"],p["title"]) if s)
        table = RefItem(cref=refs["table_ref"]).resolve(doc)
        assert all(c.bbox is None for c in table.data.table_cells)
        assert table.prov == old.prov and title.prov == old.prov
    md_tables = markdown_tables(text)
    assert len(md_tables) == len(doc.tables) == 7
    for refs, rendered in zip(b["panels"],md_tables[:len(b["panels"])],strict=True):
        item = RefItem(cref=refs["table_ref"]).resolve(doc)
        assert rendered == [[c.text for c in row] for row in item.data.grid]
    for cap in original_captions:
        assert text.count(cap["text"]) == 1
    (HERE/"document.json").write_text(doc.model_dump_json(indent=2)+"\n")
    (HERE/"document.md").write_text(text+"\n")
    (HERE/"baseline.md").write_text(old_native_md+"\n")
    write("bindings.json",bindings)
    loaded = DoclingDocument.model_validate_json((HERE/"document.json").read_text())
    assert_graph(loaded)
    assert loaded.export_to_markdown() == text
    reconstructed = recover_provider_from_cells(loaded,b)
    assert reconstructed["panels"] == raw["panels"]
    spec=importlib.util.spec_from_file_location("old_evaluator",EVAL)
    evaluator=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluator)
    cases={c["id"]:c for c in json.loads(ORACLE.read_text())["cases"]}
    evaluator.self_check(cases)
    quality=evaluator.evaluate_table(reconstructed,cases["G1-T02"]["details"])
    assert quality["source_numeric_bindings_correct"] == quality["printed_numeric_strings_exact"] == 84
    assert quality["all_critical_numeric_bindings_preserved"] and not quality["extra_numeric_observations"]
    write("typed-quality.json",quality)
    assert not {"torch","transformers","mlx"}.intersection(sys.modules), "no inference runtime imports allowed"
    elapsed=time.perf_counter()-start
    assert elapsed < 5400
    report={"status":"offline mechanical gate passed; source-caption semantic review recorded separately",
        "controls":checked_controls,"checks":{
          "native_tree_and_all_references_valid":True,"no_orphan_nodes":True,
          "non_target_content_position_order_unchanged":True,"native_caption_preserved_once":True,
          "table3_preserved":True,"panels":len(raw["panels"]),"data_rows":sum(len(p["rows"]) for p in raw["panels"]),
          "typed_numeric_bindings":84,"markdown_numeric_strings_and_bindings":84,
          "critical_comparisons":8,"typed_roundtrip_exact":True,"stock_markdown_roundtrip_exact":True,
          "input_raw_and_baseline_unchanged":sha(RAW)==registration["input_hashes"][str(RAW.relative_to(ROOT))] and sha(BASE)==registration["input_hashes"][str(BASE.relative_to(ROOT))]},
        "duration_seconds":elapsed,"process_peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "new_inferences":0,"new_installs":0,"private_api_calls":0,"custom_renderers":0,
        "limits":["known replay source binding only", "whole-table envelope, not panel/cell geometry",
                  "provider conditions remain in bindings; source caption carries visible conditions in Markdown",
                  "frozen DEV, no holdout or company GPU/latency proof"],
        "api_stage":"not started; OPENAI_API_KEY unavailable at preflight"}
    write("verification.json",report)
    print(json.dumps({k:report[k] for k in ("status","checks","duration_seconds","process_peak_rss_bytes","api_stage")},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
