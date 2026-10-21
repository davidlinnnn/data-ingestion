# Caption ownership：零模型控制與 T05 重播

2026-10-17。**既有 T05 caption 重複可以靠保留原有 ownership 避免，無須再呼叫模型，也無須文字去重。** 六個合成情境、一個非法輸入拒絕控制與一次保存輸出的 T05 重播皆通過。本輪只證明接合與來源保留；不能推論已找回原流程漏掉的 caption，也沒有新增「必須有 native caption link」的驗收要求。

## 最小政策

沿用 frozen `adapter.py` 的所有型別、完整 grid、來源、graph 與 serializer 檢查。新研究 wrapper 在呼叫 mapper 時不把 provider caption 當作新增 source text；原始 provider caption／完整 response 保存在 bindings 的 observation 中。已有的 native caption link 和正文節點均完整保留。

沒有 native link 且 provider 傳回 caption 時，記錄 `unresolved_provider_observation=true`。這表示來源歸屬／是否缺漏沒有由系統確認，**不是自動拒絕 canonical 的新條件**。若來源 caption 原本就在正文，F07 可以允許它以 standalone／uncertain association 形式保留。若來源 caption 真正未被 baseline 擷取，wrapper 不會憑 caption 字串推定位置或增補，因此此情境仍未解決；不能因為沒有重複而判定內容完整。

| 控制 | 主要 Markdown 的結果 | 歸屬／完整性界線 |
|---|---|---|
| Native linked caption，provider 相同 | 原 caption 一次；原 link／provenance 保留 | 證明 ownership 保留，沒有重新驗證來源語義 |
| Native linked caption，provider 不同 | 原 caption 一次；不以 model observation 覆寫 | 不同 observation 原樣保留，未判定哪一份語義正確 |
| Caption 已在正文，但沒有 native link | 正文原 caption 一次；不新增 duplicate | 保留 standalone；不靠字串相同建立 attachment |
| Caption 真正沒有在 baseline 中 | 不新增 caption；provider observation 保留並標為未解決 | 缺漏沒有被補回；不能當成完整 caption 交付通過 |
| 正文原本有兩個相同字串 | 兩個節點、內容與順序皆保留 | 沒有做 text dedup，避免誤刪合法重複來源 |
| 沒有 native link，provider 也回空白 | 保持來源原狀 | 不能從兩者皆空推論來源沒有 caption |

這些情境的「已存在／真正缺漏」由合成 fixture 作者知道；runtime 對沒有 native link 的情境無法自行作出這個判斷。provider 字串相等僅用於 assertion 計數，沒有進入政策決策或 attachment 實作。

## T05 保存輸出重播

輸入只讀先前已產生的 WikiSkill p13 `baseline.json` 與 `output.json`。原 frozen mapper 重現 canonical／Markdown caption 各兩次：baseline 的 `#/texts/1` 已含完整 caption，而 native table `captions=[]`，fallback 又新增一次。

新政策保留原正文 caption，canonical／Markdown各一次；table cells 與原 mapper 完全一致，原始 provider observation 保留。**T05 的 caption 來源保留與 duplicate 缺陷控制通過；它沒有取得新的 native caption attachment，也不需要把 attachment 缺失自行升格為失敗。** 沒有重新評分數字、論文內容或宣布完整 ProcessingProfile／G2 合格。

## 檢查與重現

每個合成情境及 T05 都驗：輸入 document／response 不變、完整 tree／reference 有效、非目標 content／語義 reference／順序／provenance 不變、原 native captions 保留、table envelope 不變、provider response 保留、serializer spans 指向 canonical 節點、serialization 不改 canonical、JSON roundtrip／Markdown 一致。另有一個不完整 grid 的拒絕控制，確認 wrapper 沒有繞過 frozen 邊界驗證。非目標 rich cell 的 reference 允許公開 API 合法重編號，核對其指向的來源與 provenance。

使用既有 Docling Core2.99.0 環境執行：

```sh
rtk proxy /private/tmp/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-caption-ownership-2026-10-17/verify.py
```

[registration.json](registration.json) 記錄程式與所有 frozen direct-cell artifacts／共用 helper 的 SHA256；[verification.json](verification.json) 記錄執行後 hashes 與 assertions，前後一致。新輸出為明確標示 provisional 的 document／Markdown／bindings；舊 adapter、gate、實驗 artifacts、production 與 SDK 均未修改。沒有新套件、模型、API、來源 PDF、oracle 或 holdout 讀取。

**建議保留此 ownership 政策作下一個 bounded candidate 的接合規則；缺漏偵測與來源關係的驗證仍需另外量測。** 不值得加入全文字串 dedup、模糊比對或猜測 caption attachment。此結果只消除額外重複的接合行為，不改善 T04 的大量遺漏，也不改變 latency／accuracy 的候選取捨。
