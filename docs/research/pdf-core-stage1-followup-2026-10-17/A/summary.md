# A：責任與 fragment ordering 的有界離線接點

2026-10-17。**有新的公開 Core 接點實證；完整 A coverage／模型 gate 仍未通過。** 本輪沒有模型、API、下載、安裝或 holdout。停止在通用方法與來源覆蓋界線，不追加 renderer 或案例規則。

`method.py` 以來源 native item／provenance index 綁定輸出 blocks；`order` 同時包含 target fragments 與未消耗的 sibling anchors。用公開 `insert_node_items`／`delete_items` 建立派生 Core，再用未修改的 `MarkdownDocSerializer`。同一 owner 的兩個 fragments 因而可以分別交付在另一個原生 sibling 前後；原 `BODY → middle → TITLE` 反例已實際得到正確順序。這是相對 whole-owner 單點替換的接點改進，不是新的閱讀順序模型，也沒有用幾何排序當來源真相。

原始文件及 provenance 留在 scope／binding；派生文字 charspan 與原始 source charspan 分開，實際 response／fragment indices 也保存。Parent captions、tables／pictures 由各自原生 render owner 保留，不因 standalone text boundary 不可達就誤判丟失。非目標 anchor 的相對順序與 stock 序列化內容必須一致，公開 Core 重新編號後的 refs 另有對照。

## 實際產出

| 證據 | 範圍與結果 |
|---|---|
| `inventory.json` | 同 pinned cached S0：WikiSkill p20–22、DGM p51、SEAL p2–4、controls p1，共四來源八頁。162 個 native items 加 34 個 table cells，共 196 rows；77 body、4 caption、37 table（含容器）、68 picture（含 children）、10 unresolved furniture。這是責任／transport 清單，並非來源 recall 或 API calls。 |
| `native-replay/` | 四份實際 stock Markdown；caption refs 均在原生 parent 路徑序列化一次。Table cell 已保存字串不再另列 A VLM 工作，但 table 意思／結構是否正確仍由 B 與來源評讀負責。 |
| `mock-replay/`、`replay-results.json` | 四來源、66 個 body direct-parent targets 真正映射及 JSON reload；空原生公式使用明示 MOCK placeholder，其他文字沿用 native，不能算轉錄成績。 |
| `group-replay/`、`group-replay-results.json` | 另外 11 個 eligible group children（SEAL 9、controls 2）以同一規則、逐原生 parent 實際映射／reload。這兩份是分別從原 S0 出發的控制，沒有拼成同一份完整候選。 |
| `picture-replay/`、`picture-replay-results.json` | 三個原生 pure-formula picture envelopes 的合法 native／MOCK handoff；公開 Core 將公式放在可達位置，原 picture image 欄位及來源保留。三個 children 是 members，不重複計 jobs；未驗影像 crop 完整或模型公式準度。 |
| `controls/interleaved-fragments/` | 保存來源、scope、合法 response、派生 Core／binding 及實際 Markdown，具體解原 whole-owner 排序反例。 |
| `test_method.py`、`test-log-final.txt` | 17 個 unittest 通過；含 interleaving、cross-page 單次交付、空 formula、prose＋inline LaTeX、`<s>`／`&`、code identifier／縮排、native list marker、caption／picture／table、foreign／stale／duplicate／overlap／missing fragments、不可消耗 anchors、source geometry 與 saved artifacts 的 byte-exact reload。 |

## 必須保留的界線

1. **Mapping 順序能力不等於發現或辨識能力。** 本機合成回應能指定正確 fragment order；四來源 native/MOCK replay 則沿用 native sibling order。沒有聲稱實際來源讀序、完整 inline／code 轉錄或模型品質通過。全來源 figure／body 交界、native 未 emit 的 glyphs 仍不能靠這份 inventory 宣稱已涵蓋。
2. **Caption 原生運輸與 inline enrichment 分開。** Stock Core 的 caption 路徑讀 caption.text；把 typed InlineGroup 掛到 caption 下，不能證明它在原 caption 位置遞迴序列化。新方法保留普通 caption text 的原位一次交付；typed inline caption enrichment 明確拒絕並列未解，不另加 renderer。
3. **Picture 責任不是「圖內內容已完成」。** 一般 picture children 可由 C 的 image content 工作承接，但原生 picture marker 並未把 61 個 hidden text children 當正文交付。Pure-formula envelopes 有上述機械 handoff，混合 figure／body 的來源內容仍待獨立 coverage 判定。
4. **表格不重複送 A，但也不自動視為語意正確。** Table cells、span／row association、table envelope provenance 及 literal 是否出現在 stock Markdown 已分列；沒有虛構 cell bbox。複雜 fraction／cell 歸屬若失真，仍是必要工作，而非以責任轉移排除。

因此保留這個通用公開接點，**停止完整 A 的新增推論；`N_CF=null`**。完整來源比較由隔離 A-review 另交付，不把 84 個各類 eligible records（77 body、4 caption transport、3 picture envelopes）冒充可執行 calls 上限。沒有重新跑相同 whole-owner 反例或把來源答案／人工 bbox 注入 jobs。

比較用入口（不寫檔、不叫模型）：

```sh
rtk <tmp>/pdf-core-native-std-20261017/venv/bin/python -B -m unittest discover -s docs/research/pdf-core-stage1-followup-2026-10-17/A -p test_method.py -v
```

`method.py`／`replay.py`／`test_method.py --record` 是首次產生證據的入口，使用 exclusive writes，不能拿來覆寫既有證據。`precheck-*` 保存 development 前版與原因；最終 method／inventory hashes、時間及輸出另見 registration／artifact manifest。

未做新模型準度、fresh Standard、完整合成配置或成本／GPU／吞吐測量；17 個離線測試不是完整 A 或整體 profile 驗收。
