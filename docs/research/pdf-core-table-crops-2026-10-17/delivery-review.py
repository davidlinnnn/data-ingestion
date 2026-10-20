"""Independent offline delivery review; requires all API calls and page assembly done."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "pdf-core-direct-cell-2026-10-17"
sys.path.insert(0, str(PREVIOUS))
spec = importlib.util.spec_from_file_location("frozen_delivery_checks", PREVIOUS / "delivery-check.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
sys.path.pop(0)
old.HERE = HERE


def rejection_controls():
    doc, keys, payload, _ = old.gate.fixture()
    before = doc.model_dump_json()
    variants = {}
    for name in ("missing_cell", "overlap", "span_mismatch", "unknown_target"):
        value = deepcopy(payload)
        data = value["targets"][0]["panels"][0]["data"]
        if name == "missing_cell":
            data["table_cells"].pop()
        elif name == "overlap":
            data["table_cells"].append(deepcopy(data["table_cells"][0]))
        elif name == "span_mismatch":
            data["table_cells"][0]["col_span"] = 2
        else:
            value["targets"][0]["target_key"] = "unknown"
        variants[name] = value
    for name, value in variants.items():
        try:
            old.adapter.map_response(doc, value, 1, keys)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid table accepted: " + name)
        assert doc.model_dump_json() == before
    return list(variants)


def main():
    assert (HERE / "all-calls-complete.json").exists(), "do not inspect outputs before all calls finish"
    assert (HERE / "page-assembly.json").exists(), "wait for completed page assembly"
    reg = json.loads((HERE / "registration.json").read_text())
    done = json.loads((HERE / "all-calls-complete.json").read_text())
    records = json.loads((HERE / "live-observations.json").read_text())
    pages = {p["name"]: p for p in json.loads((HERE / "page-assembly.json").read_text())}
    assert done["requests"] == len(records) == len(reg["jobs"]) == 6
    assert all(r["attempts"] == 1 for r in records)
    for job in reg["jobs"]:
        assert old.sha(Path(job["directory"]) / "response.json") == done["response_hashes"][job["name"]]
    for path, expected in reg["method_files"].items():
        assert old.sha(path) == expected, "frozen method changed"
    protected = [HERE / name for name in ("registration.json", "all-calls-complete.json", "page-assembly.json")]
    protected += [Path(path) for path in reg["method_files"]]
    for page in reg["pages"]:
        protected.append(Path(page["baseline"]))
        protected += [p for p in (HERE / page["name"]).rglob("*") if p.is_file()]
    before = {str(p): old.sha(p) for p in protected}
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "runner_sha256": old.sha(__file__),
              "pages": {}, "targets": {}, "rejection_controls": rejection_controls()}
    records_by_name = {record["name"]: record for record in records}
    for job in reg["jobs"]:
        try:
            payload = json.loads((Path(job["directory"]) / "content.txt").read_text())
            parsed = old.adapter.parse_response(payload, [job["target_key"]])
            assert parsed.targets[0].caption == "", "body-only crop supplied a caption"
        except (ValueError, AssertionError) as error:
            assert records_by_name[job["name"]]["result"] == "target rejected"
            assert not (Path(job["directory"]) / "output.json").exists()
            if hasattr(error, "errors"):
                detail = [{key: item[key] for key in ("loc", "msg", "type")} for item in error.errors()]
            else:
                detail = str(error)
            result["targets"][job["name"]] = {"status": "independently rejected", "reason": detail}
        else:
            assert records_by_name[job["name"]]["result"] == "valid target; pending page assembly"
            result["targets"][job["name"]] = {"status": "complete-cell schema passed; source accuracy separate"}
    for page in reg["pages"]:
        name, dest = page["name"], HERE / page["name"]
        if pages[name]["status"] != "mapped; semantic quality not evaluated":
            assert not any((dest / file).exists() for file in ("document.json", "document.md", "bindings.json"))
            result["pages"][name] = {"status": "not delivered; whole page unaccepted", "accepted_artifacts": 0}
            continue
        audit = old.audit(page)
        baseline = old.DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
        doc = old.DoclingDocument.model_validate_json((dest / "document.json").read_text())
        bindings = json.loads((dest / "bindings.json").read_text())
        markdown = (dest / "document.md").read_text()
        observations, unresolved = [], []
        for binding in bindings:
            assert binding["provider"]["caption"] == ""
            ownership = binding["caption_ownership"]
            assert not ownership["provider_caption_applied"]
            assert not ownership["source_completeness_verified"]
            native = old.adapter.inventory(baseline, page["page_no"])[binding["target_key"]]
            assert ownership["native_link_preserved"] == bool(native.captions)
            assert [old.gate.old.signature(old.RefItem(cref=ref).resolve(doc)) for ref in binding["captions"]] == [
                old.gate.old.signature(ref.resolve(baseline)) for ref in native.captions]
            for condition in binding["provider"]["conditions"]:
                visible = old.normalize(condition) in old.normalize(markdown)
                observation = {"target_key": binding["target_key"], "condition": condition,
                               "literal_condition_visible_in_main_markdown": visible}
                observations.append(observation)
                if not visible:
                    unresolved.append(observation)
        audit["caption_ownership"] = "native linked captions and all standalone body nodes preserved; no provider caption inserted"
        audit["provider_conditions"] = observations
        audit["condition_visibility_requiring_semantic_review"] = unresolved
        if name == "wikiskill-p13":
            caption = old.RefItem(cref="#/texts/1").resolve(baseline)
            assert caption.text.startswith("Table 4")
            baseline_count = sum(n.text == caption.text for n in baseline.texts)
            output_count = sum(n.text == caption.text for n in doc.texts)
            assert baseline_count == output_count == markdown.count(caption.text) == 1
            audit["T05_standalone_caption"] = {"baseline_occurrences": baseline_count,
                "canonical_occurrences": output_count, "markdown_occurrences": markdown.count(caption.text),
                "association": "not newly established; standalone source preservation passes"}
        result["pages"][name] = audit
    assert all(old.sha(path) == expected for path, expected in before.items()), "audit changed frozen evidence"
    result.update(status="passed" if all(p["status"] == "passed" for p in result["pages"].values()) else "incomplete or failed delivery",
        protected_hashes=before, protected_files_unchanged=True,
        new_inferences=0, API_requests=0, oracle_reads=0, source_image_reads=0,
        limitations=["mechanical delivery/ownership audit; numeric source correctness reviewed separately",
            "source standalone captions are permitted; native-link absence is not itself rejection",
            "condition literal matching is only a visibility screen, not semantic equivalence or source completeness proof",
            "unaccepted pages contribute no accepted artifact; no repair or producer retry"])
    (HERE / "delivery-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    lines = ["# Table crops：獨立交付審查", "", "2026-10-17。六次 API 與 page assembly 全部完成後，才讀取本輪結果。只讀保存輸出，沒有新增 inference、oracle 或來源圖片讀取。", "",
        "| 頁面 | 交付檢查 | condition visibility 待核對 |", "|---|---|---|"]
    for name, page in result["pages"].items():
        lines.append(f"| {name} | {page['status']} | {len(page.get('condition_visibility_requiring_semantic_review', []))} |")
    lines += ["", "六個 target 原始 content 另逐一重驗。兩個 target schema 通過；四個拒絕與 live 記錄一致：", "",
        "| Target | Schema 結果 |", "|---|---|"]
    for name, target in result["targets"].items():
        reason = target.get("reason", target["status"])
        if isinstance(reason, list):
            reason = "; ".join(".".join(map(str, item["loc"])) + ": " + item["msg"] for item in reason)
        lines.append(f"| {name} | {reason} |")
    lines += ["", "映射成功頁面核對 graph／全部 references、非目標正文及順序、linked／standalone caption、來源 provenance、完整 physical cells、實際 Markdown 渲染的 cell literals／header ancestry、canonical 不變、source spans、JSON reload。四個合成拒絕控制涵蓋缺 cell、重疊、span mismatch 與未知 target。", "",
        "Schema 拒絕不等於所有數值錯誤。尤其 SkillOpt collateral 的問題是 root 多出 uncertainties 欄位；本輪遵守凍結 strict contract 拒絕，沒有刪欄位後重新接受。來源數值品質需另外閱讀 raw 評分。", "",
        "T05 若有交付，另核對原正文 Table 4 caption 僅出現一次；沒有自行建立 native link，也沒有把 standalone association 當成驗收失敗。真正缺漏 caption 並未由此審查補回。", "",
        "Provider conditions 若沒有逐字出現在主要 Markdown，會列為待語義核對；不能只因已存入 bindings，就推論主要內容交付完整。這是可見性篩查，不是來源等價性裁決。數值與 critical comparisons 由另外的來源評分處理。", "",
        "所有 frozen method／保存輸入輸出 hashes 前後一致。完整逐項結果見 [delivery-review.json](delivery-review.json)。"]
    (HERE / "delivery-review.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"status": result["status"], "pages": {name: {"status": page["status"],
        "errors": page.get("errors", []), "conditions": page.get("condition_visibility_requiring_semantic_review", []),
        "T05": page.get("T05_standalone_caption")} for name, page in result["pages"].items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
