"""#174 inputs: the verify units, labelled cases and one d3 request per evidence group.

    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/inputs.py dev OUT
    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/inputs.py heldout RUN SET OUT

dev reuses #166's inputs (~/archive/research/166-d3-router: items, units, cases, steps from
#155's frozen-1), every one of the 20 papers, without #166's control cases. heldout builds the
same files from a new t5b-seam-b run directory RUN (summary-N.json) and its t5b-accuracy set
RUN/accuracy-SET.json, by #166's rules (build_inputs.py there).

OUT/SPLIT/ (outside git, it holds paper text) gets units.json, cases.json, steps.json and
requests.json: one request per distinct evidence (the paper's title and the Sections D4's verify
reads), with every sentence item judged against it. Each request carries the evidence in both
state formats (JSON as #166, and plain text) and the sentences; the questions are built from
questions.json at run time. Here: inputs-SPLIT.json (counts only, no text).
"""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V1 = HERE.parent / "d3-summary-router-2026-11-05"
V1_OUT = Path("~/archive/research/166-d3-router").expanduser()


def v1(name: str):
    sys.path.insert(0, str(V1))
    spec = importlib.util.spec_from_file_location(f"v1_{name}", V1 / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def text_state(state: dict) -> str:
    parts = [f"Paper title: {state['paper_title']}"]
    parts += [f"Section: {s['heading']}\n{s['text']}" for s in state["sections"]]
    return "\n\n".join(parts)


def requests(items: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for i in items:
        evidence = {k: i["state"][k] for k in ("category", "paper_title", "sections")}
        evidence["category"] = "summary evidence"
        key = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()[:16]
        group = groups.setdefault(key, {"id": key, "state_json": evidence,
                                        "state_text": text_state(evidence), "items": []})  # fmt: skip
        group["items"].append({"id": i["id"], "sentence": i["state"]["sentence"]})
    return list(groups.values())


def heldout(run: Path, accuracy: str) -> tuple[list, list, list, dict]:
    """#166 build_inputs.main's rules over every summary in RUN, one split, no control cases."""
    b = v1("build_inputs")
    t5b, ds = b.t5b, b.ds
    items: dict[str, dict] = {}

    def item(paper: int, document: dict, indices: list[int], sentence: str) -> str:
        key = b.item_id(paper, indices, sentence)
        items.setdefault(key, {"id": key, "split": "heldout", "state": b.state(document, indices, sentence)})
        return key

    papers = sorted(int(p.stem.split("-")[1]) for p in run.glob("summary-*.json"))
    summaries = {p: json.loads((run / f"summary-{p}.json").read_text()) for p in papers}
    units = []
    for p, summary in summaries.items():
        document, record = summary["sections"], summary["record"]
        if record is None:
            continue  # a failed summary has no verify calls
        by_id = {s["section_id"]: i for i, s in enumerate(document["sections"])}
        verified = [(f"s{i}", "section", [i], s["fates"])
                    for i, s in enumerate(record["sections"]) if s["fates"]]  # fmt: skip
        verified += [(f"o{k}", "overview", [by_id[e["section_id"]] for e in f["evidence"]], [f])
                     for k, f in enumerate(record["overview"]["fates"])
                     if f.get("reason") != "NO_SOURCES"]  # fmt: skip
        calls = 0
        for name, kind, indices, fates in verified:
            entered = [f.get("original", f["text"]) for f in fates]
            # a dropped rewrite without second_reason was never verified (#164: not a sentence)
            rewrites = [f for f in fates if "original" in f
                        and not ("rewrite" in f and f["second_reason"] is None)]  # fmt: skip
            units.append({
                "id": f"{p}:{name}", "split": "heldout", "paper": p, "kind": kind, "indices": indices,
                "sentences": [{"item": item(p, document, indices, s), "llm_flagged": "original" in f,
                               "final": item(p, document, indices, f["text"]) if f["text"] else None}
                              for s, f in zip(entered, fates, strict=True)],
                "verify_chars": b.chars(ds.verify_request(document, indices, entered)),
                "repair_chars": [b.chars(ds.repair_request(document, indices, f["original"], f["reason"]))
                                 for f in fates if "original" in f],
                "reverify_chars": [b.chars(ds.verify_request(document, indices,
                                                             [f.get("rewrite", f["text"])]))
                                   for f in rewrites],
            })  # fmt: skip
            calls += 1 + len(rewrites)
        assert calls == record["steps"]["verify"]["calls"], p  # every verify call accounted for

    cases = []
    pool = {(c["paper"], c["kind"], tuple(c["indices"]), c["text"]): c
            for s in summaries.values() if s["record"] for c in t5b.candidates(s)}  # fmt: skip
    for n, case in enumerate(json.loads((run / f"accuracy-{accuracy}.json").read_text())):
        p, document = case["paper"], summaries[case["paper"]]["sections"]
        c = pool[(p, case["kind"], tuple(case["indices"]), case["text"])]
        batch = [item(p, document, c["indices"], s) for s in c["batch"]]
        base = {"case": f"heldout-{n}", "split": "heldout", "paper": p, "kind": case["kind"],
                "error": case["error"], "valid": t5b.valid(case)}  # fmt: skip
        cases.append({**base, "role": "original", "item": batch[c["n"]],
                      "llm_caught": not case["original_supported"]})  # fmt: skip
        if t5b.valid(case):
            cases.append({**base, "role": "planted", "item": item(p, document, c["indices"], case["planted"]),
                          "llm_caught": not case["planted_supported"],
                          "mates": [k for j, k in enumerate(batch) if j != c["n"]]})  # fmt: skip
    unit_of = {s["final"]: u["id"] for u in units for s in u["sentences"] if s["final"]}
    home = {c["case"]: unit_of[c["item"]] for c in cases if c["role"] == "original"}
    for c in cases:
        c["unit"] = home[c["case"]]
    steps = {str(p): s["record"]["steps"] for p, s in summaries.items() if s["record"]}
    return list(items.values()), units, cases, steps


def dev() -> tuple[list, list, list, dict]:
    load = lambda name: json.loads((V1_OUT / f"{name}.json").read_text())  # noqa: E731
    cases = [{**c, "split": "dev"} for c in load("cases") if c["role"] != "control"]
    units = [{**u, "split": "dev"} for u in load("units")]
    needed = {s[k] for u in units for s in u["sentences"] for k in ("item", "final") if s[k]}
    needed |= {c["item"] for c in cases} | {m for c in cases for m in c.get("mates", [])}
    items = [{**i, "split": "dev"} for i in load("items") if i["id"] in needed]
    return items, units, cases, load("steps")


def main(argv: list[str]) -> None:
    split = argv[0]
    if split == "dev":
        items, units, cases, steps = dev()
        out = Path(argv[1]).expanduser()
    else:
        items, units, cases, steps = heldout(Path(argv[1]).expanduser(), argv[2])
        out = Path(argv[3]).expanduser()
    groups = requests(items)
    scored = {i["id"] for g in groups for i in g["items"]}
    assert all(s["item"] in scored for u in units for s in u["sentences"]), "every unit sentence scored"
    (out / split).mkdir(parents=True, exist_ok=True)
    for name, data in {"requests": groups, "units": units, "cases": cases, "steps": steps}.items():
        (out / split / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    counts = {"papers": len({u["paper"] for u in units}), "units": len(units),
              "unit_sentences": sum(len(u["sentences"]) for u in units),
              "llm_flagged": sum(s["llm_flagged"] for u in units for s in u["sentences"]),
              "requests": len(groups), "items": len(scored),
              "max_items_per_request": max(len(g["items"]) for g in groups),
              "cases": {r: sum(c["role"] == r for c in cases) for r in ("original", "planted")}}  # fmt: skip
    (HERE / f"inputs-{split}.json").write_text(json.dumps(counts, indent=1) + "\n")
    print(json.dumps(counts))


if __name__ == "__main__":
    main(sys.argv[1:])
