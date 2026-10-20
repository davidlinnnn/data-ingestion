"""Map saved parser geometry to source pages; never edit recognition output."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def top_left(bbox, height):
    if bbox.get("coord_origin") == "BOTTOMLEFT":
        return [bbox["l"], height - bbox["t"], bbox["r"], height - bbox["b"]]
    assert bbox.get("coord_origin") == "TOPLEFT"
    return [bbox["l"], bbox["t"], bbox["r"], bbox["b"]]


def intersection(box, placement):
    x, y, width, height = placement
    result = [max(box[0], x), max(box[1], y), min(box[2], x + width), min(box[3], y + height)]
    return result if result[2] > result[0] and result[3] > result[1] else None


def mapped(box, matrix):
    points = [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]]
    transformed = [[matrix[0][0] * x + matrix[0][1] * y + matrix[0][2],
                    matrix[1][0] * x + matrix[1][1] * y + matrix[1][2]] for x, y in points]
    return {"polygon_top_left_points": transformed,
            "bbox_top_left_points": [min(p[0] for p in transformed), min(p[1] for p in transformed),
                                     max(p[0] for p in transformed), max(p[1] for p in transformed)]}


def main():
    assert intersection([0, 0, 20, 20], [5, 7, 10, 10]) == [5, 7, 15, 17]
    assert intersection([0, 0, 2, 2], [5, 7, 10, 10]) is None
    assert mapped([3, 6, 9, 12], [[1/3, 0, 2], [0, 1/3, 4], [0, 0, 1]])["bbox_top_left_points"] == [3, 6, 5, 8]
    counts = {}
    for phase in ["page", "paragraph"]:
        for folder in sorted((HERE / phase / "runs").iterdir()):
            if not (folder / "source-input.json").exists():
                continue
            source = json.loads((folder / "source-input.json").read_text())
            mapping_path = folder / "source-mapping.json"
            if not mapping_path.exists():
                continue
            source_mapping = json.loads(mapping_path.read_text())
            docs = [folder / "document.json"] if phase == "page" else [folder / "official-parser-component/document.json"]
            docs.append(folder / "token-aware-parser-candidate/document.json")
            for doc_path in docs:
                if not doc_path.exists():
                    continue
                document = json.loads(doc_path.read_text())
                rows = []
                for kind in ["texts", "tables", "pictures", "groups"]:
                    for item in document.get(kind, []):
                        for prov in item.get("prov", []):
                            page = document["pages"][str(prov["page_no"])]
                            box = top_left(prov["bbox"], page["size"]["height"])
                            fragments = []
                            if phase == "page":
                                points = source_mapping["source_page_size_points"]
                                matrix = [[points["width"] / page["size"]["width"], 0, 0],
                                          [0, points["height"] / page["size"]["height"], 0], [0, 0, 1]]
                                fragments.append({"original_physical_page_1based": source["physical_page_1based"],
                                                  "parser_to_source_matrix_3x3": matrix, **mapped(box, matrix)})
                            else:
                                for fragment in source["fragments"]:
                                    overlap = intersection(box, fragment["paragraph_canvas_xywh"])
                                    if overlap is not None:
                                        matrix = fragment["paragraph_pixels_to_source_top_left_points_3x3"]
                                        fragments.append({"original_physical_page_1based": fragment["physical_page_1based"],
                                            "paragraph_overlap_pixels": overlap, "paragraph_to_source_matrix_3x3": matrix,
                                            "producer_fragment_charspan": fragment["provider_provenance"]["charspan"], **mapped(overlap, matrix)})
                            rows.append({"item_ref": item["self_ref"], "label": item["label"], "parser_provenance": prov,
                                "parser_bbox_top_left_pixels": box, "source_fragments": fragments,
                                "mapping_status": "mapped_intersection" if fragments else "no_fragment_overlap"})
                target = doc_path.parent / "source-mapped-geometry.json"
                target.write_text(json.dumps({"basis": "Model-produced parser geometry only; intersections bind geometry, not character/formula semantics. No source coordinate or physical page rewritten in document.",
                    "source": source, "document_path": str(doc_path.relative_to(HERE)), "items": rows}, ensure_ascii=False, indent=2) + "\n")
                counts[str(doc_path.relative_to(HERE))] = len(rows)
    (HERE / "mapped-geometry-check.json").write_text(json.dumps({"self_check": "passed", "mapped_documents": counts}, indent=2) + "\n")
    print(json.dumps({"mapped_documents": len(counts), "self_check": "passed"}))


if __name__ == "__main__":
    main()
