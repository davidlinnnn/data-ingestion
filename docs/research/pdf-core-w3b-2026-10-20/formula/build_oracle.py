"""Source-only HTML formula-line oracle. Never opens Docling artifacts."""
from pathlib import Path
from lxml import html,etree
import json,re,hashlib,unicodedata,collections,argparse
import pypdfium2 as pf
ROOT=Path(__file__).resolve().parent;W=ROOT.parent;SEED='W3b-html-formula-oracle-20261020-v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s).casefold()if c.isalnum())
def local(n):return n.tag.split('}')[-1]if isinstance(n.tag,str)else''
def cls(n,c):return c in n.get('class','').split()
def tex(m):
 a=m.get('alttext')
 if a:return a
 return next((''.join(x.itertext())for x in m.iter()if local(x)=='annotation'and x.get('encoding')in{'application/x-tex','application/x-latex'}),'')
def descendants(n,tag):return [x for x in n.iter()if local(x)==tag]
def row_tex_split(s,env):
 # Split only line breaks at target environment depth; nested matrices/cases stay atomic.
 match=re.search(r'\\begin\s*\{'+re.escape(env)+r'\}',s)
 if not match:return None
 start=match.end()
 # Array column specifications are layout metadata, not formula content.
 if env=='array':
  while start<len(s)and s[start].isspace():start+=1
  if start<len(s)and s[start]=='[':
   k=s.find(']',start+1)
   if k>=0:start=k+1
  while start<len(s)and s[start].isspace():start+=1
  if start<len(s)and s[start]=='{':
   depth=1;k=start+1
   while k<len(s)and depth:
    depth+=(s[k]=='{')-(s[k]=='}');k+=1
   if not depth:start=k
 stack=[env];last=start;rows=[];pos=start
 token=re.compile(r'\\begin\s*\{([^}]+)\}|\\end\s*\{([^}]+)\}|\\\\(?:\s*\[[^\]]*\])?')
 for m in token.finditer(s,start):
  if m.group(1):stack.append(m.group(1))
  elif m.group(2):
   if stack and stack[-1]==m.group(2):
    stack.pop()
    if not stack:rows.append(s[last:m.start()]);return [r.strip()for r in rows if r.strip()]
   else:return None
  elif len(stack)==1:rows.append(s[last:m.start()]);last=m.end()
 return None

def standalone_row(s):
 out=[];depth=0;envs=[];i=0
 while i<len(s):
  match=re.match(r'\\(?:begin|end)\{([^}]+)\}',s[i:])
  if match:
   if s[i:].startswith(r'\begin'):envs.append(match.group(1))
   elif envs:envs.pop()
   out.append(match.group());i+=len(match.group());continue
  if s[i]=='\\'and i+1<len(s)and s[i+1]in '{}&':out.append(s[i:i+2]);i+=2;continue
  if s[i]=='{':depth+=1
  elif s[i]=='}':depth-=1
  if s[i]=='&'and not depth and not envs:out.append(' ')
  else:out.append(s[i])
  i+=1
 return ''.join(out).strip()

def split_math(m):
 s=tex(m);tables=[t for t in descendants(m,'mtable')if not any(local(a)=='mtable'for a in t.iterancestors()if a is not m)]
 # Explicit matrices and piecewise/cases are one mathematical object, never row-counted.
 firstenv=re.search(r'\\begin\s*\{([^}]+)\}',s)
 if firstenv and re.fullmatch(r'[pbBvV]?matrix|cases|dcases|smallmatrix',firstenv.group(1)):return [{'latex':s,'mathml':etree.tostring(m,encoding='unicode'),'split':'ATOMIC_MATRIX_OR_CASES','row_index':1}]
 envmatch=re.search(r'\\begin\s*\{(aligned\*?|align\*?|gathered|gather\*?|eqnarray\*?|array|split)\}',s)
 if not tables:return [{'latex':s,'mathml':etree.tostring(m,encoding='unicode'),'split':'SINGLE_MATH','row_index':1}]
 if not envmatch:return [{'latex':s,'mathml':etree.tostring(m,encoding='unicode'),'split':'UNKNOWN_MTABLE_GRANULARITY','row_index':1,'unknown':True}]
 env=envmatch.group(1);rows=row_tex_split(s,env);trs=[x for x in tables[0]if local(x)in{'mtr','mlabeledtr'}]
 if not rows or len(rows)!=len(trs):return [{'latex':s,'mathml':etree.tostring(m,encoding='unicode'),'split':'UNKNOWN_TEX_MATHML_ROW_CORRESPONDENCE','row_index':1,'unknown':True,'tex_rows':len(rows or[]),'mathml_rows':len(trs)}]
 # Unfenced array can be a comparison table of independent relations; matrix-like arrays stay atomic.
 if env=='array'and(re.search(r'\\left\s*[\[(|]',s[:envmatch.start()])or sum(any(''.join(x.itertext())in {'=','<','>','≤','≥','≠','←','→'}for x in descendants(tr,'mo'))for tr in trs)<2):return [{'latex':s,'mathml':etree.tostring(m,encoding='unicode'),'split':'ATOMIC_ARRAY_OR_MATRIX','row_index':1}]
 out=[]
 for i,(r,tr)in enumerate(zip(rows,trs),1):
  relation=any(''.join(x.itertext())in {'=','<','>','≤','≥','≠','←','→','≔'}for x in descendants(tr,'mo'))
  if env=='array'and not relation:continue
  out.append({'latex':standalone_row(r),'latex_row_raw':r,'mathml':etree.tostring(tr,encoding='unicode'),'split':'MATHML_TEX_ROW_ALIGNED','row_index':i,'depends_on_previous_row':bool(re.match(r'\s*&?\s*(?:=|\\(?:le|ge|approx|equiv))',r))})
 return out or [{'latex':s,'mathml':etree.tostring(m,encoding='unicode'),'split':'UNKNOWN_EMPTY_SPLIT','row_index':1,'unknown':True}]

def chunks(node):
 out=[]
 def rec(n):
  if local(n)=='math'or cls(n,'ltx_eqn_eqno'):return
  if n.text and len(n.text.split())>=6:out.append(n.text)
  for ch in n:
   rec(ch)
   if ch.tail and len(ch.tail.split())>=6:out.append(ch.tail)
 rec(node);return out

def pdf_pages(job):
 f=Path(job['pdf']);assert sha(f.read_bytes())==job['pdf_sha256'];d=pf.PdfDocument(str(f));pages=[]
 for pg in d:
  t=pg.get_textpage();pages.append(norm(t.get_text_range()));t.close();pg.close()
 d.close();return pages

def locate(context,pages):
 evidence=[]
 for side,text in context:
  words=re.findall(r'\S+',text)
  for part in [words[:10],words[-10:]]:
   q=' '.join(part);n=norm(q)
   if len(part)<6 or len(n)<32:continue
   hits=[i+1 for i,s in enumerate(pages)if n in s]
   if len(hits)==1:evidence.append({'side':side,'text':q,'page':hits[0],'unique_across_pdf_pages':True})
 before={e['page']for e in evidence if e['side']=='before'};after={e['page']for e in evidence if e['side']=='after'};common=before&after
 if len(common)==1:return next(iter(common)),'BRACKETED_PROSE_SAME_PAGE',evidence
 return None,'UNKNOWN_PAGE',evidence

def granularity(raw,split):
 clean=re.sub(r'\\(?:displaystyle|textstyle|scriptstyle|scriptscriptstyle)\b','',raw).strip()
 # Escaped delimiter characters and TeX layout argument [] do not define independent math rows.
 for op,cl in [('(',')'),('[',']')]:
  depth=0
  for c in clean:
   if c==op:depth+=1
   elif c==cl:depth-=1
  if depth:return 'UNKNOWN_WRAPPED_EXPRESSION_LINE'
 if re.match(r'^(?:=|\\(?:approx|equiv|leq?|geq?))',clean):return 'UNKNOWN_CONTINUATION_LINE'
 if split.startswith('UNKNOWN'):return 'UNKNOWN_UNRESOLVED_SPLIT'
 return 'SINGLE_FORMULA_CANDIDATE'

def extract(job):
 f=Path(job['html_path']);data=f.read_bytes();assert sha(data)==job['sha256'];d=html.fromstring(data);nodes=list(d.iter());order={n:i for i,n in enumerate(nodes)};blocks=[]
 for n in nodes:
  if local(n)in{'p','figcaption','h1','h2','h3','h4'}:
   cc=chunks(n)
   if cc:blocks.append((order[n],cc))
 pages=pdf_pages(job);units=[];covered=set();containers=[n for n in nodes if local(n)=='tr'and cls(n,'ltx_eqn_row')]
 containers +=[m for m in nodes if local(m)=='math'and m.get('display')=='block'and not any(local(a)=='tr'and cls(a,'ltx_eqn_row')for a in m.iterancestors())]
 for ci,n in enumerate(containers,1):
  ms=descendants(n,'math')if local(n)!='math'else[n];ms=[m for m in ms if not any(local(a)=='math'for a in m.iterancestors()if a is not n)]
  if not ms:continue
  context=[];oi=order[n]
  for side,bb in [('before',[b for b in blocks if b[0]<oi][-3:]),('after',[b for b in blocks if b[0]>oi][:3])]:
   for _,cc in bb:
    for ch in cc:context.append((side,ch))
  page,pstatus,evidence=locate(context,pages)
  fragments=[tex(m)for m in ms];literal=bool(re.search(r'\\(?:tt|texttt)|\\text\s*\{[^{}]*(?:\[CLS\]|\[MASK\]|IsNext)', ' '.join(fragments)))and not any(local(x)in{'mi','mn','mfrac','msub','msup','msubsup','munderover'}for m in ms for x in m.iter())
  parts=split_math(ms[0])if len(ms)==1 else[{'latex':' '.join(fragments),'mathml':'\n'.join(etree.tostring(m,encoding='unicode')for m in ms),'split':'HTML_EQUATION_ROW_MATH_CELLS_COMBINED','row_index':1,'fragments':fragments}]
  for part in parts:
   ident=n.get('id')or(ms[0].get('id')if ms else None)or f'row-{ci}';uid=f"{job['job_id']}:html-formula:{ident}:r{part['row_index']}";raw=part['latex'];scope='UNKNOWN'if page is None else'IN_SCOPE'if job['first']<=page<=job['last']else'OUT_OF_SCOPE';kind='NON_FORMULA_LITERAL_DISPLAY'if literal else'FORMULA'
   units.append({'unit_id':uid,'job_id':job['job_id'],'family':job['family'],'kind':kind,'html_container_id':ident,'html_math_ids':[m.get('id')for m in ms],'html_source_line':n.sourceline,'html_xpath':d.getroottree().getpath(n),'formula_order':len(units)+1,'row_index':part['row_index'],'latex':raw,'latex_row_raw':part.get('latex_row_raw',raw),'latex_sha256':sha(raw.encode()),'mathml':part['mathml'],'split_policy':part['split'],'granularity_status':granularity(raw,part['split']),'split_unknown':part.get('unknown',False)or not raw.strip(),'depends_on_previous_row':part.get('depends_on_previous_row',False),'parent_full_alttext':fragments,'literal_example_candidate':literal,'page':page,'page_status':pstatus,'scope':scope,'page_evidence':evidence,'single_formula_comparable':kind=='FORMULA'and scope=='IN_SCOPE'and not part.get('unknown',False)and granularity(raw,part['split'])=='SINGLE_FORMULA_CANDIDATE','scope_note':'Only source prose/PDF brackets; no Docling output location.','html_url':job['final_url'],'arxiv_version':job['arxiv_version'],'html_sha256':job['sha256'],'pdf_sha256':job['pdf_sha256'],'audit_hash':sha((SEED+'|audit20|'+job['job_id']+'|'+ident+'|'+str(part['row_index'])+'|'+sha(raw.encode())).encode())})
 return units,{'job_id':job['job_id'],'status':job['status'],'html_sha256':job['sha256'],'arxiv_version':job['arxiv_version'],'html_url':job['final_url'],'source_only':True,'all_math':len([m for m in nodes if local(m)=='math']),'equation_containers':len(containers),'formula_units':sum(u['kind']=='FORMULA'for u in units),'nonformula_literal_displays':sum(u['kind']!='FORMULA'for u in units),'scope':dict(collections.Counter(u['scope']for u in units)),'splits':dict(collections.Counter(u['split_policy']for u in units))}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--final',action='store_true');a=ap.parse_args();manifest=json.loads((W/'html-manifest.json').read_text());allunits=[];jobs=[]
 for j in manifest['jobs']:
  if j['status']!='AVAILABLE'or str(j.get('answer_availability','')).startswith(('STRUCTURAL_ANSWER_UNAVAILABLE','UNAVAILABLE')):jobs.append({'job_id':j['job_id'],'status':'ANSWER_UNAVAILABLE','html_status':j['status'],'formula_oracle':'ANSWER_UNAVAILABLE_OR_UNKNOWN','reason':j.get('answer_availability','HTML_UNAVAILABLE')});continue
  uu,jj=extract(j);allunits+=uu;jobs.append(jj);print(j['job_id'],len(uu),flush=True)
 if a.final:assert manifest['complete']and len(manifest['jobs'])==36
 eligible=[u for u in allunits if u['kind']=='FORMULA'and u['scope']=='IN_SCOPE'and not u['split_unknown']];selected=sorted(eligible,key=lambda u:u['audit_hash'])[:20]if a.final else[]
 if a.final and (ROOT/'audit20-packets.json').exists():
  fixed=json.loads((ROOT/'audit20-packets.json').read_text());byid={u['unit_id']:u for u in allunits};assert all(u['unit_id']in byid for u in fixed);selected=[byid[u['unit_id']]for u in fixed]
 result={'source_only':True,'version':'W3b-html-formula-line-v1','html_manifest_complete':manifest['complete'],'html_manifest_sha256':sha((W/'html-manifest.json').read_bytes()),'jobs':jobs,'units':allunits,'unit_policy':'Source HTML equation rows, split TeX/MathML align rows, matrix/cases atomic. Continuations retain parent context. Unknown splits excluded from comparable denominator.','audit20':{'selection_final':a.final,'seed':SEED,'eligible':len(eligible),'selected_unit_ids':[u['unit_id']for u in selected]},'summary':{'units':len(allunits),'formula_units':sum(u['kind']=='FORMULA'for u in allunits),'scope':dict(collections.Counter(u['scope']for u in allunits)),'unknown_granularity':sum(u['split_unknown']for u in allunits)}};dump(ROOT/'oracle.json',result);dump(ROOT/'audit20-selection.json',selected);print(result['summary'])
if __name__=='__main__':main()
