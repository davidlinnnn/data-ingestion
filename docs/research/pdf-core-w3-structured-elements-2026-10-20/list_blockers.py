"""Readable index of visually confirmed cases, keeping variant and units apart."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


def safe(value):
    return str(value).replace("|", "&#124;").replace("\n", " ")


def main():
    formula = load("formula-code/blocking-cases.json")
    tables = load("table/E0-results-v2.json")
    images = load("image/blocking-cases.json")
    text = ["# 已確認阻擋索引", "", "全部有來源頁圖或原生格位的人工證據。RAW／MAPPED在下列阻擋的裁決相同。公式／code／algorithm屬E1，表格／圖片屬E0，不能相加成同一設定的整體失敗率。P13p8的表／圖共用一個根因。全表清單另見 table-status.md。", ""]
    for key, title in (("formula_selected", "E1 公式 Q31：15 個最終抽查 block"),
                       ("code_manual", "E1 literal code／prompt／log Q4：6 個來源單位"),
                       ("algorithm_manual", "E1 algorithm 靜態 Q33：1 個來源單位")):
        text.extend(["## " + title, "", "|來源 ID|頁|family|改義片段／原因|", "|---|---|---|---|"])
        for case in formula[key]:
            reason = case["meaning_reason"]
            if key != "algorithm_manual":
                reason = reason[:240] + ("…" if len(reason) > 240 else "")
            text.append("|" + "|".join(safe(v) for v in (case["unit_id"], ",".join(map(str, case["source_pages"])), case["family"], reason)) + "|")
        text.append("")
    text.extend(["## E0 表格 Q13：5 張", "", "逐點錯誤下界與分母見主報告／table/E0-results-v2.json。", "", "|來源 ID|頁|family|類型|裁決|", "|---|---|---|---|---|"])
    for case in tables["tables"]:
        if case["verdict"] == "FAIL":
            text.append("|" + "|".join(safe(v) for v in (case["id"], ",".join(map(str, case["source_pages"])), case["family"], case["complexity"], "FAIL／FAIL")) + "|")
    text.extend(["", "## E0 圖片 Q4：2 件", "", "|來源 ID|頁|family|stage／原因|", "|---|---|---|---|"])
    for case in images:
        text.append("|" + "|".join(safe(v) for v in (case["case_id"], ",".join(map(str, case["source_pages"])), case["family"], case["stage"] + ": " + case["reason"])) + "|")
    text.extend(["", "公式完整source／active／refs／PNG SHA：formula-code/blocking-cases.json。程式runtime未執行；TeX渲染合法性未驗。未裁決或oracle錯配不列為模型blocking；6個inline-math樣本僅列F13攤平，不加入本索引的Q31改義件數。"])
    (HERE / "blocking-list.md").write_text("\n".join(text) + "\n")
    print(json.dumps(dict(formula=len(formula["formula_selected"]), code=len(formula["code_manual"]), algorithm=len(formula["algorithm_manual"]), tables=sum(t["verdict"] == "FAIL" for t in tables["tables"]), images=len(images))))


if __name__ == "__main__":
    main()
