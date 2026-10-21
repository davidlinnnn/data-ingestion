# Canonical 候選 spike

[Review 索引](README.md) · [候選草稿](../design/knowledge-platform-canonical-contract-draft.md) · [已確認決策](../design/knowledge-platform-canonical-design.md)

**日期：2026-10-09。結論：六組資訊的邏輯骨架可保留；未找到需要重開已確認決策的矛盾。**
本次是人類 review 前的文件／情境 spike；以下發現與待確認狀態保留原始審查時點。

**後續處置（2026-10-09）：** 使用者於 [Q21](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6075416972)確認六組資訊、
確切候選的驗證／接受紀錄與最少重複原則。正式欄位與完整案例 review 仍待完成；此後續確認不構成 runtime 驗收。

## 範圍與證據

固定審查版本為 [`498bff0`](https://github.com/davidlinnnn/data-ingestion/tree/498bff0d18858dc4e727479fbda64732c6fae285)。
原始候選 `docs/design/knowledge-platform-canonical-contract-draft.md` 的 SHA-256 為
`dec92c986d14e49ff238c8265260bd15b2797b4ff92e950c139ad044d2d9d35e`。
此綁定指向補入本次澄清之前的草稿，不是修訂後檔案的雜湊。

一個未繼承對話的 reviewer 對照候選、已確認設計與 ADR 做反例檢查；
另兩個 reviewer 分別檢查資訊重複，以及固定 PDF core 的實際完成／證據契約。
主 agent 核對原則與 producer 程式後，整理以下處置。

本次只做文件／情境與程式核對；未執行 parser、mapper、Wiki 或 Retrieval。
目前反例可由已確認規則與現有程式回答，沒有需要 executable probe 才能決定的新設計未知。
真實映射與方法能力仍須後續驗證；本次不提供 runtime 品質保證。

## 補清楚兩個既有原則

| 反例 | 必須保留的結果／依據 | 草稿處置 |
|---|---|---|
| PPTX 解讀依賴 rendering，驗證當下可讀，卻仍會隨 processing checkpoint 清理。 | 必要來源與採用證據的 custody 保護須先於完成接受；見[整體設計](../design/knowledge-platform-logical-design.md)。可讀不等於已建立適用的保留保護。 | 接受列明說此條件。沒有新增服務、複製 bytes 或永久保留要求。 |
| SOP C1 已接受，後來發現漏了原規則就要求的必要警告。 | 保留歷史接受，記錄失效理由、證據、範圍及可歸責判定；停止合格選用並交接 Projection／治理，不能等 C2 完成才處理；依 [Q9](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035318528)。後來規則變嚴不等於原接受錯誤。 | 補入跨案例檢查。沿用目前資格與既有 owner，不增加專用工作流。 |

這些是既有決策的澄清，不是新的待決架構。

## 減少草稿可能暗示的重複

六組資訊是 review 清單，不是六份獨立資料或六個服務。建議同一事實只保留一個權威表示：

- 圖片出現組件可直接承載原始引用與固定目標；包含／順序已表達的關係無須再複製到另一清單。
- 支持對應不必在內容與證據兩端雙向維護。必要支持範圍與限制仍須保留。
- 限制保留在所屬結果／映射，整份涵蓋報告引用即可；採納的 Enrichment 文字也不要求再複製一次。

草稿已加入上述簡化建議；具體欄位安排仍待 Q21 review。
不能為了去重而合併 Q20 已確認的兩個圖片出現位置，也不能混同處理輸入、結果目標與支持證據。

## 保留兩個 PDF 映射負例

PDF core 固定為 `fe1b283c49c83ad5aeee6808e77b4f25549eba03`。
以下是程式允許的狀態或 mapper 可能犯的錯，不是本次觀測到的 parser 失真。

1. **OCR complete，必要警告仍缺失。** [選取集合](https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/enrichment.py#L49) 是 parser 已輸出的 PictureItems，排除 page render；[完成檢查](https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/enrichment.py#L112) 允許 `no_text_detected`。因此 completion 不能證明必要意思已保存。負例的預期結果：候選缺少必要警告，就不得接受。
2. **mapper 只帶文字／完成 manifest，漏接採用結果的證據。** Core 已[核對保存的 OCR crop](https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/tests/pdf_processing/q04/consumer.py#L273)，並[發布固定來源與頁面證據](https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/enrichment.py#L194)。負例的預期結果：候選無法連回實際輸入、方法與必要支撐 artifact，就不得接受。這不是 core 未留存的缺陷，也不要求另存所有表格 crop。

這兩項加入草稿的後續驗證案例，沒有新增 schema 要求。
[既有 retained-output 研究](https://github.com/davidlinnnn/data-ingestion/blob/47b363781448cc72d6cb12df2b76927c101c2e23/docs/research/docling-capabilities-vs-pdf-core-2026-10-02.md#L250)
也已區分 bytes／歸屬核對與 OCR／關係語意品質。

## 其餘情境與後續

PDF 的值／表頭／單位／註解、SOP 的完整條件與重複附件上下文、PPTX 的方向／分支／備註，
都有既有規則可判定遺失或錯配不可接受。
附件 I1→I2、採納新 Enrichment、舊 S1 搭配新前置條件、歷史 C1 引用與接受前撤回，
也未暴露新的責任缺口。這是契約檢查，不是實際抽取能力已通過。

建議以修訂草稿繼續 Q21 人類 review，不先建立通用 graph、細粒度重算引擎或消費端實作。
本票仍須完成三格式案例、映射驗證計畫、完整 PDF reconciliation、研究 disposition 與歷史 ADR 盤點。
[Design canonical processing profiles and PDF-core integration](https://github.com/davidlinnnn/data-ingestion/issues/72)、
[Define canonical consumption and publication for Wiki and Retrieval](https://github.com/davidlinnnn/data-ingestion/issues/55)、
[Define governance enforcement across canonical data and published views](https://github.com/davidlinnnn/data-ingestion/issues/56)與
[Select canonical persistence and artifact ownership](https://github.com/davidlinnnn/data-ingestion/issues/57)沿用既有責任。
沒有新增 ADR、勾選結案條件、關閉決策票或更新 map 的已解決索引。
