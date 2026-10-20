"""Evaluator-only exposed DEV coverage comparison; never supplies producer jobs."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pypdfium2 as pdf

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OLD = REPO / "docs/research/pdf-core-stage1-2026-10-17"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def contains(fragment, page, x, y):
    if fragment["physical_page_1based"] != page:
        return False
    left, top, right, bottom = fragment["bbox_top_left_points"]
    return left - 2 <= x <= right + 2 and top - 2 <= y <= bottom + 2


def measure(rows, points, page):
    hits = Counter()
    discovered = eligible = 0
    responsibilities = Counter()
    for _, x, y in points:
        matches = [row for row in rows if any(contains(f, page, x, y) for f in row["fragments"])]
        discovered += bool(matches)
        eligible += any(row["eligible"] for row in matches)
        hits.update(row["target_ref"] for row in matches)
        responsibilities.update({row.get("responsibility", "historical") for row in matches})
    status = ("eligible_scope_present" if eligible == len(points) else
              "partial_eligible_scope" if eligible else
              "discovered_unsupported" if discovered else "not_discovered")
    return {"source_chars": len(points), "discovered_chars": discovered, "eligible_chars": eligible,
            "geometry_status": status, "matching_rows": dict(hits),
            "glyph_responsibilities": dict(responsibilities)}


def main():
    registration = read(HERE / "comparison-registration.json")
    invpath = REPO / registration["inventory_path"]
    assert sha(invpath) == registration["inventory_sha256"]
    assert sha(REPO / registration["method_path"]) == registration["method_sha256"]
    inventory = read(invpath)
    census_path = OLD / "A-evaluator/source-census.json"
    freeze = read(OLD / "A-evaluator/source-census.freeze.json")
    assert sha(census_path) == freeze["sha256"]
    census = read(census_path)
    original = read(OLD / "A-evaluator/producer-coverage-comparison.json")
    old_inventory = read(OLD / "A/inventory.json")
    assert sha(OLD / "A/inventory.json") == original["producer_inventory_sha256"]
    points, heights, rows, provenance = {}, {}, {}, []
    for source in inventory["sources"]:
        name = source["source"]
        path = REPO / source["document_path"]
        assert sha(path) == source["document_sha256"]
        pdf_path = REPO / source["pdf"]["path"]
        assert sha(pdf_path) == source["pdf"]["sha256"]
        document = pdf.PdfDocument(pdf_path)
        for number in source["physical_pages"]:
            page = document[int(number) - 1]
            heights[name, int(number)] = page.get_height()
            textpage = page.get_textpage()
            raw = textpage.get_text_range()
            assert len(raw.encode("utf-16-le")) // 2 == textpage.count_chars()
            assert raw.replace("\r", "") == (OLD / f"A-evaluator/{name}-p{number}.txt").read_text()
            glyphs = []
            utf16_index = normalized_index = 0
            for char in raw:
                if char != "\r":
                    if not char.isspace():
                        index = pdf.raw.FPDFText_GetCharIndexFromTextIndex(textpage.raw, utf16_index)
                        assert index >= 0
                        left, bottom, right, top = textpage.get_charbox(index)
                        glyphs.append((normalized_index, (left + right) / 2,
                                       page.get_height() - (bottom + top) / 2))
                    normalized_index += 1
                utf16_index += 2 if ord(char) > 0xffff else 1
            points[name, int(number)] = glyphs
        new_rows = []
        for row in source["rows"]:
            # Cells inherit a table envelope, not a source-proven cell bounding box.
            if "/data/table_cells/" in row["target_ref"]:
                continue
            fragments = []
            for prov in row["native_provenance"]:
                box = prov["bbox"]
                if box["coord_origin"] == "BOTTOMLEFT":
                    height = heights[name, prov["page_no"]]
                    bounds = [box["l"], height - box["t"], box["r"], height - box["b"]]
                else:
                    assert box["coord_origin"] == "TOPLEFT"
                    bounds = [box["l"], box["t"], box["r"], box["b"]]
                fragments.append({"physical_page_1based": prov["page_no"], "bbox_top_left_points": bounds})
            new_rows.append({**row, "fragments": fragments})
        rows[name] = new_rows
        provenance.append({"source": name, "document_path": str(path.relative_to(REPO)),
                           "document_sha256": sha(path), "pdf_path": str(pdf_path.relative_to(REPO)),
                           "pdf_sha256": sha(pdf_path)})

    historical_rows = {source["source"]: [{**row, "fragments": [fragment
        for entry in row.get("scope", {}).get("entries", []) for fragment in entry["fragments"]]}
        for row in source["rows"]] for source in old_inventory["sources"]}
    target_results = []
    for unit, previous in zip(census["targets"], original["targets"], strict=True):
        assert unit["id"] == previous["census_id"]
        start, end = unit["span"]["char_0based_halfopen"]
        glyphs = [point for point in points[unit["source"], unit["physical_page"]]
                  if start <= point[0] < end]
        check = measure(historical_rows[unit["source"]], glyphs, unit["physical_page"])
        assert (check["source_chars"], check["discovered_chars"], check["eligible_chars"]) == (
            previous["char_centers_evaluated"], previous["discovered_char_centers"],
            previous["eligible_char_centers"])
        new = measure(rows[unit["source"]], glyphs, unit["physical_page"])
        target_results.append({"census_id": unit["id"], "source": unit["source"],
                               "physical_page": unit["physical_page"], "kind": unit["kind"], **new,
                               "previous_geometry_status": previous["status"],
                               "source_visual_targets": unit["visual_targets"],
                               "source_requirements": unit["requirements"]})

    negatives = []
    for unit in census["ordinary_negatives"]:
        source = unit["source"]
        page = unit["physical_page"]
        lines = (OLD / f"A-evaluator/{source}-p{page}.txt").read_text().splitlines(keepends=True)
        first, last = unit["lines_1based"]
        start, end = sum(map(len, lines[:first - 1])), sum(map(len, lines[:last]))
        glyphs = [point for point in points[source, page] if start <= point[0] < end]
        negatives.append({"negative_id": unit["id"], "source": source, "physical_page": page,
                          **measure(rows[source], glyphs, page)})

    def overlap(a, b):
        area = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
        intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
        return intersection / max(area, 1e-10)

    legacy = []
    old_contract = read(REPO / "docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json")
    for unit in old_contract["units"]:
        fragments = []
        for fragment in unit["scope_fragments"]:
            matches = []
            for row in rows[unit["source"]]:
                covered = max([overlap(fragment["bbox_top_left_points"], f["bbox_top_left_points"])
                    for f in row["fragments"] if f["physical_page_1based"] == fragment["physical_page_1based"]] + [0])
                if covered >= .45:
                    matches.append({"ref": row["target_ref"], "eligible": row["eligible"],
                                    "responsibility": row["responsibility"], "covered_fraction": covered})
            fragments.append({"physical_page": fragment["physical_page_1based"], "matches": matches})
        common = set.intersection(*[{m["ref"] for m in f["matches"] if m["eligible"]} for f in fragments])
        legacy.append({"old_unit_id": unit["unit_id"], "prior_prepared": unit["prior_prepared"],
                       "fragments": fragments, "common_eligible_refs": sorted(common),
                       "geometry_status": "eligible_source_owner_present" if common else "not_A_eligible"})

    value = {"format": "A-followup-independent-source-comparison-v1",
             "created_at": datetime.now(timezone.utc).isoformat(), "registration": registration,
             "source_census_freeze": freeze, "verified_sources": provenance,
             "targets": target_results, "target_geometry_counts": dict(Counter(r["geometry_status"] for r in target_results)),
             "ordinary_negatives": negatives,
             "ordinary_geometry_counts": dict(Counter(r["geometry_status"] for r in negatives)),
             "legacy41": legacy, "legacy_geometry_counts": dict(Counter(r["geometry_status"] for r in legacy)),
             "historical_geometry_selfcheck": "All 44 original glyph/discovery/eligibility counts reproduced exactly",
             "method": "Nonspace source glyph centers, 2pt envelope tolerance; old41 envelope overlap >=0.45 only a locator. Table cell rows excluded because their provenance is the whole table envelope.",
             "source_answers_leaked_to_producer": False, "model_calls": 0,
             "limits": "Geometry/responsibility are not source meaning or delivered reconstruction. Native literal preservation, legal transfer controls, actual source order and model quality are judged separately. 44 groups, old41 and 27 negatives are separate denominators, never API jobs."}
    with (HERE / "producer-coverage-comparison.json").open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({key: value[key] for key in ["target_geometry_counts", "ordinary_geometry_counts", "legacy_geometry_counts"]}))


if __name__ == "__main__":
    main()
