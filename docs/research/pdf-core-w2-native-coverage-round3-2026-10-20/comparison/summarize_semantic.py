"""Merge disjoint page-reviewed V2 identities, separately from raw metric churn."""
import collections
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "comparison"
sys.path.insert(0, str(ROOT))
from build_report import table


def load(path):
    return json.loads(path.read_text())


def save(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def key(row):
    return (row["direction"], row["job_id"], row["kind"],
            json.dumps(row["identity"], ensure_ascii=False, sort_keys=True))


def failure_type(group):
    explicit = {
        "p16-task-ids-formula-role-p25": "formula_mapping_omission",
        "v2-p03-analyst-example-picture-delivery-p23": "picture_delivery_omission",
        "v2-p16-self-improve-prompt-picture-delivery-p23-p24": "picture_delivery_omission",
        "v2-p16-polyglot-constraint-tail-order-p24": "reading_order",
        "v2-p18-table5-breaks-effectiveness-clause-p7": "caption_splice",
    }
    value = explicit.get(group["source_rootcause_group"], group.get("failure_type"))
    if value == "caption_algorithm_splice":
        return "caption_splice"
    if value == "NEW_SOURCE_PROMPT_PICTURE_EXPORT_OMISSION":
        return "picture_delivery_omission"
    return value


def main():
    catalogs = load(HERE / "V2-official-changed-cases.json")
    other = load(HERE / "V2-semantic-records.json")
    recovery = load(HERE / "V2-semantic-recovery-records.json")
    heading = load(HERE / "V2-semantic-p07p08.json")
    records = other + recovery["records"] + heading["records"]
    expected = {key(c) for c in catalogs}
    actual = [key(r) for r in records]
    assert len(actual) == len(set(actual)) == len(expected) == 330
    assert set(actual) == expected
    assert all(r.get("reviewed_visual") and (r.get("reviewed_native_and_markdown") or
               (r.get("baseline_evidence") and r.get("variant_evidence"))) for r in records)
    assert all("PENDING" not in r["semantic_verdict"] for r in records)
    family = {x["id"]: x["family"] for x in load(ROOT / "analysis/baseline/summary.json")}
    groups = []
    for gid in sorted({r["source_rootcause_group"] for r in records}):
        rr = [r for r in records if r["source_rootcause_group"] == gid]
        statuses = {r["semantic_verdict"] for r in rr}
        assert len(statuses) == 1, (gid, statuses)
        first = rr[0]
        group = {
            "source_rootcause_group": gid, "job_id": first["job_id"],
            "family": family[first["job_id"]], "semantic_verdict": first["semantic_verdict"],
            "changed_rows": len(rr),
            "affected_pages": sorted({p for r in rr for p in r.get("affected_pages", r.get("pages", []))}),
            "failure_type": first.get("failure_type"),
            "source_reason": first.get("source_reason"),
            "baseline_reason": first.get("baseline_reason"),
            "variant_reason": first.get("variant_reason"),
        }
        group["failure_type"] = failure_type(group)
        if group["semantic_verdict"] == "CONFIRMED_NEW_BLOCKING" and not group["failure_type"]:
            # Both native payload retention and Markdown suppression were independently page-reviewed.
            assert group["job_id"] == "P-07-2504.15228v2"
            group["failure_type"] = "picture_delivery_omission"
        groups.append(group)
    checks = load(HERE / "V2-baseline-group-checks.json") + recovery["baseline_group_checks"] + heading["baseline_group_checks"]
    incidental = next(x for x in recovery["incidental_findings"] if x.get("verdict") == "INCIDENTAL_FIX_OUTSIDE_FROZEN_BASELINE_GROUP_DENOMINATOR")
    checks.append({"job_id": incidental["job_id"],
                   "source_rootcause_group": "incidental-p03-table3-breaks-reporting-clause-p5-p6",
                   "pages": incidental["pages"], "affected_pages": incidental["pages"],
                   "semantic_verdict": "CONFIRMED_FIXED", "q4_fixed": True,
                   "failure_type": "caption_splice", "reason": incidental["reason"],
                   "reviewed_visual": True, "reviewed_native_and_markdown": True,
                   "incidental_outside_original_24_groups": True})
    baseline_groups = load(ROOT / "adjudication/root-groups.json")
    baseline_ids = {g["group_id"] for g in baseline_groups}
    assert len(checks) == len({c["source_rootcause_group"] for c in checks}) == len(baseline_ids)
    assert {c["source_rootcause_group"] for c in checks} == baseline_ids
    fixed = [c for c in checks if c["semantic_verdict"] == "CONFIRMED_FIXED"]
    partial = [c for c in checks if c["semantic_verdict"] == "PARTIAL_IMPROVEMENT"]
    new = [g for g in groups if g["semantic_verdict"] == "CONFIRMED_NEW_BLOCKING"]
    assert len(fixed) == 3 and len(new) == 13
    events = []
    # V1 full-document deltas were exhaustively inspected after exact native comparison.
    v1_events = [
        ("p02-first-author-attribution-order", "P-02-2603.02766v1", [1], "FIXED", "reading_order"),
        ("v1-p18-table17-conditions-separated", "P-18-2511.16043v1", [18], "NEW_BAD", "reading_order"),
        ("v1-p10-prompt-order-p23", "P-10-2509.25140v2", [23], "NEW_BAD", "reading_order"),
        ("v1-p10-datasets-prompt-interruption-p24-p25", "P-10-2509.25140v2", [24, 25], "NEW_BAD", "reading_order"),
    ]
    for gid, jid, pages, effect, kind in v1_events:
        events.append(dict(variant="V1", source_rootcause_group=gid, job_id=jid, family=family[jid],
                           affected_pages=pages, effect=effect, failure_type=kind))
    for group, effect in [(g, "FIXED") for g in fixed] + [(g, "NEW_BAD") for g in new] + [(g, "PARTIAL") for g in partial]:
        events.append(dict(variant="V2", source_rootcause_group=group["source_rootcause_group"],
                           job_id=group["job_id"], family=family[group["job_id"]],
                           affected_pages=group.get("affected_pages", group["pages"] if "pages" in group else []),
                           effect=effect, failure_type=failure_type(group) or group.get("failure_type")))
    family_rows, type_rows = [], []
    for variant in ("V1", "V2"):
        for dimension, rows in (("family", family_rows), ("failure_type", type_rows)):
            values = set(family.values()) if dimension == "family" else {e[dimension] for e in events}
            for value in sorted(values):
                selected = [e for e in events if e["variant"] == variant and e[dimension] == value]
                count = collections.Counter(e["effect"] for e in selected)
                rows.append([variant, value, count["FIXED"], count["NEW_BAD"], count["PARTIAL"]])
    save("V2-semantic-all-records.json", records)
    save("V2-semantic-all-groups.json", groups)
    save("V2-all-baseline-group-checks.json", checks)
    save("semantic-events.json", events)
    summary = {"V1": {"fixed": 1, "new_bad": 3},
               "V2": {"fixed": len(fixed), "fixed_from_original_24": len(fixed)-1,
                      "fixed_newly_discovered_outside_oracle": 1, "new_bad": len(new),
                      "partial_baseline_groups": len(partial)},
               "V2_delta_rows": len(records), "V2_delta_coverage_complete": True,
               "V2_baseline_groups_checked": len(checks),
               "oracle_catalog_sha256": hashlib.sha256((HERE / "V2-official-changed-cases.json").read_bytes()).hexdigest(),
               "meaning": "Counts are page-verified source events, not candidate IDs or paper pass rates."}
    save("semantic-summary.json", summary)
    event_rows = [[e["variant"], e["effect"], e["family"], e["failure_type"], e["job_id"],
                   ",".join(map(str, e["affected_pages"])), e["source_rootcause_group"]] for e in events]
    text = f"""# 官方選項的語意修好／新壞

單位是經頁圖確認的來源事件，不是自動告警。V1 的完整輸出差異都經核對；V2 的 330 個凍結指標差異全部按來源 identity 覆蓋，另逐一回查 {len(checks)} 個已知 baseline 來源事件。沒有把刪掉 metadata 告警當成語意修復。

| 變體 | 完整修好 | 新增阻擋 | 原事件部分改善但未修好 |
| --- | --- | --- | --- |
| V1 separators=False | 1 | 3 | 0 |
| V2 Egret medium | 3 | 13 | 1 |
| V3 bookmark-only | 175 個標題 | 0 個標題 | 不適用 |

V2 的 3 個完整修好含原 24 件的 2 件（Image Transformer p5、P16 p25），以及本輪差異核對新發現的 P03 p5–6。SkillRL p24 的一個 duplicate instance 改善，但 p22–23 的同根因重複仍在，只算部分改善。SICA p13 native 順序改善卻整框被轉 picture 而 Markdown 仍缺，不算整體修好。V3 標題單位不同，不能與正文事件加總。

## 按 family

""" + table(["變體", "family", "完整修好", "新增阻擋", "部分改善"], family_rows)
    text += "\n\n## 按失敗類型\n\n" + table(["變體", "類型", "完整修好", "新增阻擋", "部分改善"], type_rows)
    text += "\n\n## 逐來源事件與頁碼\n\n" + table(["變體", "判定", "family", "類型", "論文", "頁", "來源事件"], event_rows)
    text += "\n\n頁圖、完整前後片段與逐 identity 理由：[V2-semantic-all-records.json](V2-semantic-all-records.json)、[V2-semantic-all-groups.json](V2-semantic-all-groups.json)、[V2-all-baseline-group-checks.json](V2-all-baseline-group-checks.json)。V1 詳見 [V1-supplementary-heading-review.md](V1-supplementary-heading-review.md) 與 [V1-supplementary-trace-review.md](V1-supplementary-trace-review.md)。\n\n這不是 V2 全文逐字驗收，凍結 oracle 對作者、表格、短句、數學與部分框內內容仍有盲點。未把未被自動抓到當成沒有錯誤。建議維持 Heron＋separators=True，採 B-only heading；本輪不做 per-document 例外或額外數值調整。\n"
    (HERE / "semantic-summary.md").write_text(text)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
