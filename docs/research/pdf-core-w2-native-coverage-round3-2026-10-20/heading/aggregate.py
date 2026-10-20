"""Aggregate all heading ablations, with baseline/all-rules comparisons and families."""
import collections
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
OLD = ROOT.parent / "pdf-core-w2-native-coverage-round2-2026-10-20"
NAMES = [f"b{b}-n{n}-s{s}" for b in (0, 1) for n in (0, 1) for s in (0, 1)]

def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")

def tally(summaries):
    answer = {}
    for name in NAMES:
        members = [v[name] for v in summaries if name in v]
        result = {"documents": len(members),
            "documents_with_evaluable_headings": sum(v["in_scope_headings"] > 0 for v in members),
            "structural_counts": dict(sum((collections.Counter(v["structural_counts"]) for v in members), collections.Counter())),
            "all_source_command_counts": dict(sum((collections.Counter(v["all_source_command_counts"]) for v in members), collections.Counter())),
            "level_only": all(v["level_only"] for v in members),
            "text_sequence_unchanged": all(v["text_sequence_unchanged"] for v in members),
            "orig_and_provenance_unchanged": all(v["orig_and_provenance_unchanged"] for v in members),
            "actual_parents_unchanged": all(v["actual_parents_unchanged"] for v in members),
            "stage_seconds": sum(v["stage_seconds"] for v in members)}
        for comparison in ("versus_baseline", "versus_all_rules"):
            result[comparison] = {
                "fixed": sum(v[comparison]["fixed"] for v in members),
                "new_bad": sum(v[comparison]["new_bad"] for v in members),
                "transitions": dict(sum((collections.Counter(v[comparison]["transitions"]) for v in members), collections.Counter()))}
        answer[name] = result
    return answer

def main():
    jobs = json.loads((OLD / "jobs.json").read_text())["jobs"]
    summaries, pending = [], []
    for job in jobs:
        path = OUT / "jobs" / job["id"] / "summary.json"
        if path.exists():
            summaries.append(json.loads(path.read_text()))
        else:
            pending.append(job["id"])
    totals = tally(summaries)
    families = collections.defaultdict(list)
    for summary in summaries:
        families[summary["b0-n0-s0"]["family"]].append(summary)
    by_family = {family: tally(rows) for family, rows in families.items()}
    regression_min = min((v["versus_baseline"]["new_bad"] for v in totals.values()), default=0)
    best_fixed = max((v["versus_baseline"]["fixed"] for v in totals.values() if v["versus_baseline"]["new_bad"] == regression_min), default=0)
    candidates = [name for name, v in totals.items() if v["versus_baseline"]["new_bad"] == regression_min and v["versus_baseline"]["fixed"] == best_fixed]
    result = {"completed_documents": len(summaries), "pending_documents": pending,
        "definition": "fixed=non-correct baseline/reference -> correct; new_bad=correct baseline/reference -> any non-correct. Same frozen IN_SCOPE oracle and evaluator. No fuzzy or paragraph missing promoted to correct.",
        "totals": totals, "by_family": by_family,
        "minimum_regression_candidates": candidates,
        "selection_rule": "Descriptive ranking only: minimum new_bad versus baseline, then maximum fixed. No deployment decision.",
        "jobs": summaries}
    write(OUT / "summary.json", result)
    lines = ["# 官方 heading 全因子結果", "",
        f"已完成 {len(summaries)} 篇；待輸入 {len(pending)} 篇。fixed 為 reference 非正確→正確；new_bad 為 reference 正確→非正確。", "",
        "| bookmark/number/style | correct | level error | strict missing | role error | ambiguous | baseline fixed / new bad | all-rules fixed / new bad |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, v in totals.items():
        c, b, a = v["structural_counts"], v["versus_baseline"], v["versus_all_rules"]
        lines.append(f"| {name} | {c.get('correct',0)} | {c.get('level_error',0)} | {c.get('missing',0)} | {c.get('role_error',0)} | {c.get('ambiguous',0)} | {b['fixed']} / {b['new_bad']} | {a['fixed']} / {a['new_bad']} |")
    lines += ["", "描述性最低退化候選：" + ", ".join(candidates) + "。未採用或部署。", "",
        "三個主要結構命令 section/subsection/subsubsection 見上表；paragraph/subparagraph run-in 仍在 JSON all_source_command_counts 另列。strict missing 只代表 title 匹配失敗，不等於內容漏失。", "",
        "## 按家族", ""]
    for family, rows in by_family.items():
        lines += [f"### {family}", "", "| rules | baseline fixed | baseline new bad | level errors |", "|---|---:|---:|---:|"]
        for name, v in rows.items():
            lines.append(f"| {name} | {v['versus_baseline']['fixed']} | {v['versus_baseline']['new_bad']} | {v['structural_counts'].get('level_error',0)} |")
        lines.append("")
    (OUT / "results.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"completed_documents": len(summaries), "pending_documents": len(pending), "minimum_regression_candidates": candidates,
        "counts": {name: {"fixed": v["versus_baseline"]["fixed"], "new_bad": v["versus_baseline"]["new_bad"]} for name, v in totals.items()}}))

if __name__ == "__main__":
    main()

