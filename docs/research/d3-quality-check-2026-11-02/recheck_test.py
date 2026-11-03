"""Independent recomputation of #153 test metrics (no score.py import)."""
import json, math, sys, random
from pathlib import Path
out = Path(sys.argv[1])

def auroc(pos, neg):  # P(score_correct > score_changed), ties 1/2
    if not pos or not neg: return None
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))

def cal(c, s):
    s = min(max(s, 1e-6), 1 - 1e-6)
    z = c["a"] * math.log(s / (1 - s)) + c["b"]
    return 1 / (1 + math.exp(-z))

bad = []
for m in ["d3-nano", "d3-mini", "d3-flash"]:
    sel = json.loads((out / "selection" / f"{m}.json").read_text())["models"][m]
    met = json.loads((out / "metrics" / f"{m}.json").read_text())["models"][m]
    rows = [json.loads(l) for l in (out / "rows" / f"{m}-test.jsonl").read_text().splitlines()]
    for c, s in sel.items():
        rs = [r for r in rows if r["category"] == c]
        mine = {}
        pos = [r["score"] for r in rs if r["label"] == "correct"]
        neg = [r["score"] for r in rs if r["label"] == "meaning_changed"]
        mine["AUROC_raw"] = auroc(pos, neg)
        # page bootstrap, own RNG: only the order of magnitude is comparable
        groups = {}
        for r in rs: groups.setdefault(r["group"], []).append(r)
        keys = sorted(groups); rng = random.Random(153); vals = []
        for _ in range(2000):
            pick = [r for k in (rng.choice(keys) for _ in keys) for r in groups[k]]
            a = auroc([r["score"] for r in pick if r["label"] == "correct"], [r["score"] for r in pick if r["label"] == "meaning_changed"])
            if a is not None: vals.append(a)
        vals.sort()
        lo = vals[int(0.025 * len(vals))] if vals else None
        if s["t_v"] is not None or s["t_d"] is not None:
            p = {r["id"]: cal(s["calibrator"], r["score"]) for r in rs}
            ver = [r for r in rs if s["t_v"] is not None and p[r["id"]] >= s["t_v"]]
            dis = [r for r in rs if s["t_d"] is not None and p[r["id"]] <= s["t_d"]]
            assert not set(map(id, ver)) & set(map(id, dis))
            mine["verified"] = (len(ver), sum(r["label"] == "meaning_changed" for r in ver))
            mine["disputed"] = (len(dis), sum(r["label"] == "meaning_changed" for r in dis))
            theirs = {"verified": (met[c]["verified"]["count"], met[c]["verified"]["changed"]),
                      "disputed": (met[c]["disputed"]["count"], met[c]["disputed"]["precision"]["k"])}
            for k in ["verified", "disputed"]:
                if mine[k] != theirs[k]: bad.append((m, c, k, mine[k], theirs[k]))
            if c == "formula":
                t4 = [r for r in rs if r["rule_flag"] is not None]
                missed = [r for r in t4 if r["label"] == "meaning_changed" and not r["rule_flag"]]
                caught = sum(r in dis for r in missed)
                corr = [r for r in t4 if r["label"] == "correct"]
                orf = sum(r["rule_flag"] or r in dis for r in corr)
                andf = sum(r["rule_flag"] and r in dis for r in corr)
                cw = met[c]["combined_with_rule"]
                mine_c = (caught, len(missed), orf, andf, len(corr), len(rs) - len(t4))
                theirs_c = (cw["changed_missed_by_rule_caught_by_d3"]["k"], cw["changed_missed_by_rule_caught_by_d3"]["n"],
                            cw["correct_false_flag_or"]["k"], cw["correct_false_flag_and"]["k"], cw["correct_false_flag_or"]["n"], cw["excluded_null_rule_flag"])
                if mine_c != theirs_c: bad.append((m, c, "combined", mine_c, theirs_c))
                print(m, "formula T4", len(t4), "labels", {l: sum(r["label"] == l for r in t4) for l in ["correct", "minor", "meaning_changed"]},
                      "rule flags", sum(r["rule_flag"] for r in t4), "rule hits on changed", sum(r["rule_flag"] for r in t4 if r["label"] == "meaning_changed"),
                      "d3 disputed in T4", sum(r in dis for r in t4), "d3 false flags in T4 (correct/minor)", sum(r in dis for r in t4 if r["label"] != "meaning_changed"))
        ta = met[c].get("AUROC_raw")
        if (ta is None) != (mine["AUROC_raw"] is None) or (ta is not None and abs(ta - mine["AUROC_raw"]) > 1e-12):
            bad.append((m, c, "AUROC", mine["AUROC_raw"], ta))
        tl = (met[c].get("AUROC_CI") or {}).get("interval")
        print(m, c, "AUROC", None if mine["AUROC_raw"] is None else round(mine["AUROC_raw"], 3), "my lo", None if lo is None else round(lo, 3), "their lo", None if not tl else round(tl[0], 3), mine.get("verified"), mine.get("disputed"))
print("MISMATCHES", bad)
