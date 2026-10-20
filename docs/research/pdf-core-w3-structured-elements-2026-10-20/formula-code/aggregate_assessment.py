"""Assemble current evidence without changing sealed oracle or sample gate."""
from pathlib import Path
import json,collections,hashlib,datetime
P=Path(__file__).resolve().parent
def read(n,default=None):
 f=P/n;return json.loads(f.read_text())if f.exists()else default
def dump(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def records(n):
 d=read(n,[]);return d.get('records',[])if isinstance(d,dict)else d

def main():
 oracle=read('oracle.json');u={x['id']:x for x in oracle['units']};e0=read('e0-delivery-scores.json');e1=read('e1-scores.json');sel=read('audit50-current-selection.json');selected={r['unit_id']for r in sel['selection']};allreviews=[]
 for name in ['audit/reviews-trace.json','audit/table-reviewer.json','audit/reviews-root.json','audit/reviews-root-v2.json','audit/reviews-trace-v2.json','audit/reviews-root-final.json','audit/reviews-trace-final.json']:
  for r in records(name):
   r=dict(r,review_file=name,render_syntax='UNKNOWN_NOT_RENDERED',whole_faithful_delivery='NOT_ESTABLISHED_BY_CORE_MEANING_ALONE')
   gold=u[r['unit_id']];r.update({'job_id':gold['job_id'],'family':gold['family'],'kind':gold['kind'],'source_pages':gold['pages'],'source_rows_field_count':len(gold.get('rows',[])),'RAW_verdict':r['status'],'MAPPED_verdict':r['status']})
   refs=r.get('output_refs',[])
   if isinstance(refs,dict):r['output_refs_original']=refs;r['output_refs']=refs.get('fixed_E0',refs.get('fixed_E0_refs',[]))
   packet=Path(r.get('packet',str(P/'audit/packets'/(r['unit_id'].replace(':','__')+'.json'))))
   if packet.exists():
    actualsha=hashlib.sha256(packet.read_bytes()).hexdigest();r['current_packet_sha256']=actualsha
    if r.get('packet_sha256')and r['packet_sha256']!=actualsha:r['packet_refresh_note']='Derived packet regenerated after v2 format/order scoring. Original review payload and source-image hashes retained; source and active model evidence unchanged.'
   allreviews.append(r)
 by={r['unit_id']:r for r in allreviews};chosen=[by[x['unit_id']]for x in sel['selection']if x['unit_id']in by];extra=[by[k]for k in sorted(by)if k not in selected];pending=sorted(selected-set(by));blocks=[r for r in chosen if 'BLOCKING'in r.get('status','')];alignment=[r for r in chosen if r.get('status')in{'ORACLE_ALIGNMENT_ERROR','UNKNOWN'}];code=records('audit/code-review.json')
 for r in code:
  gold=u[r['unit_id']];r.update({'job_id':gold['job_id'],'family':gold['family'],'kind':gold['kind'],'source_pages':gold['pages'],'RAW_verdict':r.get('status','UNKNOWN'),'MAPPED_verdict':r.get('status','UNKNOWN'),'output_refs':r.get('fixed_E0_refs',r.get('output_refs',[]))})
 algorithms=records('audit/algorithm-role-review.json');algorithm_blocks=[]
 for r in algorithms:
  e=r.get('E1',{})
  if e.get('semantic_verdict')=='CONFIRMED_BLOCKING':
   gold=u[r['unit_id']];algorithm_blocks.append({'unit_id':r['unit_id'],'job_id':gold['job_id'],'family':gold['family'],'kind':'algorithm','source_pages':gold['pages'],'status':'CONFIRMED_BLOCKING','meaning_reason':'; '.join(x['reason']for x in e['evidence']),'output_refs':e['manual_matched_processed_refs'],'RAW_verdict':'CONFIRMED_BLOCKING','MAPPED_verdict':'CONFIRMED_BLOCKING','Q33_static_algorithm_logic':'CONFIRMED_CHANGED','runtime_execution_verified':False,'source_rootcause_group':e['source_rootcause_group'],'evidence':e['evidence'],'source_image':r['source_image'],'review_file':'audit/algorithm-role-review.json','manual_identity_exception_to_frozen_gate':True,'not_double_counted_with_code_alignment_error':True})
 for r in chosen:r['selected_under_amended_formula_only_50']=True
 dump('audit/final-selected-reviews-current.json',{'selection_final':sel['final'],'selection_sha256':hashlib.sha256((P/'audit50-current-selection.json').read_bytes()).hexdigest(),'selected_block_count':len(selected),'reviewed':len(chosen),'pending':pending,'records':chosen,'supplementary_reviews':extra,'formula_unit_policy':'Frozen outer environment/block, not one independent equation; entire visible rows should be reviewed. Independent-equation completion count unknown.'})
 family=[]
 for variant,rs in [('E0',e0),('E1',e1)]:
  for fam in sorted({x['family']for x in rs}):
   for kind in ['formula','code','algorithm']:
    rr=[x for x in rs if x['family']==fam and x['kind']==kind];known=[x for x in rr if x['known_gold_denominator']];proc=[x for x in known if x.get('actual_processed_refs')]if variant=='E1'else known
    family.append({'variant':variant,'family':fam,'kind':kind,'source_units_in_read_jobs':len(rr),'known_gold_units':len(known),'unknown_gold_units':len(rr)-len(known),'actual_processed_source_units':len(proc)if variant=='E1'else None,'auto_eligible_role_alignment_candidates':sum(x['detected_eligible_role_candidate']for x in known),'scored_channel_population':'actual_processed_known'if variant=='E1'else'known','RAW_canonical_status':dict(collections.Counter(x['channels']['RAW']['status']for x in proc)),'MAPPED_canonical_status':dict(collections.Counter(x['channels']['MAPPED']['status']for x in proc)),'official_MD_literal_presence_candidates':sum(x['delivery_modes']['RAW_official_markdown']['all_nonempty_active_items_present']for x in proc),'MAPPED_rendered_all_refs_once':sum(x['delivery_modes']['MAPPED_rendered']['all_refs_rendered_once']for x in proc),'MAPPED_nonempty_text':sum(x['delivery_modes']['MAPPED_rendered']['all_ref_text_nonempty']for x in proc),'MAPPED_picture_uncertain_units':sum(bool(x['delivery_modes']['MAPPED_rendered']['picture_uncertain_refs'])for x in proc)})
 audit_by_family=[]
 for fam in sorted({u[r['unit_id']]['family']for r in chosen}):
  ar=[r for r in chosen if u[r['unit_id']]['family']==fam];audit_by_family.append({'family':fam,'selected_formula_blocks_reviewed':len(ar),'statuses':dict(collections.Counter(x['status']for x in ar)),'confirmed_blocking_blocks':sum('BLOCKING'in x.get('status','')for x in ar),'TeX_render_syntax':'UNKNOWN_NOT_RENDERED'})
 source_counts={k:{'source_units':sum(x['kind']==k for x in u.values()),'known_gold_units':sum(x['kind']==k and x['known_gold_denominator']for x in e0),'auto_eligible_role_alignment_candidates':sum(x['kind']==k and x['known_gold_denominator']and x['detected_eligible_role_candidate']for x in e0)}for k in ['formula','code','algorithm']}
 summary={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PARTIAL_TIME_BUDGET_STOP','analysis_version':'v2-fixed-E0refs-bodytree-format-only','source_counts':source_counts,'family':family,'E1':read('e1-summary.json'),'formula_audit':{'protocol':'audit-protocol-amendment.json','selection_final':sel['final'],'population':sel['population'],'near':sel['near'],'error':sel['error'],'selected_formula_blocks':len(selected),'reviewed_selected':len(chosen),'pending_selected':pending,'confirmed_blocking_selected':len(blocks),'statuses':dict(collections.Counter(r['status']for r in chosen)),'alignment_errors_or_unknown_selected':len(alignment),'supplementary_reviewed':len(extra),'by_family':audit_by_family,'sampling_limit':'Near/error sampled source blocks, not representative model error prevalence. Outer-block units are not per-independent-equation denominator.'},'final_processing_coverage':read('final-processing-coverage.json'),'algorithm_role_review':read('audit/algorithm-role-review.json'),'inline':read('inline-summary.json'),'inline_manual':{'reviewed':len(records('inline-audit/reviews.json')),'population_flattening_rate':'UNKNOWN'},'observed_false_formula_role_lower_bound':read('false-positive-evidence.json')['confirmed_nonformula_role_items'],'code_manual':{'reviewed':len(code),'statuses':dict(collections.Counter(x.get('status','UNKNOWN')for x in code)),'Q33_runtime_execution_performed':False,'Q4_log_literal_failure_is_not_executable_logic_claim':True},'algorithm_manual':{'known_source_algorithms_reviewed':len(algorithms),'E0_complete_semantic_fidelity':'UNKNOWN_SCOPE_OR_MATH_STRUCTURE','E0_numbered_rows_present':43,'manually_verified_E1_processed':len(algorithm_blocks),'confirmed_static_logic_blocking':len(algorithm_blocks),'runtime_execution_verified':False,'unknown_source_algorithms_unchanged':19},'E0_native_role_inventory':{'formula':366,'formula_active_empty':366,'formula_orig_nonempty':366,'code':187,'code_active_nonempty':187,'note':'All empty formula text is materialization evidence, not proof all366 are true formulas. Confirmed35 taskID false roles kept separately.'},'formula_detection_nonmatches':read('formula-detection-other-roles.json'),'row_inventory':{k:v for k,v in read('row-inventory.json').items()if k!='records'},'limits':['E0 detected roles are automatically aligned candidates, not manually established detection precision.','RAW official Markdown locator and MAPPED saved renderer provenance are separate from native scalar quality.','Meaning preserved does not certify compilable/renderable TeX; no TeX renderer executed.','Source unknown pages remain UNKNOWN; output locations never promote frozen source denominator.','No-source Adam includepdf wrapper excluded from LaTeX denominators.','No code execution; literal/line/indentation comparisons plus manual semantics only.'],'no_arbitrary_overall_pass_rate':True}
 dump('assessment-summary.json',summary);dump('blocking-cases.json',{'formula_selected':blocks,'formula_supplementary':[r for r in extra if'BLOCKING'in r.get('status','')],'code_manual':[r for r in code if'BLOCKING'in r.get('status','')],'algorithm_manual':algorithm_blocks,'inline_F13_only':records('inline-audit/reviews.json'),'unadjudicated_not_automatically_blocking':True})
 report=f"""# W3 公式、程式與行內數學：時間預算內部分評估

主線因預估剩餘推論時間超過回合上限，停止新增 conversion。E1 最終範圍17篇、85實際處理refs；封存211gate refs中84已處理、127未處理，另pilot有1額外code ref。未執行清單見 final-processing-coverage.json，不算模型失敗。封存 gold／抽樣 gate／E0 matched refs 不變；分析採 v2 格式正規化與 body tree 順序。

**口徑限制：387 是外層公式區塊，不是已逐條拆開的獨立公式。** 封存rows合計431；lexical TeX行段910，118區塊有多段。多列環境保留 rows，derived row inventory 不能區分單條跨行與多條等式；50 人工抽樣也是公式區塊，未完全達成使用者逐條公式的分母要求。

現行人工規則是 `audit-protocol-amendment.json` 的 **50 FORMULA near/error**，不是早期文件的 20/15/15 混合抽樣。按固定 SHA 排序，近／錯各25，不足轉移；最終pool55（38近／17錯），選33近／17錯，不以 exact/code 補足。

E0：公式 known {source_counts['formula']['known_gold_units']}，自動 eligible-role 對齊候選 {source_counts['formula']['auto_eligible_role_alignment_candidates']}；這是候選覆蓋，不是已證偵測準確率。程式 known {source_counts['code']['known_gold_units']}；演算法 known {source_counts['algorithm']['known_gold_units']}。封存未對齊的7單位另全看圖：6其實有formula角色，1 P12來源長式與PDF簡式不一致；不把它們稱7真漏。原生366個formula角色text全空、orig全在，這是materialization現象，並不證366全是真公式。另已看頁圖確證 P16 p25 有35個非公式 task ID 被標 formula，僅為觀測誤偵測下界。

E1：已完成 {summary['E1']['completed_jobs']} 篇；凍結自動對齊樣本中已實際處理的 known source 公式／程式／演算法單位分別 {summary['E1']['by_kind']['formula']['known_actual_processed_source_units']}／{summary['E1']['by_kind']['code']['known_actual_processed_source_units']}／{summary['E1']['by_kind']['algorithm']['known_actual_processed_source_units']}；另由頁圖人工身分核對確認P04有1個算法實際處理，見下方例外證據，不改封存map。沒有被選或未實際推論的單位不記作模型失敗。

目前公式抽樣選 {len(selected)} 區塊，已審 {len(chosen)}，待審 {len(pending)}；其中確證 blocking {len(blocks)}。已依固定規則封存最終50；額外已審 {len(extra)} 案另列。人工先核對來源與固定 native ref 是否同式，再核模型 active text；非空錯字不以 orig 救回。

RAW 官方 Markdown 與 MAPPED 實際 renderer 輸出，逐 family 數字在 assessment-summary.json。MAPPED 使用凍結 R4 三規則；空 text 才回 orig，保留 picture child 不確定性。數學核心保義、整體重建忠實度與 TeX 可渲染性分開；未執行 TeX rendering，因此 syntax/render 一律未證。

行內來源共4571處，正文候選3751處，其餘按 caption/table/figure/footnote 等脈絡分開；不能將來源 `$` 或上下標數量當成已觀測攤平頻率。固定 hash 的6個正文例已看圖確認 E0 RAW/MAPPED 上下標攤平（F13），未另證 F01/F02 改義。

程式／演算法全99 source 單位已有逐行自動診斷；literal Unicode 不正規化，運算子與字串保留，縮排另列。自動逐行差異受換行與未展開巨集影響，均非自動 Q33 判定。人工程式21單位已全審：9保義、6個Q4忠實度阻擋、4個source→native對齊錯誤、2個語義UNKNOWN。SICA列印log的工具字串/agent ID/數值變更屬Q4忠實度阻擋，不等同已證可執行邏輯改變；P01兩個跨頁partial ref對齊錯誤不計模型漏行。兩個known algorithm另見audit/algorithm-role-review.json：E0共43/43行文字存在，P04在code角色（原對齊漏），SICA在list角色；E0完整邏輯因變數/縮排仍UNKNOWN。P04實際經錯配code5選中refs424/425，E1將集合測試∈改=、epoch e≥2改>2、else分支破壞，確證1個靜態Q33算法邏輯阻擋，RAW/MAPPED都交付；不能被frozen算法gate0掩蓋，也不與code5對齊錯重算。SICA ref90未實際處理、文字與E0相同，不算模型錯。19個來源頁UNKNOWN算法不變。

來源頁 UNKNOWN、巨集與條件式、未編譯 TeX、原生公式誤對齊及未可定位演算法仍保留限制。Adam 僅 includepdf wrapper，沒有可用正文 LaTeX。完整證據見 audit/、row-inventory.json、code-line-assessment.json、blocking-cases.json。
"""
 (P/'report.md').write_text(report);print(json.dumps(summary['formula_audit'],ensure_ascii=False))
if __name__=='__main__':main()
