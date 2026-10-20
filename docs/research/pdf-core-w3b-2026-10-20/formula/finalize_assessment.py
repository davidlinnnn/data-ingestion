from pathlib import Path
import json,collections,hashlib
P=Path(__file__).resolve().parent;O=P/'assessment'
def read(n):return json.loads((O/n).read_text())
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 for n in ['per-formula.json','summary.json']:
  v=O/(Path(n).stem+'-machine.json')
  if not v.exists():v.write_bytes((O/n).read_bytes())
 raw=read('per-formula-machine.json');machine=read('summary-machine.json');reviews=read('manual-review.json')['records'];by={r['unit_id']:r for r in reviews};exclusion={r['unit_id']for r in reviews if r['status']=='ORACLE_GRANULARITY_ERROR'}
 for r in raw:
  r['source_evaluable_after_adjudication']=r['single_formula_comparable']and r['unit_id']not in exclusion
  r['identity_manual_review']='CONFIRMED_SOURCE_NATIVE_ON_ORIGINAL_PDF'if r['unit_id']in by else'AUTOMATIC_LOCATOR_NOT_VISUALLY_CERTIFIED'
  if r['unit_id']in by:r['manual_review']=by[r['unit_id']]
  if r['unit_id']in exclusion:
   r['source_exclusion']='ORACLE_GRANULARITY_ERROR';r['E0orig_before_exclusion']=r['E0orig'];r['E1_before_exclusion']=r['E1'];r['E0orig']=None;r['E1']={'status':'UNKNOWN_EXCLUDED_COMPOUND_SOURCE_UNIT','lexical':None}
 aa=[r for r in raw if r['source_evaluable_after_adjudication']];aligned=[r for r in aa if r['fixed_E0_refs']];actual=[r for r in aligned if r['actual_enriched']];scored=[r for r in actual if(r['E1']or{}).get('status')=='ACTUALLY_ENRICHED_INDEPENDENT_TEXT'];ss={k:v for k,v in machine.items()if k not in ['family','E0orig_lexical_aligned','E1_RAW','E1_MAPPED','E1_status']}
 ss.update({'stage':3,'final':True,'frozen_source_candidate_denominator':286,'single_formula_source_denominator':len(aa),'source_single_formula_evaluable_after_adjudication':len(aa),'source_eligible_excluded_after_source_review':len(exclusion),'source_unique_E0_identity':len(aligned),'source_identity_UNKNOWN':len(aa)-len(aligned),'source_aligned_actual_enriched':len(actual),'source_aligned_actual_enriched_independent_scored':len(scored),'source_aligned_actual_enriched_unresolved':len(actual)-len(scored),'E0orig_lexical_aligned':dict(collections.Counter((r['E0orig']or{}).get('class')or'UNKNOWN_BOUNDARY'for r in aligned)),'E1_RAW':dict(collections.Counter(r['E1']['RAW']['class']for r in scored)),'E1_MAPPED':dict(collections.Counter(r['E1']['MAPPED']['class']for r in scored)),'E1_status':dict(collections.Counter((r['E1']or{}).get('status','UNKNOWN_SOURCE_IDENTITY')for r in aa)),'identity_status':dict(collections.Counter(r['source_identity_status']for r in aa)),'E0orig_representation_limit':'E0GLYPH_ONLY_STRUCTURAL_LIMITATION: orig is flattened PDF glyph text; exact/near/error compare normalized textual reconstruction, NOT mathematical meaning.','manual_source_to_native_page_reviews':len(reviews),'manual_single_formula_evaluable_reviews':len(scored),'manual_single_formula_evaluable_verdicts':dict(collections.Counter(r['manual_review']['status']for r in scored)),'core_math_changed_confirmed_in_this_aligned_subset':sum(r['manual_review']['status']=='CONFIRMED_BLOCKING'for r in scored),'not_a_replacement_for_W3_50_block_audit':True,'mapping_substring_dominance_guard':0.70,'guard_note':'Conservative text boundary guard, not semantic pass criterion; all17 scored E1 identities reviewed on originalPDF. Other exact locators remain automatic evidence.','taskID_false_formula_roles_in_source_denominator':0,'family':[]})
 for fam in sorted({r['family_analysis']for r in aa}):
  ff=[r for r in aa if r['family_analysis']==fam];mm=[r for r in aligned if r['family_analysis']==fam];pp=[r for r in scored if r['family_analysis']==fam];ss['family'].append({'family':fam,'source_single_formula':len(ff),'aligned_E0_locators':len(mm),'source_identity_unknown':len(ff)-len(mm),'E0orig_lexical':dict(collections.Counter((r['E0orig']or{}).get('class')or'UNKNOWN_BOUNDARY'for r in mm)),'actual_enriched_scored':len(pp),'E1_RAW':dict(collections.Counter(r['E1']['RAW']['class']for r in pp)),'E1_MAPPED':dict(collections.Counter(r['E1']['MAPPED']['class']for r in pp)),'manual_semantic':dict(collections.Counter(r['manual_review']['status']for r in pp))})
 dump('source-exclusions.json',{'frozen_oracle_unchanged':True,'frozen_candidate_denominator':286,'evaluable_after_source_review':len(aa),'records':[r for r in reviews if r['unit_id']in exclusion],'exclusion_applies_to':['E0orig','E1_RAW','E1_MAPPED']});dump('per-formula.json',raw);dump('summary.json',ss);dump('blocking-cases.json',[r for r in reviews if r['status']=='CONFIRMED_BLOCKING'])
 table='| Family | 單條可評來源 | 唯一E0字流定位 | E1獨立可評 | exact/near/error |\n|---|---:|---:|---:|---|\n'
 for r in ss['family']:
  e=r['E1_RAW'];table+=f"| {r['family']} | {r['source_single_formula']} | {r['aligned_E0_locators']} | {r['actual_enriched_scored']} | {e.get('EXACT',0)}/{e.get('NEAR',0)}/{e.get('ERROR',0)} |\n"
 (O/'family-table.md').write_text(table)
 print({k:ss[k]for k in ['source_single_formula_evaluable_after_adjudication','source_unique_E0_identity','source_aligned_actual_enriched_independent_scored','E0orig_lexical_aligned','E1_RAW','manual_single_formula_evaluable_verdicts']})
if __name__=='__main__':main()
