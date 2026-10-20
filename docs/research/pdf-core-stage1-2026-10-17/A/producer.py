"""Offline whole-owner experiment; no oracle, inference or lexical routing."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = load("stage1_legacy_adapter", REPO / "docs/research/pdf-core-g2-context-candidate-2026-10-15/adapter.py")
geometry = load("stage1_native_geometry", REPO / "docs/research/pdf-core-g2-context-candidate-2026-10-15/candidate.py")
digest = legacy.digest


def bind_scope(raw, targets, contexts=()):
    targets, contexts = legacy._references(targets), legacy._references(contexts)
    if not targets or set(targets) & set(contexts):
        raise ValueError("empty targets or consumed context")
    effects, entries = set(), []
    parents = [raw[k] for k in ("body", "furniture")]
    for key in ("groups", "texts", "pictures", "tables", "key_value_items", "form_items"):
        parents.extend(raw.get(key, []))
    for reference in targets:
        native = legacy.item(raw, reference)
        subtree = legacy._descendants(raw, reference)
        if effects & subtree:
            raise ValueError("overlapping target ownership")
        effects.update(subtree)
        if native["label"] == "picture":
            children = [legacy.item(raw, c["$ref"]) for c in native["children"]]
            if not children or any(c["label"] != "formula" or c.get("children") for c in children):
                raise ValueError("unsupported picture owner")
        elif not reference.startswith("#/texts/") or native.get("children"):
            raise ValueError("unsupported text owner")
    context_effects = set()
    for reference in contexts:
        context_effects.update(legacy._descendants(raw, reference))
    if effects & context_effects:
        raise ValueError("context overlaps consumed subtree")
    for reference in sorted(effects | context_effects):
        native = legacy.item(raw, reference)
        owners = [p["self_ref"] for p in parents for c in p.get("children", []) if c.get("$ref") == reference]
        if owners != [native.get("parent", {}).get("$ref")]:
            raise ValueError("ownership not unique and reciprocal")
        fragments, problem = geometry._fragments(raw, native)
        if problem:
            raise ValueError(problem)
        entries.append({"item_ref": reference, "sha256": digest(native), "fragments": fragments})
    scope = {"format": "stage1-whole-owner-v1", "document_sha256": digest(raw),
             "target_item_refs": targets, "context_only_refs": contexts,
             "consumption_effect_refs": sorted(effects), "entries": entries}
    return {**scope, "scope_sha256": digest(scope)}


def apply(raw, scope, contract, response):
    if scope != bind_scope(raw, scope["target_item_refs"], scope["context_only_refs"]):
        raise ValueError("stale or changed scope")
    fields = ("image_sha256", "image_pixels_wh", "request_sha256", "manifest_row_sha256")
    if contract != legacy.bind_input(scope, **{k: contract[k] for k in fields}):
        raise ValueError("changed input contract")
    if response["input_fingerprint"] != contract["input_fingerprint"]:
        raise ValueError("foreign input response")
    data = response["data"]
    if digest(data) != response["output_sha256"]:
        raise ValueError("changed response")
    if not isinstance(data, dict) or set(data) != {"targets"} or not isinstance(data["targets"], list):
        raise ValueError("invalid root")
    if [t.get("target_ref") for t in data["targets"]] != scope["target_item_refs"]:
        raise ValueError("missing, duplicate, unknown or reordered target")
    proposals = []
    for target in data["targets"]:
        if set(target) != {"target_ref", "content"}:
            raise ValueError("unknown target field")
        content = target["content"]
        legacy.parser.validate(content, contract["image_pixels_wh"])
        if any(s["kind"] == "unknown" or not s["text"] for b in content["blocks"] for s in b["segments"]):
            raise ValueError("unresolved or empty segment")
        markdown, offsets = legacy.parser.render(content)
        proposals.append({"id": target["target_ref"], "consumed_item_refs": [target["target_ref"]],
                          "markdown": markdown, "segment_offsets": offsets})
    document = DoclingDocument.model_validate(raw)
    working, spans, outside = legacy.renderer.render(document, proposals)
    _, _, original_outside = legacy.renderer.render(document, [{**p, "markdown": "BASELINE"} for p in proposals])
    if [s["sha256"] for s in outside] != [s["sha256"] for s in original_outside]:
        raise ValueError("non-target literal changed")
    return {"working": working, "spans": spans, "outside": outside,
            "proposals": proposals, "scope": scope, "response": response,
            "semantic_acceptance": False}


def plan(raw):
    """All body text roles, not just native text/code/formula; no answer filters."""
    rows, members = [], set()
    for picture in raw.get("pictures", []):
        children = [legacy.item(raw, c["$ref"]) for c in picture.get("children", [])]
        if children and all(c["label"] == "formula" and not c.get("children") for c in children):
            members.update(c["self_ref"] for c in children)
            rows.append({"target_ref": picture["self_ref"], "kind": "formula_picture_envelope"})
    for native in raw["texts"]:
        if native["self_ref"] not in members:
            rows.append({"target_ref": native["self_ref"], "kind": native["label"]})
    document = DoclingDocument.model_validate(raw)
    for row in rows:
        native = legacy.item(raw, row["target_ref"])
        row.update(discovered=True, scoped=False, eligible=False, scheduled=False,
                   delivered=False, model_calls=0)
        try:
            scope = bind_scope(raw, [row["target_ref"]])
            row.update(scoped=True, scope=scope)
            pages = [p["page_no"] for p in native.get("prov", [])]
            # shortcut: interleaved same-page fragments need an ordering method before admission.
            if len(pages) != len(set(pages)):
                raise ValueError("same_page_multiple_fragments_order_unresolved")
            legacy.renderer.render(document, [{"id": row["target_ref"],
                "consumed_item_refs": [row["target_ref"]], "markdown": "SYNTHETICBOUNDARY"}])
            row.update(eligible=True, status="ready_not_scheduled")
        except ValueError as error:
            row.update(status="unsupported", reason=str(error))
    return rows


def main():
    import importlib.metadata
    sources = json.loads((REPO / "docs/research/pdf-core-g2-inline-2026-10-15/inputs/input-manifest.json").read_text())["sources"]
    root = REPO / "docs/research/pdf-core-native-round-2026-10-17/S0"
    records = []
    for source in sources:
        name = source["name"]
        path = root / name / "document.json"
        raw = json.loads(path.read_text())
        before = digest(raw)
        rows = plan(raw)
        assert digest(raw) == before
        pdf = REPO / source["source"]["path"]
        assert hashlib.sha256(pdf.read_bytes()).hexdigest() == source["source"]["sha256"]
        version = json.loads((root / name / "result.json").read_text())["version"]
        assert (version["docling_slim_version"],version["docling_core_version"],version["docling_parse_version"]) == ("2.132.0","2.99.0","7.22.3")
        records.append({"source": name,"pdf": source["source"], "physical_pages": list(raw["pages"]),
                        "document_path": str(path.relative_to(REPO)), "document_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "upstream": "cached-S0", "version": version, "rows": rows,
                        "all_native_items_preserved": True})
    result = {"format":"stage1-A-inventory-v1", "method_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "sources":records,"next_stage_jobs_candidate_count":sum(r["eligible"] for s in records for r in s["rows"]),
              "N_CF":None,"N_CF_unready_reason":"Source census comparison and full coverage gate pending; requests/caps not frozen",
              "model_calls":0,"oracle_reads":0,"weights_loaded":0,
              "official":"Pinned public Core model validation and Markdown serializer extension interfaces",
              "custom":"Native geometry/ownership inventory, whole-owner response protocol and marker substitution"}
    (HERE / "inventory.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({"sources":len(records),"candidate_jobs":result["next_stage_jobs_candidate_count"],
                      "unsupported":sum(not r["eligible"] for s in records for r in s["rows"])}))


if __name__ == "__main__":
    main()
