"""Corpus accuracy of the #132 local enrichment methods against the #84 gold.

    env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t3-accuracy/run.py ARCHIVE [CACHE]

ARCHIVE is the untracked tree that holds the #84 evidence and the pilot corpus
(docs/research/..., docs/fixtures/...). Gold answers quote third-party papers, so they stay
there; this script writes only scores, ids and hashes to evidence.json next to it. CACHE, an
existing directory outside the repo, keeps each paper's pipeline output between runs.

Each paper runs through the real stages in process (prepare, parse, assemble, inventory,
enrich_local) with the DEV profile and an in-memory store, as the workers would run them.

  picture-ocr   #84 image gold (round2 evaluator), pilot images. Each gold picture is matched
                to an inventory item on its page by box overlap; the item's OCR lines are scored
                with #84's score_ocr_v2 (literal, NFKC, whitespace removed). Baseline: the #84
                round-4 automatic score on the same items.
  code          #84 code units comparable on a fixed source region (13). The code method runs
                on the union box of the unit's regions; raw CER and operator and number
                sequences use #84's metrics.compare. Baseline: #84's native channel per unit.
                Inventory coverage: whether an inventory code item overlaps the region.
  table-status  #84 E0 tables of the pilot papers with a decided verdict (PASS or FAIL). Each
                is matched to an inventory table item by page and box overlap; the item's grid
                is compared cell by cell with the E0 table that #84 adjudicated.
"""

import asyncio
import csv
import hashlib
import importlib.util
import json
import statistics
import sys
from pathlib import Path

from kp_processing.methods import code
from kp_processing.ports.clock import FakeClock
from kp_processing.ports.object_store import DictObjectStore
from kp_processing.ports.status_reporter import RecordingStatusReporter
from kp_processing.profile import load_profile
from kp_processing.stages import (
    AssembleInput,
    EnrichInput,
    GroupInput,
    InventoryInput,
    Ports,
    PrepareInput,
    Runtime,
    enrich_local,
    inventory,
    parse,
    prepare,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RESEARCH = "docs/research"
CORPUS = "docs/fixtures/agent-self-evolution-pilot-2026-10-11"
OCR_GOLD = f"{RESEARCH}/pdf-core-r1-method-2026-10-20/live-preflight"
CODE_GOLD = f"{RESEARCH}/pdf-core-w3b-2026-10-20/code-native-v4-utf16"
TABLE_GOLD = f"{RESEARCH}/pdf-core-w3b-2026-10-20"
E0_JOBS = f"{RESEARCH}/pdf-core-w2-native-coverage-round3-2026-10-20/runs/V3_B/jobs"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def box(b) -> tuple[float, float, float, float]:
    """(left, bottom, right, top) in BOTTOMLEFT PDF points from a docling dict or a list."""
    if isinstance(b, dict):
        assert b.get("coord_origin", "BOTTOMLEFT") == "BOTTOMLEFT"
        return b["l"], b["b"], b["r"], b["t"]
    return tuple(b)  # type: ignore[return-value]


def iou(a, b) -> float:
    (al, ab, ar, at), (bl, bb, br, bt) = box(a), box(b)
    w, h = min(ar, br) - max(al, bl), min(at, bt) - max(ab, bb)
    inter = max(w, 0) * max(h, 0)
    union = (ar - al) * (at - ab) + (br - bl) * (bt - bb) - inter
    return inter / union if union > 0 else 0.0


async def through_enrichment(pdf: bytes, runtime: Runtime) -> dict:
    """The paper's assembly, inventory items and outcome records, from the real stages."""
    ports = Ports(DictObjectStore(), RecordingStatusReporter(), FakeClock())
    digest = sha(pdf)
    await ports.store.put_if_absent(f"custody/{digest}", pdf)
    start = {
        "request_id": f"acc_{digest[:12]}", "document_uid": f"doc_{digest[:12]}",
        "source_revision_id": "srv_1", "adopted_version": runtime.profile.profile,
        "adoption_sequence": 1, "initiator": "source", "priority": "normal",
        "trace_id": "0", "files": [{"path": "paper.pdf", "role": "main",
        "custody_ref": f"s3://kp-dev/custody/{digest}", "sha256": digest, "size": len(pdf),
        "media_type": "application/pdf"}],
    }  # fmt: skip
    uid = start["document_uid"]
    plan = await prepare.run(PrepareInput(start, "run_1"), ports, runtime)
    groups = [
        await parse.run_group(
            GroupInput(uid, plan.source_key, plan.source_sha256, pages), ports, runtime
        )
        for pages in plan.groups
    ]
    assembly = await parse.run_assemble(
        AssembleInput(uid, plan.source_key, plan.source_sha256, groups), ports, runtime
    )
    inv = await inventory.run(
        InventoryInput(uid, plan.source_key, plan.source_sha256, groups, assembly), ports, runtime
    )
    outcomes = await enrich_local.run(EnrichInput(uid, inv), ports, runtime)
    items = json.loads(await ports.store.get(inv.ref))["items"]
    records = {o.item_id: json.loads(await ports.store.get(o.ref)) for o in outcomes}
    lines = {}
    for item_id, record in records.items():
        if record["provider_artifact_ref"]:
            lines[item_id] = json.loads(await ports.store.get(record["provider_artifact_ref"]))
    return {"items": items, "records": records, "provider": lines,
            "assembly": json.loads(await ports.store.get(assembly.ref))["document"]}  # fmt: skip


def best(items: list[dict], method: str, page: int, target) -> tuple[dict | None, float]:
    candidates = [(iou(i["bbox"], target), i) for i in items
                  if i["method"] == method and i["page"] == page]  # fmt: skip
    if not candidates:
        return None, 0.0
    overlap, item = max(candidates, key=lambda pair: pair[0])
    return (item, overlap) if overlap >= 0.5 else (None, overlap)


# Sample sizes of the #84 gold this script scores; a smaller sample means a broken measurement.
OCR_ITEMS, OCR_IMAGES, CODE_UNITS, TABLES = 358, 18, 13, 15


def score_ocr(archive: Path, papers: dict[str, dict]) -> dict:
    scorer = load(archive / OCR_GOLD / "round4-local-ocr/score_ocr_v2.py", "score_ocr_v2")
    evaluator = archive / OCR_GOLD / "round2/evaluator"
    gold = json.loads((evaluator / "image-gold.json").read_text())["records"]
    refs = {r["index"]: r for r in json.loads((evaluator / "crop-source-references.json").read_text())}
    baseline = {r["id"]: r["state"] for r in json.loads(
        (archive / OCR_GOLD / "round4-local-ocr/ocr-score-v2.json").read_text())["records"]}  # fmt: skip
    rows = []
    for record in gold:
        name = record["source"]["path"].split("/")[-1]
        if name not in papers:
            continue
        native = refs[record["index"]]["crop"]["mapping"]["native_bbox"]
        item, overlap = best(papers[name]["items"], "picture-ocr", record["physical_page"], native)
        lines = papers[name]["provider"].get(item["item_id"], {"lines": []})["lines"] if item else []
        lines = [{"text": line["text"], "bbox": line["box"]} for line in lines]  # scorer's shape
        matched = scorer.assign(record["image_ocr_occurrences"], lines)
        for unit in record["image_ocr_occurrences"]:
            rows.append({"image_index": record["index"], "paper": name, "unit": unit["id"],
                         "item_id": item["item_id"] if item else None, "overlap": round(overlap, 3),
                         "ours": matched[unit["id"]]["state"],
                         "baseline": baseline[unit["id"]]})  # fmt: skip
    ours = sum(r["ours"] == "PASS_LITERAL" for r in rows)
    base = sum(r["baseline"] == "PASS_LITERAL" for r in rows)
    images = {r["image_index"] for r in rows}
    unmatched = sorted({r["image_index"] for r in rows if r["item_id"] is None})
    return {"items": len(rows), "images": len(images), "unmatched_images": unmatched,
            "literal_pass": ours, "baseline_literal_pass": base,
            "bar": f"{OCR_ITEMS} items in {OCR_IMAGES} images, all matched, and "
                   "baseline_literal_pass <= literal_pass <= items",
            "pass": (len(rows), len(images), unmatched) == (OCR_ITEMS, OCR_IMAGES, [])
                    and base <= ours <= len(rows),
            "rows": rows}  # fmt: skip


def score_code(archive: Path, papers: dict[str, dict], pdfs: dict[str, bytes]) -> dict:
    metrics = load(archive / CODE_GOLD / "metrics.py", "code_metrics")
    gold = {u["unit_id"]: u for u in json.loads((archive / CODE_GOLD / "per-unit.json").read_text())}
    native = [r for r in csv.DictReader((archive / CODE_GOLD / "per-unit.csv").open())
              if r["channel"] == "native" and r["status"].startswith("COMPARABLE")]  # fmt: skip
    rows = []
    for unit in native:
        uid = unit["unit_id"]
        evidence = json.loads((archive / CODE_GOLD / "native-evidence" /
                               (uid.replace(":", "__") + ".json")).read_text())  # fmt: skip
        pdf_name = evidence["pdf"].split("/docs/", 1)[1]
        data = (archive / "docs" / pdf_name).read_bytes()
        assert sha(data) == evidence["pdf_sha256"]
        unions = {}  # page -> union box of the unit's regions on it; a unit may span pages
        for region in evidence["regions"]:
            l, b, r, t = region["bbox"]
            u = unions.setdefault(region["page"], {"l": l, "b": b, "r": r, "t": t,
                                                   "coord_origin": "BOTTOMLEFT"})  # fmt: skip
            u.update(l=min(u["l"], l), b=min(u["b"], b), r=max(u["r"], r), t=max(u["t"], t))
        outputs = [code.run({"page": page, "bbox": union}, [data])
                   for page, union in sorted(unions.items())]  # fmt: skip
        text = "\n".join(o.content for o in outputs if o.content)
        page, union = min(unions.items())
        reference = gold[uid]["source_text"]
        ours = metrics.compare(reference, text)
        own = metrics.compare(reference, evidence["text"])  # #84's own native text, re-scored
        paper = pdf_name.split("/")[-1]
        covered = None
        if paper in papers:
            item, _ = best(papers[paper]["items"], "code", page, union)
            covered = item is not None or any(
                i["method"] == "code" and i["page"] == page and iou(i["bbox"], union) > 0
                for i in papers[paper]["items"])  # fmt: skip
        rows.append({"unit": uid, "pages": sorted(unions),
                     "outcome": [o.outcome for o in outputs],
                     "cer": ours["raw"]["CER"], "baseline_cer": float(unit["CER"]),
                     "baseline_rescored_cer": own["raw"]["CER"],
                     "operators_exact": ours["operator_sequences"]["exact"],
                     "numbers_exact": ours["number_sequences"]["exact"],
                     "baseline_numbers_exact": unit["number_exact"] == "True",
                     "inventory_covers_region": covered})  # fmt: skip
    cers = [r["cer"] for r in rows if r["cer"] is not None]
    median = statistics.median(cers) if cers else None
    return {"units": len(rows), "cer_median": median,
            "baseline_cer_median": statistics.median(r["baseline_cer"] for r in rows),
            "operators_exact": sum(r["operators_exact"] for r in rows),
            "numbers_exact": sum(r["numbers_exact"] for r in rows),
            "baseline_numbers_exact": sum(r["baseline_numbers_exact"] for r in rows),
            "bar": f"{CODE_UNITS} units, 0 <= cer_median <= 0.037 and operators/numbers exact on "
                   "every unit #84 had exact",
            "pass": len(cers) == len(rows) == CODE_UNITS and median is not None
                    and 0 <= median <= 0.037 and all(
                r["operators_exact"] and (r["numbers_exact"] or not r["baseline_numbers_exact"])
                for r in rows),
            "rows": rows}  # fmt: skip


def cells(table: dict) -> list[tuple]:
    return sorted((c["start_row_offset_idx"], c["start_col_offset_idx"],
                   c["end_row_offset_idx"] - c["start_row_offset_idx"],
                   c["end_col_offset_idx"] - c["start_col_offset_idx"], c["text"].strip())
                  for c in table["data"]["table_cells"])  # fmt: skip


def score_tables(archive: Path, papers: dict[str, dict]) -> dict:
    final = json.loads((archive / TABLE_GOLD / "cell-matching-confirm/per-table-final.json").read_text())
    verdicts = {r["id"]: r["verdict"] for r in final
                if r["variant"] == "E0" and r["channel"] == "RAW" and r["verdict"] in ("PASS", "FAIL")}  # fmt: skip
    semantic = json.loads((archive / TABLE_GOLD / "table/results/E0-v4.json").read_text())
    rows = []
    for table in semantic["semantic_tables"]:
        if table["id"] not in verdicts or len(table["native_tables"]) != 1:
            continue
        e0 = table["native_tables"][0]
        job = table["job_id"]
        paper = job.removeprefix("P-") + ".pdf"
        if paper not in papers:
            continue
        doc = json.loads((archive / E0_JOBS / job / "document.json").read_text())
        node = doc["tables"][int(e0["ref"].split("/")[-1])]
        prov = e0["prov"][0]
        item, overlap = best(papers[paper]["items"], "table-status", prov["page_no"], prov["bbox"])
        row = {"table": table["id"], "verdict_84": verdicts[table["id"]], "overlap": round(overlap, 3),
               "item_id": item["item_id"] if item else None}  # fmt: skip
        if item:
            record = papers[paper]["records"][item["item_id"]]
            grid = record["content"]["grid"] if record["content"] else None
            ours = sorted((c["row"], c["col"], c["row_span"], c["col_span"], c["text"].strip())
                          for c in grid["cells"]) if grid else []  # fmt: skip
            theirs = cells(node)
            row.update({"outcome": record["outcome"], "cells": len(ours), "cells_84": len(theirs),
                        "identical": ours == theirs,
                        "differing_cells": len(set(ours) ^ set(theirs))})  # fmt: skip
        rows.append(row)
    identical = sum(bool(r.get("identical")) for r in rows)
    return {"tables": len(rows), "identical": identical,
            "pass_84": sum(r["verdict_84"] == "PASS" for r in rows),
            "fail_84": sum(r["verdict_84"] == "FAIL" for r in rows),
            "bar": f"all {TABLES} decided tables matched and cell-identical to the adjudicated "
                   "E0 output",
            "pass": identical == len(rows) == TABLES, "rows": rows}  # fmt: skip


async def main(archive: Path, cache: Path | None) -> None:
    runtime = Runtime(load_profile(REPO / "tests/profiles/paper-pdf-dev.yaml"), "acc-r1")
    manifest = json.loads((archive / CORPUS / "manifest.json").read_text())
    wanted = {"01", "03", "04", "05", "06", "07", "10", "11", "13", "15", "17", "19", "20"}
    papers, pdfs = {}, {}
    for paper in manifest["papers"]:
        if paper["file"][:2] not in wanted:
            continue
        data = (archive / CORPUS / paper["file"]).read_bytes()
        assert sha(data) == paper["sha256"]
        pdfs[paper["file"]] = data
        cached = cache / f"{paper['sha256']}.json" if cache else None
        if cached and cached.exists():
            papers[paper["file"]] = json.loads(cached.read_text())
        else:
            papers[paper["file"]] = await through_enrichment(data, runtime)
            if cached:
                cached.write_text(json.dumps(papers[paper["file"]]))
        print(paper["file"], len(papers[paper["file"]]["items"]), "items", flush=True)
    evidence = {
        "profile": runtime.profile.profile,
        "methods": {m.id: m.module_digest for m in runtime.profile.methods.values()},
        "papers": {name: sha(data) for name, data in pdfs.items()},
        "picture_ocr": score_ocr(archive, papers),
        "code": score_code(archive, papers, pdfs),
        "table_status": score_tables(archive, papers),
    }
    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=1) + "\n")
    for key in ("picture_ocr", "code", "table_status"):
        print(key, {k: v for k, v in evidence[key].items() if k != "rows"})


if __name__ == "__main__":
    cache = Path(sys.argv[2]) if len(sys.argv) > 2 else None  # pipeline outputs, outside git
    asyncio.run(main(Path(sys.argv[1]).expanduser(), cache))
