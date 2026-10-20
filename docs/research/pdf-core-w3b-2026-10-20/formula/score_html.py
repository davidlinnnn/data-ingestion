"""Stage3 only: frozen HTML -> E0 orig identity, then fixed-ref saved E1."""
from pathlib import Path
from lxml import html,etree
import json,re,hashlib,unicodedata,collections,difflib,importlib.util
P=Path(__file__).resolve().parent;W=P.parent;REPO=P.parents[3];OUT=P/'assessment';OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
protocol=read(W/'formula-score-preregistration.json');normalizer=REPO/protocol['normalizer_source'];assert sha(normalizer)==protocol['normalizer_sha256'];spec=importlib.util.spec_from_file_location('w3v2',normalizer);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
SYMBOLMAP={'−':'-','–':'-','ϵ':'ε','µ':'μ','ϕ':'φ','ϑ':'θ'}
def visible(t):
 out=[];idx=[]
 for i,c in enumerate(t):
  for z in unicodedata.normalize('NFKD',c):
   z=SYMBOLMAP.get(z,z)
   if z.isalnum()or z in '=<>+-*/∈∉≤≥≠←→|':out.append(z);idx.append(i)
 return ''.join(out),idx

def source_visible(u):
 root=html.fromstring(u['mathml'])
 for n in root.xpath('.//annotation|.//annotation-xml'):n.getparent().remove(n)
 return visible(''.join(root.itertext()))[0]
def refs(doc):return {t['self_ref']:t for t in doc.get('texts',[])}
def pages(t):return {v['page_no']for v in t.get('prov',[])}
def bucket(expected,text):
 a=s.math_tokens(expected);b=s.math_tokens(text);r=s.ratio(a,b);return {'class':'EXACT'if a and a==b else'NEAR'if r>=.75 else'ERROR','canonical_ratio':r,'text':text,'semantic_verdict':'UNADJUDICATED_NOT_LEXICAL_PASS'}
def top_rows(t):
 # Structural row position only; never choose row by E1 similarity.
 env=re.search(r'\\begin\s*\{(aligned\*?|align\*?|gathered|gather\*?|eqnarray\*?|split)\}',t)
 if env:
  sp=importlib.util.spec_from_file_location('source_parser',P/'build_oracle.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b);rr=b.row_tex_split(t,env.group(1));return rr or[]
 # Explicit TeX top-level row breaks; nested matrix/cases environment not cut.
 stack=[];last=0;out=[]
 for m in re.finditer(r'\\begin\s*\{([^}]+)\}|\\end\s*\{([^}]+)\}|\\\\',t):
  if m.group(1):stack.append(m.group(1))
  elif m.group(2):
   if stack:stack.pop()
  elif not stack:out.append(t[last:m.start()].strip());last=m.end()
 if out:out.append(t[last:].strip());return [x for x in out if x]
 return [t]

def main():
 oracle=read(P/'oracle.json');cross={j['job_id']:j['family']for j in read(REPO/'docs/research/pdf-core-w3-structured-elements-2026-10-20/source-manifest.json')['jobs']};base=REPO/'docs/research/pdf-core-w2-native-coverage-round3-2026-10-20/runs/V3_B/jobs';w3=REPO/'docs/research/pdf-core-w3-structured-elements-2026-10-20';e1folders={};docs0={};docs1={};processed={};inputs={}
 for stage in ['E1_pilot','E1_sampled_v2']:
  for cf in(w3/'runs'/stage/'jobs').glob('*/conversion.json'):
   if read(cf).get('status')=='success':e1folders[cf.parent.name]=cf.parent
 out=[]
 for j in oracle['jobs']:
  jid=j['job_id'];fd=base/jid
  if not(fd/'document.json').exists():continue
  d=read(fd/'document.json');docs0[jid]=refs(d);inputs[jid]={'E0_document_sha256':sha(fd/'document.json')}
  if jid in e1folders:
   ff=e1folders[jid];docs1[jid]=refs(read(ff/'document.json'));b=read(ff/'enrichment-batches.json')if(ff/'enrichment-batches.json').exists()else[];processed[jid]={x['ref']for batch in b if'outputs'in batch for x in batch.get('inputs',[])};inputs[jid].update(E1_document_sha256=sha(ff/'document.json'),E1_folder=str(ff),actual_processed_refs=sorted(processed[jid]))
 for u in oracle['units']:
  r={'unit_id':u['unit_id'],'job_id':u['job_id'],'family_analysis':cross.get(u['job_id'],'UNKNOWN'),'family_frozen_html':u['family'],'source_page':u['page'],'source_latex':u['latex'],'source_latex_sha256':u['latex_sha256'],'scope':u['scope'],'granularity_status':u['granularity_status'],'single_formula_comparable':u['single_formula_comparable'],'source_identity_status':'NOT_EVALUATED_SOURCE_OUTSIDE_DENOMINATOR','fixed_E0_refs':[],'E0orig':None,'E1':None,'actual_enriched':False,'candidate_only_not_Q4':True};out.append(r)
  if not u['single_formula_comparable']:continue
  jid=u['job_id'];expected=source_visible(u);r['source_mathml_visible']=expected
  if len(expected)<6:r['source_identity_status']='UNKNOWN_TOO_SHORT_FOR_UNIQUE_IDENTITY';continue
  pool=[t for t in docs0[jid].values()if u['page']in pages(t)and t.get('content_layer')!='furniture'];hits=[];candidates=[]
  for t in pool:
   raw=t.get('orig')or t.get('text','');v,idx=visible(raw);start=v.find(expected)
   if start>=0 and v.find(expected,start+1)<0:
    a=idx[start];z=idx[start+len(expected)-1]+1;hits.append({'ref':t['self_ref'],'start':a,'end':z,'text':raw[a:z],'item_visible_length':len(v),'match_visible_length':len(expected),'label':t['label']})
   if t.get('label')in {'formula','code'}:candidates.append({'ref':t['self_ref'],'ratio':difflib.SequenceMatcher(None,expected,v,autojunk=False).ratio(),'label':t['label']})
  if len(hits)!=1:
   r['source_identity_status']='UNKNOWN_AMBIGUOUS_SOURCE_IDENTITY'if len(hits)>1 else'UNKNOWN_NO_EXACT_SOURCE_IDENTITY';r['exact_hits']=hits;r['untrusted_nearest_E0_candidates']=sorted(candidates,key=lambda x:-x['ratio'])[:2];continue
  hit=hits[0];r.update(source_identity_status='UNIQUE_SOURCE_VISIBLE_SUBSTRING_E0_ORIG',fixed_E0_refs=[hit['ref']],identity_evidence=hit,E0orig=bucket(u['latex'],hit['text']));r['E0_native_label']=hit['label']
 groups=collections.defaultdict(list)
 for r in out:
  if r['fixed_E0_refs']:groups[(r['job_id'],r['fixed_E0_refs'][0])].append(r)
 for (jid,ref),rr in groups.items():
  rr.sort(key=lambda r:r['identity_evidence']['start']);e0=docs0[jid][ref];after=docs1.get(jid,{}).get(ref);actually=ref in processed.get(jid,set())
  # Disjoint raw spans are essential; overlapping source lines cannot be independent slices.
  overlap=any(a['identity_evidence']['end']>b['identity_evidence']['start']for a,b in zip(rr,rr[1:]));combined=len(rr)>1
  coverage=sum(r['identity_evidence']['match_visible_length']for r in rr)/max(1,len(visible(e0.get('orig')or e0.get('text',''))[0]))
  original=e0.get('orig')or e0.get('text','')
  for ix,r in enumerate(rr):
   if overlap or coverage<.70:r['E0orig']={'status':'UNKNOWN_INDEPENDENT_TEXT_BOUNDARY','class':None,'text':None,'reason':'Locator substring is not assumed to be a complete delivered formula; native item substantial extra content/overlap.'}
   else:
    a=0 if ix==0 else r['identity_evidence']['start'];z=rr[ix+1]['identity_evidence']['start']if ix+1<len(rr)else len(original);r['E0orig']=bucket(r['source_latex'],original[a:z]);r['E0orig']['status']='INDEPENDENT_RAW_TEXT_BOUNDARY';r['E0orig']['E0GLYPH_ONLY_STRUCTURAL_LIMITATION']=True;r['E0orig']['partition_policy']='Whole item once or disjoint source-aligned raw intervals, preserving closing punctuation and labels; never duplicate full item per source row.'

  if not after:
   for r in rr:r['E1']={'status':'NOT_PROCESSED_JOB_UNAVAILABLE','lexical':None}
   continue
  intact=e0.get('orig')==after.get('orig')and e0.get('prov')==after.get('prov');text=after.get('text','');decomp=top_rows(text)
  for ix,r in enumerate(rr):
   r['actual_enriched']=actually;r['fixed_ref_identity_orig_prov_unchanged']=intact;r['source_units_sharing_item']=len(rr);r['E1_native_item_active_text']=text;r['E1_native_item_orig_evidence']=after.get('orig','')
   if not actually:r['E1']={'status':'NOT_ENRICHED','lexical':None};continue
   if not intact:r['E1']={'status':'UNKNOWN_ITEM_IDENTITY_CHANGED','lexical':None};continue
   if overlap:r['E1']={'status':'MANY_TO_ONE_UNRESOLVED','reason':'overlapping source-visible spans','lexical':None};continue
   if combined:
    if len(decomp)!=len(rr):r['E1']={'status':'MANY_TO_ONE_UNRESOLVED','reason':'E1 structural row count does not equal independently source-aligned rows','structural_rows':len(decomp),'lexical':None};continue
    piece=decomp[ix];r['decomposition']='FIXED_RAW_SOURCE_SPAN_ORDER_TO_EQUAL_COUNT_STRUCTURAL_E1_ROWS';r['row_ordinal']=ix+1
   else:
    hit=r['identity_evidence']
    if hit['match_visible_length']/max(1,hit['item_visible_length'])<.70:r['E1']={'status':'MANY_TO_ONE_UNRESOLVED','reason':'native item contains substantial extra material; no independently established row boundary','lexical':None};continue
    piece=text;r['decomposition']='ONE_SOURCE_FORMULA_DOMINATES_ONE_FIXED_NATIVE_ITEM'
   r['E1']={'status':'ACTUALLY_ENRICHED_INDEPENDENT_TEXT','RAW':bucket(r['source_latex'],piece),'MAPPED':bucket(r['source_latex'],piece if piece.strip()else after.get('orig','')),'orig_not_union_with_nonempty_model_text':True}
 comparable=[r for r in out if r['single_formula_comparable']];aligned=[r for r in comparable if r['fixed_E0_refs']];scored=[r for r in aligned if r['E1']and r['E1']['status']=='ACTUALLY_ENRICHED_INDEPENDENT_TEXT'];actual=[r for r in aligned if r['actual_enriched']];summary={'status':'FINAL_PARTIAL_TIME_BUDGET_E1_SAVED_OUTPUTS_ONLY','source_display_candidates':len(out),'single_formula_source_denominator':len(comparable),'source_unique_E0_identity':len(aligned),'source_identity_UNKNOWN':len(comparable)-len(aligned),'source_aligned_actual_enriched':len(actual),'source_aligned_actual_enriched_independent_scored':len(scored),'source_aligned_actual_enriched_unresolved':len(actual)-len(scored),'E1_completed_saved_jobs':len(e1folders),'identity_status':dict(collections.Counter(r['source_identity_status']for r in comparable)),'E1_status':dict(collections.Counter((r['E1']or{}).get('status','UNKNOWN_SOURCE_IDENTITY')for r in comparable)),'E0orig_lexical_aligned':dict(collections.Counter(r['E0orig']['class']or'UNKNOWN_BOUNDARY'for r in aligned)),'E1_RAW':dict(collections.Counter(r['E1']['RAW']['class']for r in scored)),'E1_MAPPED':dict(collections.Counter(r['E1']['MAPPED']['class']for r in scored)),'family':[],'source_oracle_sha256':sha(P/'oracle.json'),'preregistration_sha256':sha(W/'formula-score-preregistration.json'),'normalizer_sha256':sha(normalizer),'mapping_policy':'Unique exact Presentation-MathML-visible substring within one same-source-page E0 orig item. Operators preserved. Nearest candidates never promoted without identity. Fixed same refs E1; source raw disjoint slices, structural equal-row decomposition only.','manual_review_required_for_semantic_Q31':True,'not_automatic_pass_rate':True,'no_new_enrichment':True,'RAW_MAPPED_definition':'Scalar native text vs orig fallback only when empty; official delivery separate prior W3 artefacts, not inferred by scalar class.'}
 for fam in sorted({r['family_analysis']for r in comparable}):
  aa=[r for r in comparable if r['family_analysis']==fam];mm=[r for r in aa if r['fixed_E0_refs']];pp=[r for r in scored if r['family_analysis']==fam];summary['family'].append({'family':fam,'source_single_formula':len(aa),'aligned':len(mm),'source_identity_unknown':len(aa)-len(mm),'actual_enriched_scored':len(pp),'E1_RAW':dict(collections.Counter(r['E1']['RAW']['class']for r in pp)),'E1_MAPPED':dict(collections.Counter(r['E1']['MAPPED']['class']for r in pp))})
 dump(OUT/'per-formula.json',out);dump(OUT/'summary.json',summary);dump(OUT/'input-hashes.json',inputs);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
