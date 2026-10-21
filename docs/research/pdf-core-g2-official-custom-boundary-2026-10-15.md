# PDF core G2：官方機制與自訂重建的邊界

2026-10-15。只核對官方來源與既有研究程式，沒有新推論或流程變更。

**裁圖→模型→寫回結果是官方機制；普通段落＋context→typed JSON→working Markdown 回填是本案研究方法。** 本次查閱來源沒有提供後者的完整即用方案，不能把擴充介面當成官方已驗證解法。

| 範圍 | 核對結果與來源 |
|---|---|
| 官方 `v2.102.0` | Gate 只收 `CodeItem` 或 `FORMULA` TextItem；模型輸出清理後寫入 `item.text`，此 stage 沒有更新 `item.orig`。[Tagged stage](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/code_formula/code_formula_vlm_model.py) |
| 官方 crop | 基底從 `prov[0]` bbox 擴張裁圖；不包含本案跨 provenance、parent/child union、相鄰 context 規則。[Tagged base](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/base_model.py) |
| 官方擴充範例 | Formula 範例僅 scaffold，沒有真實推論；另一範例示範既有 JSON 的轉換後 enrichment，支持擴充但不保證本案品質。[Formula example](https://docling-project.github.io/docling/_generated/examples/develop_formula_understanding/)、[Existing-document example](https://docling-project.github.io/docling/_generated/examples/enrich_doclingdocument/) |
| 官方 `VlmPipeline` | 頁面 VLM predictions 組裝 document，屬另一主轉換方法。[Tagged pipeline](https://github.com/docling-project/docling/blob/v2.102.0/docling/pipeline/vlm_pipeline.py) |
| 本案 | Planner (`pdf-core-g2-context-candidate-2026-10-15/candidate.py`)選普通段落與 context；Parser (`pdf-core-g2-inline-api-2026-10-15/parsed/parse.py`)採自訂 text/math/code segments，並非 DocTags；Adapter (`pdf-core-g2-context-candidate-2026-10-15/adapter.py`)保留 raw graph，以序列化邊界產生 working Markdown overlay，結構合法不代表內容正確。 |

滾動文件的 repetition 處理、native inline／HTML 路徑是新版調查線索，不能回推舊版可用或宣稱已測。[Enrichments](https://docling-project.github.io/docling/usage/enrichments/)、[Vision guide](https://docling-project.github.io/docling/usage/vision_models/)

建議保留最小 adapter，重心回到模型／方法比較。有證據證明目標裁切或格式接點有錯，才做通用修正；輸入完整而 raw response 仍改錯 prime、字面值、識別字，就記為辨識缺口，停止用特例追答案。改善須跨案例有效、保留回歸，否則停止該假設；沿用[既有評估預算](pdf-core-g2-eval-freeze-2026-10-15.md)，不新增數值門檻。

未重新排名模型、升版或驗公司 GPU／負載；現有結果不足以宣稱已達模型準確率上限。
