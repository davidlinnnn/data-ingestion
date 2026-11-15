"""#212: the formula items the inventory hands to formula@1, on the 20 corpus papers and W2,
with parse and inventory only (no VLM).

    scripts/heavy-lock 212-inventory -- env HF_HUB_OFFLINE=1 .venv/bin/python \\
        docs/validation/212/run.py OUT CORPUS_MANIFEST ARCHIVE LABEL
    .venv/bin/python docs/validation/212/run.py compare OUT
    .venv/bin/python docs/validation/212/run.py e2e E2E_OUT NAME

The stages run in process on paper-pdf@1.yaml, with a file-backed object store under
OUT/store: their keys carry the source and method digests, so a rerun of the same code reuses
the parse. ARCHIVE is the untracked tree holding W2 (#199's ARCHIVE). Writes OUT/LABEL.json:
per paper, the source sha256, the docling-parse module digest, and each formula item of the
inventory as {target_ref, page, orig, params_digest, recorded, control_recorded}; for paper 16
also every
node on page 25 as {label, text, orig} and the SWE-bench instance ids that page's text layer
holds (read with pypdfium2, not docling). orig is the node's text-layer characters;
params_digest is that of formula@1's request for the item, as enrich_vlm computes it; recorded
says whether t4-seam-b recorded that request (a response under tests/fixtures/vlm/formula named
by it), the request #199's workflow sent for every corpus formula item; control_recorded is the
same for the item with its bbox moved 1 pt, the negative control.

compare reads OUT/before.json and OUT/after.json and writes inventory.json here: per paper the
formula items before and after, the items no longer handed to formula@1 (removed) and any new
one (added), how many kept items send the same request as before, and the recorded counts; for
paper 16, which source ids are missing from the text of page 25's nodes, before and after; and
manifest.json here: each paper's sha256 and the sha256 of OUT/before.json and OUT/after.json.

e2e reads paper 16's request from E2E_OUT, the OUT of #199's run.py, through #199's S3 stand-in
(started on E2E_OUT/s3 and stopped again), and writes NAME.json here: the failed formula
enrichments and all formula statuses, the formula@1 receipts by result, page 25's inventory
items per method and its receipts by result, and which source ids of page 25 (from the custody
copy of the PDF) are missing from the text of that page's nodes in the Processing Result's
assembly. Every result in RESULTS and every method in ITEM_METHODS is counted, 0 included, and
one outside them stops the check. Paper text other than the ids stays out.
"""

import asyncio
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path

import pypdfium2 as pdfium

from kp_canonicalization.identity import canonical_json
from kp_canonicalization.methods import formula
from kp_canonicalization.ports.object_store import ObjectNotFound
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
FIXTURES = REPO / "tests/fixtures/vlm/formula"
W2 = "docs/research/pdf-core-w2-native-coverage-2026-10-20/corpus/arxiv_gradientdescent/pdf.pdf"
INSTANCE_ID = re.compile(r"[a-z][\w.-]*__[\w.-]+-\d+")  # django__django-12754
RESULTS = ("ok", "unavailable", "invalid", "refused", None)  # a receipt's result; None: incomplete
ITEM_METHODS = ("picture-ocr", "picture-interpretation", "formula", "code", "table-status")


class FileStore:
    """The ObjectStore protocol on a directory, one file per key."""

    def __init__(self, root: Path) -> None:
        self.root = root

    async def put_if_absent(self, key: str, data: bytes) -> bool:
        if (self.root / key).exists():
            return False
        await self.put(key, data)
        return True

    async def put(self, key: str, data: bytes) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.with_name(path.name + ".tmp").write_bytes(data)
        path.with_name(path.name + ".tmp").rename(path)

    async def get(self, key: str) -> bytes:
        try:
            return (self.root / key).read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFound(key) from exc

    async def head(self, key: str) -> int | None:
        path = self.root / key
        return path.stat().st_size if path.exists() else None

    async def list_prefix(self, prefix: str) -> list[str]:
        return sorted(
            str(p.relative_to(self.root))
            for p in self.root.rglob("*")
            if p.is_file() and str(p.relative_to(self.root)).startswith(prefix)
        )


def request_digest(item: dict, inputs: list[bytes]) -> str:
    return hashlib.sha256(canonical_json(formula.request(item, inputs))).hexdigest()


def recorded(params_digest: str) -> bool:
    return (FIXTURES / f"{params_digest}.json").exists()


def source_ids(data: bytes, page: int) -> list[str]:
    with pdfium.PdfDocument(data) as document, closing(document[page - 1]) as source:
        with closing(source.get_textpage()) as text:
            return INSTANCE_ID.findall(text.get_text_range())


def on_page(node: dict, page: int) -> bool:
    return bool(node["prov"]) and node["prov"][0]["page_no"] == page


def missing(ids: list[str], nodes: list[dict]) -> list[str]:
    """The ids that are in no node's text."""
    return [i for i in ids if not any(i in node["text"] for node in nodes)]


async def paper(ports: Ports, runtime: Runtime, data: bytes, uid: str) -> dict:
    # prepare keeps its plan under requests/{request_id}: one request id per paper.
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
    nodes = {node["self_ref"]: node for node in document["texts"]}
    formulas = []
    for item in json.loads(await ports.store.get(inv.ref))["items"]:
        if item["method"] != "formula":
            continue
        inputs = [await ports.store.get(source["ref"]) for source in item["input_refs"]]
        moved = {**item, "bbox": {**item["bbox"], "l": item["bbox"]["l"] + 1}}
        params_digest = request_digest(item, inputs)
        formulas.append({"target_ref": item["target_ref"], "page": item["page"],
                         "orig": nodes[item["target_ref"]]["orig"], "params_digest": params_digest,
                         "recorded": recorded(params_digest),
                         "control_recorded": recorded(request_digest(moved, inputs))})  # fmt: skip
    found = {
        "sha256": plan.source_sha256,
        "parse_module_digest": runtime.profile.methods["docling-parse"].module_digest,
        "formula_items": formulas,
    }
    if uid == "doc_16":
        found["page_25"] = [{key: node[key] for key in ("label", "text", "orig")}
                            for node in document["texts"] if on_page(node, 25)]  # fmt: skip
        found["page_25_source_ids"] = source_ids(data, 25)
    return found


async def main(out: Path, manifest: Path, archive: Path, label: str) -> None:
    ports = Ports(store=FileStore(out / "store"), reporter=RecordingStatusReporter())
    runtime = Runtime(profile=load_profile(PROFILE), build_id="212", custody_bucket="kp-dev")
    papers = [(str(p["index"]), manifest.parent / p["file"], p["sha256"])
              for p in json.loads(manifest.read_text())["papers"]]  # fmt: skip
    papers.append(("w2", archive / W2, None))
    result = {}
    for index, path, sha in papers:
        data = path.read_bytes()
        assert sha in (None, hashlib.sha256(data).hexdigest()), f"paper {index} differs"
        result[index] = await paper(ports, runtime, data, f"doc_{index}")
        print(index, len(result[index]["formula_items"]), "formula items", flush=True)
    (out / f"{label}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")


def compare(out: Path) -> None:
    before, after = (json.loads((out / f"{label}.json").read_text()) for label in ("before", "after"))
    assert before.keys() == after.keys()
    papers, totals = {}, {"before": 0, "after": 0, "removed": 0, "added": 0, "same_request": 0,
                          "recorded": 0, "control_recorded": 0}  # fmt: skip
    for index in before:
        old, new = before[index], after[index]
        assert old["sha256"] == new["sha256"]
        kept = {i["target_ref"] for i in new["formula_items"]}
        old_digests = {i["target_ref"]: i["params_digest"] for i in old["formula_items"]}
        row = {
            "before": len(old["formula_items"]),
            "after": len(new["formula_items"]),
            "removed": [{k: i[k] for k in ("target_ref", "page", "orig")}
                        for i in old["formula_items"] if i["target_ref"] not in kept],  # fmt: skip
            "added": sorted(kept - old_digests.keys()),
            "same_request": sum(old_digests.get(i["target_ref"]) == i["params_digest"]
                                for i in new["formula_items"]),  # fmt: skip
            "recorded": sum(i["recorded"] for i in new["formula_items"]),
            "control_recorded": sum(i["control_recorded"] for i in new["formula_items"]),
        }
        papers[index] = row
        for key in totals:
            totals[key] += row[key] if isinstance(row[key], int) else len(row[key])
    ids = before["16"]["page_25_source_ids"]
    assert ids == after["16"]["page_25_source_ids"]
    page_25 = {"source_ids": len(ids), "missing_before": missing(ids, before["16"]["page_25"]),
               "missing_after": missing(ids, after["16"]["page_25"]),
               "labels_after": sorted({n["label"] for n in after["16"]["page_25"]
                                       if INSTANCE_ID.search(n["text"])})}  # fmt: skip
    digests = {label: sorted({p["parse_module_digest"] for p in run.values()})
               for label, run in (("before", before), ("after", after))}  # fmt: skip
    report = {"parse_module_digest": digests, "totals": totals, "papers": papers,
              "paper_16_page_25": page_25}  # fmt: skip
    (HERE / "inventory.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    manifest = {"papers": {index: run["sha256"] for index, run in before.items()},
                "outputs": {f"OUT/{label}.json": hashlib.sha256((out / f"{label}.json").read_bytes()).hexdigest()
                            for label in ("before", "after")}}  # fmt: skip
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(json.dumps({"totals": totals, "page_25": {k: v if isinstance(v, int) else len(v)
                      for k, v in page_25.items()}}))  # fmt: skip


async def e2e(out: Path, name: str) -> None:
    spec = importlib.util.spec_from_file_location("run199", HERE.parent / "199/run.py")
    assert spec and spec.loader
    run199 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run199)
    state = json.loads((out / "requests.json").read_text())
    request_id = state["papers"]["16"]["request_id"]
    container = run199.s3_up(out)
    try:
        store = run199.t2.store(state["bucket"])
        result = json.loads(await store.get(f"requests/{request_id}/result.json"))
        items = json.loads(await store.get(result["inventory"]["ref"]))["items"]
        document = json.loads(await store.get(result["native"]["assembly_ref"]))["document"]
        pdf = await store.get(result["request"]["files"][0]["custody_ref"].split("/", 3)[3])
        receipts = await run199.t4.receipts(store, request_id)
    finally:
        subprocess.run(["docker", "stop", container], capture_output=True)
    assert all(r.get("result") in RESULTS for r in receipts)
    assert {i["method"] for i in items} <= {*ITEM_METHODS, "document-summary"}
    pages = {item["item_id"]: item.get("page") for item in items}
    formulas = [e for e in result["enrichments"] if e["method_ref"]["id"] == "formula"]
    on_25 = [r for r in receipts if pages.get(r["item_id"]) == 25]

    def by_result(sent: list[dict]) -> dict[str, int]:
        return {str(k): sum(r.get("result") == k for r in sent) for k in RESULTS}

    ids = source_ids(pdf, 25)
    report = {
        "request_id": request_id,
        "formula_failed": sum(e["status"] == "failed" for e in formulas),
        "formula_statuses": Counter(f"{e['status']} {e['status_reason']}" for e in formulas),
        "formula_receipts": by_result([r for r in receipts if r["method"] == "formula@1"]),
        "page_25": {
            "inventory_items": {m: sum(i["method"] == m and i.get("page") == 25 for i in items)
                                for m in ITEM_METHODS},  # fmt: skip
            "receipts": len(on_25),
            "receipts_by_result": by_result(on_25),
            "source_ids": len(ids),
            "missing_from_text": missing(ids, [n for n in document["texts"] if on_page(n, 25)]),
        },
    }
    (HERE / f"{name}.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    if sys.argv[1] == "compare":
        compare(Path(sys.argv[2]))
    elif sys.argv[1] == "e2e":
        asyncio.run(e2e(Path(sys.argv[2]), sys.argv[3]))
    else:
        asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]))
