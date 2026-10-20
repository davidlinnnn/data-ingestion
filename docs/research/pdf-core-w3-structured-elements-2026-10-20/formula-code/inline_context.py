"""Derived context filter and exploratory inline locators; frozen gold unchanged."""
from pathlib import Path
import json,re,hashlib,collections,importlib.util,unicodedata
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[3];OLD=REPO/'docs/research/pdf-core-w2-native-coverage-round2-2026-10-20/oracle'
def read(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s).casefold()if c.isalnum())
spec=importlib.util.spec_from_file_location('frozen_source_parser',ROOT/'build_oracle.py');parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
def arguments(s,commands):
 ranges=[]
 for m in re.finditer(r'\\('+commands+r')(?![A-Za-z@])\*?\s*(?:\[[^\]]*\])?\s*\{',s):
  i=m.end();depth=1
  while i<len(s)and depth:
   if s[i]=='\\':i+=2;continue
   if s[i]=='{':depth+=1
   if s[i]=='}':depth-=1
   i+=1
  if depth==0:ranges.append((m.end(),i-1,m.group(1)))
 return ranges

def stream(items,channel):
 chars=[];positions=[];raw=[];offset=0
 for t in items:
  v=t.get('text','')if t.get('text','')or channel=='RAW'else t.get('orig','');raw.append(v);raw.append('\n')
  for i,c in enumerate(v):
   n=norm(c)
   for z in n:chars.append(z);positions.append(offset+i)
  offset+=len(v)+1
 return ''.join(chars),positions,''.join(raw)

def main():
 oracle=read(ROOT/'oracle.json');index=read(OLD/'job-index.json');out=[];e0root=REPO/'docs/research/pdf-core-w2-native-coverage-round3-2026-10-20/runs/V3_B/jobs'
 allowed={'document','abstract','enumerate','itemize','description','center','flushleft','flushright','adjustbox','minipage','proof','theorem','lemma','corollary','definition','proposition','remark','example'}
 for job in oracle['jobs']:
  jid=job['job_id'];ii=[x for x in oracle['inline_math']if x['job_id']==jid]
  if not ii:continue
  old=read(Path(index[jid]));audit=next(a for a in oracle['source_audit']if a['job_id']==jid);files=parser.load_archive(Path(audit['source_path']).read_bytes());expanded,refs,_=parser.expand(files,old['source_audit']['root']);envs,_=parser.env_spans(expanded);args=arguments(expanded,'caption|captionof|footnote|footnotetext|texttt|lstinline');prior=collections.defaultdict(list)
  for a in old.get('inline_math_source_candidates',[]):prior[(a['source_file'],a['source_line'],norm(a['raw'].strip('$'))) ].append(a)
  doc=read(e0root/jid/'document.json');items=[t for t in doc['texts']if t.get('content_layer')!='furniture'];streams={ch:stream(items,ch)for ch in['RAW','MAPPED']}
  for x in ii:
   pos=x['expanded_offset'];anc=[e['env']for e in envs if e['body_start']<=pos<e['body_end']];arg=[c for a,b,c in args if a<=pos<b];line=files[x['source_file']].splitlines()[x['source_line']-1];context='PROSE_CANDIDATE'
   if any(c in arg for c in['caption','captionof']):context='CAPTION'
   elif any(c in arg for c in['footnote','footnotetext']):context='FOOTNOTE'
   elif any(c in arg for c in['texttt','lstinline']):context='CODE_OR_MONOSPACE_ARGUMENT'
   elif any(c in anc for c in['table','table*','tabular','tabular*','tabularx','longtable','tabu']):context='TABLE'
   elif any(c in anc for c in['figure','figure*','tikzpicture','axis']):context='FIGURE'
   elif any(c in anc for c in['thebibliography','bibliography']):context='BIBLIOGRAPHY'
   elif re.match(r'\s*\\(?:newcommand|renewcommand|providecommand|def|gdef)\b',line):context='MACRO_DEFINITION_UNEXECUTED'
   elif any(c not in allowed for c in anc):context='UNKNOWN_ENV_CONTEXT'
   z=dict(x,source_context=context,enclosing_environments=anc,enclosing_macro_arguments=arg,source_subscript_candidate=bool(re.search(r'(?<!\\)_',x['raw'])),source_superscript_candidate=bool(re.search(r'(?<!\\)\^',x['raw'])),frozen_gold_page_status=x['page_status'],observed_flattening=False,not_a_Q4_verdict=True)
   aa=prior.get((x['source_file'],x['source_line'],norm(x['raw'])),[]);z['prior_source_pdf_context_status']='UNIQUE_AUX_SOURCE_CONTEXT'if len(aa)==1 else'UNKNOWN_NO_UNIQUE_PRIOR_CONTEXT';z['auxiliary_prior_pdf_pages']=sorted({a['pdf_page']for a in aa if a.get('pdf_page')});z['gold_page_status']='UNKNOWN_NOT_PROMOTED'
   z['E0_context_alignment']={}
   if len(aa)==1:
    a=aa[0];before=norm(a.get('context_before',''))[-48:];after=norm(a.get('context_after',''))[:48];z['source_context_before']=a.get('context_before');z['source_context_after']=a.get('context_after')
    for ch,(st,positions,raw)in streams.items():
     hits=[];at=0
     if len(before)>=20 and len(after)>=20:
      while(at:=st.find(before,at))>=0:
       p0=at+len(before);p1=st.find(after,p0,p0+1200)
       if p1>=0:hits.append((p0,p1))
       at+=1
     if len(hits)==1:
      a0,b0=hits[0];text=raw[positions[a0-1]+1:positions[b0]]if a0>0 and b0<len(positions)else'';z['E0_context_alignment'][ch]={'status':'EXPLORATORY_CONTEXT_ALIGNED','delivered_between_contexts':text,'source_subscript_without_explicit_marker_candidate':z['source_subscript_candidate']and'_'not in text and not any(c in text for c in'₀₁₂₃₄₅₆₇₈₉'),'source_superscript_without_explicit_marker_candidate':z['source_superscript_candidate']and'^'not in text and not any(c in text for c in'⁰¹²³⁴⁵⁶⁷⁸⁹'),'not_verified_loss':True}
     else:z['E0_context_alignment'][ch]={'status':'UNKNOWN_CONTEXT_AMBIGUOUS_OR_ABSENT','matches':len(hits)}
   out.append(z)
  print(jid,len(ii),flush=True)
 dump(ROOT/'inline-derived-context.json',out)
 summary={'source_spans_total':len(out),'source_context_counts':dict(collections.Counter(x['source_context']for x in out)),'source_prose_candidates':sum(x['source_context']=='PROSE_CANDIDATE'for x in out),'source_prose_subscript_candidates':sum(x['source_context']=='PROSE_CANDIDATE'and x['source_subscript_candidate']for x in out),'source_prose_superscript_candidates':sum(x['source_context']=='PROSE_CANDIDATE'and x['source_superscript_candidate']for x in out),'actual_observed_flattening_frequency':'NOT_ESTABLISHED_FROM_SOURCE_SPANS','gold_unknown_unchanged':True,'aux_context_pages_not_denominator_promoted':True,'E0_prose_context_locator_candidates':{ch:sum(x['source_context']=='PROSE_CANDIDATE'and x['E0_context_alignment'].get(ch,{}).get('status')=='EXPLORATORY_CONTEXT_ALIGNED'for x in out)for ch in['RAW','MAPPED']}}
 dump(ROOT/'inline-summary.json',summary)
 candidates=[x for x in out if x['source_context']=='PROSE_CANDIDATE'and x['auxiliary_prior_pdf_pages']and x['E0_context_alignment'].get('RAW',{}).get('status')=='EXPLORATORY_CONTEXT_ALIGNED'];chosen=[]
 for field in['source_subscript_candidate','source_superscript_candidate']:
  pool=sorted([x for x in candidates if x[field]and x['id']not in{z['id']for z in chosen}],key=lambda x:hashlib.sha256(('W3-formula-code-source-v1-20261020|inline-audit|'+x['id']).encode()).hexdigest());chosen+=pool[:3]
 dump(ROOT/'inline-audit-selection.json',{'rule':'Fixed seed hash; first3 prose/context-aligned subscript, then first3 nonoverlapping superscript. Auxiliary source PDF pages remain supplemental; frozen gold UNKNOWN is unchanged.','cases':chosen});print(summary)
if __name__=='__main__':main()
