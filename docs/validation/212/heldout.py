"""#212 held-out check: does IDENTIFIER turn a real formula into text on papers it was not
designed on? The rule was written while looking at the 257 formula items of the 21 papers.

    PYTHONPATH=. .venv/bin/python docs/validation/212/heldout.py fetch OUT
    scripts/heavy-lock 212-heldout -- env HF_HUB_OFFLINE=1 PYTHONPATH=. .venv/bin/python \\
        docs/validation/212/heldout.py parse OUT
    scripts/heavy-lock 212-heldout -- env HF_HUB_OFFLINE=1 PYTHONPATH=. .venv/bin/python \\
        docs/validation/212/heldout.py control OUT CORPUS_MANIFEST

fetch takes, per arXiv category in CATEGORIES, the newest submissions of at most MAX_PAGES pages
(PER_CATEGORY each, no paper twice), and writes OUT/papers/<id>.pdf and OUT/manifest.json
{id, category, pages, sha256}; requests are 3 s apart and carry no personal data.

parse runs prepare, parse and assemble on paper-pdf@1.yaml with the relabel switched off
(pipeline.IDENTIFIER never matches), so every node docling labels formula stays one, and then
classifies each with the real IDENTIFIER. Writes OUT/heldout.json (each formula node's page,
orig and match) and heldout.json here: the papers with their sha256, per paper the formula
nodes and the matches, and every match's orig, for review.

control, the positive control, runs the same parse on corpus paper 16 (CORPUS_MANIFEST as in
run.py), whose 35 ids on page 25 must match, and adds its counts to heldout.json here.
"""

import asyncio
import hashlib
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import pypdfium2 as pdfium

from kp_canonicalization.methods.docling_parse import pipeline
from kp_canonicalization.ports.status_reporter import RecordingStatusReporter
from kp_canonicalization.profile import load_profile
from kp_canonicalization.stages import (
    AssembleInput,
    GroupInput,
    Ports,
    PrepareInput,
    Runtime,
    parse,
    prepare,
)
from tests.stages.conftest import start_input

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import PROFILE, FileStore  # noqa: E402

CATEGORIES = ("math.PR", "math.AP", "math.OC", "stat.ML", "stat.ME", "hep-th", "quant-ph",
              "cond-mat.stat-mech", "cs.LG", "cs.IT", "cs.DS", "econ.EM", "q-fin.MF", "cs.SE",
              "cs.CL", "eess.SP")  # fmt: skip
PER_CATEGORY, MAX_PAGES = 2, 40
API = "https://export.arxiv.org/api/query?search_query=cat:{}&sortBy=submittedDate&max_results=10"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
IDENTIFIER = pipeline.IDENTIFIER


def get(url: str) -> bytes:
    time.sleep(3)  # arXiv's rate limit for scripted access
    request = urllib.request.Request(url, headers={"User-Agent": "kp-212-heldout/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def fetch(out: Path) -> None:
    (out / "papers").mkdir(parents=True, exist_ok=True)
    chosen: list[dict] = []
    for category in CATEGORIES:
        feed = ET.fromstring(get(API.format(category)))
        taken = 0
        for entry in feed.findall("a:entry", ATOM):
            arxiv_id = entry.findtext("a:id", "", ATOM).rsplit("/abs/", 1)[1]
            if taken == PER_CATEGORY or any(p["id"] == arxiv_id for p in chosen):
                continue
            data = get(f"https://arxiv.org/pdf/{arxiv_id}")
            if not data.startswith(b"%PDF"):
                continue
            with pdfium.PdfDocument(data) as document:
                pages = len(document)
            if pages > MAX_PAGES:
                continue
            (out / "papers" / f"{arxiv_id}.pdf").write_bytes(data)
            chosen.append({"id": arxiv_id, "category": category, "pages": pages,
                           "sha256": hashlib.sha256(data).hexdigest()})  # fmt: skip
            taken += 1
            print(category, arxiv_id, pages, flush=True)
    (out / "manifest.json").write_text(json.dumps(chosen, indent=1) + "\n")


async def formulas(ports: Ports, runtime: Runtime, data: bytes, uid: str) -> list[dict]:
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
    document = json.loads(await ports.store.get(assembly.ref))["document"]
    return [{"page": node["prov"][0]["page_no"] if node["prov"] else None, "orig": node["orig"],
             "match": IDENTIFIER.fullmatch(node["orig"]) is not None}
            for node in document["texts"] if node["label"] == "formula"]  # fmt: skip


def relabel_off(out: Path) -> tuple[Ports, Runtime]:
    pipeline.IDENTIFIER = re.compile(r"(?!)")  # keep every docling formula node a formula
    # The store is this check's own: its assemblies carry the relabel-off documents.
    ports = Ports(store=FileStore(out / "store"), reporter=RecordingStatusReporter())
    return ports, Runtime(profile=load_profile(PROFILE), build_id="212", custody_bucket="kp-dev")


async def control(out: Path, manifest: Path) -> None:
    ports, runtime = relabel_off(out)
    paper = next(p for p in json.loads(manifest.read_text())["papers"] if p["index"] == 16)
    data = (manifest.parent / paper["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == paper["sha256"]
    found = await formulas(ports, runtime, data, "doc_c16")
    report = json.loads((HERE / "heldout.json").read_text())
    report["control_paper_16"] = {"formula_nodes": len(found), "matched": sum(f["match"] for f in found),
                                  "matched_pages": sorted({f["page"] for f in found if f["match"]})}  # fmt: skip
    (HERE / "heldout.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(report["control_paper_16"]))


async def run_parse(out: Path) -> None:
    ports, runtime = relabel_off(out)
    papers = json.loads((out / "manifest.json").read_text())
    found = {}
    for index, paper in enumerate(papers):
        data = (out / "papers" / f"{paper['id']}.pdf").read_bytes()
        assert hashlib.sha256(data).hexdigest() == paper["sha256"]
        found[paper["id"]] = await formulas(ports, runtime, data, f"doc_h{index}")
        print(paper["id"], len(found[paper["id"]]), "formula nodes",
              sum(f["match"] for f in found[paper["id"]]), "matched", flush=True)  # fmt: skip
    (out / "heldout.json").write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n")
    report = {
        "papers": papers,
        "totals": {"papers": len(papers), "pages": sum(p["pages"] for p in papers),
                   "formula_nodes": sum(len(f) for f in found.values()),
                   "matched": sum(n["match"] for f in found.values() for n in f)},  # fmt: skip
        "per_paper": {i: {"formula_nodes": len(f), "matched": sum(n["match"] for n in f)}
                      for i, f in found.items()},  # fmt: skip
        "matches": [{"paper": i, "page": n["page"], "orig": n["orig"]}
                    for i, f in found.items() for n in f if n["match"]],  # fmt: skip
    }
    (HERE / "heldout.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        fetch(Path(sys.argv[2]))
    elif sys.argv[1] == "control":
        asyncio.run(control(Path(sys.argv[2]), Path(sys.argv[3])))
    else:
        asyncio.run(run_parse(Path(sys.argv[2])))
