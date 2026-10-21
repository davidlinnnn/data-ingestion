# G2 API：NCCU panel／英語 scan 來源核對

2026-10-14。這次只查來源、下載公開 PDF 和比較本機 pixels，沒有讀取 API credential、呼叫推論 API 或傳送文件圖片。

**G1-O03 英語 scan：公開來源與內容一致性已驗證。** 原稿是 [arXiv:2303.18223v1](https://arxiv.org/abs/2303.18223v1)，官方 [版本化 PDF](https://arxiv.org/pdf/2303.18223v1) 本次 unauthenticated GET 為 HTTP200，1,817,841 bytes，SHA-256 `d58be5fc39608dc9aec45194c602436d793f2f2bf56f267d0e38d6258a9f7a9e`，與本機原稿及既有 fixture manifest 完全相同。下載證據 (`public-ocr-order.json`)。

本機 scan fixture（SHA `7856cfe6127948d506ca5fad750e915134be362b5e1436c70b378f42a6fda2a0`）的兩張 embedded raster，逐像素等同本次公開原稿 physical p3／p5 以 PDFium scale2／144dpi 產生的 RGB 圖片；對應既有 `fixtures.py` 的生成方式。預計 API 只用 scan p1，即原稿 p3；1,224×1,584，PNG SHA `9323155f3b6ca2c24a9483a9532e8bf947d512c0ec1a5686a6113eca8d8db1f3`，也逐像素等同 scan p1 的 scale2 render。raster 比對證據 (`english-scan-raster-check.json`)。已目視該頁，內容是 LLM survey 正文、研究引用及註腳，沒有私人帳號、credential、公司內部資料或個人紀錄。

**G1-O01 NCCU：既有公開來源證據成立，但本次直接下載 bytes 尚未重新驗證。** 凍結 registry 和原 acquisition manifest 均記錄 [政大官方公開 PDF](https://posman.nccu.edu.tw/files/archive/424_1f69c9f2.pdf)，七頁「個人簡要自述—一般公務人員使用手冊」，local PDF SHA `3a8d8a946a5962cc1b666ec6a33dc5482556da7013a70ca096fc8d86439a5f6e`。本次 web open 仍能讀到這個 URL 的七頁 manual 內容；然而直接 unauthenticated urllib GET 為 HTTP403，web screenshot 亦為 cache miss，故不宣稱新下載 bytes 相符。直接下載結果 (`public-ocr-order.json`)。

預計 API 圖片只含 p3 的 685×230 中央 navigation panel，PNG SHA `67daf56dc4b467605c202096cb16413818dd22063a85dc13a40d2401ce109f68`。已斷言它逐像素等同本機 p3 唯一 embedded image（1,262×731）以 pypdf `PageObject.images` 解碼 Image35.jpg 為 RGB，再以 `[240,132,925,362]` crop 產生的圖片，沒有私有 overlay。panel 比對證據 (`nccu-selected-panel-check.json`)。已目視 panel；只有「首頁／我的專區／應用系統」等導航標籤、操作提示及 `B5A:個人簡要自述` 連結名稱，沒有實際姓名、帳號、身分證號、登入 credential 或個人自述。文件名稱中的「個人」是產品功能名，這張 panel 沒有個人檔案內容；不會上傳整份 manual，其他頁面的範例也不在此次 payload。

以上是重新送交 automatic approval review 的具體來源與內容證據，不能代替其判定。既有 session 已允許暫用官方 OpenAI VLM 作比較；root 回報補充公開來源證據後，正式重新審查已批准四次單次 request，無剩餘 permission block。本 source check 本身沒有執行推論或取得 credential；實際 API 執行結果由 root 另外記錄。

未推論／未接觸 credential；NCCU 官方 URL 的本次 HTTP403 使目前公開 bytes 的重新核對仍有限制。
