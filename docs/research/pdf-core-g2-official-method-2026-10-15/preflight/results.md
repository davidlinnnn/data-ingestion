# Official VLM pipeline：離線接點與 parser 核對

2026-10-15。使用既有 CPU `.venv` 的 Docling **2.102.0／Core 2.96.0**，實際執行 `DocumentConverter → VlmPipeline → ApiVlmEngine → official parser/assembly`；僅將 HTTP transport 換成固定 mock。兩頁 synthetic PDF，不讀取來源論文、holdout 或憑證，不載入模型權重，不修改套件。這是格式／整合可行性檢查，不是辨識品質測試。

| 固定 synthetic 輸出 | Markdown | HTML | DocTags |
|---|---|---|---|
| 普通文字與第二頁 sentinel | 保留 | 保留 | 保留 |
| Inline LaTeX `x^{2} + y_{i}` → Markdown | 下標被文字 exporter 轉為 `y\_{i}`；沒有 formula item | 同左，math wrapper 仍為普通文字 | 原樣保留，有 inline group／formula item |
| Inline code、獨立 code 的縮排／字面值 | 保留 | 保留 | 保留 |
| 2×2 table 的 cells／數值 | 保留 | 保留 | 保留 |
| Picture／caption | 有 picture，無內嵌圖、caption 未綁定 | 有 picture／caption 綁定，無內嵌圖 | 有來源 crop、caption 綁定及內嵌圖 |
| 頁碼與座標 | 頁碼1/2保留，全部 bbox 為零 | 同左 | 頁碼1/2保留，11個非零 bbox |

**決定：DocTags 是下一組官方 API 方法的可用格式。** 固定模型若能生成這套官方 grammar，原生 parser 足以交付此 synthetic 結構，不需要自訂 typed JSON／回填或數學修補。這不表示模型已能正確辨識、產生所有內容或準確定位 bbox；此次座標由 fixture 預先給定。此處 MD／HTML 僅測所列原生表示，不宣稱所有 HTML math encoding 都失敗。[Tagged pipeline](https://github.com/docling-project/docling/blob/v2.102.0/docling/pipeline/vlm_pipeline.py)

原生 page stage 硬編碼 `temperature=0`／4096 tokens；官方 API runtime 的 `params` 可覆寫。已捕捉實際 payload 證明 `temperature: null`、`max_completion_tokens: 8192`、`reasoning_effort: low` 與 `store: false` 原樣送出，衝突的 `max_tokens` 被移除。這是既有配置介面，沒有 source patch；真實服務是否接受 null 尚未在此測試。[Stage](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/vlm_convert/vlm_convert_model.py)、[API engine](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/vlm/api_openai_compatible_engine.py)

Malformed HTTP error envelope 負例被 helper 吞成空結果，native pipeline 仍可能回報 `success`。外層必須保存並核對 raw HTTP response、每頁非空輸出與 stop reason，不能單憑 native status 判完成；這是傳輸／完整性檢查，不是輸出修補。[Helper](https://github.com/docling-project/docling/blob/v2.102.0/docling/utils/api_image_request.py)、負例實測 (`negative-control.json`)

重現：`rtk proxy docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python docs/research/pdf-core-g2-official-method-2026-10-15/preflight/run.py`。斷言通過，所有非 mock transport 被封鎖；selfcheck (`selfcheck.json`)、summary (`summary.json`)、合成 request／response (`transport-captures.json`) 保留實際結果。未測模型品質、真實 API 接受度、GPU／負載或 Canonical Acceptance。
