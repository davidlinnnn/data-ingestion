# W3c Q13人工裁定後彙總

僅16張定向稽核表套用人工裁定；其他表沿用W3b機器結果，未冒稱全量人審。60張來源定位UNKNOWN、3張範圍外仍另列，Adam來源不可知。

|版本|交付|一般 P/F/U|複雜 P/F/U|合計 P/F/U|
|---|---|---|---|---|
|E0|RAW|7/5/59|4/7/101|11/12/160|
|E0|MAPPED|7/5/59|4/7/101|11/12/160|
|cellFalse|RAW|19/4/48|8/5/99|27/9/147|
|cellFalse|MAPPED|21/4/46|9/4/99|30/8/145|

# 全部FAIL表的錯率

精確率以=標示；≥為確證下界，未完成全點／多生裁定時無精確率或上界。沿用機器者另標。漏與多生都計錯，不將率硬截100%。RAW/MAPPED相同表仍保留兩行供核對。

|版本/交付|表/頁|Q13|錯率|來源|
|---|---|---|---|---|
|E0/RAW|F-acl_sbert:html-semantic-table:S4.T2 p5|complex|≥6.6667%|本輪人審|
|E0/MAPPED|F-acl_sbert:html-semantic-table:S4.T2 p5|complex|≥6.6667%|本輪人審|
|E0/RAW|F-ieee_tacotron2:html-semantic-table:S3.T4 p4|complex|≥14.2857%|沿用機器，非本輪人審|
|E0/MAPPED|F-ieee_tacotron2:html-semantic-table:S3.T4 p4|complex|≥14.2857%|沿用機器，非本輪人審|
|E0/RAW|F-nips_attention:html-semantic-table:S6.T3 p9|complex|≥8.4211%|沿用機器，非本輪人審|
|E0/MAPPED|F-nips_attention:html-semantic-table:S6.T3 p9|complex|≥8.4211%|沿用機器，非本輪人審|
|E0/RAW|P-01-2608.27454v1:html-semantic-table:S4.T1 p8|complex|≥6.0000%|本輪人審|
|E0/MAPPED|P-01-2608.27454v1:html-semantic-table:S4.T1 p8|complex|≥6.0000%|本輪人審|
|E0/RAW|P-03-2603.25158v5:html-semantic-table:A2.T9.fig1 p14|complex|≥50.0000%|沿用機器，非本輪人審|
|E0/MAPPED|P-03-2603.25158v5:html-semantic-table:A2.T9.fig1 p14|complex|≥50.0000%|沿用機器，非本輪人審|
|E0/RAW|P-06-2606.14239v2:html-semantic-table:A1.T4 p15|complex|≥8.3333%|沿用機器，非本輪人審|
|E0/MAPPED|P-06-2606.14239v2:html-semantic-table:A1.T4 p15|complex|≥8.3333%|沿用機器，非本輪人審|
|E0/RAW|P-10-2509.25140v2:html-semantic-table:A3.T5 p27|ordinary|≥23.0769%|沿用機器，非本輪人審|
|E0/MAPPED|P-10-2509.25140v2:html-semantic-table:A3.T5 p27|ordinary|≥23.0769%|沿用機器，非本輪人審|
|E0/RAW|P-11-2508.19828v5:html-semantic-table:S4.T2 p8|ordinary|≥16.6667%|本輪人審|
|E0/MAPPED|P-11-2508.19828v5:html-semantic-table:S4.T2 p8|ordinary|≥16.6667%|本輪人審|
|E0/RAW|P-11-2508.19828v5:html-semantic-table:A6.T3 p18|complex|≥5.9259%|沿用機器，非本輪人審|
|E0/MAPPED|P-11-2508.19828v5:html-semantic-table:A6.T3 p18|complex|≥5.9259%|沿用機器，非本輪人審|
|E0/RAW|P-13-2601.01885v3:html-semantic-table:S4.T4 p9|ordinary|≥12.5000%|本輪人審|
|E0/MAPPED|P-13-2601.01885v3:html-semantic-table:S4.T4 p9|ordinary|≥12.5000%|本輪人審|
|E0/RAW|P-13-2601.01885v3:html-semantic-table:A4.T6 p26|ordinary|≥12.5000%|本輪人審|
|E0/MAPPED|P-13-2601.01885v3:html-semantic-table:A4.T6 p26|ordinary|≥12.5000%|本輪人審|
|E0/RAW|P-20-2505.03335v1:html-semantic-table:A3.T5 p32|ordinary|≥19.7531%|沿用機器，非本輪人審|
|E0/MAPPED|P-20-2505.03335v1:html-semantic-table:A3.T5 p32|ordinary|≥19.7531%|沿用機器，非本輪人審|
|cellFalse/RAW|F-acl_sbert:html-semantic-table:S4.T2 p5|complex|≥10.0000%|本輪人審|
|cellFalse/MAPPED|F-acl_sbert:html-semantic-table:S4.T2 p5|complex|≥10.0000%|本輪人審|
|cellFalse/RAW|F-cvpr_yolo:html-semantic-table:S4.T3 p7|ordinary|≥0.2381%|本輪人審|
|cellFalse/MAPPED|F-cvpr_yolo:html-semantic-table:S4.T3 p7|ordinary|≥0.2381%|本輪人審|
|cellFalse/RAW|F-lncs_deeplab:html-semantic-table:S4.T3 p9|complex|≥23.2143%|本輪人審|
|cellFalse/MAPPED|F-lncs_deeplab:html-semantic-table:S4.T3 p9|complex|≥23.2143%|本輪人審|
|cellFalse/RAW|P-04-2605.23904v2:html-semantic-table:S3.T1 p7|complex|≥5.2326%|本輪人審|
|cellFalse/MAPPED|P-04-2605.23904v2:html-semantic-table:S3.T1 p7|complex|≥5.2326%|本輪人審|
|cellFalse/RAW|P-04-2605.23904v2:html-semantic-table:S3.T3 p8|ordinary|≥4.0000%|本輪人審|
|cellFalse/MAPPED|P-04-2605.23904v2:html-semantic-table:S3.T3 p8|ordinary|≥4.0000%|本輪人審|
|cellFalse/RAW|P-13-2601.01885v3:html-semantic-table:A4.T7 p27|ordinary|=12.5000%|本輪人審|
|cellFalse/MAPPED|P-13-2601.01885v3:html-semantic-table:A4.T7 p27|ordinary|=12.5000%|本輪人審|
|cellFalse/RAW|P-15-2610.05923v1:html-semantic-table:A1.T5 p15|ordinary|=33.3333%|本輪人審|
|cellFalse/MAPPED|P-15-2610.05923v1:html-semantic-table:A1.T5 p15|ordinary|=33.3333%|本輪人審|
|cellFalse/RAW|P-19-2511.10395v1:html-semantic-table:S7.T2 p20|complex|=10.4167%|本輪人審|
|cellFalse/MAPPED|P-19-2511.10395v1:html-semantic-table:S7.T2 p20|complex|=10.4167%|本輪人審|
|cellFalse/RAW|P-19-2511.10395v1:html-semantic-table:S7.T3 p21|complex|≥33.3333%|本輪人審|

P04 p7 T1原frozen N344不是完整的主分數＋gain component分母；本輪用完整數字個數上界688與36個確證缺失，報≥36/688=5.2326%，不再冒稱36/344為精確率。原答案不改，來源缺陷另記。
