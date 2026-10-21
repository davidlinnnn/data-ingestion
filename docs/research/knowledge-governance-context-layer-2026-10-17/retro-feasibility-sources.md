# 治理控制可行性反證：四個可執行邊界

**查閱日期：2026-10-17。狀態：針對既有治理研究的可行性檢查；以下最小契約均為建議，尚未採納為 MVP 要求。**

本筆記只挑戰 purpose enforcement、withdrawal／cache、delivery／actual use、prompt injection 四項承諾。共四個主要官方來源；沒有實作或 runtime 測試。

## 1. Purpose：能限制受控路徑，不能驗證人的真實目的

**來源事實。**[NIST SP 800-162](https://nvlpubs.nist.gov/nistpubs/specialpublications/NIST.SP.800-162.pdf)（2014-01，PDF 含 2019 errata）區分政策判定 PDP、實際執行 PEP、屬性來源 PIP；屬性須由有權責來源建立與維護，並考量時效、完整性與 provenance。這是 ABAC 指引，不是 agent purpose enforcement 的現成產品或認證。參見 §§1.4、2.4.2、3.2.2.10。

**最小契約建議。**由既有 Serving／consumer 整合固定一個已核准的應用與模型處理路徑；以已驗證 actor、consumer、操作及可信政策決定是否交付。caller 的 `purpose` 是申請資訊，不能自行建立權力。若目前要求禁止外送，就須在可控制的 provider／egress 邊界落實，或不開放該路徑。

**不能保證。**平台把文字交給任意 caller 後，無法僅靠標籤或 purpose 欄位阻止另行複製／訓練；通過判定也不能證明人的主觀用途。未知 provider 是否保留／訓練，不能由來源 ACL 推定。最小驗證是讓同一已獲讀權身份，經未核准 consumer／route 申請時被拒絕，而非只看到警告。

## 2. Withdrawal：撤 token 不等於撤完資料，也不等於所有節點同步完成

**來源事實。**[RFC 7009](https://www.rfc-editor.org/rfc/rfc7009.html)（2013-08，Standards Track）§2.1 承認實務 revocation propagation delay；§3 說明立即 access-token 撤銷需要 resource server 協作，短期 token 只是限制窗口。它處理 token，不規定內容快取、衍生產物或已交付資料的追回。

**最小契約建議。**先只對一個 selected consumer 承諾：每次平台披露前檢查目前資格；無法建立可信 current state 時不披露。首版若沒有可驗證的 client cache 失效機制，就先不允許該 client 持久快取受控內容。宣告撤回開始、平台阻擋新披露、consumer 處理完成與 custody purge 是不同事實，不共用一個籠統「已撤回」狀態。

**不能保證。**TTL 到期不是即時撤回；通知送出不是接收方已失效；刪除原文不是下游副本／模型 context 已清除。撤回與在途請求的先後切點、允許窗口及完成證據仍須由 #56／Serving owner 明定，不能從 OAuth 引用自動得出。

## 3. Cache 與 injection：控制每次操作，不能以一次 retrieval 授權包辦

**來源事實。**[OWASP RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)（rolling guidance，查閱頁未標版本日）§§10–12 區分 retrieval 與 tool authorization，建議 cache 依權限範圍隔離並隨來源／權限變更失效，也記錄 cache hits；預設不記 raw query／context／output。§1 明說 digest 符合保護基線不代表沒有 injection，§3 要求逐模型測試。這是安全指引，非無注入保證。

**最小契約建議。**選定 harness 把來源內容當資料；測試僅涵蓋 selected client 實際暴露的能力。若該路徑暴露 tool／egress，才在其執行邊界檢查 actor、任務、目標與參數，並測原本已允許能力的任務外目標／外送副作用。只有 bounded read 的 client 不因此需要新增或認證寫入工具批准機制。任何 cache hit 也不能繞過目前資格。保留固定原證據；掃描結果另記，不默默改寫原文。

**不能保證。**allowlist 只能限制可碰的工具，不能保證獲准工具不被濫用；delimiter／system prompt／scanner 都不能承諾偵測全部攻擊。此建議不要求每份文件人工簽核。完整 agent 控制仍在 Knowledge Platform 之外，由實際 consumer／agent／tool owners 承接。

## 4. Delivery：最多證明觀測到的事件，不宣稱模型真的依賴了內容

**來源事實。**[Databricks service lineage](https://docs.databricks.com/gcp/en/data-governance/unity-catalog/ai-gateway-service-lineage)（current product docs，查閱頁未標發布日）在 Limitations 明說只記 service definition 的 dependencies，不捕捉 runtime callers／agents 及其存取資料。這是產品能力的具體限制，不能推廣為所有 lineage 或 tracing 工具都辦不到。

**最小契約建議。**平台先記可觀測的結果版本、證據參照、actor／consumer、政策判定、事件時間與 correlation；該時間不代表實際使用時間。事件名稱區分「選取／送出／客戶端確認收到」；沒有 acknowledgement 不把 server 寫 log 當成客戶端收到。若要知道有無送進模型，需 selected consumer 另回報對應 model-request 的 context 版本參照。

**不能保證。**catalog dependency、server delivery log、consumer 回報都不能單獨證明該內容造成某項推理或決策。首版不需要完整 trajectory 或保存所有 prompt；可先把「實際使用／決策歸因未提供」明示為證據界線。

## 可直接縮成產品工作的結論

四個候選交付單位是：**一條受控 consumer／provider 路徑、一個有目前資格檢查的披露契約、所選路徑實際暴露能力的相應測試、最小可歸責交付事件。**先證明這些邊界，再決定是否要擴大 policy vocabulary、cache 協定或 traces；並不需要先建立通用 policy engine、prompt-injection classifier 或全域 agent 監控平台。

未做端到端攻擊、撤回競態或 provider 設定實測；以上來源只支持控制位置與限制，不能據此宣稱本平台已具備 enforcement 或決定新增驗收門檻。
