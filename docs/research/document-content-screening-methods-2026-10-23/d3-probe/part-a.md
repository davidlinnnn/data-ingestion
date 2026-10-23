# d3 probe Part A：confidence 的實測定義

執行環境：Apple Silicon、MPS、torch 2.14.0、transformers 5.17.0；模型 `vllm-sr/d3-nano@462efc36`、`vllm-sr/d3-mini@bd0090dd`，離線載入、官方 `AutoModel` + `system_one()`，runtime 與權重未修改。Codex 在其 sandbox 內無法取得 Metal 裝置（`results.json` 的兩筆 failures），測試改由主線在 sandbox 外以相同腳本與凍結輸入執行。環境與 hash 見 `environment.json`。

## 結果

| model | request | returned confidence | max(p) | 1 − normalized entropy | 符合 |
|---|---|---|---|---|---|
| nano | choice-2-clear | 0.997350 | 0.999808 | 0.997350 | entropy |
| nano | choice-2-tie | 0.000019 | 0.502577 | 0.000019 | entropy |
| nano | choice-3-clear | 0.997555 | 0.999728 | 0.997555 | entropy |
| nano | choice-3-tie | 0.000482 | 0.344954 | 0.000482 | entropy |
| nano | choice-5-clear | 0.997900 | 0.999675 | 0.997900 | entropy |
| nano | choice-5-tie | 0.004037 | 0.228336 | 0.004037 | entropy |
| nano | score-3-level-0 | 0.995311 | 0.999436 | 0.995311 | entropy |
| nano | score-3-level-2 | 0.985679 | 0.997936 | 0.985679 | entropy |
| nano | score-5-level-0 | 0.995817 | 0.999292 | 0.995817 | entropy |
| nano | score-5-level-4 | 0.991640 | 0.998453 | 0.991640 | entropy |
| nano | noul-true | absent | 0.998688 | 0.985552 | — |
| nano | noul-false | absent | 0.999868 | 0.998103 | — |
| mini | choice-2-clear | 0.996208 | 0.999713 | 0.996208 | entropy |
| mini | choice-2-tie | 0.007283 | 0.550199 | 0.007283 | entropy |
| mini | choice-3-clear | 0.997928 | 0.999774 | 0.997928 | entropy |
| mini | choice-3-tie | 0.057843 | 0.506006 | 0.057843 | entropy |
| mini | choice-5-clear | 0.997400 | 0.999588 | 0.997400 | entropy |
| mini | choice-5-tie | 0.020377 | 0.296828 | 0.020377 | entropy |
| mini | score-3-level-0 | 0.987240 | 0.998215 | 0.987240 | entropy |
| mini | score-3-level-2 | 0.987328 | 0.998219 | 0.987328 | entropy |
| mini | score-5-level-0 | 0.989560 | 0.997945 | 0.989560 | entropy |
| mini | score-5-level-4 | 0.976154 | 0.994645 | 0.976154 | entropy |
| mini | noul-true | absent | 0.998764 | 0.986278 | — |
| mini | noul-false | absent | 0.999842 | 0.997779 | — |

## 結論

- HF 套件路徑（`AutoModel` / `system_one()`）：`choice` 與 `score` 的 `confidence` 在 nano、mini 全部 20 筆都等於 **1 − normalized Shannon entropy**（誤差 ≤ 1e-6），沒有一筆等於 max(p)。平手案例最明顯：choice-2-tie 的 max(p) = 0.503，confidence 約 0。
- `noul` 只回傳 `noul`（P(yes)），沒有 `probabilities`，也沒有 `confidence`。
- 套件沒有公開 `label_mass`，因此 vLLM 公式 `max(p) × label_mass` 無法在此路徑重算。
- vLLM `/v1/systemone` 路徑：依 upstream 原始碼 `vllm/entrypoints/openai/decisions/question_types.py`（choice、score、noul 皆回 `confidence = max(p) × label_mass`）與 `adapters.py`；vLLM 只支援 CUDA／ROCm，本機未執行。d3 模型卡「Run with vLLM」一節說的「chosen option probability」描述的是這條路徑，省略了 `label_mass`。
- 因此兩份官方文件各自描述不同路徑，都不是錯的；#84 W4b 把套件路徑的觀察推論為「recipe 說法錯誤」，是推論過度。
- 另注意：套件內的 `d3_engine.py` 是 Decision Index 評測 kit 的 engine，不是 vLLM Semantic Router 的 Engine mode。
- 實務規則：判斷時一律讀 `probabilities`（或 `noul`），不讀 `confidence`；兩條路徑的 `confidence` 定義不同，換服務方式會改變數值。
