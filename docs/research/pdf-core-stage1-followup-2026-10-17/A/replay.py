"""One cached-source transport replay per source; mock text is not source truth."""
import hashlib
import json
from pathlib import Path
import sys

from docling_core.types.doc import DoclingDocument, DocItemLabel
import method as m


def mock_response(doc, bound):
    targets = bound["targets"]
    blocks = {}
    for ref in targets:
        item = m.resolve(doc, ref)
        kind = {DocItemLabel.FORMULA: "formula", DocItemLabel.CODE: "code",
                DocItemLabel.SECTION_HEADER: "heading"}.get(item.label, "paragraph")
        blocks[ref] = [{"fragment_indices": list(range(len(item.prov))), "kind": kind,
                        "segments": [{"kind": {"formula": "math", "code": "code"}.get(kind, "text"),
                                      "text": item.text or r"x_{\mathrm{MOCK}}"}]}]
    order = [(f"target:{ref.cref}:0" if ref.cref in targets else "anchor:" + ref.cref)
             for ref in m.resolve(doc, bound["parent_ref"]).children]
    return {"scope_sha256": m.digest(bound), "targets": blocks, "order": order}


def main():
    inventory = json.loads((m.HERE / "inventory.json").read_text())
    records = []
    for source in inventory["sources"]:
        path = m.REPO / source["document_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["document_sha256"]
        raw = json.loads(path.read_text())
        doc = DoclingDocument.model_validate(raw)
        targets = [row["target_ref"] for row in source["rows"]
                   if row["responsibility"] == "body" and row["eligible"] and row["parent_ref"] == "#/body"]
        bound = m.scope(raw, targets)
        response = mock_response(doc, bound)
        result = m.apply_ordered(raw, bound, response)
        restored = DoclingDocument.model_validate_json(json.dumps(result["document"]))
        assert m.serialize(restored).text == result["markdown"]
        assert restored.validate_tree(restored.body, raise_on_error=True)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["document_sha256"]
        folder = m.HERE / "mock-replay" / source["source"]
        folder.mkdir(parents=True, exist_ok=True)
        for name, value in {"document.json": result["document"], "response.json": response,
                            "binding.json": result["binding"]}.items():
            with (folder/name).open("x") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2); stream.write("\n")
        with (folder/"document.md").open("x") as stream:
            stream.write(result["markdown"])
        records.append({"source": source["source"], "target_owners": len(targets),
                        "delivered_derived_blocks": len(result["binding"]["derived_items"]),
                        "anchors": len(bound["anchors"]), "reload_passed": True,
                        "native_original_unchanged": True, "source_reading_order_verified": False,
                        "empty_native_formula_mock_count": sum(not m.resolve(doc, ref).text for ref in targets),
                        "outside_parent_body_group_targets_not_replayed": sum(
                            row["responsibility"] == "body" and row["eligible"] and row["parent_ref"] != "#/body"
                            for row in source["rows"])})
    report = {"sources": records, "model_calls": 0, "source_quality_verified": False,
              "policy": "Native direct-sibling order, one block per owner; empty source formulas use explicit MOCK placeholder. This validates public Core transport and reload only, not source order or transcription.",
              "separate_ordering_control": "controls/interleaved-fragments/document.md",
              "inventory_sha256": hashlib.sha256((m.HERE/"inventory.json").read_bytes()).hexdigest()}
    with (m.HERE/"replay-results.json").open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps(report, ensure_ascii=False))


def group_replay():
    inventory = json.loads((m.HERE/"inventory.json").read_text())
    records = []
    for source in inventory["sources"]:
        path = m.REPO/source["document_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["document_sha256"]
        raw = json.loads(path.read_text())
        doc = DoclingDocument.model_validate(raw)
        parents = sorted({row["parent_ref"] for row in source["rows"]
                          if row["responsibility"] == "body" and row["eligible"] and row["parent_ref"] != "#/body"})
        for parent in parents:
            targets = [row["target_ref"] for row in source["rows"]
                       if row["responsibility"] == "body" and row["eligible"] and row["parent_ref"] == parent]
            bound = m.scope(raw, targets)
            result = m.apply_ordered(raw, bound, mock_response(doc, bound))
            restored = DoclingDocument.model_validate(result["document"])
            assert m.serialize(restored).text == result["markdown"]
            assert restored.validate_tree(restored.body, raise_on_error=True)
            folder = m.HERE/"group-replay"/source["source"]/parent.removeprefix("#/").replace("/", "-")
            folder.mkdir(parents=True, exist_ok=True)
            with (folder/"result.json").open("x") as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2); stream.write("\n")
            with (folder/"document.md").open("x") as stream:
                stream.write(result["markdown"])
            records.append({"source": source["source"], "parent_ref": parent, "target_owners": len(targets),
                            "delivered_derived_blocks": len(result["binding"]["derived_items"]),
                            "output": str(folder.relative_to(m.HERE)), "reload_passed": True,
                            "scope": "separate cached-source group transport control; not a combined enhanced document"})
    report = {"groups": records, "model_calls": 0, "source_quality_verified": False,
              "inventory_sha256": hashlib.sha256((m.HERE/"inventory.json").read_bytes()).hexdigest()}
    with (m.HERE/"group-replay-results.json").open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps(report, ensure_ascii=False))


def picture_replay():
    inventory = json.loads((m.HERE/"inventory.json").read_text())
    records = []
    for source in inventory["sources"]:
        raw = json.loads((m.REPO/source["document_path"]).read_text())
        doc = DoclingDocument.model_validate(raw)
        for row in source["rows"]:
            if row.get("disposition") != "formula_picture_envelope":
                continue
            picture = m.resolve(doc, row["target_ref"])
            children = [ref.resolve(doc) for ref in picture.children]
            blocks = [{"fragment_indices": list(range(len(child.prov))), "kind": "formula",
                       "segments": [{"kind": "math", "text": child.text or r"x_{\mathrm{MOCK}}"}]} for child in children]
            result = m.expose_formula_picture(raw, picture.self_ref, blocks)
            restored = DoclingDocument.model_validate(result["document"])
            assert m.serialize(restored).text == result["markdown"]
            assert restored.validate_tree(restored.body, raise_on_error=True)
            derived_picture = m.resolve(restored, result["binding"]["derived_picture_ref"])
            assert derived_picture.image == picture.image and derived_picture.prov == picture.prov
            folder = m.HERE/"picture-replay"/source["source"]/picture.self_ref.removeprefix("#/").replace("/", "-")
            folder.mkdir(parents=True, exist_ok=True)
            with (folder/"result.json").open("x") as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2); stream.write("\n")
            with (folder/"document.md").open("x") as stream:
                stream.write(result["markdown"])
            records.append({"source": source["source"], "picture_ref": picture.self_ref,
                            "formula_children": len(children), "reload_passed": True,
                            "original_image_field_preserved": derived_picture.image == picture.image,
                            "output": str(folder.relative_to(m.HERE)), "source_quality_verified": False})
    report = {"formula_pictures": records, "model_calls": 0,
              "scope": "Independent native/MOCK picture envelope transport controls; no transcription score",
              "inventory_sha256": hashlib.sha256((m.HERE/"inventory.json").read_bytes()).hexdigest()}
    with (m.HERE/"picture-replay-results.json").open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    if "--groups" in sys.argv:
        group_replay()
    elif "--pictures" in sys.argv:
        picture_replay()
    else:
        main()
