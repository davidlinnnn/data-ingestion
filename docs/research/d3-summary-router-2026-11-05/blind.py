"""freeze.md §6: blind check of the delivered test sentences t_d marks, plus an unmarked arm.

    .venv/bin/python docs/research/d3-summary-router-2026-11-05/blind.py pack OUT [unmarked]
    .venv/bin/python docs/research/d3-summary-router-2026-11-05/blind.py tally OUT [unmarked]

pack samples 60 of OUT/flagged-delivered.json (seed 166) and writes OUT/blind/pack-N.json: the
paper title, the Section text and the sentences under blind ids, no d3 score. Reviewers write
OUT/blind/verdicts-N.json, [{"id", "supported", "reason"}]. tally checks every id was judged
once and writes blind-check.json here (counts only, no text).

The unmarked arm (post hoc, added 2026-11-07 after the marked arm's verdicts) samples 60 of the
delivered test sentences t_d leaves unmarked, the same way, into OUT/blind-unmarked/ under u-ids;
its tally writes blind-unmarked.json and compares the two arms.
"""

import json
import random
import sys
from pathlib import Path

from scipy.stats import fisher_exact

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import router  # noqa: E402
import score as s153  # noqa: E402

from kp_canonicalization.methods.document_summary import _titled_sections_xml  # noqa: E402

SAMPLE, PACKS, SEED = 60, 4, 166
ARMS = {"marked": ("blind", "b", "blind-check.json"),
        "unmarked": ("blind-unmarked", "u", "blind-unmarked.json")}  # fmt: skip


def delivered(out: Path, arm: str) -> list[dict]:
    marked = json.loads((out / "flagged-delivered.json").read_text())
    if arm == "marked":
        return marked
    selection = json.loads((HERE / "selection.json").read_text())
    items, results, units, _, _ = router.inputs(out, "test")
    scores = {i: r["scores"][selection["question"]] for i, r in results.items()}
    state = {i["id"]: i["state"] for i in items}
    unmarked = [{"unit": u["id"], "item": s["final"], "score": scores[s["final"]], **state[s["final"]]}
                for u in units for s in u["sentences"]
                if s["final"] and s153.calibrate(selection["platt"], scores[s["final"]]) > selection["t_d"]]  # fmt: skip
    t_d = json.loads((HERE / "metrics.json").read_text())["t_d"]
    assert len(unmarked) == t_d["delivered_sentences"] - t_d["delivered_marked"], "same delivered set"
    assert not {m["item"] for m in marked} & {u["item"] for u in unmarked}, "arms disjoint"
    return unmarked


def pack(out: Path, arm: str) -> None:
    directory, prefix, _ = ARMS[arm]
    pool = delivered(out, arm)
    picked = random.Random(SEED).sample(pool, min(SAMPLE, len(pool)))
    groups: dict[str, dict] = {}
    for n, m in enumerate(picked, 1):
        document = {"title": m["paper_title"], "sections": m["sections"]}
        evidence = _titled_sections_xml(document, list(range(len(m["sections"]))))
        group = groups.setdefault(m["unit"], {"evidence": evidence, "sentences": []})
        assert group["evidence"] == evidence, m["unit"]
        group["sentences"].append({"id": f"{prefix}{n:02d}", "unit": m["unit"], "sentence": m["sentence"]})
    packs: list[list[dict]] = [[] for _ in range(PACKS)]
    for group in groups.values():  # keep a unit's sentences together, balance the reading
        min(packs, key=lambda p: sum(len(g["evidence"]) for g in p)).append(group)
    ids = [s["id"] for p in packs for g in p for s in g["sentences"]]
    assert sorted(ids) == [f"{prefix}{n:02d}" for n in range(1, len(picked) + 1)], "each item once"
    (out / directory).mkdir(exist_ok=True)
    for n, p in enumerate(packs, 1):
        groups_out = [{"evidence": g["evidence"],
                       "sentences": [{"id": s["id"], "sentence": s["sentence"]} for s in g["sentences"]]}
                      for g in p]  # fmt: skip
        (out / directory / f"pack-{n}.json").write_text(json.dumps(groups_out, ensure_ascii=False, indent=1))
    (out / directory / "key.json").write_text(json.dumps(
        {s["id"]: s["unit"] for g in groups.values() for s in g["sentences"]}, indent=1))  # fmt: skip
    print(json.dumps({f"{arm}_delivered": len(pool), "sampled": len(picked), "units": len(groups),
                      "packs": [sum(len(g["sentences"]) for g in p) for p in packs]}))  # fmt: skip


def tally(out: Path, arm: str) -> None:
    directory, _, name = ARMS[arm]
    key = json.loads((out / directory / "key.json").read_text())
    verdicts = [v for n in range(1, PACKS + 1)
                for v in json.loads((out / directory / f"verdicts-{n}.json").read_text())]  # fmt: skip
    assert sorted(v["id"] for v in verdicts) == sorted(key), "every id judged once"
    assert all(isinstance(v["supported"], bool) for v in verdicts)
    pool = len(delivered(out, arm))
    unsupported = [v for v in verdicts if not v["supported"]]
    kind = {"s": "section", "o": "overview"}
    by_kind = {k: s153.rate(sum(key[v["id"]].split(":")[1][0] == c for v in unsupported),
                            sum(u.split(":")[1][0] == c for u in key.values()))
               for c, k in kind.items()}  # fmt: skip
    result = {f"{arm}_delivered": pool, "sampled": len(verdicts), "seed": SEED,
              "reviewer": "Claude Opus 5.5 subagents, effort high, D4 verify rule",
              "unsupported": s153.rate(len(unsupported), len(verdicts)), "by_kind": by_kind}  # fmt: skip
    if arm == "unmarked":
        marked = json.loads((HERE / "blind-check.json").read_text())
        arms = [(marked["marked_delivered"], marked["unsupported"]), (pool, result["unsupported"])]
        size = sum(n for n, _ in arms)
        result["comparison"] = {
            "fisher_exact_p_two_sided": fisher_exact([[r["k"], r["n"] - r["k"]] for _, r in arms]).pvalue,
            # every delivered test sentence, weighting each arm by its pool; bounds from each arm's Wilson
            "delivered_unsupported": {"value": sum(n * r["value"] for n, r in arms) / size,
                                      "bounds": [sum(n * r["wilson95"][i] for n, r in arms) / size
                                                 for i in (0, 1)]},
        }  # fmt: skip
    (HERE / name).write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    arm = sys.argv[3] if len(sys.argv) > 3 else "marked"
    {"pack": pack, "tally": tally}[sys.argv[1]](Path(sys.argv[2]).expanduser(), arm)
