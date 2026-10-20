from pathlib import Path
import json,sys,hashlib,re,collections
import pypdfium2 as pdfium
import pypdfium2.raw as pdfraw
ROOT=Path('/Users/david/work/data-ingestion');W=ROOT/'docs/research/pdf-core-w3b-2026-10-20';R=ROOT/'docs/research/pdf-core-r1-method-2026-10-20/live-preflight/round5-strict';sys.path.insert(0,str(W/'signals'))
from character_helpers import agreement,tex_visible,tex_syntax_preflight
from render_helpers import render_batch
from pdfium_glyph_helpers import decode_selected_utf16
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
A=read(R/'human-A-review-v3.json');C=read(R/'human-C-review-v1.json');jobs={x['job_id']:x for x in read(R/'jobs.json')['jobs']};bundles={};logs=[]
for b in (R/'live-relocated-pending').glob('*.source'):
 x=read(b/'binding.json');bundles[x['source_revision']]=(b,x,read(b/'source.json'))
cache={};rows=[];render=[];(W/'signals/r1-native').mkdir(exist_ok=True)
def unknown(reason,status='UNKNOWN'):return {'status':status,'pass':None,'unknown_reasons':[reason]}
def evidence(job,refs,uid):
 rev=jobs[job]['binding']['document_revision'];b,bind,source=bundles[rev];sp=bind['source_pdf'];pdfpath=ROOT/sp['path'];assert 'holdout' not in str(pdfpath).lower()
 regions=[]
 for ref in refs:
  if not ref.startswith('#/'):continue
  typ,i=ref[2:].split('/');item=source.get(typ,[])[int(i)]
  for p in item.get('prov',[]):
   box=p['bbox'];page=p['page_no'];regions.append({'page':page,'bbox':[box['l'],min(box['b'],box['t']),box['r'],max(box['b'],box['t'])],'bbox_origin':box['coord_origin'],'native_refs':[ref]})
 if 'scan-pages' in str(pdfpath):return sp,regions,None,'scan original deliberately not opened; existing metadata only'
 if str(pdfpath) not in cache:
  assert sha(pdfpath)==sp['sha256'];logs.append({'source_pointer':str(b/'binding.json')+'#/source_pdf','actual_read':str(pdfpath),'purpose':'Original born-digital native glyph source region only; no OCR/render','sha256':sp['sha256'],'holdout_check':True});(W/'required-external-reference-read-log.json').write_text(json.dumps(logs,indent=2));cache[str(pdfpath)]=pdfium.PdfDocument(pdfpath)
 pdf=cache[str(pdfpath)];allglyph=[];seen=set()
 for reg in regions:
  page=pdf[reg['page']-1];tp=page.get_textpage();width,height=page.get_size();reg['page_dimensions']=[width,height];l,b,r,t=reg['bbox']
  if reg['bbox_origin']=='TOPLEFT':b,t=height-t,height-b;reg['bbox']=[l,b,r,t];reg['bbox_origin']='BOTTOMLEFT'
  glyph=[]
  for i in range(tp.count_chars()):
   x0,y0,x1,y1=tp.get_charbox(i);cx=(x0+x1)/2;cy=(y0+y1)/2
   if l<=cx<=r and b<=cy<=t and (reg['page'],i) not in seen:
    seen.add((reg['page'],i));g={'page':reg['page'],'raw_char_index':i,'text':tp.get_text_range(i,1),'raw_unicode':int(pdfraw.FPDFText_GetUnicode(tp.raw,i)),'bbox':[x0,y0,x1,y1]};glyph.append(g);allglyph.append(g)
  decoded=decode_selected_utf16(glyph);reg['glyphs']=decoded['glyphs'];reg['utf16_decoding_status']=decoded['status'];reg['unpaired_surrogate_indices']=decoded['unpaired_surrogate_indices'];tp.close();page.close()
 allglyph=[g for reg in regions for g in reg['glyphs']];allglyph.sort(key=lambda g:(g['page'],g['raw_char_index']));native=''.join(g['text'] for g in allglyph);utf16_complete=all(reg['utf16_decoding_status']=='KNOWN' for reg in regions)
 path=W/'signals/r1-native'/f'{uid}.json';path.write_text(json.dumps({'pdf':str(pdfpath),'pdf_sha256':sp['sha256'],'regions':regions,'glyphs':allglyph,'text':native,'policy':'Tight character bbox center in source consumed native bbox union; original physical PDF char indices retained, no output-text search.'},ensure_ascii=False,indent=2))
 return sp,regions,{'status':'AVAILABLE' if native.strip() and utf16_complete else 'INCOMPLETE_UTF16' if not utf16_complete else 'EMPTY_REGION','kind':'ALIGNED_TEXT_LAYER_GLYPHS','visible_text':native,'path':str(path),'sha256':sha(path),'primary_eligible':bool(native.strip()) and utf16_complete},None
oldmap={1:'inline-expression',2:'matrix',3:'fraction',4:'piecewise-expression',5:'code-block',6:'inline-code',23:'wikiskill-call-equation',30:'objective-equation',31:'algorithm-1-pseudocode',35:'binary-reward-equation',37:'gradient-equation-3',38:'gradient-equation-4',40:'reconstruct-diff-code'}
def make(x,cohort,obs=None,whole=False):
 uid=x['unit_id'];f=x['frozen_unit'];kind=f.get('kind',x.get('kind',''));category='code' if any(w in kind for w in ['code','command','procedural']) else 'formula';state=x['state'];err=True if state.startswith('BLOCKED') else False if state.startswith('PASS') else None
 r={'row_id':cohort+':'+uid,'original_unit_id':uid,'cohort':cohort,'category':category,'unit_scope':'ORIGINAL_HUMAN_GROUP' if cohort=='R1_OLD44' else 'FROZEN_SOURCE_SUBUNIT','label_scope':'Q4 literal/semantic faithfulness at original human group scope; code not necessarily executable logic','model':'gpt-6-luna reasoning-medium strict','human_status':state,'human_error':err,'primary_label_eligible':err is not None,'human_label_evidence':{'path':str(R/'human-A-review-v3.json'),'sha256':sha(R/'human-A-review-v3.json'),'record_locator':uid,'scope_note':'Original group, never expanded to fragments'},'human_reason':x.get('reason'),'original_pages':[f.get('physical_page',f.get('page'))],'refs':obs.get('consume',[]) if obs else [],'source_identity':{'kind':'FROZEN_SOURCE_UNIT','value':uid,'frozen_unit':f},'regions':[],'native_evidence':{'status':'UNKNOWN','kind':'NONE','primary_eligible':False},'reconstruction':{'status':'AVAILABLE' if obs else 'UNKNOWN','target_text':obs.get('text') if obs else None,'format':'LATEX' if category=='formula' else 'CODE','path':str(R/x['raw_response']),'locator':{k:obs.get(k) for k in ['action','block','segment']} if obs else None,'human_adjudicated_delivery_channel':'TYPED_SOURCE_ACTION','feature_scope':'MATCHED_HUMAN_UNIT' if whole else 'FROZEN_SUBUNIT_OR_UNRESOLVED_GROUP'},'a':unknown('Source region or whole human-unit reconstruction scope unavailable'),'b':unknown('No full source-region independent-model pair proven'),'c':unknown('Unsupported/missing original formula target') if category=='formula' else unknown('Not formula','NA'),'primary_scope_compatible':whole,'unknown_reasons':[]}
 if obs:
  r['prediction_group_id']='luna:'+x['job_id']+':'+obs['action']+':'+str(obs['block'])+':'+str(obs['segment'])
  sp,regions,native,reason=evidence(x['job_id'],obs.get('consume',[]),uid);r['pdf_sha256']=sp['sha256'];r['regions']=regions
  if native:r['native_evidence']=native
  elif reason:r['unknown_reasons'].append(reason)
  if category=='formula':
   projection=tex_visible(obs['text']);r['reconstruction'].update({'visible_text':projection.get('visible_text') if projection['status']=='KNOWN' else None,'mathml':projection.get('mathml'),'projection_status':projection['status']});syntax=tex_syntax_preflight(obs['text']);r['syntax_pipeline']=syntax
   if syntax['status']=='KNOWN' and syntax.get('pass') is False:r['c']={'status':'KNOWN','pass':False,'reason':syntax['reason']}
   elif syntax['status']=='READY_FOR_ACTUAL_RENDER':render.append({'unit_id':r['row_id'],'mathml':syntax['mathml']})
   target=r['reconstruction']['visible_text']
  else:target=obs['text'];r['reconstruction']['visible_text']=target
  if not whole and cohort.startswith('R1_ADDITIONAL_') and native and native['primary_eligible'] and f.get('expected'):
   expected=f['expected'];projected=tex_visible(expected) if category=='formula' else {'status':'KNOWN','visible_text':expected}
   needle=projected.get('visible_text') if projected['status']=='KNOWN' else None
   hay=native['visible_text']
   if needle and hay.count(needle)==1:
    # Frozen original source-subunit expected locates physical chars independently of prediction.
    start=hay.index(needle);ev=read(Path(native['path']));glyphs=ev['glyphs'];offset=0;selected=[]
    for g in glyphs:
     end=offset+len(g['text'])
     if offset>=start and end<=start+len(needle):selected.append(g)
     offset=end
    if ''.join(g['text'] for g in selected)==needle:
     subpath=W/'signals/r1-native'/(uid+'-source-subunit.json');subpath.write_text(json.dumps({'pdf':ev['pdf'],'pdf_sha256':ev['pdf_sha256'],'glyphs':selected,'text':''.join(g['text'] for g in selected),'frozen_expected_locator':expected,'unique_exact':True,'policy':'Frozen source single-unit expected only; physical chars extracted, never prediction search.'},ensure_ascii=False,indent=2))
     r['native_evidence'].update({'visible_text':''.join(g['text'] for g in selected),'path':str(subpath),'sha256':sha(subpath),'locator':'Source-frozen single complete subunit unique exact occurrence; original PDF physical indices retained.'});r['primary_scope_compatible']=True;r['reconstruction']['feature_scope']='MATCHED_HUMAN_UNIT';whole=True
   if not whole:r['unknown_reasons'].append('Complete frozen single-subunit expected has no unique exact source glyph occurrence; no target search or fuzzy relocation.')
  if whole and native and native['primary_eligible'] and target is not None:r['a']=agreement(r['native_evidence']['visible_text'],target,category)
 rows.append(r)
for x in A['old_A_groups']:
 n=int(x['unit_id'][1:]);action=oldmap.get(n);matches=[o for o in x.get('observed_typed_fragments',[]) if o['action']==action];obs=matches[0] if len(matches)==1 else None
 make(x,'R1_OLD44',obs,whole=n in {2,3,4,5,23,30,31,35,37,38,40})
for x in A['additional_registry']:
 if x['kind']=='source_code_font':continue
 # Inline subunits deliberately not compared against a larger consumed native paragraph.
 make(x,'R1_ADDITIONAL_'+x['kind'].upper(),x.get('observed'),whole=x['unit_id']=='A2-014')
for x in C['images']:
 state=x['description_state'];err=True if state=='BLOCKED' else False if state.startswith('PASS') else None
 rows.append({'row_id':'R1_DESCRIPTION29:'+str(x['image_index']),'original_unit_id':x['image_key'],'cohort':'R1_DESCRIPTION29','category':'description','unit_scope':'WHOLE_SEMANTIC_DESCRIPTION','model':'gpt-6-luna reasoning-medium strict','human_status':state,'human_error':err,'primary_label_eligible':err is not None,'human_reason':x['description_reason'],'human_label_evidence':{'path':str(R/'human-C-review-v1.json'),'sha256':sha(R/'human-C-review-v1.json'),'record_locator':x['image_index']},'reconstruction':{'target_text':json.dumps(x.get('observed_description'),ensure_ascii=False),'path':str(R/x['raw_description_response']),'feature_scope':'MATCHED_HUMAN_WHOLE_DESCRIPTION'},'prediction_group_id':'luna-description:'+x['description_job'],'a':unknown('Literal glyph agreement cannot establish whole semantic image-description obligations','NA'),'b':unknown('No independent same description-scope reconstruction','NA'),'c':unknown('Description has no formula syntax gate','NA'),'native_evidence':{'status':'NA','kind':'NONE'},'primary_scope_compatible':True})
rr=render_batch(render,W,'r1-round5');(W/'signals/r1-render-evidence.json').write_text(json.dumps(rr,indent=2));by={x['unit_id']:x for x in rr['results']}
for r in rows:
 if r['row_id'] in by:r['c']=by[r['row_id']];r['syntax_pipeline']['actual_render']=by[r['row_id']]
counts=collections.Counter(r['prediction_group_id'] for r in rows if r.get('prediction_group_id'))
for r in rows:
 r['duplicate_prediction_group']=r.get('prediction_group_id') if counts[r.get('prediction_group_id')]>1 else None
 if r['original_unit_id'] in {'A2-100','A2-101'}:r['human_obligation_dependency_group']='R1:two-recalc.py-source-obligations-one-unassigned-typed-occurrence'
 artifact=r.get('reconstruction',{}).get('path')
 if artifact and Path(artifact).exists():r['reconstruction']['sha256']=sha(Path(artifact))
 r['notes']=['Human-adjudicated typed-fragment snapshot is the target; raw response SHA retained as provenance, not a new literal interpretation or relabeling.']

out={'schema_version':'w3b-signals-cohort-v1','cohort':'R1_ROUND5_STRICT_STRATIFIED','original_human_unit_count':len(rows),'rows':rows,'notes':['43 font evidence records are not independent semantic labels and are excluded.','Whole original44 human groups preserved; unresolved multi-target action attribution remains UNKNOWN rather than labeling all job outputs.','No original scan PDF opened; no inference/API.','Inline source-subunit vs full consumed paragraph primary a is UNKNOWN unless full exact source scope independently proved.','R1 first/second attempts same Luna model are not independent b.']}
out['method_sha256']=sha(W/'signals-character-method.json');out['inputs']=[{'path':str(p),'sha256':sha(p)} for p in [R/'human-A-review-v3.json',R/'human-C-review-v1.json',R/'jobs.json',W/'signals/character_helpers.py',W/'signals/render_helpers.py',W/'signals/pdfium_glyph_helpers.py',W/'signals-character-method-bug-amendment-pdfium-utf16.json',W/'signals-r1-source-adapter.json',W/'signals-r1-label-adapter-correction.json']]
(W/'signals/cohort-r1-round5-strict.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print('rows',len(rows),'strata',dict(collections.Counter(r['cohort'] for r in rows)),'a',dict(collections.Counter(r['a']['status'] for r in rows)),'c',dict(collections.Counter(r['c']['status'] for r in rows)))
