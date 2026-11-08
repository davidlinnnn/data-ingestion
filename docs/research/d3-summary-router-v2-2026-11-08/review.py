"""#174 natural-error review (freeze.md §3): blind Claude Fable 5.1 verdicts on the candidates.

    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/review.py pack OUT SPLIT
    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/review.py tally OUT SPLIT

Candidates: every unit sentence the LLM verify flagged; for dev also the 15 delivered sentences
#166's blind check judged unsupported. Decoys: as many unit sentences the LLM did not flag, at
random (seed 174). pack shuffles both under r-ids, keeps sentences with the same evidence
together, and writes OUT/SPLIT/review/pack-N.json (evidence and sentences only) and key.json.
Reviewers write verdicts-N.json, [{"id", "supported", "reason"}]. tally checks every id was
judged once, writes OUT/SPLIT/confirmed.json (the candidates judged unsupported) and
review-SPLIT.json here (counts only, no text).
"""

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from inputs import V1_OUT, v1  # noqa: E402

from kp_processing.methods.document_summary import _titled_sections_xml  # noqa: E402

PACKS, SEED = 8, 174


def blind_found() -> list[str]:
    """The items #166's blind check (both arms) judged unsupported."""
    blind, found = v1("blind"), []
    for arm, (directory, prefix, _) in blind.ARMS.items():
        pool = blind.delivered(V1_OUT, arm)
        picked = random.Random(blind.SEED).sample(pool, min(blind.SAMPLE, len(pool)))
        verdicts = [v for n in range(1, blind.PACKS + 1)
                    for v in json.loads((V1_OUT / directory / f"verdicts-{n}.json").read_text())]  # fmt: skip
        found += [picked[int(v["id"][1:]) - 1]["item"] for v in verdicts if not v["supported"]]
    return found


def pack(out: Path, split: str) -> None:
    units = json.loads((out / split / "units.json").read_text())
    groups = json.loads((out / split / "requests.json").read_text())
    where = {i["id"]: (g, i["sentence"]) for g in groups for i in g["items"]}
    sentences = [s for u in units for s in u["sentences"]]
    candidates = {s["item"]: "llm" for s in sentences if s["llm_flagged"]}
    if split == "dev":
        candidates |= {item: "blind" for item in blind_found() if item not in candidates}
    rng = random.Random(SEED)
    others = sorted({s["item"] for s in sentences if s["item"] not in candidates})
    decoys = rng.sample(others, len(candidates))
    chosen = [(item, "candidate", source) for item, source in candidates.items()]
    chosen += [(item, "decoy", None) for item in decoys]
    rng.shuffle(chosen)
    key, by_group = {}, {}
    for n, (item, role, source) in enumerate(chosen, 1):
        group, sentence = where[item]
        rid = f"r{n:03d}"
        key[rid] = {"item": item, "role": role, "source": source}
        entry = by_group.setdefault(group["id"], {"evidence": _titled_sections_xml(
            {"title": group["state_json"]["paper_title"], "sections": group["state_json"]["sections"]},
            list(range(len(group["state_json"]["sections"])))), "sentences": []})  # fmt: skip
        entry["sentences"].append({"id": rid, "sentence": sentence})
    packs: list[list[dict]] = [[] for _ in range(PACKS)]
    for entry in by_group.values():  # keep an evidence's sentences together, balance the reading
        min(packs, key=lambda p: sum(len(e["evidence"]) for e in p)).append(entry)
    ids = sorted(s["id"] for p in packs for e in p for s in e["sentences"])
    assert ids == sorted(key) and len(set(ids)) == len(ids), "each item once"
    (out / split / "review").mkdir(exist_ok=True)
    for n, p in enumerate(packs, 1):
        (out / split / "review" / f"pack-{n}.json").write_text(json.dumps(p, ensure_ascii=False, indent=1))
    (out / split / "review" / "key.json").write_text(json.dumps(key, indent=1))
    print(json.dumps({"candidates": len(candidates), "decoys": len(decoys),
                      "packs": [sum(len(e["sentences"]) for e in p) for p in packs],
                      "chars": [sum(len(e["evidence"]) for e in p) for p in packs]}))  # fmt: skip


def tally(out: Path, split: str) -> None:
    rate = v1("router").s153.rate
    key = json.loads((out / split / "review" / "key.json").read_text())
    verdicts = [v for n in range(1, PACKS + 1)
                for v in json.loads((out / split / "review" / f"verdicts-{n}.json").read_text())]  # fmt: skip
    assert sorted(v["id"] for v in verdicts) == sorted(key), "every id judged once"
    assert all(isinstance(v["supported"], bool) for v in verdicts)
    unsupported = {key[v["id"]]["item"] for v in verdicts if not v["supported"]}
    confirmed = sorted(k["item"] for k in key.values() if k["role"] == "candidate" and k["item"] in unsupported)
    (out / split / "confirmed.json").write_text(json.dumps(confirmed, indent=1) + "\n")
    groups = {"llm": ("candidate", "llm"), "blind": ("candidate", "blind"), "decoy": ("decoy", None)}
    result = {"reviewer": "Claude Fable 5.1 subagents, effort high, D4 verify rule", "seed": SEED,
              "unsupported": {name: rate(sum(k["item"] in unsupported for k in key.values()
                                             if (k["role"], k["source"]) == g),
                                         sum((k["role"], k["source"]) == g for k in key.values()))
                              for name, g in groups.items() if any((k["role"], k["source"]) == g
                                                                  for k in key.values())},
              "confirmed": len(confirmed)}  # fmt: skip
    (HERE / f"review-{split}.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    {"pack": pack, "tally": tally}[sys.argv[1]](Path(sys.argv[2]).expanduser(), sys.argv[3])
