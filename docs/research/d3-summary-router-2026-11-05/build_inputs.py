"""#166 inputs: every d3 request, the verify units and the labelled cases, from #155's frozen-1 run.

    .venv/bin/python docs/research/d3-summary-router-2026-11-05/build_inputs.py FROZEN OUT

FROZEN is the frozen-1 directory (summary-N.json, accuracy-{dev,held-out}.json). OUT (outside git,
it holds paper text) gets:

- items.json: one d3 request per distinct (paper, Section indices, sentence): {"id", "split",
  "state"}. State is the evidence D4's LLM verify reads (the paper's title and the Sections'
  heading and text) and the sentence.
- units.json: every first verify call of the run (a Section with sentences, or one verified
  overview sentence): its sentences as they entered verify, whether the LLM flagged each, the
  kept final texts, and the request sizes the token model needs.
- cases.json: the t5b labelled cases (valid plants only, t5b's rule), each with the items of its
  original, its plant and the plant's batch-mates; and the dev control cases (an original
  Section sentence against another Section of the same paper).
- steps.json: each paper's LLM calls and tokens per step, as frozen-1 recorded them.

Here: inputs-counts.json (counts only, no text). Splits follow t5b: the dev papers are
evidence-dev.json's, every other paper is test.
"""

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
T5B = HERE.parents[1] / "validation/80/t5b-accuracy"
sys.path.insert(0, str(T5B))
import run as t5b  # noqa: E402

from kp_processing.methods import document_summary as ds  # noqa: E402

SEED = 166


def item_id(paper: int, indices: list[int], sentence: str) -> str:
    return hashlib.sha256(json.dumps([paper, indices, sentence]).encode()).hexdigest()[:16]


def state(document: dict, indices: list[int], sentence: str) -> dict:
    sections = [{"heading": document["sections"][i]["heading"],
                 "text": document["sections"][i]["text"]} for i in indices]  # fmt: skip
    return {"category": "summary sentence", "paper_title": document["title"],
            "sections": sections, "sentence": sentence}  # fmt: skip


def chars(request: dict) -> int:
    return len(request["messages"][0]["content"])


def main(frozen: Path, out: Path) -> None:
    dev = set(json.loads((T5B / "evidence-dev.json").read_text())["papers"])
    items: dict[str, dict] = {}

    def item(paper: int, document: dict, indices: list[int], sentence: str) -> str:
        key = item_id(paper, indices, sentence)
        items.setdefault(key, {"id": key, "split": "dev" if paper in dev else "test",
                               "state": state(document, indices, sentence)})  # fmt: skip
        return key

    summaries = {p: json.loads((frozen / f"summary-{p}.json").read_text()) for p in range(1, 21)}
    units = []
    for p, summary in summaries.items():
        document, record = summary["sections"], summary["record"]
        by_id = {s["section_id"]: i for i, s in enumerate(document["sections"])}
        verified = [(f"s{i}", "section", [i], s["fates"])
                    for i, s in enumerate(record["sections"]) if s["fates"]]  # fmt: skip
        verified += [(f"o{k}", "overview", [by_id[e["section_id"]] for e in f["evidence"]], [f])
                     for k, f in enumerate(record["overview"]["fates"])
                     if f.get("reason") != "NO_SOURCES"]  # fmt: skip
        calls = 0
        for name, kind, indices, fates in verified:
            entered = [f.get("original", f["text"]) for f in fates]
            rewrites = [f for f in fates if "original" in f and f.get("rewrite", f["text"])]
            units.append({
                "id": f"{p}:{name}", "split": "dev" if p in dev else "test", "paper": p,
                "kind": kind, "indices": indices,
                "sentences": [{"item": item(p, document, indices, s), "llm_flagged": "original" in f,
                               "final": item(p, document, indices, f["text"]) if f["text"] else None}
                              for s, f in zip(entered, fates, strict=True)],
                "verify_chars": chars(ds.verify_request(document, indices, entered)),
                "repair_chars": [chars(ds.repair_request(document, indices, f["original"], f["reason"]))
                                 for f in fates if "original" in f],
                "reverify_chars": [chars(ds.verify_request(document, indices,
                                                           [f.get("rewrite", f["text"])]))
                                   for f in rewrites],
            })  # fmt: skip
            calls += 1 + len(rewrites)
        assert calls == record["steps"]["verify"]["calls"], p  # every verify call accounted for

    cases, rng = [], random.Random(SEED)
    for name in ("dev", "held-out"):
        pool = {(c["paper"], c["kind"], tuple(c["indices"]), c["text"]): c
                for s in summaries.values() for c in t5b.candidates(s)}  # fmt: skip
        for n, case in enumerate(json.loads((frozen / f"accuracy-{name}.json").read_text())):
            p, document = case["paper"], summaries[case["paper"]]["sections"]
            c = pool[(p, case["kind"], tuple(case["indices"]), case["text"])]
            batch = [item(p, document, c["indices"], s) for s in c["batch"]]
            base = {"case": f"{name}-{n}", "split": "dev" if p in dev else "test", "paper": p,
                    "kind": case["kind"], "error": case["error"], "valid": t5b.valid(case)}  # fmt: skip
            cases.append({**base, "role": "original", "item": batch[c["n"]],
                          "llm_caught": not case["original_supported"]})  # fmt: skip
            if t5b.valid(case):
                planted = item(p, document, c["indices"], case["planted"])
                cases.append({**base, "role": "planted", "item": planted,
                              "llm_caught": not case["planted_supported"],
                              "mates": [k for j, k in enumerate(batch) if j != c["n"]]})  # fmt: skip
            if name == "dev" and case["kind"] == "section":
                others = [j for j, s in enumerate(document["sections"])
                          if s["target"] and j not in c["indices"]]  # fmt: skip
                wrong = [rng.choice(others)]
                cases.append({**base, "role": "control", "item": item(p, document, wrong, case["text"]),
                              "llm_caught": None, "indices": wrong})  # fmt: skip

    unit_of = {s["final"]: u["id"] for u in units for s in u["sentences"] if s["final"]}
    home = {c["case"]: unit_of[c["item"]] for c in cases if c["role"] == "original"}
    for c in cases:
        c["unit"] = home[c["case"]]  # the bootstrap group: a plant shares its original's unit
    out.mkdir(parents=True, exist_ok=True)
    steps = {p: s["record"]["steps"] for p, s in summaries.items()}
    data = {"items": list(items.values()), "units": units, "cases": cases, "steps": steps}
    for name, data in data.items():
        (out / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    counts = {split: {
        "items": sum(i["split"] == split for i in items.values()),
        "units": sum(u["split"] == split for u in units),
        "unit_sentences": sum(len(u["sentences"]) for u in units if u["split"] == split),
        "cases": {role: sum(c["split"] == split and c["role"] == role for c in cases)
                  for role in ("original", "planted", "control")},
    } for split in ("dev", "test")}  # fmt: skip
    (HERE / "inputs-counts.json").write_text(json.dumps(counts, indent=1) + "\n")
    print(json.dumps(counts))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
