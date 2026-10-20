### G2：dots.ocr＋MLX 真實 GPU 驗證完成，本機可行但不採完整方案

依「OK, 先執行 dots.ocr＋MLX GPU」，已在M5 Pro20核GPU／48GiB上完成主實驗12頁，再完成2頁官方PDF backend渲染診斷。既有 dots-studio/dots.ocr@c0111ce6bc07803dbc267932ffef0ae3a51dc951 BF16權重直接載入，兩份shard再次核對SHA，643 tensors／3,039,179,264 parameters的原生strict loading與名稱/shape/BF16覆蓋通過。未量化或替換為社群checkpoint。

隔離Docling2.132／Core2.99／MLX0.32.4／MLX-VLM0.7.8；主機Device(gpu,0)實際生成，所有14次upstream finish reason為stop。正常渲染10頁每頁16.4–31.0秒，中位數21.5秒；同一controls頁16.4秒完成，先前CPU在180秒停止。主實驗含初始化共243.83秒。MLX peak allocated約6.65GiB、取樣process-tree RSS約3.96GiB，兩個計數不能相加。未驗高頻、多併發或公司CUDA效能。

Docling MLX loader漏傳trust_remote_code，本輪在上游公開loader API補傳trust_remote_code=True／use_fast=False；原source processor、prompt、token IDs、attention mask、pixel values、grid與CPU controls參考核對一致。沒有套件/model/parser source patch。另保存首次僅因缺rtree而在import階段失敗的紀錄，該次未建立模型或推論；官方PDF extras補齊後另存runtime v2 freeze。

八頁41來源單位仍按原oracle核對：raw內容36符合、5不符（包含原約定嚴格identifier大小寫）；F13完整交付可確認6/18，F14為3/7，不能把raw符合率當Acceptance。DGM有test_success／run_tests等識別字誤讀、edit_actions→editActions，且raw JSON invalid escape令官方parser交付空document但conversion仍success。SEAL更新式theta變theta_0；HTML sub/sup、重複$$定界符與跨頁段落仍有交付缺口。E14完整段落及六個行內公式則正確保留，局部改善原樣記錄。

獨立validation保持原12正例／10普通文字負例／60個math子項契約。主實驗第一份文件8正例中6內容符合、2失敗：影像code參數被換成黑方塊、q_tilde-phi變q_phi；兩個普通文字引用另有Iizuka大小寫誤讀。第二份文件兩頁在送模型前已被預設renderer畫黑，4正例＋1負例記為input-render failure，未從分母刪除或歸咎模型。

先以零推論的官方PyPdfiumDocumentBackend核對，兩頁恢復正常，再另登記2次相同模型/precision/prompt/scale的渲染診斷；屬不同backend處理配置，未覆寫主12頁結果或合併成更好的validation分數。診斷abstract保留；四個math段落3符合、1失敗，兩處原稿gg+gq_S被讀成gg+gq-bar-s，仍改變數學意思。

結論：本機Apple GPU已可繼續模型比較，公司endpoint不再是當前必要前提；dots.ocr尚不選作完整challenger，G2仍未通過，正式profile不變。不追加逐題prompt／字串修補或重跑挑成功。下一輪比較其他官方文件模型/元件組合，PyPdfium可列具體backend候選但未完成全範圍採用驗證。六份holdout未讀；228筆舊payload核對不變，GPU程序已清理，所有新輸出與診斷均保留。

完整本機報告：`docs/research/pdf-core-g2-dots-mlx-2026-10-16.md`；主實驗及另行登記的renderer診斷在各自同名資料夾。證據完整性通過不代表模型或Canonical Acceptance通過。
