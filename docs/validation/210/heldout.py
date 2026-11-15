"""#210 held-out check: which nodes does the listing rule turn into code on papers it was not
designed on? The rule was written while looking at the code nodes of the 21 papers.

    PYTHONPATH=. .venv/bin/python docs/validation/210/heldout.py fetch OUT
    scripts/heavy-lock 210-heldout -- env HF_HUB_OFFLINE=1 PYTHONPATH=. .venv/bin/python \\
        docs/validation/210/heldout.py parse OUT CORPUS_MANIFEST

fetch is #212's heldout.py fetch with CATEGORIES below (fields that typeset prompts and code),
PER_CATEGORY 3; it writes OUT/papers/<id>.pdf and OUT/manifest.json.

parse runs prepare, parse and assemble on paper-pdf@1.yaml with the listing rule switched off,
in a store of this check's own, then applies pipeline.whole_listings to each assembly, so each
node's label is known with and without the rule from one parse. Corpus paper 4 runs the same
way, the positive control: the rule must relabel its prompt lines. A held-out paper with the
sha256 of a corpus paper stops the check. Writes OUT/heldout.json
(per paper every relabeled or split node with its page, label before and orig, for review) and
heldout.json here: the papers with their sha256, per paper the code nodes without the rule,
the nodes relabeled and the code nodes the split added, and every relabeled node's page, label
before and character count. Paper text stays out.
"""

import asyncio
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from kp_canonicalization.methods.docling_parse import pipeline
from kp_canonicalization.ports.status_reporter import RecordingStatusReporter
from kp_canonicalization.profile import load_profile
from kp_canonicalization.stages import AssembleInput, GroupInput, Ports, PrepareInput, Runtime
from kp_canonicalization.stages import parse, prepare
from tests.stages.conftest import start_input

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import PROFILE, FileStore, load  # noqa: E402

heldout212 = load(HERE.parent / "212/heldout.py", "heldout212")
CATEGORIES = ("cs.SE", "cs.PL", "cs.CL", "cs.AI", "cs.LG", "cs.CR", "cs.DB", "cs.DC", "cs.MA",
              "cs.HC")  # fmt: skip
rule = pipeline.whole_listings


async def nodes(ports: Ports, runtime: Runtime, data: bytes, uid: str) -> dict:
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
    off = json.loads(await ports.store.get(assembly.ref))["document"]
    on = copy.deepcopy(off)
    rule(on, data)
    # By place, not self_ref: a split renumbers the text refs after it.
    def place(n: dict) -> str:
        return json.dumps([n["prov"][0]["page_no"], n["prov"][0]["bbox"]] if n["prov"] else None)

    labels = {place(n): n["label"] for n in off["texts"]}
    changed = [{"self_ref": n["self_ref"], "page": n["prov"][0]["page_no"],
                "label_before": labels.get(place(n)), "orig": n["orig"]}
               for n in on["texts"] if n["label"] == "code" and labels.get(place(n)) != "code"]  # fmt: skip
    return {"code_nodes_off": sum(n["label"] == "code" for n in off["texts"]), "changed": changed}


def rule_off(out: Path) -> tuple[Ports, Runtime]:
    pipeline.whole_listings = lambda data, source: None
    # The store is this check's own: its assemblies carry the rule-off documents.
    ports = Ports(store=FileStore(out / "store"), reporter=RecordingStatusReporter())
    return ports, Runtime(profile=load_profile(PROFILE), build_id="210", custody_bucket="kp-dev")


async def run_parse(out: Path, manifest: Path) -> None:
    ports, runtime = rule_off(out)
    papers = json.loads((out / "manifest.json").read_text())
    corpus = next(p for p in json.loads(manifest.read_text())["papers"] if p["index"] == 4)
    assert not {p["sha256"] for p in papers} & {p["sha256"] for p in json.loads(manifest.read_text())["papers"]}
    sources = [(p["id"], out / "papers" / f"{p['id']}.pdf", p["sha256"]) for p in papers]
    sources.append(("control-4", manifest.parent / corpus["file"], corpus["sha256"]))
    found = {}
    for index, (name, path, sha) in enumerate(sources):
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha
        found[name] = await nodes(ports, runtime, data, f"doc_h{index}")
        print(name, found[name]["code_nodes_off"], "code nodes",
              len(found[name]["changed"]), "changed", flush=True)  # fmt: skip
    (out / "heldout.json").write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n")
    held = {k: v for k, v in found.items() if k != "control-4"}

    def counts(paper: dict) -> dict:
        return {"code_nodes_off": paper["code_nodes_off"],
                "relabeled": sum(c["label_before"] is not None for c in paper["changed"]),
                "split_added": sum(c["label_before"] is None for c in paper["changed"]),
                "labels_before": Counter(c["label_before"] for c in paper["changed"])}  # fmt: skip

    report = {
        "papers": papers,
        "totals": {"papers": len(papers), "pages": sum(p["pages"] for p in papers),
                   **{k: sum(counts(p)[k] for p in held.values())
                      for k in ("code_nodes_off", "relabeled", "split_added")}},  # fmt: skip
        "per_paper": {name: counts(paper) for name, paper in held.items()},
        "changed": [{"paper": name, "page": c["page"], "label_before": c["label_before"],
                     "chars": len(c["orig"])} for name, p in held.items() for c in p["changed"]],  # fmt: skip
        "control_paper_4": counts(found["control-4"]),
    }
    (HERE / "heldout.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps(report["totals"]), json.dumps(report["control_paper_4"], default=str))


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        heldout212.CATEGORIES, heldout212.PER_CATEGORY = CATEGORIES, 3
        heldout212.fetch(Path(sys.argv[2]))
    else:
        asyncio.run(run_parse(Path(sys.argv[2]), Path(sys.argv[3])))
