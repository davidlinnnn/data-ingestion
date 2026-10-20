# PDF core G2：凍結評估，避免對已知案例過度調整

日期：2026-10-15（Asia/Taipei）。承接[邊界與回歸結果](pdf-core-g2-inline-boundary-2026-10-15.md)及 [#84](https://github.com/davidlinnnn/data-ingestion/issues/84)。**本輪完成評估規則、既有回歸清單與六份新文件的來源固定；沒有調整模型／規則或執行新推論。文件已取得，不代表 holdout 案例已標註或品質已通過。**

## 已固定的資料角色

| 資料 | 角色與限制 |
| --- | --- |
| 既有 G1／G2 與較早研究來源 | 保守排除於新 holdout。盤點46個 PDF 路徑、35種 bytes、32個原始作品群組；考慮 controls／survey／NCCU 的衍生連結後為30個保守連通群組，仍不等於30個獨立模板族群。 |
| 既有57個 G1 case、V01–V19、17筆 paragraph outputs及四個既有正例錨點 | 保留為開發與回歸。這兩個角色可以共用已曝光資料；其分數不能冒充獨立 validation。來源正例標籤也不等於模型已通過。 |
| 六份新科學論文 | 版本、URL、完整 SHA-256及檔案 bytes 已固定，約3.11MB；僅下載／核對 magic、大小及 hash，未開啟 PDF 內容、建立標註或跑模型。與既有排除群組及 bytes 無交集。 |

同一原稿的版本、鏡像、頁面、裁圖、掃描、旋轉及衍生內容須在同一組。歷史頁面即使未個別評分，也不因重新隨機切分成為未見資料。已曝光的失敗結果與正例均保留。[來源盤點](pdf-core-g2-eval-freeze-2026-10-15/exposure-audit.md)／[新文件 custody](pdf-core-g2-eval-freeze-2026-10-15/holdout-custody.md)／[回歸清單](pdf-core-g2-eval-freeze-2026-10-15/regression-manifest.json)

新文件是以公開 metadata、既有曝光檢查及可取得性挑選的有界論文集合，並非隨機抽取的 production corpus。這裡的「未見」只指未用於本次實驗選方法，不保證未出現在模型預訓練，也不保證模板／作者／領域統計獨立。SOP、繁中及技術手冊未補齊；公式／code子型態實際數量仍待來源標註，不能先宣稱覆蓋。

PDF bytes 依既有 fixture 慣例留於本機並由 `.gitignore` 排除版控；custody manifest 保存確切 URL與hash。重建環境仍須取得相同 bytes，缺檔不得跳過或冒充驗證成功。

## 下輪調整的限制

現在沒有進行模型權重 fine-tuning；prompt、裁圖、normalization及拒絕門檻同樣視為可造成 overfitting 的參數。反覆依測試結果選方法會產生選擇偏差，因此先限制下一個開發週期最多 **3組新完整配置**，每次先寫明假設與改動，優先沿用 defaults，不做大型 grid search。這是本案的工作預算，不是新的辨識準確率門檻。[選擇偏差研究](https://jmlr.org/papers/v11/cawley10a.html)、[官方資料洩漏說明](https://scikit-learn.org/stable/common_pitfalls.html)

所有配置使用相同已曝光資料與來源標準；已有正例新增拒絕、漏字、改義、重複或來源映射退化即阻止採用。先比較必要品質、逐文件／逐任務的交付與失敗，再在同品質條件下比較 latency／成本。前輪已否決的通用 token guard 不回頭對 E14／E04 調參；原生文字也不是 gold。

最多選定 **1個 challenger** 與固定 baseline 作配對確認。尚無乾淨 validation 分數；若需要擴大模型／門檻搜尋，先另取得與 holdout 分組隔離的 validation，不拿 holdout 決定下一組參數。現有已知案例的 grouped CV 不能消除既有曝光，因此本輪不硬湊80／10／10，也不增加 nested CV。[分組評估](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data)

## 評分先固定，缺失也計入

每份新文件的抽頁規則已固定：首、末物理頁，加上其餘頁面按 `SHA256(document_sha256:page_number)` 排序最前兩頁；去重後每份最多四個評分頁。兩方法使用相同全文頁面與相鄰頁 context。獨立 curator 先從原稿建立這些頁面全部相關段落／獨立公式／code與無公式／code的負例清單，保留延續邊界；不能從模型 emitted items 反推分母，或只挑已辨識的漂亮裁圖。這是有界頁面驗證，不宣稱全文 detector recall。

每個固定來源單位只有一個結果：忠實交付、不忠實交付、明確拒絕、執行失敗、未嘗試／缺輸出。行內公式／code是其段落的必要子項，不能另加進總分母重複計數。重複輸出使對應來源單位失敗；無來源新增內容另計，不能藉擴大分母稀釋。

| 指標 | 固定分母與解讀 |
| --- | --- |
| 交付覆蓋 | 方法交付的來源單位／全部來源清楚的必要單位；不是 Canonical Acceptance。 |
| 已交付錯誤率 | 未達來源標準的交付單位／已交付單位；全部拒絕時為未定義。 |
| 忠實交付率 | 達到既有來源標準的交付單位／全部必要單位；失敗與缺輸出仍在分母。 |
| 正例誤拒、技術失敗、未嘗試 | 分別列出被影響的來源單位／全部適用正例；失敗 request 次數另列，不能混用單位。 |
| 負例錯誤與無據新增 | 用固定負例清單另計，不能靠高正例總分掩蓋。 |

同時報告原始計數、每文件與每任務結果，以及 baseline→challenger 的新增退化／恢復。來源本來有歧義者須在看模型前明列；模型不會辨識不能改標成來源歧義。沒有適用單位時標示未驗，不能報0錯誤或100%成功。既有複雜表容差、等義 LaTeX 與使用者的普通說明文字字形容忍均保持原適用範圍，沒有新增 accuracy／CER門檻。[Coverage與selective risk](https://proceedings.neurips.cc/paper/2017/file/4a8423d5e91fda00bb7e46540e2b0cf1-Paper.pdf)

六個有目的挑選的作品不足以支持 production accuracy 或獨立模板泛化，不能將同頁大量 crops 當獨立樣本計算窄信賴區間。本輪只保留逐文件的配對計數；若後續使用區間，須另交代抽樣與群組相依假設。[NIST 小樣本區間限制](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)

## 執行前仍需完成的兩項工作

1. 在已曝光開發資料上，把局部 boundary／context 方法整理成可重現的一般候選，保住適用回歸，固定 baseline與單一 challenger 的程式、模型、prompt／parser／crop政策、依賴及執行設定 hashes。候選與程式不接收 oracle答案或人工 gold boxes。
2. 由不參與調參的 source-only curator 依固定抽頁規則建立頁面、必要來源單位與評分清單；缺的子型態明示未驗。之後才可執行一次配對 holdout，完整保留失敗，不挑成功重跑。

**目前 holdout run 尚未開啟**：方法 lock與來源清單尚未完成。看過 holdout 結果後若改方法，該批便成為下輪開發／回歸資料；保留本輪結果，再取得新批次，不能重切資料追求較好分數。隔離是工作流程上的分工，repository 權限並未建立強制的 evaluator sandbox。

[機器可讀 protocol](pdf-core-g2-eval-freeze-2026-10-15/protocol.json)、[primary-source依據](pdf-core-g2-eval-freeze-2026-10-15/primary-sources.md)與[獨立設計核對](pdf-core-g2-eval-freeze-2026-10-15/independent-review.md)保存具體規則。[離線驗證](pdf-core-g2-eval-freeze-2026-10-15/verify.py)核對來源與群組、57項回歸引用、四個正例範圍、前十輪1,816個 payload、九個 split負例，以及全拒絕／空分母／混合失敗的計分小測驗；[結果](pdf-core-g2-eval-freeze-2026-10-15/validation.json)與[manifest](pdf-core-g2-eval-freeze-2026-10-15/artifacts.json)保留證據。這些離線核對不是新候選的行為回歸通過。

沒有新推論、API費用、正式 gate／profile採用或 production改動；公司 GPU／vLLM、高頻負載及完整 Canonical整合仍待驗，G2 尚未全面通過。

[本輪結論已寫回 #84](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6193047443)，本文只新增摘要連結，44個 feature rows及既有需求均保持原樣，issue維持 OPEN；[寫回紀錄](pdf-core-g2-eval-freeze-2026-10-15/ticket-update.json)保存 exact readback與hash。
