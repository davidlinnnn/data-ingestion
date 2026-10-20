# Code UTF-16 原來源稽核

直接讀原 PDF 的 raw Unicode，非根據既有已漏字 evidence 判斷。每個原 region 各自做中心點選取／無 padding，使用統一 decode_selected_utf16；半 surrogate pair 不擴框。

{
  "original_stage4_native_units": 67,
  "original_signals_code_rows": 21,
  "union_source_units_audited": 71,
  "unique_PDF_pages_raw_unicode_scanned": 59,
  "original_raw_code_units_scanned": 178600,
  "page_problem_code_units_inside_or_outside": 10,
  "affected_source_units": 1,
  "affected_stage4_primary_native": 1,
  "affected_stage4_common": 0,
  "affected_signals21": 1,
  "affected_signals_a_known": 0
}

原 code-native 與 cohort 未改；是否可保留主結果：False。
