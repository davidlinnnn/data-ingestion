"""Zero-model ownership controls plus saved T05 replay; no source/oracle reads."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import importlib.util
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
from docling_core.types.doc import (
    BoundingBox, DocItemLabel, DoclingDocument, PageItem, ProvenanceItem,
    RefItem, RichTableCell, Size, TableCell, TableData,
)
from policy import adapter, FROZEN, map_preserving_ownership

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(FROZEN))
spec = importlib.util.spec_from_file_location("frozen_cell_gate", FROZEN / "gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
sys.path.pop(0)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def protected_hashes():
    files = [p for p in FROZEN.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    files += [FROZEN.parent / "pdf-core-table-delivery-2026-10-17" / name
              for name in ("mapper.py", "verify.py")]
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}


def fixture(ownership, provider_caption="Synthetic source caption"):
    doc = DoclingDocument(name="caption ownership control")
    for page in (1, 2):
        doc.pages[page] = PageItem(page_no=page, size=Size(width=600, height=800))
    prov = ProvenanceItem(page_no=1, bbox=BoundingBox(l=20, t=100, r=580, b=400), charspan=(0, 0))
    text_prov = ProvenanceItem(page_no=1, bbox=BoundingBox(l=20, t=410, r=580, b=440), charspan=(0, 24))
    doc.add_text(label=DocItemLabel.TEXT, text="Before table", prov=deepcopy(text_prov))
    target = doc.add_table(data=TableData(num_rows=1, num_cols=1,
        table_cells=[TableCell(**gate.cell("old", 0, 0))]), prov=prov)
    if ownership == "linked":
        caption = doc.add_text(label=DocItemLabel.CAPTION, text="Synthetic source caption",
                               parent=target, prov=deepcopy(text_prov))
        target.captions.append(caption.get_ref())
    elif ownership in ("unlinked", "repeated_unlinked"):
        for _ in range(2 if ownership == "repeated_unlinked" else 1):
            doc.add_text(label=DocItemLabel.TEXT, text="Synthetic source caption", prov=deepcopy(text_prov))
    else:
        assert ownership == "missing"
    doc.add_text(label=DocItemLabel.TEXT, text="After table", prov=deepcopy(text_prov))
    rich = doc.add_table(data=TableData(num_rows=1, num_cols=1),
        prov=ProvenanceItem(page_no=2, bbox=BoundingBox(l=20, t=100, r=580, b=400), charspan=(0, 0)))
    child = doc.add_text(label=DocItemLabel.TEXT, text="Non-target referenced source", parent=rich)
    doc.add_table_cell(rich, RichTableCell(**gate.cell("", 0, 0), ref=child.get_ref()))
    keys = list(adapter.inventory(doc, 1))
    payload = {"targets": [{"target_key": keys[0], "caption": provider_caption,
        "conditions": [], "uncertainties": [], "panels": [{"panel_label": "", "title": "",
        "data": {"num_rows": 1, "num_cols": 1, "table_cells": [gate.cell("001.20", 0, 0)]}}]}]}
    return doc, keys, payload


def preserved(doc, payload, page, keys):
    before_doc, before_payload = doc.model_dump_json(), deepcopy(payload)
    targets = adapter.inventory(doc, page)
    excluded = {n.self_ref for key in keys for n in gate.old.walk(doc, targets[key])}
    untouched = [gate.source_signature(n, doc) for n in gate.old.walk(doc) if n.self_ref not in excluded]
    source_captions = {key: [gate.old.signature(r.resolve(doc)) for r in targets[key].captions] for key in keys}
    out, bindings = map_preserving_ownership(doc, payload, page, keys)
    assert doc.model_dump_json() == before_doc and payload == before_payload
    gate.old.assert_graph(out)
    changed = {n.self_ref for binding in bindings for n in gate.old.walk(out, RefItem(cref=binding["group_ref"]).resolve(out))}
    assert [gate.source_signature(n, out) for n in gate.old.walk(out) if n.self_ref not in changed] == untouched
    assert (out.pages, out.origin, out.furniture) == (doc.pages, doc.origin, doc.furniture)
    provider = {target.target_key: target.model_dump(mode="json") for target in adapter.parse_response(payload, keys).targets}
    for binding in bindings:
        key = binding["target_key"]
        assert binding["provider"] == provider[key]
        assert [gate.old.signature(RefItem(cref=r).resolve(out)) for r in binding["captions"]] == source_captions[key]
        for panel in binding["panels"]:
            assert RefItem(cref=panel["table_ref"]).resolve(out).prov == targets[key].prov
    before_serialization = out.model_dump_json()
    rendered = adapter.serialize(out, bindings)
    assert out.model_dump_json() == before_serialization
    assert all(span.item.model_dump_json() == span.item.get_ref().resolve(out).model_dump_json() for span in rendered.spans)
    loaded = DoclingDocument.model_validate_json(out.model_dump_json())
    gate.old.assert_graph(loaded)
    assert adapter.export_markdown(loaded, bindings) == rendered.text
    return out, bindings, rendered.text


def main():
    start = time.perf_counter()
    frozen = protected_hashes()
    registration = {"started_at": datetime.now(timezone.utc).isoformat(),
        "scope": "zero-model caption ownership only", "new_model_inferences": 0, "API_requests": 0,
        "source_pdf_reads": 0, "oracle_reads": 0, "holdout_reads": 0,
        "versions": {name: version(name) for name in ("docling-core", "pydantic", "markdown-it-py")},
        "protected_hashes_before": frozen,
        "research_code_hashes": {name: sha(HERE / name) for name in ("policy.py", "verify.py")}}
    write("registration.json", registration)
    passed = []
    for ownership, provider in (("linked", "Synthetic source caption"), ("linked", "Different provider observation"),
                               ("unlinked", "Synthetic source caption"), ("missing", "Synthetic source caption"),
                               ("repeated_unlinked", "Synthetic source caption"), ("missing", "")):
        doc, keys, payload = fixture(ownership, provider)
        out, bindings, markdown = preserved(doc, payload, 1, keys)
        expected = 2 if ownership == "repeated_unlinked" else int(ownership != "missing")
        assert markdown.count("Synthetic source caption") == expected
        assert sum(n.text == "Synthetic source caption" for n in out.texts) == expected
        policy = bindings[0]["caption_ownership"]
        assert policy["unresolved_provider_observation"] == bool(provider and ownership != "linked")
        assert not policy["source_completeness_verified"]
        assert policy["provider_caption_observation"] == provider
        assert not policy["provider_caption_applied"]
        if ownership == "linked":
            assert len(bindings[0]["captions"]) == 1
        else:
            assert not bindings[0]["captions"], "no guessed attachment"
        passed.append({"case": f"{ownership}:{provider or '(empty)'}", "canonical_caption_text_occurrences": expected,
                       "ownership": policy, "preservation_checks_passed": True})
    doc, keys, payload = fixture("unlinked")
    bad = deepcopy(payload)
    bad["targets"][0]["panels"][0]["data"]["table_cells"].clear()
    before = doc.model_dump_json()
    try:
        map_preserving_ownership(doc, bad, 1, keys)
    except ValueError:
        pass
    else:
        raise AssertionError("caption policy bypassed structural validation")
    assert doc.model_dump_json() == before
    base = FROZEN / "wikiskill-p13" / "baseline.json"
    raw = FROZEN / "wikiskill-p13" / "output.json"
    doc = DoclingDocument.model_validate_json(base.read_text())
    payload = json.loads(raw.read_text())
    keys = [target["target_key"] for target in payload["targets"]]
    caption = payload["targets"][0]["caption"]
    old_doc, old_bindings = adapter.map_response(doc, payload, 13, keys)
    old_md = adapter.export_markdown(old_doc, old_bindings)
    assert len(keys) == 1 and not adapter.inventory(doc, 13)[keys[0]].captions
    baseline_nodes = [n for n in doc.texts if n.text == caption]
    assert len(baseline_nodes) == 1 and baseline_nodes[0].label == DocItemLabel.TEXT
    assert old_md.count(caption) == 2, "saved replay no longer reproduces the recorded defect"
    out, bindings, markdown = preserved(doc, payload, 13, keys)
    assert markdown.count(caption) == 1 and sum(n.text == caption for n in out.texts) == 1
    assert bindings[0]["caption_ownership"]["unresolved_provider_observation"]
    assert [table.data for table in out.tables] == [table.data for table in old_doc.tables]
    (HERE / "wikiskill-provisional-document.json").write_text(out.model_dump_json(indent=2) + "\n")
    (HERE / "wikiskill-provisional-document.md").write_text(markdown + "\n")
    write("wikiskill-provisional-bindings.json", bindings)
    assert not {"torch", "transformers", "mlx"}.intersection(sys.modules)
    after = protected_hashes()
    assert after == frozen, "frozen evidence was modified"
    result = {"status": "ownership/source-preservation controls passed; missing-caption completeness not established",
        "synthetic_scenarios_passed": len(passed), "rejection_controls_passed": 1,
        "saved_T05_replays": 1, "cases": passed,
        "T05": {"frozen_canonical_caption_occurrences": 2, "proposed_canonical_caption_occurrences": 1,
                "existing_body_caption_reference": baseline_nodes[0].self_ref,
                "provider_observation_retained": True, "native_caption_attachment_established": False,
                "source_caption_preservation_passed": True, "duplicate_defect_absent": True,
                "table_cells_unchanged": True, "complete_profile_qualification": "not evaluated"},
        "preservation_checks_per_scenario": ["input document and payload immutable", "tree and all references valid",
            "non-target semantic references, content, provenance and order unchanged", "native linked captions unchanged",
            "table provenance unchanged", "provider response retained", "source spans refer to canonical nodes",
            "canonical immutable during serialization", "JSON reload and Markdown stable"],
        "protected_hashes_after": after, "protected_hashes_unchanged": True,
        "new_model_inferences": 0, "API_requests": 0, "source_pdf_reads": 0, "oracle_reads": 0, "holdout_reads": 0,
        "duration_seconds": time.perf_counter() - start,
        "limits": ["No runtime claim that an unlinked caption exists or is missing; only the fixture author knows that distinction",
            "Provider-only caption remains visible in evidence as unresolved_provider_observation=true, and is absent from primary Markdown",
            "An unresolved association is not automatically an acceptance failure: a source caption may remain standalone under F07",
            "Linked-caption preservation is ownership proof, not source semantic completeness proof",
            "No text deduplication, attachment guessing, new model call, frozen change or production change"]}
    write("verification.json", result)
    print(json.dumps({key: result[key] for key in ("status", "synthetic_scenarios_passed", "rejection_controls_passed",
        "saved_T05_replays", "T05", "protected_hashes_unchanged", "duration_seconds")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
