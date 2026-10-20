"""Seven unchanged saved payloads through the frozen new public Core seam."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        if isinstance(value, str):
            stream.write(value)
        else:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")


def main():
    registration = json.loads((HERE / "comparison-registration.json").read_text())
    method_path = REPO / registration["method_path"]
    assert sha(method_path) == registration["method_sha256"]
    spec = importlib.util.spec_from_file_location("frozen_a_method", method_path)
    method = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(method)
    inventory_path = REPO / registration["inventory_path"]
    assert sha(inventory_path) == registration["inventory_sha256"]
    inventory = json.loads(inventory_path.read_text())
    sources = {source["source"]: source for source in inventory["sources"]}
    previous_path = REPO / "docs/research/pdf-core-stage1-2026-10-17/A-evaluator/saved-payload-replay.json"
    previous = json.loads(previous_path.read_text())
    outcomes = []
    for prior in previous["outcomes"]:
        source_name = prior["old_unit_id"].split("/")[0]
        source = sources[source_name]
        source_path = REPO / source["document_path"]
        assert sha(source_path) == source["document_sha256"]
        raw = json.loads(source_path.read_text())
        before = method.digest(raw)
        ref = prior["current_target_ref"]
        bound = method.scope(raw, [ref])
        payload_path = Path(prior["payload_path"])
        assert sha(payload_path) == prior["payload_sha256"]
        payload = json.loads(payload_path.read_text())
        assert len(payload["blocks"]) == 1
        assert all(block["code_language"] is None for block in payload["blocks"])
        blocks = [{"kind": block["kind"], "segments": block["segments"],
                   "fragment_indices": list(range(len(bound["provenance"][ref])))}
                  for block in payload["blocks"]]
        parent = method.resolve(DoclingDocument.model_validate(raw), bound["parent_ref"])
        response = {"scope_sha256": method.digest(bound), "targets": {ref: blocks},
                    "order": [f"target:{ref}:0" if item.cref == ref else f"anchor:{item.cref}"
                              for item in parent.children]}
        result = method.apply_ordered(raw, bound, response)
        assert method.digest(raw) == before
        restored = DoclingDocument.model_validate(result["document"])
        assert restored.validate_tree(restored.body, raise_on_error=True)
        assert method.serialize(restored).text == result["markdown"]
        root = method.resolve(restored, result["binding"]["derived_items"][0]["derived_ref"])

        def leaves(item):
            return ([leaf for child in item.children for leaf in leaves(child.resolve(restored))]
                    if item.children else [(str(item.label), item.text)])

        descendants = leaves(root)
        expected_text = "".join(segment["text"] for block in payload["blocks"] for segment in block["segments"])
        assert "".join(text for _, text in descendants) == expected_text
        expected_math = [segment["text"] for block in payload["blocks"] for segment in block["segments"]
                         if segment["kind"] == "math"]
        assert [text for label, text in descendants if label == "formula"] == expected_math
        actual_markdown = method.MarkdownDocSerializer(doc=restored).serialize(item=root).text
        for literal, count in Counter(expected_math).items():
            assert actual_markdown.count(literal) >= count
        assert result["binding"]["scope"]["provenance"] == bound["provenance"]
        assert sha(payload_path) == prior["payload_sha256"]
        folder = HERE / "saved-payload-replay" / prior["old_unit_id"]
        save(folder / "response.json", response)
        save(folder / "result.json", result)
        save(folder / "document.md", result["markdown"])
        outcomes.append({"old_unit_id": prior["old_unit_id"], "target_ref": ref,
                         "protected_positive": prior["protected_positive"], "crosspage_join": prior["crosspage_join"],
                         "payload_path": str(payload_path), "payload_sha256": prior["payload_sha256"],
                         "typed_literal_sequence_preserved": True, "typed_math_sequence_preserved": True,
                         "math_literals_in_markdown": True, "non_target_anchor_serialization_unchanged": True,
                         "source_provenance_in_binding_preserved": True, "json_reload_and_stock_markdown_pass": True,
                         "math_segments": len(expected_math),
                         "historical_internal_paragraph_breaks_retained": "\n\n" in expected_text,
                         "new_model_quality": "not evaluated", "source_semantic_acceptance": False})
    report = {"completed_at": datetime.now(timezone.utc).isoformat(),
              "inventory_sha256": registration["inventory_sha256"], "method_sha256": registration["method_sha256"],
              "previous_replay_path": str(previous_path.relative_to(REPO)), "previous_replay_sha256": sha(previous_path),
              "outcomes": outcomes, "unique_payloads": len(outcomes),
              "protected_positives_transport_pass": sum(o["protected_positive"] for o in outcomes),
              "crosspage_joins_transport_pass": sum(o["crosspage_join"] for o in outcomes), "model_calls": 0,
              "wrapper_adaptation": "Keep block kinds and segment literals unchanged; replace historical crop-relative bbox/null code_language metadata with pinned native scope/fragment provenance and order tokens.",
              "limit": "Only the evaluator wrapper changed. Saved payload values/segmentation were not repaired. Transport does not establish source correctness or new model quality; inherited internal paragraph breaks remain."}
    save(HERE / "saved-payload-replay.json", report)
    print(json.dumps({key: report[key] for key in ["unique_payloads", "protected_positives_transport_pass", "crosspage_joins_transport_pass"]}))


if __name__ == "__main__":
    main()
