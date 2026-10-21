# 表格交付接合：離線驗證結果

後續：使用者本輪直接提供credential後，已完成[兩頁live驗證](pdf-core-table-live-results-2026-10-17.md)。以下保留離線階段當時的結果與credential阻礙紀錄。

2026-10-17；依[確認計畫](pdf-core-table-delivery-plan-2026-10-17.md)完成步驟一。**離線交付 gate 通過：既有正確表格回應可用公開 Docling Core 型別與文件樹 API，完整交付至主要 Markdown，不需要修數值或自訂 renderer。** 兩頁 live API 尚未執行：目前執行環境沒有配置 `OPENAI_API_KEY`，已向使用者要求環境變數名稱或設定檔路徑，未從歷史聊天擷取金鑰。

這是表示／交付可行的證據，**不是新的模型準度成功或完整 Processing Profile**。沒有新增模型推論、安裝套件、下載權重、讀取 PDF／圖片像素、開啟 holdout 或恢復 Paddle；只使用既有 JSON／原始碼、Markdown，及原 API image bytes 的 lineage hash。

## 實際配置與範圍

| 項目 | 本次執行 |
|---|---|
| 上游 | 重用2.132 S0 StandardPdfPipeline 的 SkillOpt p8結果；PyPdfium、Heron、selective RapidOCR、TableFormer V1 accurate、原生 assembly；本輪未重新推論 |
| 既有 producer | 10/14暫用 gpt-6-luna 的完整 Table2 raw；未改 prompt、raw或評分規則，未作新API呼叫 |
| 實際 runtime | 既有 Standard venv，Core2.99／Pydantic，僅載資料型別；檢查未匯入torch／transformers／mlx |
| 新增接合 | research-only mapper (`pdf-core-table-delivery-2026-10-17/mapper.py`)：公開 GroupItem、TableData／TableCell、insert／append／add／delete API；不是官方內建API table stage |
| 表示 | 一個邏輯 group，六個 panel titles＋六張子表；原 source caption由首張子表引用一次，其他表格與正文保持原順序 |
| 匯出 | 原生 `export_to_markdown()`，預設 stock serializer；JSON reload後再次匯出一致 |
| 來源 | 沿用whole-table native envelope，cell bbox=None；保存原API input／request／response與baseline hashes、source key、原始provenance及provider metadata |

## 已驗證的內容

| 檢查 | 結果 |
|---|---|
| Panel／資料列 | 6個panel、28列完整保留 |
| Typed table | 84/84數值與metric／setting／panel綁定正確；printed strings全部相符，0 unmatched extras |
| 主要 Markdown | 從實際匯出表格逐cell比對，84/84綁定與printed strings保留；不是只在JSON內數數字 |
| 必要比較 | typed內容重建後沿用原評分器，8/8 critical comparisons成立；Markdown與typed grid相同 |
| Caption／條件 | 原Standard完整caption保留一次，原有三組條件可解讀；provider conditions亦保留於manifest，詳見[來源評讀](pdf-core-table-delivery-2026-10-17/source-review.md) |
| 回歸 | Table3、其他正文、來源位置與順序相同；不把正常ref重編號誤報為內容改動 |
| 文件完整性 | tree／全部references有效、無orphan／重複節點；JSON reload與stock Markdown roundtrip一致 |
| 格式／失敗控制 | 新live schema普通表走相同parser→mapper→export；缺target、重複／未知key、缺欄／重複metric／超列寬、數值型別強制轉換、重複panel、無效來源／越界bbox均拒絕 |
| 避免oracle滲入 | mapper不讀oracle、不硬編84／28；格式合法的新增row明確允許進入source evaluator評分，不能在ingest冒稱已辨識它是多寫 |

完整檢查 (`pdf-core-table-delivery-2026-10-17/verification.json`)、逐點評分 (`pdf-core-table-delivery-2026-10-17/typed-quality.json`)、輸入與程式身分 (`pdf-core-table-delivery-2026-10-17/registration.json`)已保存。探索過一次public mapper與一次printed precision控制；完整gate首次已通過，補齊lineage記錄後再驗一次，沒有對內容／numeric結果調參。`doc.furniture`公開相容屬性有deprecated warning，未為消警告修改SDK或移動來源。

## 必須保留的界線

- 舊raw漏字面`Table 2`沒有被改寫；Markdown引用本來已有表號的native source caption。這是採用既有來源文字，不是從oracle補字。
- Markdown將左右排列展開為六個依序子表，不保證重現PDF排版。原caption位於(a)title後、第一張子表前；邏輯group及manifest保留共同來源身分。
- Panel title／table共用整張表的envelope，並不表示各panel覆蓋整張表，更不表示有精確panel／cell bbox。來源粒度已明列，完整F18未認證。
- Table3原本的flattening／內容問題仍存在。「未改」不代表Table3正確；下一階段同頁全部native tables均須處理與評讀。
- 此次使用已知T02 target做replay，不證明自動inventory→request路由。兩頁都是曝光DEV，未新增泛化／holdout證據。

## 下一步與目前阻礙

公開映射可行，因此不用擴張內容後處理，也不需重試Granite CPU。已固定通用prompt (`pdf-core-table-delivery-2026-10-17/prompt.txt`)、新response schema (`pdf-core-table-delivery-2026-10-17/response-schema.json`)與API readiness (`pdf-core-table-delivery-2026-10-17/api-readiness.json`)。它們不含正確數值、表名或oracle內容。

**目前停在credential條件，0/2個live requests送出。** 待安全配置可用後，完成Memory-R1 p8的同版S0 conversion，再凍結兩頁全部native targets／144dpi影像hash，按已確認的單一協定普通表→複雜表各一次比較。Memory-R1已有舊2.102結果，不能冒稱它是本輪2.132 S0，因此尚未列為可直接執行的完整registration；SkillOpt S0已清點兩個targets。沒有跳過缺失的普通表control或只測Table2。

Live仍維持2頁／最多2requests／8targets、retry0、concurrency1、每request180秒、max_completion_tokens8192、整個API／映射／export階段30分鐘。ordinary保護、T02≤5%及全部8關鍵比較、同頁附帶工作均沿用原計畫。不從本次離線結果推論Qwen3、GPU／vLLM latency、高頻吞吐或完整Canonical Acceptance。
