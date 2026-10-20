"""Evidence-backed adjudication of frozen table source gold; no gold edits."""
import collections,copy,hashlib,importlib.util,json,pathlib

ROOT=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('assess',ROOT/'assess_e0.py');assess=importlib.util.module_from_spec(spec);spec.loader.exec_module(assess)


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    oracle=json.loads((ROOT/'oracle.json').read_text());frozen=json.loads((ROOT/'freeze.json').read_text());assert hashlib.sha256((ROOT/'oracle.json').read_bytes()).hexdigest()==frozen['oracle_sha256']
    prelim=json.loads((ROOT/'E0-preliminary.json').read_text());delivery=json.loads((ROOT/'delivery-audit.json').read_text());source={t['id']:t for t in oracle['tables']};nativeaudit={(t['job_id'],t['native_ref']):t for t in delivery['tables']};tables=[];reviews=[]
    source_ready=[t for t in oracle['tables']if t['scope']=='IN_SCOPE'and not t['source_uncertainty']and t['required_numeric_point_candidates']and t['trusted_numeric_points']==t['required_numeric_point_candidates']and not any(g['issues']for g in t['grids'])]
    assert len(source_ready)==14
    contamination=json.loads((ROOT/'P13-chart-contamination.json').read_text())
    failures={'P-11-2508.19828v5:table-001':{'missing':['grid-00-point-0001'],'extra':[('grid-00-point-0004','41.05')],'reason':'Printed F1/B1/J are separate columns. Native PPO(J-based) B1 is empty while 23.36 appears in row-header; native PPO(EM-based) B1 contains 41.05 (belongs to F1) and 32.91.','source_stage':'native_table_structure','details':'Original table crop shows all 4 columns and both data rows. Saved table bbox covers them; the missing/extra association is already in native cells/grid, before Markdown serializer. Mapper preserves native cell text/positions.'},'P-13-2601.01885v3:table-003':{'missing':['grid-00-point-0003'],'extra':[('grid-00-point-0002','3.93')],'reason':'Printed Answer-Only has MQ=0.479 and TC=3.93. Native MQ cell contains both 0.479 and 3.93 while the TC grid position is empty.','source_stage':'native_table_structure','details':'Source PDF p9 Table4, source LaTeX and native bbox/cells reviewed. Wrong column association exists in native grid; not caused by RAW span expansion or mapper.'},'P-13-2601.01885v3:table-005':{'missing':['grid-00-point-0003'],'extra':[('grid-00-point-0002','7.21')],'reason':'Printed Answer-Only has MQ=0.415 and TC=7.21. Native MQ cell contains both 0.415 and 7.21 while TC grid position is empty.','source_stage':'native_table_structure','details':'Source PDF p26 Table6 and source LaTeX confirm numeric object association. Mapper retains merged native text and does not split or reassign values.'},'P-06-2606.14239v2:table-015':{'missing':[f'grid-01-point-{i:04d}'for i in range(1,34,2)],'extra':[],'reason':'Composite source Table12 contains 8 knowledge-type rows plus17 task-type rows, each n and Reward:50 source datapoints. Native right table retains Reward header, but all17 Reward positions are empty; reward values are packed into task row-header cells.','source_stage':'native_table_structure','details':'Original full p27 plus right table crop inspected; native table18 is right-hand task-type subtable. Source left/right table identity preserved as one composite gold. Only right-side17 missing Reward tuples counted; remaining33 points are not silently declared correct.'}}
    visual_detections={'P-03-2603.25158v5:table-004':'#/tables/5','P-19-2511.10395v1:table-004':'#/tables/3'}
    for original in prelim['tables']:
        row=copy.deepcopy(original);gold=source[row['id']];jid=row['job_id']
        if row['id']in visual_detections:
            native_doc=json.loads(pathlib.Path(row['input']['native_json']).read_text());source_input=row['input']
            row=assess.assess_table(gold,assess.native_tables(native_doc),visual_detections[row['id']]);row['input']=source_input
        row['source_full_denominator_eligible']=gold['id']in {t['id']for t in source_ready}
        if row['id']in visual_detections:
            ref=visual_detections[row['id']];row.update(detection='DETECTED',alignment='VISUAL_SOURCE_AND_NATIVE_BBOX_CONTENT_WITNESS',native_ref=ref,visual_reviewed=True)
            row['manual_detection_evidence']={'original_page_image':str(ROOT/'review/pages'/f'{jid}-p{row["source_pages"][0]:03d}.png'),'crop':str(ROOT/'review/pages'/(row['id'].replace(':','-')+'-crop.png')),'source_caption':[c['text']for c in gold['captions']],'native_ref':ref,'reason':'Caption is present in original source page but not linked as native table caption. Original grid location, full distinctive header/row labels and exact body values identify the unique native table; not same-page-only matching.'}
            reviews.append(dict(id=row['id'],kind='detection_resolved',**row['manual_detection_evidence']))
        audit=nativeaudit.get((jid,row.get('native_ref')))
        if audit:row['delivery_evidence']={k:audit[k]for k in ['RAW_export_path','MAPPED_export_path','RAW_official_export_exactly_in_saved_document','raw_native_table_cell_count','raw_grid_slots','raw_same_native_cell_repeated_in_grid','raw_numeric_nonheader_repeated_exposures','mapped_same_ref_duplicates','native_cells_unchanged_by_mapper']}
        verdict='OUT_OF_SCOPE'if row['source_scope']=='OUT_OF_SCOPE'else'UNKNOWN'
        confirmed=[]
        if row['id']in failures:
            spec=failures[row['id']];pointmap={p['id']:p for p in row['points']}
            for pid in spec['missing']:
                point=pointmap[pid];assert point['assessment']['status']=='MISSING_VALUE_CANDIDATE'
                confirmed.append({'type':'missing_value_row_col_tuple','point_id':pid,'value':point['source']['value_text'],'row_labels':point['source']['row_labels'],'col_labels':point['source']['col_labels'],'native_empty_position':point['assessment']['native_cell'],'source_point_status':point['source']['status']})
            for pid,value in spec['extra']:
                point=pointmap[pid];assert value in point['assessment']['extra_value_candidates']
                confirmed.append({'type':'extra_value_under_wrong_row_col_label','at_source_point':pid,'value':value,'row_labels':point['source']['row_labels'],'col_labels':point['source']['col_labels'],'native_cell':point['assessment']['native_cell'],'source_required_value_at_position':point['source']['value_text']})
            denominator=gold['required_numeric_point_candidates'];assert gold['trusted_numeric_points']==denominator
            lower=len(confirmed)/denominator
            assert gold['complexity']=='ordinary'or lower>0.05
            verdict='FAIL';page=row['source_pages'][0]
            review={'id':row['id'],'job_id':jid,'source_pages':[page],'source_caption':[c['text']for c in gold['captions']],'source_origin':gold['source'],'original_page_image':str(ROOT/'review/pages'/f'{jid}-p{page:03d}.png'),'crop':str(ROOT/'review/pages'/(row['id'].replace(':','-')+'-crop.png')),'native_ref':row['native_ref'],'RAW_export':audit['RAW_export_path'],'MAPPED_export':audit['MAPPED_export_path'],'reviewed_visual':True,'reason':spec['reason'],'stage':spec['source_stage'],'stage_evidence':spec['details'],'confirmed_errors':confirmed,'source_complete_numeric_denominator':denominator,'confirmed_error_count_lower_bound':len(confirmed),'error_rate_lower_bound':lower,'exact_full_error_rate':None,'unknown_other_points_retained':True,'Q13_verdict':'FAIL','Q13_basis':'ordinary requires zero errors'if gold['complexity']=='ordinary'else'confirmed error lower bound exceeds5% with complete source denominator','RAW_MAPPED_same_failure':True}
            row.update(visual_reviewed=True,confirmed_error_count_lower_bound=len(confirmed),source_complete_numeric_denominator=denominator,error_rate_lower_bound=lower,exact_full_error_rate=None,confirmed_errors=confirmed,stage=spec['source_stage'],visual_adjudication=review)
            reviews.append(review)
        if row['id']==contamination['id']:
            verdict='FAIL';confirmed=contamination['confirmed_errors'];reviews.append(contamination)
            row.update(visual_reviewed=True,verdict_subtype='FAIL_WITH_PARTIAL_ORACLE',confirmed_error_count_lower_bound=len(confirmed),source_complete_numeric_denominator=None,source_numeric_denominator_upper_bound=87,error_rate_lower_bound=len(confirmed)/87,exact_full_error_rate=None,confirmed_errors=confirmed,stage=contamination['stage'],visual_adjudication=contamination)
        row['RAW']={'verdict':verdict,'verdict_subtype':row.get('verdict_subtype'),'wrong':None,'missing_confirmed':sum(e['type']=='missing_value_row_col_tuple'for e in confirmed),'extra_confirmed':sum(e['type'].startswith('extra_')for e in confirmed),'numerator_lower_bound':len(confirmed),'denominator':row.get('source_complete_numeric_denominator'),'source_denominator_upper_bound':row.get('source_numeric_denominator_upper_bound'),'exact_error_rate':None,'error_rate_lower_bound':row.get('error_rate_lower_bound'),'unknown_retained':True}
        row['MAPPED']=copy.deepcopy(row['RAW']);row['MAPPED']['native_data_unchanged']=True
        if row['source_full_denominator_eligible']:
            row['source_complete_numeric_denominator']=gold['required_numeric_point_candidates']
            row['RAW']['denominator']=gold['required_numeric_point_candidates']
            row['MAPPED']['denominator']=gold['required_numeric_point_candidates']
        row['verdict']=verdict
        if verdict=='UNKNOWN':
            row['reason']='Source/label/structure/alignment/delivery uncertainties remain; cannot turn strict numeric subset or native-row/column counts into a whole-table pass/fail.'
        tables.append(row)
    families=[]
    for family in sorted({t['family']for t in tables}):
        group=[t for t in tables if t['family']==family];families.append({'family':family,'source_tables':len(group),'source_scope':dict(collections.Counter(t['source_scope']for t in group)),'complexity':dict(collections.Counter(t['complexity']for t in group)),'confirmed_native_detection':sum(t['detection']=='DETECTED'for t in group),'native_detection_unknown':sum(t['detection']!='DETECTED'and t['source_scope']=='IN_SCOPE'for t in group),'RAW':dict(collections.Counter(t['RAW']['verdict']for t in group)),'MAPPED':dict(collections.Counter(t['MAPPED']['verdict']for t in group))})
    result={'version':'w3-E0-tables-adjudicated-v1','oracle_sha256':frozen['oracle_sha256'],'source_gold_unchanged_after_global_seal':True,'scope':'All36 saved E0 documents; official RAW table export and unchanged frozen W2 JSON-only mapper. No conversion/inference. FAIL based on visually proven numeric tuple errors; UNKNOWN never pass.','counting':'Value+row/column label tuples. A missing required tuple and an extra tuple at a different label position are separately counted, as preregistered. Wrong values can be counted once when replacing a value at same labels. Counts here are confirmed lower bounds, not complete full-table error rates.','source_counts':oracle['counts'],'families':families,'counts':{'documents':36,'source_tables':len(tables),'IN_SCOPE':sum(t['source_scope']=='IN_SCOPE'for t in tables),'OUT_OF_SCOPE':sum(t['source_scope']=='OUT_OF_SCOPE'for t in tables),'source_localization_UNKNOWN':sum(t['source_scope']=='UNKNOWN'for t in tables),'confirmed_detection':sum(t['detection']=='DETECTED'for t in tables),'IN_SCOPE_matching_UNKNOWN':sum(t['source_scope']=='IN_SCOPE'and t['detection']!='DETECTED'for t in tables),'RAW_verdicts':dict(collections.Counter(t['RAW']['verdict']for t in tables)),'MAPPED_verdicts':dict(collections.Counter(t['MAPPED']['verdict']for t in tables)),'visually_confirmed_failed_tables':len(failures),'confirmed_error_tuple_lower_bound':sum(t.get('confirmed_error_count_lower_bound',0)for t in tables)},'tables':tables}
    result['counts']['visually_confirmed_failed_tables']=sum(t['verdict']=='FAIL'for t in tables)
    result['counts']['source_full_numeric_denominator_eligible_tables']=len(source_ready)
    result['counts']['source_full_numeric_denominator_eligible_complexity']=dict(collections.Counter(t['complexity']for t in source_ready))
    result['source_full_denominator_eligible_ids']=[t['id']for t in source_ready]
    result['papers']=[]
    for paper in oracle['papers']:
        group=[t for t in tables if t['job_id']==paper['id']]
        result['papers'].append({'id':paper['id'],'family':paper['family'],'source_inventory_status':paper['inventory_status'],'source_inventory_uncertainty':paper['inventory_uncertainty'],'source_tables':len(group),'IN_SCOPE':sum(t['source_scope']=='IN_SCOPE'for t in group),'confirmed_detection':sum(t['detection']=='DETECTED'for t in group),'source_full_denominator_eligible_tables':sum(t['source_full_denominator_eligible']for t in group),'RAW':dict(collections.Counter(t['RAW']['verdict']for t in group)),'MAPPED':dict(collections.Counter(t['MAPPED']['verdict']for t in group)),'zero_source_tables_is_not_paper_PASS':True})
    result['prior_raw_to_Core_bbox_normalization']=[]
    for jid in ['P-10-2509.25140v2','P-20-2505.03335v1']:
        input_path=assess.R3/'heading/jobs'/jid/'inputs.json';normal=json.loads(input_path.read_text());bboxdiff=[d for d in normal['source_to_core_normalization_diff']if'/bbox/'in d['path']]
        result['prior_raw_to_Core_bbox_normalization'].append({'id':jid,'evidence':str(input_path),'bbox_coordinate_differences':len(bboxdiff),'scope':'Existing raw recovery baseline to Core normalization before B-only E0 serialization; not new inference/model/table improvement. The current mapper reads raw JSON directly and does not clamp.','diff':bboxdiff})
    for family in families:
        group=[t for t in tables if t['family']==family['family']]
        structural=[s for t in group for s in t.get('structural',[])]
        family['full_source_numeric_denominator_eligible_tables']=sum(t['source_full_denominator_eligible']for t in group)
        family['source_IN_SCOPE_trusted_points_partial_or_full']=sum(source[t['id']]['trusted_numeric_points']for t in group if t['source_scope']=='IN_SCOPE')
        family['automatic_point_alignment_observations']=dict(collections.Counter(p['assessment']['status']for t in group for p in t.get('points',[])))
        family['observed_structural_comparisons_not_Q13_failures']={'grids_compared':len(structural),'row_count_equal':sum(s['rows_equal']for s in structural),'col_count_equal':sum(s['cols_equal']for s in structural),'explicit_source_header_grids':sum(s['source_header_status']=='EXPLICIT_MIDRULE'for s in structural),'source_header_roles_all_present':sum(s['header_roles_all_present']is True for s in structural)}
        family['confirmed_tuple_error_lower_bounds']={'missing':sum(t['RAW']['missing_confirmed']for t in group),'extra':sum(t['RAW']['extra_confirmed']for t in group)}
    save(ROOT/'E0-results.json',result);save(ROOT/'E0-visual-adjudication.json',{'reviews':reviews,'scope':'Five Q13 counterexamples (one partial oracle with certified source point upper bound) and two detection identities manually confirmed from original PDF page images and native/RAW/MAPPED. No source gold changed.'})
    lines=['# E0 table：RAW／MAPPED 逐表結果','', '36 篇保存輸出已評；來源 gold 沿全域封存 v2，沒有以輸出修 gold。未跑 conversion／模型。', '', '|family|來源表|IN／OOS／定位未知|已證偵測／IN對齊未知|RAW FAIL／UNKNOWN／OOS|MAPPED FAIL／UNKNOWN／OOS|','|---|---:|---:|---:|---:|---:|']
    for f in families:
        s=f['source_scope'];raw=f['RAW'];mp=f['MAPPED'];lines.append(f"|{f['family']}|{f['source_tables']}|{s.get('IN_SCOPE',0)}／{s.get('OUT_OF_SCOPE',0)}／{s.get('UNKNOWN',0)}|{f['confirmed_native_detection']}／{f['native_detection_unknown']}|{raw.get('FAIL',0)}／{raw.get('UNKNOWN',0)}／{raw.get('OUT_OF_SCOPE',0)}|{mp.get('FAIL',0)}／{mp.get('UNKNOWN',0)}／{mp.get('OUT_OF_SCOPE',0)}|")
    lines+=['', '沒有將 UNKNOWN 當 PASS；本輪沒有證成整表 PASS。來源共252候選，175 IN_SCOPE、3 OOS、74定位未知；其中138表有來源文字／多點值與標籤／原圖對 native 的唯一偵測證據，37個 IN_SCOPE 的native對齊仍未知。這是確認量與未知量，不把37算漏偵測，也不計虛假的100% detection rate。','', '必須區分：175個IN_SCOPE只是來源表存在與頁碼可定位；其中只有14表（ordinary9／complex5）有完整可信numeric分母。其餘可有trusted子集，但不能用子集誤差宣稱整表通過。另有1個complex表用來源點數保守上界確證FAIL；無法補齊的gold仍不更動。','', '|確證表（各自裁決，不平均）|類別／來源分母|確證錯誤下界|RAW／MAPPED|','|---|---|---|---|']
    for review in [r for r in reviews if r.get('Q13_verdict')=='FAIL']:
        g=source[review['id']];denom=review.get('source_complete_numeric_denominator')or'上界'+str(review['source_numeric_denominator_upper_bound']);lines.append(f"|{review['id']} p{review['source_pages'][0]}|{g['complexity']}／{denom}|{review['confirmed_error_count_lower_bound']}（錯率至少{review['error_rate_lower_bound']:.1%}）|FAIL／FAIL|")
    lines+=['', '這五表共29個確證 tuple 錯誤下界（20 missing＋9 extra），不是完整誤差總數；其他點的未知仍保留。P06 複合表有完整50點來源分母，僅右側17個 Reward tuple 已缺於對應欄，17/50=34%已大於5%，足以FAIL；不把另33點宣稱全對。三個ordinary表各有至少一個原圖確證錯誤即不符零錯規則。', '', '另P13p8 Table2被下方Figure4條圖合併：native tables/1 row15 metric欄2–7至少6個不同cell納入Figure4數字。凍結來源cell只含format/color/multirow命令，沒有未知或產生數字macro；連backbone標籤內數字一起數，共87個numeric token可當保守來源點數上界，因此6/87=至少6.9%已超過5%。這是FAIL_WITH_PARTIAL_ORACLE，沒有把兩個未知model-label候選改成gold。stage由image零推論replay證實：較寬table11勝過table9，picture panels合成picture13後被cross-type overlap刪除，圖表混入表框。見 [P13-chart-contamination.json](P13-chart-contamination.json)。', '', '其餘四表的錯誤在 native cells/grid 已存在；表框涵蓋原圖完整表格，但多欄數值被塞到 row-header 或鄰欄。定位到 native table structure／TableFormer 重建出口，無證據宣稱 reading-order／serializer 是這些 tuple 錯配的首因。mapper保留原格位，不能修好這些關聯。', '', 'RAW官方逐表export共238個native表，237個完整export字串可在保存Markdown找到；EfficientNet tables/0另保留出口不一致待解。RAW expanded grid有73表、677次同native cell額外曝光，MAPPED每cell ref單次；這些曝光含headers，不能直接當677個錯誤來源資料點。RAW與MAPPED共同的numeric關聯失敗和serializer重複風險分開報。', '', '11,095等W2 mapper leaf/item量不當W3表格語義分母。未解析巨集／表頭、無numeric表、multi-value cell語義或唯一對齊不足均保留UNKNOWN。沒有用列數／欄數不符就將每點都算錯；全header壓成一格且無法確定值的對象者也不算全對。', '', '逐表、逐點、rows/cols/header證據與分子／分母見 [E0-results.json](E0-results.json)；原圖與native ref、兩出口片段見 [E0-visual-adjudication.json](E0-visual-adjudication.json)；全部native表出口與span曝光見 [delivery-audit.json](delivery-audit.json)。']
    lines+=['', '輸入沿R3/V3_B已保存的官方JSON；P10／P20先前raw baseline→Core的79／143個bbox座標clamp另存summary的provenance欄，不視為模型改善。本mapper直接讀JSON、不新增clamp；五個確證失敗在P06／P11／P13，沒有依這兩篇的clamp作裁定。36篇逐篇表（含零來源表也不當PASS）另見 [summary.json](summary.json)。']
    (ROOT/'E0-report.md').write_text('\n'.join(lines)+'\n')
    (ROOT/'report.md').write_text('\n'.join(lines)+'\n')
    save(ROOT/'summary.json',{k:v for k,v in result.items()if k!='tables'})
    print(json.dumps(result['counts']))


if __name__=='__main__':main()
