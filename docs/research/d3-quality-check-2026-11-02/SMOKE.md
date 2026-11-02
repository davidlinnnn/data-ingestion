# #153 phase 1 smoke evidence

Executed with the worktree's installed Python, offline, without inference or
importing W4b's scorer. The command below takes W4b's directory from `W_DIR`.
Only aggregate counts, probabilities' aggregate AUROCs and hashes are retained;
no row IDs, gold reasons, reconstructions or absolute local paths are copied.

The first check validates every saved output's join to gold and checks nested raw
answers against cached `safe_scores`. Reading W4b test rows here checks mapping
and score extraction only; no test AUROC, calibration, threshold or evaluation
metrics are computed in phase 1. The smoke then converts mini/formula dev into
the requested schema in memory and computes dev AUROCs by average-rank sums.
It excludes minor, uses correct as positive and does not call W4b's `auc`.

## Reproduce

Set `W_DIR` to the read-only W4b directory supplied with the task, then run from
the worktree root:

```sh
rtk .venv/bin/python - "$W_DIR" <<'PY'
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import sys

w = Path(sys.argv[1])
gold = json.loads((w / "gold.json").read_text())["items"]
assert len(gold) == len({r["id"] for r in gold}) == 266
assert {r["label"] for r in gold} == {"correct", "minor", "meaning_changed"}
assert not ({r["split_group"] for r in gold if r["split"] == "dev"}
            & {r["split_group"] for r in gold if r["split"] == "test"})


def raw_score(record, question):
    answer = record["result"]["answers"][question]
    return answer["probabilities"]["faithful"] if question == "Q1" else answer["noul"]


loaded = {}
answers_checked = 0
receipts = hashlib.sha256()
print("model split outputs mapped unknown missing duplicate failed raw_cache_mismatches")
for model in ("d3-nano", "d3-mini"):
    selection = json.loads((w / "selection" / model / "selection.json").read_text())["categories"]
    for split in ("dev", "test"):
        expected = {r["id"]: r for r in gold if r["split"] == split}
        records = []
        for path in sorted((w / "runs" / model / split).glob("*.result.json")):
            data = path.read_bytes()
            records.append(json.loads(data))
            receipts.update(path.relative_to(w).as_posix().encode() + b"\0")
            receipts.update(hashlib.sha256(data).digest())
        counts = Counter(r["id"] for r in records)
        unknown = len(set(counts) - set(expected))
        missing = len(set(expected) - set(counts))
        duplicate = sum(n - 1 for n in counts.values())
        assert not (unknown or missing or duplicate), "STOP: output/gold join failed"
        cache_mismatches = 0
        for record in records:
            item = expected[record["id"]]
            assert record["split"] == split and record["category"] == item["category"]
            questions = ["Q1", "Q2"] if split == "dev" else [selection[item["category"]]["question"]]
            assert record["questions"] == questions
            if record["state"] == "OK":
                for question in questions:
                    raw = raw_score(record, question)
                    assert isinstance(raw, (int, float)) and not isinstance(raw, bool)
                    assert math.isfinite(raw) and 0 <= raw <= 1
                    cache_mismatches += raw != record["safe_scores"][question]
                    answers_checked += 1
        assert cache_mismatches == 0, "STOP: cached safe score differs from raw answer"
        loaded[model, split] = {r["id"]: r for r in records}
        print(model, split, len(records), len(counts), unknown, missing, duplicate,
              sum(r["state"] != "OK" for r in records), cache_mismatches)

rows = []
for item in gold:
    if item["split"] != "dev" or item["category"] != "formula":
        continue
    record = loaded["d3-mini", "dev"][item["id"]]
    failed = record["state"] != "OK"
    rows.append({
        "id": item["id"], "model": "d3-mini", "category": item["category"],
        "split": item["split"], "group": item["split_group"], "label": item["label"],
        "q1": None if failed else raw_score(record, "Q1"),
        "q2": None if failed else raw_score(record, "Q2"),
        "score": None, "failed": failed, "rule_flag": None,
    })
assert len(rows) == 23
assert Counter(r["label"] for r in rows) == {"correct": 18, "minor": 1, "meaning_changed": 4}
binary = [r for r in rows if not r["failed"] and r["label"] != "minor"]


def rank_auc(question):
    ordered = sorted((r[question], r["label"] == "correct") for r in binary)
    positive = sum(label for _, label in ordered)
    negative = len(ordered) - positive
    if not positive or not negative:
        return None
    rank_sum = 0.0
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][0] == ordered[i][0]:
            j += 1
        rank_sum += ((i + 1 + j) / 2) * sum(label for _, label in ordered[i:j])
        i = j
    return (rank_sum - positive * (positive + 1) / 2) / (positive * negative)


print("schema_rows=23 correct=18 minor=1 meaning_changed=4 binary_auc_rows=22")
for question in ("q1", "q2"):
    value = rank_auc(question)
    saved = json.loads((w / "selection" / "d3-mini" / "selection.json").read_text())
    expected = saved["categories"]["formula"]["dev_AUROC"][question.upper()]
    assert value == expected, "STOP: smoke AUROC differs from saved selection receipt"
    print(f"d3-mini formula dev {question.upper()} AUROC={value:.16f} saved_receipt_exact_match=True")
print(f"raw_answer_cache_checks={answers_checked} all_equal=True")
print(f"raw_receipts_digest={receipts.hexdigest()}")
for name in ("gold.json", "protocol.json", "calibrate.py", "evaluate.py", "summarize.py",
             "test_calibration.py", "test_evaluate.py", "comparison.json", "report.md",
             "selection/d3-nano/selection.json", "selection/d3-mini/selection.json"):
    print(f"sha256 {name} {hashlib.sha256((w / name).read_bytes()).hexdigest()}")
PY
```

## Captured stdout

```text
model split outputs mapped unknown missing duplicate failed raw_cache_mismatches
d3-nano dev 81 81 0 0 0 0 0
d3-nano test 185 185 0 0 0 0 0
d3-mini dev 81 81 0 0 0 0 0
d3-mini test 185 185 0 0 0 0 0
schema_rows=23 correct=18 minor=1 meaning_changed=4 binary_auc_rows=22
d3-mini formula dev Q1 AUROC=0.8750000000000000 saved_receipt_exact_match=True
d3-mini formula dev Q2 AUROC=0.9305555555555556 saved_receipt_exact_match=True
raw_answer_cache_checks=694 all_equal=True
raw_receipts_digest=95a28cb019d555743a177de788ce373290464c171412d69b80404161098b8304
sha256 gold.json 0571c9c553fa51a783eb63f37ef4fa39424043acddaa2ab5a229ab4f53d7eeec
sha256 protocol.json e3bf04022d41e067885ed39fa5608d1f5e37138678079e077db31d936a65f5b2
sha256 calibrate.py 9b8eb77181ac1419904b283ea8902564175535034d706ade72fea85993322601
sha256 evaluate.py 3f7872bf5591cf310286730843f1d1d20ae01e2999964149c0569c0be3e46294
sha256 summarize.py c358b6745b7ae309e5fa0b391009a2ed60d132b16fae28573b8a8a97e418e5cb
sha256 test_calibration.py 031a6020f1f8e231665732926b0c246eb725b2c8e87001a4fe95a97e85a61701
sha256 test_evaluate.py 58cc134a69c386b68b023095bf739a4d4798e14270db3bed6392da891d340a44
sha256 comparison.json 226f7db4a2f4b02d39256f3f3ddda7f364e7da35a3fe0f1fba12a1b9cd7fcf60
sha256 report.md a08132a3cb38e854c0a3c95b6ef9a284aaef1995753bdfb3c32b95666bd22941
sha256 selection/d3-nano/selection.json 2d0455a1f512a779c126e3dd9e762391c3e1dcac56dff0f8ebd8e6314a94e140
sha256 selection/d3-mini/selection.json cfaeef5fe513a546a27f1db37a6a335578b369d9c24dffa62f4620738d402af3
```

## Result and limits

PASS for this smoke only: all 532 saved outputs join uniquely to gold, with no
unknown, missing or duplicate IDs and no dev/test source-page overlap. All 694
raw question answers equal their cached safe scores. Mini/formula dev has 23
rows; excluding its one minor row gives 18 correct and 4 changed for AUROC.
Q1 is 0.875 and Q2 is 0.9305555555555556, exactly matching the saved dev AUROC
receipts; the registered higher-AUROC rule would choose Q2.

UNKNOWN until phase 2: independently reproduced Platt parameters, thresholds,
ECE, test metrics and all published section 3 numbers. No production scorer,
pytest suite or completion check has been implemented or run. The smoke's
executed assertions are mapping/extraction/AUROC controls, not a claim that the
full protocol passes. Phase 1 stops at the requested review gate.
