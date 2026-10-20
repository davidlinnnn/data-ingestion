"""Read-only evaluator: fixed 55-page regression inventory and source gates."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

from docling_core.types.doc import DoclingDocument, RefItem

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def norm(text):
    return re.sub(r"[\s-]+", "", unicodedata.normalize("NFKC", text).casefold())


def main():
    registration = json.loads((HERE / "registration.json").read_text())
    rows = []
    for scope in registration["ranges"]:
        baseline = REPO / scope["baseline"]
        assert sha256(baseline.read_bytes()).hexdigest() == scope["baseline_sha256"]
        dest = HERE / "native" / scope["range_id"]
        old = DoclingDocument.model_validate_json(baseline.read_text())
        new = DoclingDocument.model_validate_json((dest / "document.json").read_text())
        conversion = json.loads((dest / "conversion.json").read_text())
        assert conversion["status"] == "success"
        assert sorted(old.pages) == sorted(new.pages) == list(range(scope["first"], scope["last"]+1))
        left = Counter(c.text for t in old.tables for c in t.data.table_cells)
        right = Counter(c.text for t in new.tables for c in t.data.table_cells)
        rows.append({"range_id": scope["range_id"], "pages": sorted(new.pages),
                     "conversion": conversion, "old_counts": {k: len(getattr(old, k)) for k in ("texts", "tables", "pictures")},
                     "new_counts": {k: len(getattr(new, k)) for k in ("texts", "tables", "pictures")},
                     "table_shapes_before": [[t.data.num_rows, t.data.num_cols] for t in old.tables],
                     "table_shapes_after": [[t.data.num_rows, t.data.num_cols] for t in new.tables],
                     "table_cell_strings_only_in_baseline": list((left-right).elements()),
                     "table_cell_strings_only_in_candidate": list((right-left).elements()),
                     "candidate_json_sha256": sha256((dest / "document.json").read_bytes()).hexdigest(),
                     "comparison_limit": "String/shape changes are diagnostics, not numeric accuracy or proof of semantic regressions. Both corpora are exposed DEV."})
    assert len(rows) == 19 and sum(len(r["pages"]) for r in rows) == 55
    seal = DoclingDocument.model_validate_json((HERE / "native/SRC11-cached-seal/document.json").read_text())
    title = next(t for t in seal.texts if "RL Outer Loop Iteration" in t.text)
    picture = seal.pictures[0]
    box, title_box = picture.prov[0].bbox, title.prov[0].bbox
    title_contained = box.l <= title_box.l and box.r >= title_box.r and box.b <= title_box.b and box.t >= title_box.t
    assert not title_contained and title.text.endswith(" t")
    picture.get_image(seal).save(HERE / "candidate-seal-figure1.png")
    reason = DoclingDocument.model_validate_json((HERE / "native/SRC13-p09-09/document.json").read_text())
    picture5 = reason.pictures[1]
    caption = " ".join(RefItem(cref=r.cref).resolve(reason).text for r in picture5.captions)
    expected = "Figure 5 | Snapshot of MaTTS on WebArena-Shopping subset with different memory mechanisms with k = 5. We compute BoN for all 5 trajectories and Pass@1 with one randomly selected trajectory."
    caption_equivalent = norm(caption) == norm(expected)
    assert caption_equivalent, "Do not equate absence of pollution alone with complete source-caption recovery"
    picture5.get_image(reason).save(HERE / "candidate-reasoningbank-figure5.png")
    result = {"fixed_pages": 55, "ranges": rows,
              "source_gates": {
                  "SEAL": {"native_crop_title_complete": title_contained, "canonical_body_title": title.text,
                           "title_provenance": title.prov[0].model_dump(mode="json"), "picture_provenance": box.model_dump(mode="json"),
                           "interpretation": "Canonical title is preserved (now including t), but still outside the native picture crop and not linked as its child."},
                  "ReasoningBank": {"original_caption_semantically_recovered": caption_equivalent,
                                    "actual_caption": caption, "source_expected": expected,
                                    "minor_differences": "MaTTS case and WebArena-Shopping line-break hyphen; existing minor tolerance applies."}},
              "total_conversion_seconds": sum(r["conversion"]["seconds"] for r in rows),
              "native_pictures": sum(r["new_counts"]["pictures"] for r in rows),
              "C_enrichment_gate": "blocked: SEAL source image boundary still incomplete",
              "new_component_enrichment_calls": 0, "new_remote_calls": 0,
              "full_55_page_semantic_accuracy_claim": False,
              "production_routing_rule_validated": False,
              "candidate_promoted": False}
    old_cpu = REPO / "docs/research/pdf-core-eval-interfaces-2026-10-18/C/native"
    matched = [r for r in rows if (old_cpu / r["range_id"] / "conversion.json").exists()]
    result["matched_44_page_conversion_cost"] = {
        "pages": sum(len(r["pages"]) for r in matched),
        "baseline_seconds": sum(json.loads((old_cpu/r["range_id"]/"conversion.json").read_text())["seconds"] for r in matched),
        "candidate_seconds": sum(r["conversion"]["seconds"] for r in matched),
        "limit": "Same registered ranges and hardware; sequential runs, no repeated latency distribution or formal SLO."}
    with (HERE / "comparison.json").open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({k: result[k] for k in ("fixed_pages", "native_pictures", "source_gates", "matched_44_page_conversion_cost", "C_enrichment_gate")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
