"""freeze.md §6: blind check of the delivered test sentences t_d marks.

    .venv/bin/python docs/research/d3-summary-router-2026-11-05/blind.py pack OUT
    .venv/bin/python docs/research/d3-summary-router-2026-11-05/blind.py tally OUT

pack samples 60 of OUT/flagged-delivered.json (seed 166) and writes OUT/blind/pack-N.json: the
paper title, the Section text and the sentences under blind ids, no d3 score. Reviewers write
OUT/blind/verdicts-N.json, [{"id", "supported", "reason"}]. tally checks every id was judged
once and writes blind-check.json here (counts only, no text).
"""

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score as s153  # noqa: E402

from kp_processing.methods.document_summary import _titled_sections_xml  # noqa: E402

SAMPLE, PACKS, SEED = 60, 4, 166


def pack(out: Path) -> None:
    marked = json.loads((out / "flagged-delivered.json").read_text())
    picked = random.Random(SEED).sample(marked, min(SAMPLE, len(marked)))
    groups: dict[str, dict] = {}
    for n, m in enumerate(picked, 1):
        document = {"title": m["paper_title"], "sections": m["sections"]}
        evidence = _titled_sections_xml(document, list(range(len(m["sections"]))))
        group = groups.setdefault(m["unit"], {"evidence": evidence, "sentences": []})
        assert group["evidence"] == evidence, m["unit"]
        group["sentences"].append({"id": f"b{n:02d}", "unit": m["unit"], "sentence": m["sentence"]})
    packs: list[list[dict]] = [[] for _ in range(PACKS)]
    for group in groups.values():  # keep a unit's sentences together, balance the reading
        min(packs, key=lambda p: sum(len(g["evidence"]) for g in p)).append(group)
    ids = [s["id"] for p in packs for g in p for s in g["sentences"]]
    assert sorted(ids) == [f"b{n:02d}" for n in range(1, len(picked) + 1)], "each item once"
    (out / "blind").mkdir(exist_ok=True)
    for n, p in enumerate(packs, 1):
        groups_out = [{"evidence": g["evidence"],
                       "sentences": [{"id": s["id"], "sentence": s["sentence"]} for s in g["sentences"]]}
                      for g in p]  # fmt: skip
        (out / "blind" / f"pack-{n}.json").write_text(json.dumps(groups_out, ensure_ascii=False, indent=1))
    (out / "blind" / "key.json").write_text(json.dumps(
        {s["id"]: s["unit"] for g in groups.values() for s in g["sentences"]}, indent=1))  # fmt: skip
    print(json.dumps({"marked": len(marked), "sampled": len(picked), "units": len(groups),
                      "packs": [sum(len(g["sentences"]) for g in p) for p in packs]}))  # fmt: skip


def tally(out: Path) -> None:
    key = json.loads((out / "blind" / "key.json").read_text())
    verdicts = [v for n in range(1, PACKS + 1)
                for v in json.loads((out / "blind" / f"verdicts-{n}.json").read_text())]  # fmt: skip
    assert sorted(v["id"] for v in verdicts) == sorted(key), "every id judged once"
    assert all(isinstance(v["supported"], bool) for v in verdicts)
    marked = len(json.loads((out / "flagged-delivered.json").read_text()))
    unsupported = [v for v in verdicts if not v["supported"]]
    kind = {"s": "section", "o": "overview"}
    by_kind = {k: s153.rate(sum(key[v["id"]].split(":")[1][0] == c for v in unsupported),
                            sum(u.split(":")[1][0] == c for u in key.values()))
               for c, k in kind.items()}  # fmt: skip
    result = {"marked_delivered": marked, "sampled": len(verdicts), "seed": SEED,
              "reviewer": "Claude Opus 5.5 subagents, effort high, D4 verify rule",
              "unsupported": s153.rate(len(unsupported), len(verdicts)), "by_kind": by_kind}  # fmt: skip
    (HERE / "blind-check.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    {"pack": pack, "tally": tally}[sys.argv[1]](Path(sys.argv[2]).expanduser())
