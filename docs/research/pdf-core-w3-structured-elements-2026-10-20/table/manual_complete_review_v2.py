"""Manual-confirmed lexical/structure follow-up of the ten complete-gold UNKNOWN tables.
Does not repair or zip flattened output columns. Writes v2 only; v1/source unchanged.
"""
import collections,copy,decimal,hashlib,html,importlib.util,json,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parent
NUMBER=re.compile(r'(?<![A-Za-z0-9_])[-+−]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?(?:M|B|%)?(?![A-Za-z0-9_])')
REASONS={
'F-icml_efficientnet:table-009':'Source B0–B7 are eight explicit columns. Native all eight labels occupy one header cell(col1); each row packs eight values into one cell, with Test top1 moved to col2 under an empty header. Numeric words/order survive, but explicit B0–B7 value relations are not represented.',
'P-01-2608.27454v1:table-005':'Six source headers occupy one native header cell. Row names, interaction mode, Train/Val/Test counts and tools are packed together, and numeric-bearing rows alternate between native columns0/1. Correct split counts cannot be assigned to three distinct output column labels without an added token parser.',
'P-03-2603.25158v5:table-003':'Source Setting/User/Vrf/Soft/Hard collapse to two compound header cells. ReasoningBank user sizes and scores share a cell; two-line Human-Written/+Combined setting is split across output rows. All16 values incl122B/35B remain, but model-size/setting/metric relations require rebuilding the source multirow structure.',
'P-03-2603.25158v5:table-004':'Seven source headers collapse to one native header cell. No-Selection has five scores inside its row-header while HiTab43.45 occupies a blank-header column; BO-Selection has the first five scores in another cell. All12 score words survive, but no explicit six-column output mapping remains.',
'P-04-2605.23904v2:table-002':'Five source headers collapse to one native cell. Native row1 mixes three learning-rate settings and their scores, delaying61.3 until after later settings; Slow/meta label starts below one of its own data rows. Numeric multiset is complete, but row boundaries, score order and component/setting associations are not safely recoverable without reconstruction.',
'P-04-2605.23904v2:table-005':'All six source headers are one native cell(col1), while every benchmark and its five values are packed into a row-header(col0). All30 values and unitsM, comma-thousands remain in order, but explicit Initial/Final/Edits/Train/Cost columns are absent. Ordered-list zip would be new postprocessing, not evaluated output.',
'P-12-2508.16153v2:table-003':'Method and all five iteration headers occupy one native cell. Scores for two methods are inside row-header cells; scores for the third method are grouped in the other column. All15 score words survive. RAW repeats Baseline/Case-based section labels through span expansion; MAPPED fixes that local duplication but does not rebuild iteration columns.',
'P-13-2601.01885v3:table-006':'Five source headers collapse to one native cell. LangMem row and its +ST/RL variant merge into a single output row; several other score vectors split between row-header and data cell. All32 score words/order survive, but method-variant row identities and explicit benchmark columns are incomplete.',
'P-19-2511.10395v1:table-004':'Two source header levels and six metric columns collapse into compound header cells. Most values reside in row headers. Navigating(ours)85.9 precedes64.7 in output grid order, reversing the source first-two-value order. All30 numeric words survive, but explicit AppWorld/BFCL/Avg × avg@4/best@4 associations are not reliably represented.',
'P-19-2511.10395v1:table-007':'Source TGC/SGC × @4/@8 multi-level header becomes two compound cells. Values for some methods are in row headers and others are split over two cells. All16 values remain in order, but each of the four metric columns is not separately represented.'}


def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(token):
    unit=token[-1]if token[-1]in'MB%'else''
    value=token[:-1]if unit else token
    return str(decimal.Decimal(value.replace(',','').replace('−','-')).normalize())+unit


def main():
    preserved={name:sha(ROOT/name)for name in ['E0-results.json','summary.json','report.md','oracle.json','freeze.json']}
    result=json.loads((ROOT/'E0-results.json').read_text());oracle=json.loads((ROOT/'oracle.json').read_text());gold={t['id']:t for t in oracle['tables']};audit=json.loads((ROOT/'delivery-audit.json').read_text());nativeaudits={(t['job_id'],t['native_ref']):t for t in audit['tables']}
    chosen=[t for t in result['tables']if t['id']in result['source_full_denominator_eligible_ids']and t['verdict']!='FAIL']
    assert len(chosen)==10 and {t['id']for t in chosen}==set(REASONS)
    reviews=[]
    for table in chosen:
        g=gold[table['id']];doc=json.loads(pathlib.Path(table['input']['native_json']).read_text());nt=next(t for t in doc['tables']if t['self_ref']==table['native_ref']);na=nativeaudits[table['job_id'],table['native_ref']]
        native_cells=[dict(c,ref=f"{nt['self_ref']}/data/table_cells/{i}")for i,c in enumerate(nt['data']['table_cells'])]
        body_tokens=[];excluded=[]
        for c in sorted(native_cells,key=lambda c:(c['start_row_offset_idx'],c['start_col_offset_idx'])):
            if c.get('column_header'):continue
            for match in NUMBER.finditer(c.get('text','')):
                record={'literal':match.group(),'canonical':canonical(match.group()),'native_cell_ref':c['ref'],'native_row':c['start_row_offset_idx'],'native_col':c['start_col_offset_idx'],'native_row_span':c['row_span'],'native_col_span':c['col_span'],'native_cell_text':c['text'],'native_cell_row_header':c.get('row_header'),'token_offset':[match.start(),match.end()]}
                if table['id']=='P-03-2603.25158v5:table-003'and'Ouyang'in c['text']and match.group()=='2026':
                    record['reason']='Original page shows Ouyang et al.2026 citation under ReasoningBank; citation year is not a source data point.';excluded.append(record)
                else:body_tokens.append(record)
        point_reviews=[];expected=[]
        for grid in g['grids']:
            for p in grid['numeric_points']:
                tokens=NUMBER.findall(p['value_text']);assert len(tokens)==1
                key=canonical(tokens[0]);expected.append(key)
                candidates=[t for t in body_tokens if t['canonical']==key]
                assert candidates
                headers=[]
                for label in p['col_labels']:
                    norm=lambda x:''.join(ch.casefold()for ch in x if ch.isalnum())
                    text=norm(label['text']);headers.append({'source_label':label['text'],'native_header_cells_containing_label':[c['ref']for c in native_cells if c.get('column_header')and text in norm(c['text'])],'native_header_cells_exactly_equal_label':[c['ref']for c in native_cells if c.get('column_header')and text==norm(c['text'])]})
                point_reviews.append({'point_id':p['id'],'source_row':p['row'],'source_col':p['col'],'source_value':p['value_text'],'source_row_labels':p['row_labels'],'source_col_labels':p['col_labels'],'source_status':p['status'],'numeric_word_key':key,'numeric_word_candidates':candidates,'numeric_word_present':True,'lexical_candidates_are_not_assigned_to_source_point':True,'header_evidence':headers,'explicit_value_row_col_association':'UNKNOWN','association_reason':REASONS[table['id']]})
        ec=collections.Counter(expected);ac=collections.Counter(t['canonical']for t in body_tokens);assert ec==ac,(table['id'],ec-ac,ac-ec)
        actual_sequence=[t['canonical']for t in body_tokens]
        page=g['pages'][0];image=ROOT/'review/pages'/f'{g["job_id"]}-p{page:03d}.png';crop=ROOT/'review/pages'/(g['id'].replace(':','-')+'-crop.png');assert image.exists()and crop.exists()
        row={'id':g['id'],'job_id':g['job_id'],'pages':g['pages'],'complexity':g['complexity'],'source_numeric_denominator':g['required_numeric_point_candidates'],'source_unchanged':True,'source_image':str(image),'source_image_sha256':sha(image),'crop':str(crop),'reviewed_visual':True,'review_method':'Original PDF table crop previously viewed in full, frozen source cells manually compared with every native row/cell, official RAW fragment read and fixed MAPPED cells checked. No output reconstruction or gold-to-output zipping.','native_ref':nt['self_ref'],'source_rows_cols':[(gr['rows'],gr['declared_cols'])for gr in g['grids']],'native_rows_cols':[nt['data']['num_rows'],nt['data']['num_cols']],'native_table_cells':native_cells,'RAW_fragment':na['RAW_export_path'],'MAPPED_fragment':na['MAPPED_export_path'],'RAW_export_verified_in_saved_document':na['RAW_official_export_exactly_in_saved_document'],'MAPPED_single_cell_refs':True,'native_numeric_word_count':len(body_tokens),'source_numeric_word_count':len(expected),'numeric_word_multiset_equal_with_multiplicity':True,'numeric_word_source_order_equal_in_native_row_major':expected==actual_sequence,'source_numeric_word_sequence':expected,'native_numeric_word_sequence':actual_sequence,'excluded_nondata_citation_tokens':excluded,'source_numeric_word_missing':[],'source_numeric_word_extra':[],'row_col_association':'UNKNOWN','reason':REASONS[g['id']],'point_reviews':point_reviews,'RAW_verdict_before':'UNKNOWN','RAW_verdict_after':'UNKNOWN','MAPPED_verdict_before':'UNKNOWN','MAPPED_verdict_after':'UNKNOWN','exact_tuple_error_rate':None,'do_not_turn_lexical_multiset_match_into_data_point_accuracy':True}
        reviews.append(row)
    assert sum(r['source_numeric_word_count']for r in reviews)==223
    final=copy.deepcopy(result);final['analysis_version']='v2-manual-complete-gold-followup';final['v1_results_sha256']=preserved['E0-results.json'];final['manual_complete_gold_followup']={'tables':10,'source_points_lexically_reviewed':223,'numeric_word_multisets_complete':10,'data_word_sequences_preserved':sum(r['numeric_word_source_order_equal_in_native_row_major']for r in reviews),'verdict_changes':0,'reason':'Lexical delivery positive evidence; explicit row/column relations remain UNKNOWN without new reconstruction outside frozen mapper.'}
    reviewmap={r['id']:r for r in reviews}
    for t in final['tables']:
        if t['id']in reviewmap:t['manual_complete_gold_followup_v2']=reviewmap[t['id']]
    save(ROOT/'manual-complete-gold-review-v2.json',{'scope':'Ten complete-source-denominator UNKNOWN tables,223 source points. No source oracle changes, no extra mapper rules, no inference.','v1_preserved_sha256':preserved,'reviews':reviews,'summary':final['manual_complete_gold_followup']})
    save(ROOT/'E0-results-v2.json',final);save(ROOT/'summary-v2.json',{k:v for k,v in final.items()if k!='tables'})
    lines=['# E0 table v2：完整來源表的正向交付核驗','', '保留v1全部檔案與凍結gold不變，追加人工核對10張完整分母但UNKNOWN的表。依主線裁定，不按gold把壓單格數列zip回多欄後算正確。','', '這10表共223個來源numeric word／cell值，全部在native及RAW／MAPPED保留相同值、符號與M／B單位及multiplicity，未發現這批的numeric字詞缺漏或多生。8表保留來源numeric row-major序列；P04p8 component表與P19p22 ablation表的numeric序列有移位。P03p7另有原頁正確的Ouyang2026引用年份，已另列而非誤算多生data point。','', '這是正向交付證據，不是223個value+row/column資料點正確：header與score vector壓成單格、row-header吞數字或合併多個設定，仍使explicit行列關係不完整。10表均維持UNKNOWN，不把它們算FAIL，也不宣稱PASS。','', '|表／頁|來源點數|numeric multiset完整|numeric序列保留|行列關係／RAW與MAPPED結論|','|---|---:|---|---|---|']
    for row in reviews:lines.append(f"|{row['id']} p{row['pages'][0]}|{row['source_numeric_denominator']}|YES|{'YES'if row['numeric_word_source_order_equal_in_native_row_major']else'NO'}|UNKNOWN／UNKNOWN|")
    lines+=['','Native欄數與來源不符、數列壓單格的事實並未被當成每個source點都錯。反之，numeric words保留也不能當作每點row/column對象正確。原有5個有明確欄位錯配／圖表污染證據的FAIL維持；全252來源候選仍為RAW與MAPPED各5FAIL、244UNKNOWN、3OOS。175 IN_SCOPE只有14表具完整numeric來源分母，這次補核的是扣除4個既有完整分母FAIL後的10表；另一個FAIL是來源點數上界可證的partial oracle。','', '逐點候選位置、native cell text／row／col、每個source header的覆蓋或合併證據、source與native序列見 [manual-complete-gold-review-v2.json](manual-complete-gold-review-v2.json)。候選可能同值重複，不擅自指派來源對象。完整逐表v2見 [E0-results-v2.json](E0-results-v2.json)、[summary-v2.json](summary-v2.json)；v1結論／family數值仍見 [report.md](report.md)。']
    (ROOT/'report-v2.md').write_text('\n'.join(lines)+'\n')
    (ROOT/'change-log-v2.md').write_text('# v2 change log\n\n- v1 E0-results.json／summary.json／report.md與source oracle／freeze未改；SHA記於manual-complete-gold-review-v2.json。\n- 新增10表、223來源numeric值的逐點字詞候選與序列／header證據。\n- 10表numeric multiset完整；8表序列保留，2表序列移位。\n- 不新增token拆欄或按gold zip規則；explicit row/column association仍UNKNOWN，裁決數量不變。\n')
    assert all(sha(ROOT/name)==digest for name,digest in preserved.items())
    print(json.dumps(final['manual_complete_gold_followup']))


if __name__=='__main__':main()
