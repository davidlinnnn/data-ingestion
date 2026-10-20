"""Bound a complex-table error using frozen gold and independent image-stage replay."""
import hashlib,json,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parent
RESEARCH=ROOT.parent.parent


def main():
    oracle=json.loads((ROOT/'oracle.json').read_text());gold=next(t for t in oracle['tables']if t['id']=='P-13-2601.01885v3:table-001')
    cells=[c for g in gold['grids']for c in g['cells']]
    commands=sorted(set(re.findall(r'\\([A-Za-z]+)',' '.join(c['raw']for c in cells))))
    assert commands==['cellcolor','multirow','textbf','underline']
    assert not any(c['unknown_macros']for c in cells)
    upper=sum(len(c['numeric_tokens'])for c in cells);assert upper==87
    native_path=RESEARCH/'pdf-core-w2-native-coverage-round3-2026-10-20/runs/V3_B/jobs/P-13-2601.01885v3/document.json'
    native=json.loads(native_path.read_text());table=native['tables'][1]
    extra=[dict(c,native_cell_ref=f"#/tables/1/data/table_cells/{i}")for i,c in enumerate(table['data']['table_cells'])if c['start_row_offset_idx']==15 and 2<=c['start_col_offset_idx']<=7]
    assert len(extra)==6
    trace_path=ROOT.parent/'image/layout-zero-inference-replay.json';trace=json.loads(trace_path.read_text());case=next(x for x in trace if x['job_id']=='P-13-2601.01885v3'and x['page']==8)
    cross=next(c for c in case['calls']if c['stage']=='_handle_cross_type_overlaps')
    assert any(c['id']==13 and c['label']=='picture'for c in cross['before'])
    assert not any(c['label']=='picture'for c in cross['after'])and any(c['id']==11 and c['label']=='table'for c in cross['after'])
    assert case['full_clusters_equal_ignoring_order']and case['new_model_inferences']==0
    obj={'id':gold['id'],'job_id':gold['job_id'],'source_pages':[8],'source_origin':gold['source'],'source_caption':[c['text']for c in gold['captions']],'native_ref':'#/tables/1','reviewed_visual':True,'original_page_image':str(ROOT.parent/'image/visual-audit/P-13-2601.01885v3-p008-source.jpg'),'overlay':str(ROOT.parent/'image/visual-audit/P-13-2601.01885v3-p008-overlay.jpg'),'source_gold_changed':False,'source_numeric_denominator_exact':None,'source_numeric_denominator_upper_bound':upper,'bound_evidence':{'all_source_cell_numeric_tokens_including_backbone_labels':upper,'trusted_metric_points':gold['trusted_numeric_points'],'unknown_candidates':[(p['value_text'],p['numeric_tokens'])for g in gold['grids']for p in g['numeric_points']if p['status']!='TRUSTED'],'raw_cell_commands':commands,'unknown_cell_macros':[],'reason':'All commands in the frozen cells only style/position existing text; no unknown or number-generating macro. Counting every numeric token, including model-name digits, conservatively overbounds true source numeric datapoints. No gold point added or relabelled.'},'confirmed_errors':[{'type':'extra_figure_numeric_data_in_table_metric_cell','native_cell':c,'reason':'Source Figure4 bar/axis text appears in a new native table row15 under one of the six Table2 metric columns. This numeric cell belongs to the separate original figure, not any source table row. Count at least one extra value per distinct native metric cell, not every number and not label columns0/1.'}for c in extra],'confirmed_error_count_lower_bound':len(extra),'error_rate_lower_bound':len(extra)/upper,'exact_full_error_rate':None,'Q13_verdict':'FAIL','verdict_subtype':'FAIL_WITH_PARTIAL_ORACLE','Q13_basis':'complex table: confirmed extra-data lower bound6/source upper bound87=6.90% >5%','RAW_MAPPED_same_failure':True,'stage':'layout_postprocess_cross_type_overlap','stage_evidence':{'trace_path':str(trace_path),'trace_sha256':hashlib.sha256(trace_path.read_bytes()).hexdigest(),'source_result_sha256':case['source_result_sha256'],'source_layout_raw_sha256':case['source_layout_raw_sha256'],'raw_table9_bbox':[x['bbox']for x in case['raw']if x['id']==9],'raw_table11_bbox':[x['bbox']for x in case['raw']if x['id']==11],'picture_overlap_call':case['calls'][1],'table_wrapper_overlap_call':case['calls'][2],'cross_type_overlap_call':cross,'saved_replay_clusters_equal':case['full_clusters_equal_ignoring_order'],'new_model_inferences':0,'interpretation':'Wide table11 already covers upper table plus lower figure; table overlap removes narrower table9. Picture panels merge to picture13; cross-type overlap keeps table11 and removes picture13. TableFormer then consumes the mixed crop; numeric chart cells already in native grid. Serializer is downstream and mapper cannot undo this merge.'},'RAW_export':str(ROOT/'E0-delivery/P-13-2601.01885v3/table-001-RAW.md'),'MAPPED_export':str(ROOT/'E0-delivery/P-13-2601.01885v3/table-001-MAPPED.html')}
    (ROOT/'P13-chart-contamination.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    print(obj['Q13_basis'])


if __name__=='__main__':main()
