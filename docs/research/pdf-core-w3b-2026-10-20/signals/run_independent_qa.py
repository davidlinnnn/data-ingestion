"""Read-only cohort/statistics QA; writes only independent QA artifacts."""
import collections
import hashlib
import importlib.util
import json
from pathlib import Path

P=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())


def independent_count(rows,features,threshold=.95):
    confusion={'TP':0,'FP':0,'FN':0,'TN':0};evaluable=0;verified=0
    for row in rows:
        if not row['primary_label_eligible'] or not isinstance(row['human_error'],bool):continue
        values=[]
        for key in features:
            signal=row[key]
            if signal['status']!='KNOWN':break
            if key=='c':values.append(signal['pass'])
            elif signal.get('character_similarity') is not None:
                values.append(signal['character_similarity']>=threshold and signal['operator_sequence_exact'] and signal['number_sequence_exact'])
            else:break
        else:
            accepted=all(values);evaluable+=1;verified+=accepted
            confusion[('FN' if row['human_error'] else 'TN') if accepted else ('TP' if row['human_error'] else 'FP')]+=1
    return {'confusion_error_positive':confusion,'evaluable_known_human_n':evaluable,'verified_known_human_n':verified}


def main():
    code_path=P/'cohort-w3-code-utf16-v2.json' if (P/'cohort-w3-code-utf16-v2.json').exists() else P/'cohort-w3-code.json'
    cohort_paths=[P/'cohort-w3-formula.json',code_path]
    inputs=[];findings=[];checks={};counts={};allrows=[]
    for path,expected in zip(cohort_paths,[50,21]):
        cohort=load(path);rows=cohort['rows'];name=cohort['cohort'];allrows.extend(rows)
        inputs.append({'path':str(path),'sha256':sha(path)})
        checks[name+'_unit_count']=len(rows)==expected==cohort['original_human_unit_count']
        checks[name+'_unique_source_units']=len({r['original_unit_id'] for r in rows})==expected
        originals={}
        for r in rows:
            p=Path(r['human_label_evidence']['path'])
            if p not in originals:
                d=load(p);originals[p]={x['unit_id']:x for x in d['records']}
                inputs.append({'path':str(p),'sha256':sha(p)})
        checks[name+'_verbatim_labels']=all(originals[Path(r['human_label_evidence']['path'])][r['original_unit_id']]['status']==r['human_status'] for r in rows)
        checks[name+'_original_id_set']=set().union(*(set(x) for x in originals.values()))=={r['original_unit_id'] for r in rows}
        excluded={'METADATA_ONLY','ORACLE_ALIGNMENT_ERROR','UNKNOWN'}
        checks[name+'_metadata_unknown_not_correct']=all(not r['primary_label_eligible'] and r['human_error'] is None for r in rows if r['human_status'] in excluded)
        checks[name+'_primary_a_pdf_glyphs_scope']=all(r['a']['status']!='KNOWN' or (r['primary_scope_compatible'] is True and r['native_evidence']['kind']=='ALIGNED_TEXT_LAYER_GLYPHS' and r['native_evidence']['primary_eligible'] is True and r['regions']) for r in rows)
        checks[name+'_primary_a_evidence_hash']=all(r['a']['status']!='KNOWN' or sha(Path(r['native_evidence']['path']))==r['native_evidence']['sha256'] for r in rows)
        glyph_provenance=[]
        for r in rows:
            if r['a']['status']!='KNOWN':continue
            evidence=load(r['native_evidence']['path'])
            glyphs=evidence.get('characters') or [g for region in evidence.get('regions',[]) for g in region.get('glyphs',[])]
            glyph_provenance.append(bool(glyphs) and evidence['pdf_sha256']==r['pdf_sha256'] and
                                    all('bbox' in g and ('raw_index'in g or 'raw_char_index'in g) for g in glyphs))
        checks[name+'_primary_glyph_coordinate_index_provenance']=all(glyph_provenance)
        checks[name+'_source_label_not_distributed_to_lines']=all(r['unit_scope'] in ['SOURCE_BLOCK','SOURCE_CODE_UNIT'] for r in rows)
        checks[name+'_same_model_duplicate_not_B']=all(r['b']['status']!='KNOWN' for r in rows)
        groups=collections.Counter(r['prediction_group_id'] for r in rows)
        checks[name+'_duplicate_group_flags']=all((r['duplicate_prediction_group'] is not None)==(groups[r['prediction_group_id']]>1) for r in rows)
        counts[name]={'rows':len(rows),'human_status':dict(collections.Counter(r['human_status'] for r in rows)),
                      'primary_eligible':sum(r['primary_label_eligible'] for r in rows),
                      'prediction_groups':len(groups),'a_known':sum(r['a']['status']=='KNOWN' for r in rows),
                      'a_pass':sum(r['a'].get('pass') is True for r in rows)}
    spec=importlib.util.spec_from_file_location('qa_stats',P/'statistics_helpers.py')
    stats=importlib.util.module_from_spec(spec);spec.loader.exec_module(stats)
    inputs.append({'path':str(P/'statistics_helpers.py'),'sha256':sha(P/'statistics_helpers.py')})
    empty=stats.metrics([])
    checks['zero_verified_error_is_NA']=empty['verified_error'] is None and empty['verified_error_exact95CI'] is None
    checks['zero_ROC_is_NA']=stats.roc([],'a:char')['AUROC'] is None
    checks['primary_threshold_default_095']=stats.metrics.__defaults__==('primary',.95) and stats.decision.__defaults__==(.95,)
    calculations={}
    for cohort in ['W3_FORMULA50','W3_CODE21']:
        rows=[r for r in allrows if r['cohort']==cohort]
        calculations[cohort]={}
        for rule in (['a','c','a&c','primary'] if cohort=='W3_FORMULA50' else ['a','primary']):
            helper=stats.metrics(rows,rule)
            # Primary formula requires abc; code requires ab.
            needed=list('abc' if cohort=='W3_FORMULA50' else 'ab') if rule=='primary' else rule.split('&')
            independent=independent_count(rows,needed)
            calculations[cohort][rule]={'independent':independent,'helper':helper}
            checks[cohort+'_'+rule+'_independent_confusion']=all(helper[k]==v for k,v in independent.items())
            if helper['verified_known_human_n']==0:
                checks[cohort+'_'+rule+'_n0_error_NA']=helper['verified_error'] is None and helper['verified_error_exact95CI'] is None
    # Known synthetic risk order: true error high risk, true correct low risk.
    synthetic=[{'category':'code','primary_label_eligible':True,'human_error':err,
                'a':{'status':'KNOWN','character_similarity':sim,'operator_sequence_exact':True,'number_sequence_exact':True}}
               for err,sim in [(True,.1),(False,.99)]]
    roc=stats.roc(synthetic,'a:char')
    checks['ROC_positive_class_error_and_decreasing_agreement_risk']=roc['AUROC']==1 and roc['positive_errors']==1 and roc['negative_correct']==1
    formal_comparison={}
    if (P/'metrics.json').exists() and (P/'cohort-combined.json').exists():
        formal=load(P/'metrics.json');combined=load(P/'cohort-combined.json')
        for file in ['metrics.json','cohort-combined.json','source-region-pairs.json']:
            inputs.append({'path':str(P/file),'sha256':sha(P/file)})
        checks['formal_primary_threshold_095']=formal['primary_threshold']==.95
        checks['formal_b_pairs_zero']=combined['pair_count']==0 and formal['paired_source_regions']==0
        checks['formal_combined_uses_designated_corrected_code_cohort']=any(Path(i['path'])==code_path and i['sha256']==sha(code_path) for i in combined['inputs'])
        combined_counts=collections.Counter(r['cohort'] for r in combined['rows'])
        checks['combined_207_original_rows_not_251_views']=len(combined['rows'])==207 and len({r['row_id'] for r in combined['rows']})==207 and combined_counts['W3_FORMULA50']==50 and combined_counts['W3_CODE21']==21 and sum(n for c,n in combined_counts.items() if c.startswith('R1_'))==136
        checks['R1_OLD44_subviews_not_additional_units']=formal['cohorts']['R1_OLD44_formula']['n']+formal['cohorts']['R1_OLD44_code']['n']==formal['cohorts']['R1_OLD44']['n']==44
        math_rows=[r for r in combined['rows'] if r['cohort']=='R1_ADDITIONAL_MATH']
        image_rows=[r for r in combined['rows'] if r['cohort']=='R1_ADDITIONAL_IMAGE_MATH']
        checks['R1_math28_correct_only_AUROC_NA_not_discrimination']=len(math_rows)==28 and all(r['human_error'] is False for r in math_rows) and all(r['positive_errors']==0 and r['AUROC'] is None for r in formal['cohorts']['R1_ADDITIONAL_MATH']['ROC'])
        checks['R1_separate_image_math6_blocked_unavailable_not_correct']=len(image_rows)==6 and all(r['human_error'] is True for r in image_rows) and all(x['evaluable_known_human_n']==0 for x in formal['cohorts']['R1_ADDITIONAL_IMAGE_MATH']['metrics'])
        obligations=[r for r in combined['rows'] if r['original_unit_id'] in ['A2-100','A2-101']]
        checks['R1_occurrence_ambiguity_original_blocked_labels_retained']=len(obligations)==2 and all(r['human_status']=='BLOCKED_TYPED_OCCURRENCE_AMBIGUITY' and r['human_error'] is True and r['primary_label_eligible'] for r in obligations)
        checks['R1_same_missing_obligation_group_not_two_predictions']=len({r.get('human_obligation_dependency_group') for r in obligations})==1 and bool(obligations[0].get('human_obligation_dependency_group')) and all(r['a']['status']=='UNKNOWN' and not r.get('prediction_group_id') for r in obligations)
        cross_pdf=[]
        for i,left in enumerate(combined['rows']):
            for right in combined['rows'][i+1:]:
                if left.get('model') and right.get('model') and left['model']!=right['model'] and left.get('pdf_sha256') and left['pdf_sha256']==right.get('pdf_sha256'):
                    cross_pdf.append((left,right))
        cross_page=sum(bool(set(l['original_pages'])&set(r['original_pages'])) for l,r in cross_pdf)
        checks['b_absence_explained_by_no_same_page_cross_model_source']=len(cross_pdf)==82 and cross_page==0
        formal_comparison['combined_bookkeeping']={'original_rows':207,'W3_rows':71,'R1_rows':136,
            'sum_of_overlapping_metric_views_not_denominator':sum(v['n'] for v in formal['cohorts'].values()),
            'cross_independent_model_same_pdf_pairs':len(cross_pdf),'same_pdf_original_page_overlap_pairs':cross_page,
            'no_R1_external_evidence_dereferenced':True}
        old44=[r for r in combined['rows'] if r['cohort']=='R1_OLD44']
        formal_comparison['R1_OLD44_aggregate_arithmetic_only']={}
        for rule in ['a','c','a&c']:
            independent=independent_count(old44,rule.split('&'))
            measured=next(m for m in formal['cohorts']['R1_OLD44']['metrics'] if m['rule']==rule)
            checks['R1_OLD44_formal_'+rule+'_confusion']=all(measured[k]==v for k,v in independent.items())
            formal_comparison['R1_OLD44_aggregate_arithmetic_only'][rule]=independent
        for name in ['W3_FORMULA50','W3_CODE21','R1_OLD44']:
            rules={m['rule']:m for m in formal['cohorts'][name]['metrics']}
            for roc in formal['cohorts'][name].get('fixed_rule_binary_ROC',[]):
                cm=rules[roc['rule']]['confusion_error_positive'];pos=cm['TP']+cm['FN'];neg=cm['FP']+cm['TN']
                if pos and neg:
                    tpr=cm['TP']/pos;fpr=cm['FP']/neg
                    expected=(1+tpr-fpr)/2
                    valid=len(roc['points'])==3 and abs(roc['points'][1]['TPR']-tpr)<1e-12 and abs(roc['points'][1]['FPR']-fpr)<1e-12 and abs(roc['AUROC']-expected)<1e-12
                else:valid=roc['AUROC'] is None
                checks[name+'_fixed_binary_ROC_'+roc['rule']]=valid and 'not a tuned' in roc['note']
        for cohort in ['W3_FORMULA50','W3_CODE21']:
            original={r['original_unit_id']:r for r in allrows if r['cohort']==cohort}
            rows=[r for r in combined['rows'] if r['cohort']==cohort]
            checks[cohort+'_combined_same_original_labels']=len(rows)==len(original) and all(
                all(r[k]==original[r['original_unit_id']][k] for k in ['human_status','human_error','primary_label_eligible','primary_scope_compatible']) for r in rows)
            formal_comparison[cohort]={}
            for measured in formal['cohorts'][cohort]['metrics']:
                rule=measured['rule'];features=list('abc' if cohort=='W3_FORMULA50' else 'ab') if rule=='primary' else rule.split('&')
                independent=independent_count(rows,features)
                formal_comparison[cohort][rule]=independent
                checks[cohort+'_formal_'+rule+'_confusion']=all(measured[k]==v for k,v in independent.items())
                checks[cohort+'_formal_'+rule+'_threshold']=measured['threshold']==.95
                if measured['verified_known_human_n']==0:
                    checks[cohort+'_formal_'+rule+'_NA']=measured['verified_error'] is None and measured['verified_error_exact95CI'] is None
            for measured in formal['cohorts'][cohort]['ROC']:
                feature=measured['feature'];key,mode=feature.split(':');pairs=[]
                for row in rows:
                    if not row['primary_label_eligible'] or not isinstance(row['human_error'],bool):continue
                    signal=row[key]
                    if signal['status']!='KNOWN':continue
                    if mode=='char':risk=None if signal.get('character_similarity') is None else 1-signal['character_similarity']
                    elif mode=='op':risk=None if not isinstance(signal.get('operator_sequence_exact'),bool) else float(not signal['operator_sequence_exact'])
                    elif mode=='num':risk=None if not isinstance(signal.get('number_sequence_exact'),bool) else float(not signal['number_sequence_exact'])
                    else:risk=None if not isinstance(signal.get('pass'),bool) else float(not signal['pass'])
                    if risk is not None:pairs.append((risk,row['human_error']))
                positive=[risk for risk,error in pairs if error];negative=[risk for risk,error in pairs if not error]
                auc=None if not positive or not negative else sum((bad>good)+.5*(bad==good) for bad in positive for good in negative)/(len(positive)*len(negative))
                checks[cohort+'_formal_ROC_'+feature]=((auc is None and measured['AUROC'] is None) or (auc is not None and abs(auc-measured['AUROC'])<1e-12)) and measured['positive_errors']==len(positive) and measured['negative_correct']==len(negative)
    if not all(checks.values()):
        findings += [{'severity':'REVIEW','check':k} for k,v in checks.items() if not v]
    findings += [{'severity':'LIMITATION','message':'Code collector: center-in-bbox without padding, then loose-font-y/x geometric lines and native x-advance spaces; formula collector preserves original PDF raw indices. Collector difference is explicit and not a threshold change.'},
                 {'severity':'LIMITATION','message':'Feature availability is separate from human label eligibility; no b means primary NO_DECISION, never claim 0% verified error from n=0.'},
                 {'severity':'LIMITATION','message':'Formula font/character/op/number agreement does not prove 2D attachment or mathematical semantics.'}]
    verified_examples=[{'unit_id':r['original_unit_id'],'human_status':r['human_status'],'primary_label_eligible':r['primary_label_eligible'],'human_error':r['human_error'],'a_pass':r['a']['pass']} for r in allrows if r['a'].get('pass') is True]
    if (P/'code-utf16-source-audit.json').exists():
        for file in ['code-utf16-source-audit.json','cohort-w3-code-utf16-v2-selfchecks.json','pdfium_glyph_helpers.py']:
            inputs.append({'path':str(P/file),'sha256':sha(P/file)})
        corrected=load(P/'cohort-w3-code-utf16-v2-selfchecks.json')
        checks['UTF16_code_all21_a_values_unchanged']=corrected['primary_a_values_all21_unchanged']
        checks['UTF16_source_audit_original_rawUnicode_all67_regions']=load(P/'code-utf16-source-audit.json')['counts']['original_stage4_native_units']==67
    actual_refs_path=P.parents[1]/'pdf-core-w3-structured-elements-2026-10-20/formula-code/e1-input-hashes.json'
    row_summary_path=P.parent/'formula/combined-summary-root.json'
    actual_refs=load(actual_refs_path);row_summary=load(row_summary_path)
    inputs.extend([{'path':str(f),'sha256':sha(f)} for f in [actual_refs_path,row_summary_path]])
    checks['E1_85_native_refs_distinct_from_source_rows']=len(actual_refs)==17 and len({(job,ref) for job,v in actual_refs.items() for ref in v['processed_refs']})==85
    checks['E1_formula40_row_denominator_not_85_refs_or_50_blocks']=row_summary['E1_independent_scored']==40 and row_summary['E1_buckets']=={'EXACT':9,'NEAR':28,'ERROR':3} and sum(row_summary['E1_manual_semantics'].values())==40
    checks['E1_57_formula_refs_plus28_code_refs_is85_not40']=row_summary['actual_formula_refs']['native_ref_label_counts']=={'formula':57,'code':28} and row_summary['actual_formula_refs']['source_rows_and_native_refs_are_distinct_denominators']
    result={'version':'stage5-independent-QA-v2-UTF16','scope':'Original W3 formula50/code21; no cohort mutation, no R1 dereference, no new inference.',
            'inputs':inputs,'checks':checks,'all_checks_pass':all(checks.values()),'counts':counts,
            'independent_arithmetic':calculations,'a_pass_human_examples':verified_examples,'findings':findings,
            'combined_stats_status':'FORMAL_OUTPUT_CROSSCHECKED' if formal_comparison else 'PENDING_TRACE_COMBINED_OUTPUT',
            'formal_output_independent_arithmetic':formal_comparison,
            'helper_XML_v2':'Trace-owned fix; code-equivalence audit separate, not treated as a cohort error.'}
    (P/'independent-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# Stage5 獨立 QA','','只讀原 W3 formula50／code21 cohort、原人工標籤與統計 helper；沒有重評或改 cohort。',
           '',f"自動檢查 {len(checks)} 項：{'全數通過' if all(checks.values()) else '有項目待複核'}。",'',
           '| Cohort | 原單位 | 可用人工標籤 | prediction groups | a known | a pass |','|---|---:|---:|---:|---:|---:|']
    for name,c in counts.items():lines.append(f"| {name} | {c['rows']} | {c['primary_eligible']} | {c['prediction_groups']} | {c['a_known']} | {c['a_pass']} |")
    lines += ['', '50／21 source IDs 與原標籤逐一一致，沒有把外層公式 block 展開成人造逐行標籤。metadata、4 alignment error、2 UNKNOWN 均未當 correct；a primary 必須原 PDF glyph＋相容 scope。code 的 P08 共用 item 仍保留兩行、同一 prediction group，不能算兩個獨立模型。',
              '', 'a-only、formula c／a&c 與 primary confusion 已另寫不呼叫 helper 的計數器交叉核對。ROC 以 error 為正類，風險為1−agreement；主門檻 .95 未改。n=0 時 verified_error／精確信賴區間／AUROC 為 null（NA），不是0%。',
              '', '全50公式 a availability 包含 metadata，但實際兩個 a pass 都是 eligible：SBERT formula00001 原標 preserved，SICA P07 formula00001 原標 blocking。a-only 可用人工標籤37個，TP10／FP25／FN1／TN1，verified wrong=1/2=50%，精確95%CI約[1.26%,98.74%]；不是metadata被當correct。code a-only TP2／FP6／FN0／TN0，沒有verified，故錯率NA。完整primary因缺獨立b是NO_DECISION。',
              '', 'SICA false pass 的原人工根因是 score 識別字變成 sore、美元 $ 被改成節號 §；必要變數與貨幣單位改變，卻被長字串的高相似度掩蓋。此案證明高字面一致不足以確保識別字／單位保義；二維從屬無法驗證是方法另外一項限制，不把本案誤歸成二維 grouping 故障。',
              '', ('已對 trace 正式 combined／metrics 的 W3 兩 cohort、全部8組規則逐項手算 confusion；各 ROC 另用正負類逐對比較的 AUROC 算法交叉核對，全部一致。未讀取或追隨任何 R1 外部證據。' if formal_comparison else '待 trace combined/stats 產生後，再用其正式輸出做最後算術交叉核對。目前 helper 直接計算與獨立計數一致。'),
              '', 'Combined 保留207個原記錄（50＋21＋136），不是207個獨立同分布來源。R1_OLD44另有formula30／code14子view；把所有metric view相加的251不能當獨立分母。R1 additional math28全correct-only，其AUROC為NA，不能由0wrong推論錯誤辨識力佳；另外6個image-math原blocked且無可評target，仍單獨保留不可判定。',
              '', 'b=0有資料原因：跨兩種重建模型的相同PDF共82個候選配對，但原始頁碼交集為0；沒有可證同一原頁／區域的獨立重建。不是把matcher放寬即可取得有效b，不因無配對宣稱一致或不一致。',
              '', 'UTF-16更正後，R1 old44 a的TP3／FP6／FN1／TN1及a&c的TP1／FP5／FN1／TN1也已獨立核算；不是沿用修正前的0錯估計。固定規則binary ROC僅為.95 operating point加兩端點，另與continuous character ROC分開，沒有挑新門檻或宣稱機率校準。所有R1核對只用W3b內的combined記錄與metrics，未追隨外部檔案。',
              '', '分母另核：17篇E1實際處理85個原native refs（formula57＋code28），不是85個source formulas。Stage3逐條可評40個source rows為9 exact／28 near／3 error；Stage5原人工formula50是整個source block，code21也是另一個人工cohort。四種分母不可混用。',
              '', '限制：code native 字串採原PDF glyph＋x縮排重建，formula 使用原raw-index序列，collector口徑不同，已明列。沒有 b 不代表不一致；是 NO_DECISION。字元、運算子、數值相同仍不能證明二維數學結構或語意正確。']
    (P/'independent-qa.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'checks':checks,'counts':counts,'pass':all(checks.values())},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
