"""#210: the code items of the inventory, on the 20 corpus papers and W2, with parse and
inventory only (no VLM).

    scripts/heavy-lock 210-inventory -- env HF_HUB_OFFLINE=1 PYTHONPATH=. .venv/bin/python \\
        docs/validation/210/run.py run OUT CORPUS_MANIFEST ARCHIVE LABEL
    PYTHONPATH=. .venv/bin/python docs/validation/210/run.py compare OUT CORPUS_MANIFEST ARCHIVE

run reuses #212's run: the stages run in process on paper-pdf@1.yaml with #212's file-backed
object store under OUT/store, whose keys carry the source and method digests, so a rerun of the
same code reuses the parse. It writes OUT/LABEL.json: per paper the source sha256, the
docling-parse module digest, every inventory item as {item_id, method, page, bbox} and every
text node as {self_ref, label, page}; and OUT/LABEL-text.json, outside the repo, the orig of
every code node, for review.

compare reads OUT/before.json and OUT/after.json and writes inventory.json here: per paper the
items each method gained and lost, matched by method, page and box, since a split renumbers the
text refs after it, and for each code item gained the label of the node with its page and box
before (None: a node the split added); and codes.json here: for each of #84's 13 code units, the share
of its gold characters (outside spaces) whose centre lies in a code item's box of its page,
before and after, and code@1's output on the code items that overlap the unit's regions,
scored with #84's metrics like #199's score.py (CER, operators and numbers exact); and
manifest.json here: each paper's sha256 and the sha256 of OUT/before.json and OUT/after.json.
Paper text stays out.
"""

import asyncio
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

from kp_canonicalization.methods import code
from kp_canonicalization.ports.status_reporter import RecordingStatusReporter
from kp_canonicalization.profile import load_profile
from kp_canonicalization.stages import (
    AssembleInput,
    GroupInput,
    InventoryInput,
    Ports,
    PrepareInput,
    Runtime,
    inventory,
    parse,
    prepare,
)
from tests.stages.conftest import start_input

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PROFILE = REPO / "src/kp_canonicalization/profiles/paper-pdf@1.yaml"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run212 = load(HERE.parent / "212/run.py", "run212")
t3 = load(HERE.parent / "80/t3-accuracy/run.py", "t3")
FileStore = run212.FileStore  # what 212/heldout.py imports from "run"


def papers(manifest: Path, archive: Path) -> list[tuple[str, Path, str | None]]:
    listed = [(str(p["index"]), manifest.parent / p["file"], p["sha256"])
              for p in json.loads(manifest.read_text())["papers"]]  # fmt: skip
    return [*listed, ("w2", archive / run212.W2, None)]


async def paper(ports: Ports, runtime: Runtime, data: bytes, uid: str) -> tuple[dict, dict]:
    start = await start_input(ports, data, f"req_{uid}", adopted_version=runtime.profile.id,
                              document_uid=uid)  # fmt: skip
    plan = await prepare.run(PrepareInput(start=start, run_id="run_1"), ports, runtime)
    groups = [
        await parse.run_group(GroupInput(uid, plan.source_key, plan.source_sha256, pages),
                              ports, runtime)  # fmt: skip
        for pages in plan.groups
    ]
    assembly = await parse.run_assemble(
        AssembleInput(uid, plan.source_key, plan.source_sha256, groups), ports, runtime
    )
    inv = await inventory.run(
        InventoryInput(uid, plan.source_key, plan.source_sha256, groups, assembly), ports, runtime
    )
    document = json.loads(await ports.store.get(assembly.ref))["document"]
    items = json.loads(await ports.store.get(inv.ref))["items"]
    found = {
        "sha256": plan.source_sha256,
        "parse_module_digest": runtime.profile.methods["docling-parse"].module_digest,
        "items": [{key: item.get(key) for key in ("item_id", "method", "page", "bbox")}
                  for item in items],  # fmt: skip
        "texts": [{"self_ref": n["self_ref"], "label": n["label"],
                   "page": n["prov"][0]["page_no"] if n["prov"] else None,
                   "bbox": n["prov"][0]["bbox"] if n["prov"] else None}
                  for n in document["texts"]],  # fmt: skip
    }
    origs = {n["self_ref"]: n["orig"] for n in document["texts"] if n["label"] == "code"}
    return found, origs


async def main(out: Path, manifest: Path, archive: Path, label: str) -> None:
    ports = Ports(store=FileStore(out / "store"), reporter=RecordingStatusReporter())
    runtime = Runtime(profile=load_profile(PROFILE), build_id="210", custody_bucket="kp-dev")
    result, text = {}, {}
    for index, path, sha in papers(manifest, archive):
        data = path.read_bytes()
        assert sha in (None, hashlib.sha256(data).hexdigest()), f"paper {index} differs"
        result[index], text[index] = await paper(ports, runtime, data, f"doc_{index}")
        print(index, Counter(i["method"] for i in result[index]["items"])["code"], "code items",
              flush=True)  # fmt: skip
    (out / f"{label}.json").write_text(json.dumps(result, indent=1) + "\n")
    (out / f"{label}-text.json").write_text(json.dumps(text, indent=1, ensure_ascii=False) + "\n")


def inside(c: dict, item: dict) -> bool:
    l, b, r, t = c["bbox"]
    x, y = (l + r) / 2, (b + t) / 2
    box = item["bbox"]
    return box["l"] <= x <= box["r"] and box["b"] <= y <= box["t"]


def unit_row(evidence: dict, gold: str, run: dict, pdf: bytes, metrics) -> dict:
    codes = [i for i in run["items"] if i["method"] == "code"]
    characters = [c for c in evidence["characters"] if c["text"].strip()]
    covered = sum(any(i["page"] == c["page"] and inside(c, i) for i in codes) for c in characters)
    unions: dict[int, dict] = {}
    for region in evidence["regions"]:
        l, b, r, t = region["bbox"]
        u = unions.setdefault(region["page"], {"l": l, "b": b, "r": r, "t": t,
                                               "coord_origin": "BOTTOMLEFT"})  # fmt: skip
        u.update(l=min(u["l"], l), b=min(u["b"], b), r=max(u["r"], r), t=max(u["t"], t))
    covering = [i for i in codes if i["page"] in unions and t3.iou(i["bbox"], unions[i["page"]]) > 0]
    outputs = [code.run(i, [pdf]) for i in covering]  # type: ignore[arg-type]
    scored = metrics.compare(gold, "\n".join(o.content or "" for o in outputs))
    return {"characters": len(characters), "covered": covered, "items": len(covering),
            "outcomes": [o.outcome for o in outputs], "cer": scored["raw"]["CER"],
            "operators_exact": scored["operator_sequences"]["exact"],
            "numbers_exact": scored["number_sequences"]["exact"]}  # fmt: skip


def compare(out: Path, manifest: Path, archive: Path) -> None:
    before, after = (json.loads((out / f"{label}.json").read_text()) for label in ("before", "after"))
    assert before.keys() == after.keys()
    report = {}
    for index in before:
        old, new = before[index], after[index]
        assert old["sha256"] == new["sha256"]
        # By place, not item_id: a split renumbers the text refs after it.
        keys = {run: {(i["method"], i["page"], json.dumps(i["bbox"], sort_keys=True)): i
                      for i in data["items"]} for run, data in (("old", old), ("new", new))}  # fmt: skip
        labels = {(n["page"], json.dumps(n["bbox"], sort_keys=True)): n["label"] for n in old["texts"]}
        gained = [keys["new"][k] for k in keys["new"].keys() - keys["old"].keys()]
        lost = [keys["old"][k] for k in keys["old"].keys() - keys["new"].keys()]
        report[index] = {
            "items_before": Counter(i["method"] for i in old["items"]),
            "items_after": Counter(i["method"] for i in new["items"]),
            "gained": sorted(({"item_id": i["item_id"], "method": i["method"], "page": i["page"],
                               "label_before": labels.get((i["page"], json.dumps(i["bbox"], sort_keys=True)))}
                              for i in gained), key=lambda i: (i["page"], i["item_id"])),
            "lost": sorted(({"item_id": i["item_id"], "method": i["method"], "page": i["page"]}
                            for i in lost), key=lambda i: (i["page"], i["item_id"])),
        }  # fmt: skip
    (HERE / "inventory.json").write_text(json.dumps(report, indent=1) + "\n")

    root = archive / t3.CODE_GOLD
    metrics = t3.load(root / "metrics.py", "code_metrics")
    gold = {u["unit_id"]: u["source_text"] for u in json.loads((root / "per-unit.json").read_text())}
    units = [r["unit"] for r in json.loads((REPO / "docs/validation/80/t3-accuracy/evidence.json")
                                           .read_text())["code"]["rows"]]  # fmt: skip
    pdfs = {sha: path.read_bytes() for _, path, sha in papers(manifest, archive)}
    pdfs = {hashlib.sha256(data).hexdigest(): data for data in pdfs.values()}
    by_sha = {run["sha256"]: index for index, run in after.items()}
    rows = {}
    for uid in units:
        evidence = json.loads((root / "native-evidence" / (uid.replace(":", "__") + ".json")).read_text())
        index = by_sha[evidence["pdf_sha256"]]
        pdf = pdfs[evidence["pdf_sha256"]]
        rows[uid] = {"paper": index, **{label: unit_row(evidence, gold[uid], run[index], pdf, metrics)
                                        for label, run in (("before", before), ("after", after))}}  # fmt: skip
    totals = {label: {"fully_covered": sum(r[label]["covered"] == r[label]["characters"]
                                           for r in rows.values()),
                      "operators_exact": sum(r[label]["operators_exact"] for r in rows.values()),
                      "numbers_exact": sum(r[label]["numbers_exact"] for r in rows.values())}
              for label in ("before", "after")}  # fmt: skip
    (HERE / "codes.json").write_text(json.dumps({"units": len(rows), "totals": totals,
                                                 "rows": rows}, indent=1) + "\n")  # fmt: skip
    manifest_out = {"papers": {index: run["sha256"] for index, run in before.items()},
                    "outputs": {f"OUT/{label}.json": hashlib.sha256((out / f"{label}.json").read_bytes()).hexdigest()
                                for label in ("before", "after")}}  # fmt: skip
    (HERE / "manifest.json").write_text(json.dumps(manifest_out, indent=1) + "\n")
    print(json.dumps(totals))
    for index, row in report.items():
        if row["gained"] or row["lost"]:
            print(index, Counter((i["method"], i["label_before"]) for i in row["gained"]),
                  Counter(i["method"] for i in row["lost"]))  # fmt: skip


if __name__ == "__main__":
    if sys.argv[1] == "compare":
        compare(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    else:
        asyncio.run(main(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5]))
