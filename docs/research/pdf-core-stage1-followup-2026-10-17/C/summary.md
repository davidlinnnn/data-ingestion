# C 同一 native input 的圖片 supplement 接合

本輪 **機械 gate pass，完整 C 仍 partial**。相較原第一段，本輪補的是同一個 pinned S0 picture owner、同一 crop、明示 MOCK 回應、同版 supplement 與主要 Markdown 一起保存／搬移／第二 process 讀回；沒有將原先 synthetic owner 的歷史 API 回應拼接成 native enrichment 成功。新增模型／API／安裝／下載／holdout 均為 0。

| 控制 | 結果與可支持的結論 |
|---|---|
| 同一 native owner | 固定 `S0/nccu/document.json` 的 `#/pictures/0`。原圖的 53 個 children、text、caption refs、parent、順序、provenance 及全文件 graph 完整保留；允許的變動只有 picture image 資源 URI 與公開 `PictureMeta.description`。 |
| 同一 crop／回應身分 | 894×653 RGB 原生 crop 的 PNG SHA 與 image key 寫入 `provider/mock-response.json` 的 input；MOCK OCR／description 明確標示、原 payload（含額外 provider 欄位與 uncertainties）整份保存。不是模型準度。 |
| 實際映射 | 原頁 595.3200073242188×841.9199829101562 PDF points；S0 page image 1191×1684 px，固定 `images_scale=2`。Standard 的 requested bbox 經 Pillow round 得 page pixel window `[125,485,1019,1138]`，從原 page image 裁出內容與 native crop 逐像素相同。窗口、原 bbox、有效 bbox、X/Y scale、實際 crop／page 尺寸皆另存，沒有使用舊控制的固定216 DPI反推座標。 |
| Crop→原頁 | MOCK polygon 在 crop px，以 `x_pdf=(x_crop+125)/2`、`y_pdf=(y_crop+485)/2` 回填 page TOPLEFT points。幾何邊界按實際 crop pixels；不把四捨五入後 crop 的邊界冒充原 native bbox。 |
| Generated 與 source 分離 | MOCK description 透過官方 `DescriptionMetaField` 保存，OCR／映射透過自訂 sidecar image key 提供；主要 Markdown 使用 `allowed_meta_names=set()`／`include_annotations=False`，保留原生 children 與圖片 URI，不把 MOCK 文字／圖意寫成原文。 |
| 搬移／讀回 | `bundle-original/` 整份搬至 `bundle-relocated/`，從新 cwd 的第二 Python process 讀回。6 個 bundle files 驗 SHA、圖資源、完整 Core、主要 Markdown、supplement、raw payload；不是 Pod／checkpoint 恢復。 |
| 四方向 mapping | 純合成 317×199 幾何、X/Y不同縮放2.3／1.7，0/90/180/270 各6點正逆映射共24點通過；另有固定軸向預期值與錯方向對照。未載入方向模型，未驗真實頁方向判別。 |
| 負控制 | 17個邊界負例拒絕：revision／method／owner／重複owner／key／crop身分／provenance／required-work豁免／window／scale／page size／mapped polygon／另一crop回應／越界polygon／非法角度，及 scale／窗口連同 mapped polygon 一起協同錯改。 |
| 回歸測試 | 7個 unittest通過，另驗缺圖、raw mutation、native child text／順序改動，以及改像素後同步更新 SHA／key／raw input／manifest 仍拒絕；原 bundle 與引用歷史檔案不變，`--check` 不改報告或 manifest。 |

固定 runtime：Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3／PyPdfium2 5.14.0。公開部分為 `PictureItem.get_image`、Core load/export、`ImageRef`、PictureMeta description 及官方 Markdown serializer；自訂部分為 image key／sidecar、identity／mapping validation、幾何轉換與離線負控制。沒有 SDK patch、新 renderer 或新模型路由。

同輸入的 MOCK OCR 只是有界接口測試，不會拿 NCCU 原生 53 children 當新 OCR 分數，也沒有把舊 RapidOCR crop 的 53 texts 接到本輪不同 crop。Chart assessment 保留 `unattempted`、分類為 `unknown`；required work 仍包含 OCR、description、chart_assessment，未知分類不豁免它們。原 C 已保存六份 API、chart13點與一份RapidOCR證據，本輪均未重評或改寫。

可安全重跑的 read-only 檢查入口（不加參數為產物產生器，已存在時會拒絕覆寫）：

```sh
rtk <tmp>/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-stage1-followup-2026-10-17/C/controls.py --check
rtk <tmp>/pdf-core-native-std-20261017/venv/bin/python -B -m unittest discover -s docs/research/pdf-core-stage1-followup-2026-10-17/C -p 'test_controls.py' -v
```

`registration.json` 保存 started/deadline/elapsed、固定計畫 SHA 與下一段未凍結欄位；`results.json` 是實際接合結果，`test-log.txt`／`test-results.json` 是測試，`evidence-hashes.json` 登錄原有來源／方法引用，`method-hashes.json` 固定本輪方法與產物。產生器／只讀檢查分開，重跑檢查不更新 hash 或報告。

尚未完成：全55頁 source-only 圖片／required-work census；同版 heading/title/semantic parent；真實方向 detector 與 rotated-page lineage；同版分類、圖意、OCR、chart準度；fresh Standard 與 worker／Pod 恢復。`N_3`、tokens 上限仍未凍結，**不送新推論，不放行完整配置／第三段**。本 gate 不以全量 census 尚未做完否定已成立的同輸入機械接合，也不將接合成功升格為所有圖片的 coverage 成功。

主線預檢更正：初版 validate 只從 supplement mapping 重算座標，無法拒絕 scale／窗口與mapped polygon一起錯改。`precheck-v1/` 保留當時方法／結果。本輪最終版改由bundle內不可變 baseline 的原始 native provenance、page/picture ImageRef DPI、page image 與 native embedded crop 獨立重建窗口與縮放；實際reload再逐像素核對bundle crop。新增兩個協同變更負例及更新全部 hash 的錯圖測試均拒絕。原始／搬移 bundle 完全未變，不需要新模型或重建產物。
