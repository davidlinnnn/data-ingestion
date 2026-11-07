"""#159: blind judging packets, verdict merge and scoring for CodeFormulaV2, Luna and Opus.

    .venv/bin/python docs/research/codeformula-vs-vlm-2026-11-07/score.py packet OUT
    .venv/bin/python docs/research/codeformula-vs-vlm-2026-11-07/score.py merge OUT
    .venv/bin/python docs/research/codeformula-vs-vlm-2026-11-07/score.py score OUT

OUT is the research folder outside git (prepare.py). Producers per formula: cf-official and
cf-same (outputs.json), luna (t4-accuracy targets.json, the #152 answers) and opus
(t4-accuracy responses/opus, round 2).

  packet  OUT/judging/batch-NN.json: one sheet per formula with the formula@1 crop and each
          distinct non-empty answer as A, B, C... in a seeded random order (seed 159); batch-00
          is the pilot. OUT/key.json maps sheet letters to producers; judges never see it.
          Refuses to write unless every formula is in exactly one sheet, every crop file has the
          hash items.json records, and every producer's answer is under exactly one letter.
  merge   judgments.json from OUT/judging/verdicts-NN.json: every sheet and letter judged
          exactly once, mapped back to producers; an empty answer is EMPTY, never judged. Prints
          the spot-check sample and every luna/opus verdict that differs from t4-accuracy's.
  score   evidence.json: correct counts with Wilson 95% intervals, paired counts against luna
          and opus with an exact sign test, error types, FORMULA_NATIVE_MISMATCH (formula@1's
          mismatch() on each answer) against the verdicts, and CodeFormulaV2's local latency.
"""

import hashlib
import json
import math
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
T4 = REPO / "docs/validation/80/t4-accuracy"
sys.path.insert(0, str(REPO / "src"))
PRODUCERS = ("cf-official", "cf-same", "luna", "opus")
TYPES = {"letter-style", "letter-case", "script", "symbol", "missing", "extra", "structure",
         "other"}  # fmt: skip
SEED = 159
PILOT = 6
BATCH = 20


def answers() -> dict[str, dict[str, str]]:
    """Label -> producer -> LaTeX answer, for the 46 formulas."""
    outputs = json.loads((HERE / "outputs.json").read_text())["items"]
    found = {}
    for t in json.loads((T4 / "targets.json").read_text()):
        if t["kind"] != "formula":
            continue
        opus = json.loads((T4 / "responses/opus" / f"{t['label']}.json").read_text())["parsed"]
        found[t["label"]] = {"cf-official": outputs[t["label"]]["official"]["text"],
                             "cf-same": outputs[t["label"]]["same"]["text"],
                             "luna": t["luna"]["latex"], "opus": opus.get("content") or ""}  # fmt: skip
    return found


def packet(out: Path) -> None:
    items = {i["label"]: i for i in json.loads((out / "items.json").read_text())}
    rng = random.Random(SEED)
    sheets, key = [], {}
    for label, by_producer in answers().items():
        texts = sorted({a.strip() for a in by_producer.values() if a.strip()})
        rng.shuffle(texts)
        letters = dict(zip(texts, "ABCDEFGH", strict=False))
        sheet = f"s-{len(sheets):04d}"
        key[sheet] = {"label": label, "letters": {
            letters[a.strip()]: sorted(p for p, b in by_producer.items() if b.strip() == a.strip())
            for a in texts}}  # fmt: skip
        crop = out / "inputs" / f"{items[label]['crop_sha256']}.png"
        sheets.append({"sheet": sheet, "crop": str(crop),
                       "answers": {letter: text for text, letter in letters.items()}})  # fmt: skip
    rng.shuffle(sheets)
    # self-check before anything is written (#153: a packer bug showed judges the wrong image)
    assert sorted(k["label"] for k in key.values()) == sorted(items), "a formula missing or twice"
    for s in sheets:
        entry = key[s["sheet"]]
        crop = Path(s["crop"]).read_bytes()
        assert hashlib.sha256(crop).hexdigest() == items[entry["label"]]["crop_sha256"], s["sheet"]
        given = answers()[entry["label"]]
        placed = [p for producers in entry["letters"].values() for p in producers]
        assert sorted(placed) == sorted(p for p in PRODUCERS if given[p].strip()), s["sheet"]
        for letter, producers in entry["letters"].items():
            assert all(given[p].strip() == s["answers"][letter] for p in producers), s["sheet"]
    folder = out / "judging"
    folder.mkdir(exist_ok=True)
    batches = [sheets[:PILOT]] + [sheets[n:n + BATCH] for n in range(PILOT, len(sheets), BATCH)]
    for n, batch in enumerate(batches):
        (folder / f"batch-{n:02d}.json").write_text(json.dumps(batch, indent=1, ensure_ascii=False))
    (out / "key.json").write_text(json.dumps(key, indent=1, sort_keys=True))
    print(len(sheets), "sheets in", len(batches), "batches;",
          sum(len(s["answers"]) for s in sheets), "distinct answers")  # fmt: skip


def merge(out: Path) -> None:
    key = json.loads((out / "key.json").read_text())
    given = answers()
    sheets = {s["sheet"]: s for path in sorted((out / "judging").glob("batch-*.json"))
              for s in json.loads(path.read_text())}  # fmt: skip
    verdicts: dict[str, dict] = {}
    for path in sorted((out / "judging").glob("verdicts-*.json")):
        for v in json.loads(path.read_text()):
            assert v["sheet"] not in verdicts, f"{v['sheet']} judged twice"
            verdicts[v["sheet"]] = v
    assert sorted(verdicts) == sorted(key), f"unjudged: {sorted(set(key) - set(verdicts))}"
    path = HERE / "rulings.json"
    rulings = json.loads(path.read_text()) if path.exists() else {}
    judgments = {}
    for sheet, entry in key.items():
        answered = verdicts[sheet]["answers"]
        assert sorted(answered) == sorted(sheets[sheet]["answers"]), sheet
        row = {p: {"verdict": "EMPTY", "types": [], "reason": "no output"} for p in PRODUCERS
               if not given[entry["label"]][p].strip()}  # fmt: skip
        for letter, producers in entry["letters"].items():
            v = answered[letter]
            assert v["verdict"] in ("PASS", "FAIL", "UNKNOWN"), (sheet, letter)
            assert (v["verdict"] == "FAIL") == bool(v["types"]) and set(v["types"]) <= TYPES, (
                sheet, letter)  # fmt: skip
            row |= {p: {"verdict": v["verdict"], "types": v["types"], "reason": v["reason"]}
                    for p in producers}  # fmt: skip
        assert sorted(row) == sorted(PRODUCERS), sheet
        for p, ruling in rulings.get(entry["label"], {}).items():
            row[p] = {**ruling, "judge": row[p]}
        judgments[entry["label"]] = {"sheet": sheet, **row}
    (HERE / "judgments.json").write_text(json.dumps(judgments, indent=1, ensure_ascii=False) + "\n")
    rng = random.Random(SEED)
    # the sample comes from the judge's verdicts, so a user ruling never redraws it
    judged = {x: row["cf-official"].get("judge", row["cf-official"]) for x, row in judgments.items()}
    fails = [x for x in sorted(judged) if judged[x]["verdict"] == "FAIL"]
    passes = [x for x in sorted(judged) if judged[x]["verdict"] == "PASS"]
    print("spot check:", rng.sample(fails, min(5, len(fails))) + rng.sample(passes, min(5, len(passes))))
    t4 = json.loads((T4 / "judgments.json").read_text())
    for label, row in sorted(judgments.items()):
        for p in ("luna", "opus"):
            if row[p]["verdict"] != t4[label][p]:
                print("differs from t4:", label, p, t4[label][p], "->", row[p]["verdict"])


def wilson(k: int, n: int) -> list[float]:
    z = 1.959964
    centre = (k + z * z / 2) / (n + z * z)
    half = z * math.sqrt(k * (n - k) / n + z * z / 4) / (n + z * z)
    return [round(centre - half, 3), round(centre + half, 3)]


def sign_test(b: int, c: int) -> float:
    """Exact two-sided p of b against c discordant pairs."""
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2**n)


def score(out: Path) -> None:
    from kp_processing.methods.formula import mismatch

    # hand-computed: Wilson 34/46 = 0.7207 -+ 0.1233; 2 vs 8 discordant: 2 x 56/1024
    assert wilson(34, 46) == [0.597, 0.844] and sign_test(2, 8) == 0.109375
    judgments = json.loads((HERE / "judgments.json").read_text())
    native = {i["label"]: i["native_text"] for i in json.loads((out / "items.json").read_text())}
    given = answers()
    n = len(judgments)
    correct = {p: {x for x, row in judgments.items() if row[p]["verdict"] == "PASS"} for p in PRODUCERS}
    counts = {p: Counter(row[p]["verdict"] for row in judgments.values()) for p in PRODUCERS}
    # judging-rules.md: UNKNOWN counts against no producer, so it leaves the denominator
    summary = {p: {"pass": len(correct[p]), "of": n - counts[p]["UNKNOWN"],
                   "wilson95": wilson(len(correct[p]), n - counts[p]["UNKNOWN"]),
                   **{v.lower(): counts[p][v] for v in ("FAIL", "UNKNOWN", "EMPTY")},
                   "error_types": dict(Counter(t for row in judgments.values() for t in row[p]["types"]))}
               for p in PRODUCERS}  # fmt: skip
    paired = {}
    for a in ("cf-official", "cf-same"):
        for b in ("luna", "opus", "cf-same"):
            if a != b:
                only_a, only_b = len(correct[a] - correct[b]), len(correct[b] - correct[a])
                paired[f"{a} vs {b}"] = {"only_first": only_a, "only_second": only_b,
                                         "sign_test_p": round(sign_test(only_a, only_b), 4)}  # fmt: skip
    flags = {}
    for p in PRODUCERS:
        flagged = {x for x in judgments if given[x][p].strip() and mismatch(native[x], given[x][p])}
        wrong = {x for x, row in judgments.items() if row[p]["verdict"] == "FAIL"}
        if p == "luna":  # reproduces the statuses the real runs registered for Luna's answers
            disputed = {t["label"] for t in json.loads((T4 / "targets.json").read_text())
                        if t["kind"] == "formula" and t["luna"]["status"] == "disputed"}  # fmt: skip
            assert flagged == disputed, (flagged ^ disputed)
        flags[p] = {"flagged": len(flagged), "flagged_and_fail": len(flagged & wrong),
                    "flagged_and_pass": len(flagged & correct[p]), "fail": len(wrong),
                    "fail_not_flagged": sorted(wrong - flagged), "pass_flagged": sorted(flagged & correct[p])}  # fmt: skip
    outputs = json.loads((HERE / "outputs.json").read_text())
    latency = {}
    for variant in ("official", "same"):
        per_item = [r[variant]["batch_seconds"] / r[variant]["batch_size"] for r in outputs["items"].values()]
        # per item = its batch's time / batch size, so the sum is the total of all batches
        latency[variant] = {"items": len(per_item), "median_s": round(statistics.median(per_item), 2),
                            "max_s": round(max(per_item), 2), "total_s": round(sum(per_item), 1)}  # fmt: skip
    evidence = {"summary": summary, "paired": paired, "native_mismatch": flags,
                "latency_cpu": {"engine": outputs["engine"], "device": outputs["device"],
                                "torch_threads": outputs["torch_threads"], **latency}}  # fmt: skip
    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=1) + "\n")
    print(json.dumps(evidence, indent=1))


if __name__ == "__main__":
    command, folder = sys.argv[1], Path(sys.argv[2])
    {"packet": packet, "merge": merge, "score": score}[command](folder)
