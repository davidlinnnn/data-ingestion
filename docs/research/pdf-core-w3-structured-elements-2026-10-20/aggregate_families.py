"""Conditional evidence by source-manifest family, without averaging acceptance."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    e0 = load("formula-code/e0-delivery-scores.json")
    e1 = load("formula-code/e1-scores.json")
    tables = load("table/E0-results-v2.json")
    images = load("image/family-summary.json")
    cases = load("formula-code/blocking-cases.json")
    assessment = load("formula-code/assessment-summary.json")
    image_cases = load("image/blocking-cases.json")
    result = []
    for family, image in images.items():
        row = dict(family=family, documents=image["documents"], pages=image["pages"])
        for kind in ("formula", "code", "algorithm"):
            units = [u for u in e0 if u["family"] == family and u["kind"] == kind]
            known = [u for u in units if u["known_gold_denominator"]]
            enriched = [u for u in e1 if u["family"] == family and u["kind"] == kind
                        and u["known_gold_denominator"] and u["actual_processed_refs"]]
            row[kind] = dict(source_units=len(units), known_source_page_units=len(known),
                             scope_or_alignment_unknown_units=sum(not u["known_gold_denominator"] for u in units),
                             eligible_role_match_candidates=sum(u["detected_eligible_role_candidate"] for u in known),
                             E1_actual_processed_source_units=len(enriched),
                             E1_RAW=dict(Counter(u["channels"]["RAW"]["status"] for u in enriched)),
                             E1_MAPPED=dict(Counter(u["channels"]["MAPPED"]["status"] for u in enriched)))
        row["table"] = next(t for t in tables["families"] if t["family"] == family)
        row["image"] = image
        row["adjudication"] = dict(
            E1_formula_selected_Q31_blocking=sum(c["family"] == family for c in cases["formula_selected"]),
            E1_code_literal_or_log_Q4_blocking=sum(c["family"] == family for c in cases["code_manual"]),
            E1_algorithm_static_Q33_blocking=sum(c["family"] == family for c in cases["algorithm_manual"]),
            E0_table_Q13_failed_tables=row["table"]["MAPPED"].get("FAIL", 0),
            E0_image_Q4_blocking=sum(c["family"] == family for c in image_cases),
            formula_manual=next((a for a in assessment["formula_audit"]["by_family"] if a["family"] == family), None),
            full_TeX_render_validity="UNKNOWN_NOT_RENDERED",
            note="Counts have different source units and variants; do not sum into an overall document pass rate. P13p8 table/image share one root cause. Zero cases is not a qualified-clean family.")
        result.append(row)
    metadata = dict(scope="E0 all36/715; E1 only actually processed pre-registered items. Formula source units are frozen outer blocks, not independent equations.",
                    rates="Matched/source-known ratios are conditional locator/role evidence, not visually verified precision. UNKNOWN is not a miss or a pass. Tables are adjudicated individually.",
                    families=result)
    (HERE / "family-summary.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    text = ["# 按 family 的結構證據", "", metadata["scope"], "", metadata["rates"], "",
            "F／C／A 欄為 eligible role 候選匹配數／已知來源頁單位（括號為全部來源單位）；不是人工驗證的 precision。E1 欄為真正處理、已知來源頁單位的 RAW exact／near／error，MAPPED 另列於 JSON；非 Q31／Q33 裁決。圖片欄是 main-figure caption-link 候選。", "",
            "|family（篇／頁）|F 候選／已知（來源）|C 候選／已知（來源）|A 候選／已知（來源）|E1 F exact／near／error|E1 C exact／near／error|表已證偵測／IN|表 FAIL／UNKNOWN／OOS（兩出口）|主圖link候選／IN；未知|", "|---|---|---|---|---|---|---|---|---|"]
    for row in result:
        def detection(kind):
            c = row[kind]
            return f"{c['eligible_role_match_candidates']}/{c['known_source_page_units']}（{c['source_units']}）"

        def quality(kind):
            c = row[kind]["E1_RAW"]
            return "/".join(str(c.get(k, 0)) for k in ("EXACT_CANONICAL", "NEAR_CANONICAL", "ERROR_OR_MISSING"))

        t, i = row["table"], row["image"]
        verdicts = t["MAPPED"]
        values = [f"{row['family']}（{row['documents']}/{row['pages']}）", detection("formula"), detection("code"), detection("algorithm"), quality("formula"), quality("code"),
                  f"{t['confirmed_native_detection']}/{t['source_scope'].get('IN_SCOPE', 0)}",
                  "/".join(str(verdicts.get(k, 0)) for k in ("FAIL", "UNKNOWN", "OUT_OF_SCOPE")),
                  f"{i['main_caption_link_candidate']}/{i['main_in_scope']}；{i['main_unknown_including_location']}"]
        text.append("|" + "|".join(values) + "|")
    text.extend(["", "完整 RAW／MAPPED、subfigure、raster bbox 及表格分母資料見 family-summary.json；人工阻擋清單與最終抽查另見主報告及 formula-code/report.md。所有零分母欄不作準度結論。"])
    text.extend(["", "## 已確認阻擋（RAW／MAPPED同數）", "", "E1公式為最終50個near/error block中的Q31；code為literal／log Q4，algorithm為靜態Q33，沒有執行runtime。E0表格及圖片另列，不與E1相加成Profile錯誤率。P13p8表／圖同一根因不重複當全域事件。零件數不是全篇驗收通過。", "", "|family|E1公式／已審block|E1 code Q4|E1 algorithm Q33|E0表Q13|E0圖Q4|", "|---|---|---|---|---|---|"])
    for row in result:
        a = row["adjudication"]
        reviewed = (a["formula_manual"] or {}).get("selected_formula_blocks_reviewed", 0)
        values = [row["family"], f"{a['E1_formula_selected_Q31_blocking']}/{reviewed}", str(a["E1_code_literal_or_log_Q4_blocking"]), str(a["E1_algorithm_static_Q33_blocking"]), str(a["E0_table_Q13_failed_tables"]), str(a["E0_image_Q4_blocking"])]
        text.append("|" + "|".join(values) + "|")
    (HERE / "family-summary.md").write_text("\n".join(text) + "\n")
    print(json.dumps(dict(families=len(result), documents=sum(r["documents"] for r in result), pages=sum(r["pages"] for r in result))))


if __name__ == "__main__":
    main()
