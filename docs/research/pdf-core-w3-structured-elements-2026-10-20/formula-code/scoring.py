"""Read sealed source units; compare output candidates without mutating gold."""
from pathlib import Path
import json,re,hashlib,collections,argparse,difflib,unicodedata,bisect
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
SEED='W3-formula-code-source-v1-20261020'
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s).casefold()if c.isalnum())
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
SYMBOLS={'−':'-','–':'-','≤':r'\leq','≥':r'\geq','∈':r'\in','∉':r'\notin','→':r'\to','←':r'\leftarrow','↔':r'\leftrightarrow','∞':r'\infty','∑':r'\sum','∏':r'\prod','√':r'\sqrt','∇':r'\nabla','∂':r'\partial','×':r'\times','·':r'\cdot','⊙':r'\odot','⊗':r'\otimes','α':r'\alpha','β':r'\beta','γ':r'\gamma','δ':r'\delta','ϵ':r'\epsilon','ε':r'\varepsilon','θ':r'\theta','λ':r'\lambda','μ':r'\mu','π':r'\pi','ρ':r'\rho','σ':r'\sigma','τ':r'\tau','φ':r'\phi','ψ':r'\psi','ω':r'\omega','Δ':r'\Delta','Σ':r'\Sigma','Π':r'\Pi','∅':r'\emptyset'}
FONT_COMMANDS={'mathbf','mathrm','mathcal','mathbb','mathit','mathsf','mathtt','mathnormal','boldsymbol','bm','text','textbf','textit','textrm','textsf','texttt','emph','operatorname'}
SPACE_ARGS={'hspace','vspace','hskip','vskip','kern','mkern'}
def balanced(s,i,op='{',cl='}'):
 if i>=len(s)or s[i]!=op:return None,i
 depth=1;j=i+1
 while j<len(s):
  if s[j]=='\\':j+=2;continue
  if s[j]==op:depth+=1
  elif s[j]==cl:
   depth-=1
   if not depth:return s[i+1:j],j+1
  j+=1
 return None,i

def format_only(s):
 out=[];i=0
 while i<len(s):
  if s[i]!='\\':out.append(s[i]);i+=1;continue
  m=re.match(r'\\([A-Za-z@]+)',s[i:])
  if not m:
   if i+1<len(s)and s[i+1]in ',;!: ':i+=2;continue
   if s[i:i+2]in {r'\[',r'\]',r'\(',r'\)'}:i+=2;continue
   out.append(s[i:i+2]);i+=2;continue
  cmd=m.group(1);end=i+len(m.group());j=end
  if j<len(s)and s[j]=='*':j+=1
  while j<len(s)and s[j].isspace():j+=1
  if cmd in SPACE_ARGS|{'label','tag'}:
   if j<len(s)and s[j]=='[':
    _,k=balanced(s,j,'[',']');j=k if k!=j else j
    while j<len(s)and s[j].isspace():j+=1
   arg,k=balanced(s,j)
   if arg is not None:i=k;continue
   if cmd in {'kern','mkern','hskip','vskip'}:
    d=re.match(r'[+-]?[\d.]+\s*(?:mu|pt|em|ex|mm|cm|in)',s[j:])
    if d:i=j+len(d.group());continue
   i=end;continue
  if cmd in FONT_COMMANDS:
   arg,k=balanced(s,j)
   if arg is not None:out.append(format_only(arg));i=k;continue
   i=end;continue
  if cmd in {'left','right','displaystyle','textstyle','scriptstyle','scriptscriptstyle','nonumber','notag','quad','qquad','hfill','big','Big','bigg','Bigg','bigl','bigr','Bigl','Bigr','rm','bf','it'}:i=end;continue
  out.append(s[i:end]);i=end
 return ''.join(out)

def math_tokens(s):
 s=unicodedata.normalize('NFKD',s)
 for a,b in SYMBOLS.items():s=s.replace(a,' '+b+' ')
 s=re.sub(r'\\(?:begin|end)\s*\{(?:equation|align|aligned|gather|multline|eqnarray|displaymath)\*?\}','',s)
 s=format_only(s)
 # Only paired outer math delimiters are removed. Currency tokens remain significant.
 if s.startswith('$$')and s.endswith('$$')and len(s)>4:s=s[2:-2]
 elif s.startswith('$')and s.endswith('$')and len(s)>2:s=s[1:-1]
 s=s.replace(r'\$','CURRENCYDOLLAR').replace('$','CURRENCYDOLLAR')
 return re.findall(r'\\[A-Za-z@]+|CURRENCYDOLLAR|\d+(?:\.\d+)?|[A-Za-z]|[^\s]',s)

def body_order(doc):
 seen=set();ordered=[]
 def resolve(ref):
  if ref=='#/body':return doc.get('body',{})
  if ref=='#/furniture':return doc.get('furniture',{})
  try:k,n=ref.split('/')[-2:];return doc[k][int(n)]
  except(KeyError,IndexError,ValueError,TypeError):return {}
 def walk(ref):
  if ref in seen:return
  seen.add(ref);item=resolve(ref)
  if ref.startswith('#/texts/'):ordered.append(ref)
  for field in ['children','captions','footnotes']:
   for child in item.get(field,[]):
    r=child.get('$ref')if isinstance(child,dict)else child
    if r:walk(r)
 walk('#/body')
 # Unlinked items have no documented tree position: stable append and explicit diagnostic.
 unlinked=[x['self_ref']for x in doc.get('texts',[])if x['self_ref']not in seen and x.get('content_layer')!='furniture']
 return ordered+unlinked

def ordered_items(doc,refs):
 rank={r:i for i,r in enumerate(body_order(doc))};return sorted(refs,key=lambda t:rank.get(t['self_ref'],10**9))

def text_source(u):
 s=u['raw']
 if u['env']in{'verbatim','verbatim*','Verbatim','lstlisting','minted','tcblisting'}:
  s=re.sub(r'^\s*\[[^\]]*\]','',s)
  if u['env']=='minted':s=re.sub(r'^\s*\{[^{}]*\}','',s)
  return s.strip('\r\n')
 s=s.replace(r'\{','§OPEN§').replace(r'\}','§CLOSE§')
 s=re.sub(r'\\(?:label)\s*\{[^{}]*\}','',s)
 s=re.sub(r'\\(?:textbf|textit|texttt|textrm|emph|caption)\*?\s*\{([^{}]*)\}',r'\1',s)
 s=s.replace(r'\\','\n').replace(r'\_','_').replace(r'\%','%').replace(r'\&','&').replace(r'\$','$')
 s=re.sub(r'\\[A-Za-z@]+\*?(?:\[[^\]]*\])?',' ',s).replace('{','').replace('}','').replace('§OPEN§','{').replace('§CLOSE§','}').replace('~',' ')
 return s.strip()
def code_tokens(s):return re.findall(r'[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[^\s]',s)
def ratio(a,b):return difflib.SequenceMatcher(None,a,b,autojunk=False).ratio()if a and b else 0.0
def page_set(t):return {p['page_no']for p in t.get('prov',[])}
def active(t,channel):return t.get('text','')if t.get('text','').strip()or channel=='RAW'else t.get('orig','')
def rank_formula(src,items):
 tt=math_tokens(src);scores=[]
 for t in items:
  value=active(t,'MAPPED');tok=math_tokens(value)
  if tok:scores.append((ratio(tt,tok),t))
 return sorted(scores,key=lambda x:(-x[0],x[1]['_index']))
def code_refs(u,items):
 source=norm(text_source(u));pieces=[];bounds=[];at=0
 for t in items:
  n=norm(active(t,'MAPPED'));pieces.append(n);bounds.append((at,at+len(n),t));at+=len(n)
 stream=''.join(pieces);hits=[]
 for k in sorted({0,max(0,len(source)//2-45),max(0,len(source)-90)}):
  q=source[k:k+90]
  if len(q)<32:continue
  pos=stream.find(q)
  if pos>=0 and stream.find(q,pos+1)<0:hits.append((pos,pos+len(q)))
 if not hits:return [],[],source
 # Preserve all native items between matched source chunks, never concatenate in oracle order.
 lo=min(a for a,b in hits);hi=max(b for a,b in hits)
 refs=[t for a,b,t in bounds if a<hi and b>lo]
 return refs,hits,source

def evaluate(u,doc,md):
 items=[]
 for i,t in enumerate(doc.get('texts',[])):
  if t.get('content_layer')=='furniture':continue
  t=dict(t,_index=i);items.append(t)
 known=u['scope']=='IN_SCOPE'and u['page_status']!='UNKNOWN'and bool(u.get('pages'))
 allowed=set(u.get('pages',[]));pool=[t for t in items if page_set(t)&allowed]if known else items
 eligible=[t for t in pool if t.get('label')in{'formula','code'}];aligned=[];exploratory=[];align_evidence=[];ambiguous=False
 if u['kind']=='formula':
  parts=u.get('rows')or[{'raw':u['raw']}]
  for part in parts:
   if not part['raw'].strip():continue
   ranked=rank_formula(part['raw'],pool);best=ranked[0]if ranked else None;floor=.35 if known else .65
   if best and best[0]>=floor and(known or len(ranked)==1 or best[0]-ranked[1][0]>=.10):
    aligned.append(best[1]);align_evidence.append({'row_index':part.get('row_index',1),'ref':best[1]['self_ref'],'score':best[0],'label':best[1]['label'],'runnerup':ranked[1][0]if len(ranked)>1 else None})
   else:ambiguous=True
 else:
  aligned,hits,ss=code_refs(u,pool);align_evidence=[{'unique_source_chunk_native_offsets':x}for x in hits]
 aligned=sorted({t['self_ref']:t for t in aligned}.values(),key=lambda t:t['_index']);eligible_aligned=[t for t in aligned if t.get('label')in{'formula','code'}]
 result={'unit_id':u['id'],'job_id':u['job_id'],'kind':u['kind'],'env':u['env'],'family':u['family'],'gold_scope':u['scope'],'gold_page_status':u['page_status'],'gold_pages':u.get('pages',[]),'gold_page_candidates':u.get('page_candidates',[]),'known_gold_denominator':known,'alignment_status':'ALIGNED_CANDIDATE'if aligned else'UNKNOWN_ALIGNMENT'if not known else'UNMATCHED_CANDIDATE','exploratory_output_alignment':not known,'alignment_evidence':align_evidence,'matched_refs':[t['self_ref']for t in aligned],'eligible_enrichment_refs':[t['self_ref']for t in eligible_aligned],'detected_eligible_role_candidate':bool(eligible_aligned),'partial_row_alignment':ambiguous,'candidate_only_not_Q4':True,'native_items':[{'ref':t['self_ref'],'label':t['label'],'parent':t.get('parent'),'pages':sorted(page_set(t)),'active_text':t.get('text',''),'orig':t.get('orig','')}for t in aligned],'channels':{}}
 expected=math_tokens(u['raw'])if u['kind']=='formula'else code_tokens(text_source(u))
 for channel in['RAW','MAPPED']:
  delivered='\n'.join(active(t,channel)for t in aligned);tt=math_tokens(delivered)if u['kind']=='formula'else code_tokens(delivered);score=ratio(expected,tt);exact=bool(expected)and expected==tt;status='EXACT_CANONICAL'if exact else'NEAR_CANONICAL'if score>=.75 else'ERROR_OR_MISSING'
  if not known:status='UNKNOWN_GOLD_SCOPE'
  if not aligned:status='UNKNOWN_ALIGNMENT'if not known else'ERROR_OR_MISSING'
  result['channels'][channel]={'canonical_ratio':score,'status':status,'canonical_exact':exact,'delivered_text':delivered,'empty':not delivered.strip(),'orig_fallback_refs':[t['self_ref']for t in aligned if channel=='MAPPED'and not t.get('text')and t.get('orig')],'meaning_preservation':'UNADJUDICATED'}
 # This is literal/visible-text presence, not a symbolic equivalence judgement.
 clean=text_source(u)if u['kind']!='formula'else u['raw'];n=norm(clean);mn=norm(md);result['markdown_literal_normalized_presence']=bool(n)and n in mn
 result['markdown_presence_note']='Alphanumeric-normalized locator only; punctuation/negation/math correctness requires page adjudication.'
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--variant-root',required=True);ap.add_argument('--prefix',default='e0');a=ap.parse_args();vr=Path(a.variant_root);oracle=json.loads((ROOT/'oracle.json').read_text());selected=set(oracle['sampling']['formula_if_cost_over_2hours']+oracle['sampling']['all_code_algorithm']);units=oracle['units'];allresults=[];itemsbyjob={};missing=[]
 for job in oracle['jobs']:
  j=job['job_id'];fd=vr/j
  if not(fd/'document.json').exists():missing.append(j);continue
  doc=json.loads((fd/'document.json').read_text());md=(fd/'document.md').read_text();itemsbyjob[j]={'document_sha256':sha((fd/'document.json').read_bytes()),'markdown_sha256':sha((fd/'document.md').read_bytes())}
  for u in units:
   if u['job_id']==j and u['scope']!='OUT_OF_SCOPE':allresults.append(evaluate(u,doc,md))
  print(j,len([x for x in allresults if x['job_id']==j]),flush=True)
 mapping=[]
 for uid in oracle['sampling']['formula_if_cost_over_2hours']+oracle['sampling']['all_code_algorithm']:
  rr=next((x for x in allresults if x['unit_id']==uid),None)
  if rr is None:mapping.append({'unit_id':uid,'status':'UNKNOWN_NO_OUTPUT','eligible_refs':[]});continue
  mapping.append({'unit_id':uid,'job_id':rr['job_id'],'kind':rr['kind'],'gold_scope':rr['gold_scope'],'gold_page_status':rr['gold_page_status'],'gold_pages':rr['gold_pages'],'alignment_status':rr['alignment_status'],'matched_refs':rr['matched_refs'],'eligible_refs':rr['eligible_enrichment_refs'],'exploratory_output_alignment':rr['exploratory_output_alignment'],'known_gold_denominator':rr['known_gold_denominator'],'alignment_evidence':rr['alignment_evidence']})
 dump(ROOT/(a.prefix+'-scores.json'),allresults);dump(ROOT/(a.prefix+'-input-hashes.json'),itemsbyjob)
 if a.prefix=='e0':dump(ROOT/'selected-item-map.json',{'source_sample_plan_sha256':sha((ROOT/'sample-plan.json').read_bytes()),'no_gold_modified':True,'mapping':mapping,'known_page_gate':{j:sorted({ref for x in mapping if x.get('job_id')==j and not x.get('exploratory_output_alignment')for ref in x['eligible_refs']})for j in itemsbyjob},'exploratory_gate':{j:sorted({ref for x in mapping if x.get('job_id')==j and x.get('exploratory_output_alignment')for ref in x['eligible_refs']})for j in itemsbyjob}})
 summary={'variant_root':str(vr),'jobs_read':len(itemsbyjob),'missing_jobs':missing,'oracle_units_scored_or_unknown':len(allresults),'known_gold_denominator':sum(x['known_gold_denominator']for x in allresults),'by_kind':{k:{'source_units':sum(x['kind']==k for x in allresults),'known_gold':sum(x['kind']==k and x['known_gold_denominator']for x in allresults),'eligible_role_detected_known':sum(x['kind']==k and x['known_gold_denominator']and x['detected_eligible_role_candidate']for x in allresults),'RAW':dict(collections.Counter(x['channels']['RAW']['status']for x in allresults if x['kind']==k)),'MAPPED':dict(collections.Counter(x['channels']['MAPPED']['status']for x in allresults if x['kind']==k))}for k in['formula','code','algorithm']},'source_sample_ids':len(mapping),'known_page_gate_refs':len({(x['job_id'],ref)for x in mapping if x.get('job_id')and not x.get('exploratory_output_alignment')for ref in x['eligible_refs']}),'exploratory_gate_refs':len({(x['job_id'],ref)for x in mapping if x.get('job_id')and x.get('exploratory_output_alignment')for ref in x['eligible_refs']}),'no_automatic_Q4_pass_claim':True,'source_file_hash_limit':'Oracle source_file_sha256 hashes decoded UTF8 text; raw archive bytes are separately SHA-verified. Comments masked outside literal code.'};dump(ROOT/(a.prefix+'-summary.json'),summary);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
